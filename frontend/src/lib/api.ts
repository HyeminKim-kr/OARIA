import axios from "axios";

// 서버사이드(SSR)에서는 Docker 내부 통신용 API_URL 사용
// 클라이언트(브라우저)에서는 NEXT_PUBLIC_API_URL 사용
const API_BASE_URL = typeof window === "undefined"
  ? (process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
  : (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000");

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// 요청 인터셉터: 토큰 자동 추가
api.interceptors.request.use(
  (config) => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("access_token");
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 응답 인터셉터: 401 에러 시 토큰 갱신 시도
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem("refresh_token");
        if (!refreshToken) {
          throw new Error("No refresh token");
        }

        const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });

        const { access_token, refresh_token } = response.data;
        localStorage.setItem("access_token", access_token);
        localStorage.setItem("refresh_token", refresh_token);

        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return api(originalRequest);
      } catch (refreshError) {
        // 리프레시 실패 시 로그아웃 처리
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        localStorage.removeItem("user");
        window.location.href = "/";
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export const authApi = {
  getMe: () => api.get("/auth/me"),
  logout: () => api.post("/auth/logout"),
  refresh: (refreshToken: string) =>
    api.post("/auth/refresh", { refresh_token: refreshToken }),
};

// Conversation Types
export interface ConversationListItem {
  id: string;
  title: string | null;
  status: string;
  message_count: number;
  last_message_at: string | null;
}

export interface PaginatedConversations {
  items: ConversationListItem[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface MessageReference {
  paper_id: string;
  chunk_id: string;
  title: string;
  journal: string | null;
  year: number | null;
  section: string;
  snippet: string;
  offset_start: number;
  offset_end: number;
  text_version: string;
  distance: number;
}

export interface MessageItem {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  tokens_used: number | null;
  model: string | null;
  latency_ms: number | null;
  created_at: string;
  references: MessageReference[] | null;
}

export interface PaginatedMessages {
  items: MessageItem[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export const conversationsApi = {
  list: (page = 1, size = 20) =>
    api.get<PaginatedConversations>("/ai/conversations", { params: { page, size } }),

  get: (id: string) =>
    api.get(`/ai/conversations/${id}`),

  update: (id: string, data: { title?: string; status?: string }) =>
    api.patch(`/ai/conversations/${id}`, data),

  delete: (id: string) =>
    api.delete(`/ai/conversations/${id}`),

  getMessages: (conversationId: string, page = 1, size = 50) =>
    api.get<PaginatedMessages>(`/ai/conversations/${conversationId}/messages`, {
      params: { page, size },
    }),
};

// Paper Types
export interface PaperAuthor {
  author_name: string;
  author_order: number;
  is_corresponding: boolean;
  orcid?: string;
  affiliation?: string;
}

export interface Paper {
  id: string;
  paper_id: string;
  title: string;
  abstract?: string;
  journal?: string;
  year?: number;
  keywords?: string[];
  is_open_access: boolean;
  created_at: string;
  authors: PaperAuthor[];
  citation_count?: number;
  has_pdf?: boolean;
}

export interface PaginatedPapers {
  items: Paper[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

// Paper Detail (extends Paper)
export interface PaperDetail extends Paper {
  pmcid?: string;
  pmid?: string;
  doi?: string;
  source: string;
  source_url?: string;
  status: string;
  updated_at: string;
}

// Display (fulltext) Types

// DisplayContent: 문단 또는 Figure (XML 순서대로)
export interface DisplayContent {
  type: 'paragraph' | 'figure';
  // paragraph인 경우
  text?: string;
  // figure인 경우
  id?: string;
  label?: string;
  caption?: string;
  graphic_href?: string;
}

export interface DisplaySection {
  name: string;
  title: string;
  contents?: DisplayContent[];  // XML 순서대로 문단/Figure 혼합
  // Legacy fields (하위 호환)
  paragraphs?: { text: string }[];
  figures?: Figure[];
}

// Figure (Hotlink 이미지용)
export interface Figure {
  id: string;       // "fig1"
  label: string;    // "Figure 1"
  caption?: string; // 캡션 텍스트
  graphic_href: string; // "tlcr-14-12-5465-f1" (이미지 파일명)
}

export interface PaperDisplay {
  paper_id: string;
  title: string;
  journal?: string;
  year?: number;
  sections: DisplaySection[];
  figures: Figure[];  // Figure 목록 추가
  has_pdf: boolean;
}

// Similar Papers Types
export interface SimilarPaper {
  pmcid?: string;
  pmid?: string;
  doi?: string;
  title: string;
  journal?: string;
  year?: number;
  authors?: string;
  recommendation_type: "citation" | "reference" | "vector" | "hybrid";
  score: number;
  sources?: string[];
}

export interface SimilarPapersResponse {
  items: SimilarPaper[];
  source: string;
  total: number;
  paper_id: string;
}

// Papers API
export const papersApi = {
  getRecent: (limit = 10) =>
    api.get<Paper[]>(`/papers/recent?limit=${limit}`).then((res) => res.data),

  search: (params: {
    q?: string;
    page?: number;
    limit?: number;
    year_from?: number;
    year_to?: number;
  }) =>
    api
      .get<PaginatedPapers>('/papers/search', { params })
      .then((res) => res.data),

  getOne: (id: string) =>
    api.get<PaperDetail>(`/papers/${id}`).then((res) => res.data),

  getDisplay: (id: string) =>
    api.get<PaperDisplay>(`/papers/${id}/display`).then((res) => res.data),

  getSimilar: (id: string, source: string = "hybrid") =>
    api.get<SimilarPapersResponse>(`/papers/${id}/similar`, { params: { source } })
      .then((res) => res.data),
};

// Paper Chat Types
export type SummaryType = "full" | "abstract" | "methods" | "results" | "conclusion";
export type CitationFormat = "apa" | "mla" | "chicago" | "harvard" | "vancouver" | "bibtex";

export interface PaperAskRequest {
  question: string;
  conversation_id?: string;
  include_related?: boolean;
  highlight_context?: string;
}

export interface PaperConversationListItem {
  id: string;
  title: string | null;
  message_count: number;
  last_message_at: string | null;
  last_message_preview: string | null;
}

export interface PaginatedPaperConversations {
  items: PaperConversationListItem[];
  total: number;
  page: number;
  size: number;
}

export interface SummarizeRequest {
  type: SummaryType;
  stream?: boolean;
}

export interface SummarizeResponse {
  paper_id: string;
  summary_type: string;
  summary: string;
  sections_used: string[];
  tokens_used: number;
  latency_ms: number;
}

export interface CitationRequest {
  format: CitationFormat;
}

export interface CitationResponse {
  paper_id: string;
  format: string;
  citation: string;
}

// Paper Chat API
export const paperChatApi = {
  // SSE 스트리밍은 fetchWithAuth를 직접 사용
  askUrl: (paperId: string) => `${API_BASE_URL}/ai/papers/${paperId}/ask`,

  getConversations: (paperId: string, page = 1, size = 20) =>
    api.get<PaginatedPaperConversations>(`/ai/papers/${paperId}/conversations`, {
      params: { page, size },
    }),

  getMessages: (paperId: string, conversationId: string, page = 1, size = 50) =>
    api.get<PaginatedMessages>(`/ai/papers/${paperId}/conversations/${conversationId}/messages`, {
      params: { page, size },
    }),

  summarize: (paperId: string, request: SummarizeRequest) =>
    api.post<SummarizeResponse>(`/ai/papers/${paperId}/summarize`, request),

  citation: (paperId: string, request: CitationRequest) =>
    api.post<CitationResponse>(`/ai/papers/${paperId}/citation`, request),
};

/**
 * 토큰 갱신을 지원하는 fetch wrapper
 * SSE 스트리밍처럼 axios 대신 native fetch를 써야 할 때 사용
 */
export async function fetchWithAuth(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = localStorage.getItem("access_token");

  const headers = new Headers(options.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response = await fetch(url, { ...options, headers });

  // 401 발생 시 토큰 갱신 시도
  if (response.status === 401) {
    const refreshToken = localStorage.getItem("refresh_token");
    if (!refreshToken) {
      throw new Error("No refresh token available");
    }

    try {
      const refreshResponse = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!refreshResponse.ok) {
        throw new Error("Token refresh failed");
      }

      const data = await refreshResponse.json();
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);

      // 새 토큰으로 원래 요청 재시도
      headers.set("Authorization", `Bearer ${data.access_token}`);
      response = await fetch(url, { ...options, headers });
    } catch (refreshError) {
      // 갱신 실패 시 로그아웃 처리
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("user");
      window.location.href = "/";
      throw refreshError;
    }
  }

  return response;
}

// ============================================================
// Agent Jobs & Notifications Types
// ============================================================

export interface AgentJobListItem {
  id: string;
  agent_type: string;
  job_name: string | null;
  status: string;
  progress_percent: number;
  approval_required: boolean;
  experiment_count: number;
  created_at: string;
}

export interface AgentJobResponse {
  id: string;
  user_id: string;
  agent_type: string;
  job_name: string | null;
  status: string;
  current_step: string | null;
  progress_percent: number;
  progress_detail: string | null;
  approval_required: boolean;
  approval_gate_id: string | null;
  approval_choices: Record<string, unknown> | null;
  approved_at: string | null;
  executive_summary: string | null;
  experiment_count: number;
  attempt_count: number;
  max_attempts: number;
  last_error_code: string | null;
  last_error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  total_duration_ms: number | null;
  created_at: string;
  updated_at: string;
}

// Thinking History Entry (에이전트 reasoning 과정)
export interface ThinkingHistoryEntry {
  iteration: number;
  timestamp?: string;
  title: string;
  bullets: string[];
  message?: string;
  action?: string;
  parameters?: Record<string, unknown>;
  confidence?: number;
  token_usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  observation?: {
    success: boolean;
    summary?: string;
    details?: Record<string, unknown>;
  };
  status?: string;
}

export interface AgentJobDetailResponse extends AgentJobResponse {
  input_data: Record<string, unknown>;
  config: Record<string, unknown> | null;
  step_results: Record<string, unknown>[];
  approval_decision: Record<string, unknown> | null;
  result_data: Record<string, unknown> | null;
  // Thinking History (에이전트 reasoning 과정)
  thinking_history: ThinkingHistoryEntry[] | null;
  cumulative_tokens: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  } | null;
}

export interface PaginatedAgentJobs {
  items: AgentJobListItem[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface NotificationItem {
  id: string;
  type: string;
  category: string;
  title: string;
  message: string;
  priority: string;
  icon: string | null;
  entity_type: string | null;
  entity_id: string | null;
  action_type: string | null;
  action_url: string | null;
  is_read: boolean;
  created_at: string;
}

export interface PaginatedNotifications {
  items: NotificationItem[];
  total: number;
  page: number;
  size: number;
  pages: number;
  unread_count: number;
}

// Agent Jobs API
export const agentJobsApi = {
  // 작업 생성
  create: (data: {
    agent_type: string;
    input_data: Record<string, unknown>;
    config?: Record<string, unknown>;
    job_name?: string;
  }) => api.post<AgentJobResponse>('/agent-jobs/', data),

  // 작업 목록
  list: (params?: {
    page?: number;
    size?: number;
    status_filter?: string;
    agent_type?: string;
  }) => api.get<PaginatedAgentJobs>('/agent-jobs/', { params }),

  // 작업 상세
  get: (id: string) => api.get<AgentJobDetailResponse>(`/agent-jobs/${id}`),

  // 작업 스트림 URL
  streamUrl: (id: string) => `${API_BASE_URL}/agent-jobs/${id}/stream`,

  // 승인
  approve: (id: string, decision: Record<string, unknown>) =>
    api.post<AgentJobResponse>(`/agent-jobs/${id}/approve`, { decision }),

  // 취소
  cancel: (id: string) => api.post<AgentJobResponse>(`/agent-jobs/${id}/cancel`),

  // 재시도
  retry: (id: string, reset_config?: Record<string, unknown>) =>
    api.post<AgentJobResponse>(`/agent-jobs/${id}/retry`, { reset_config }),

  // 삭제
  delete: (id: string) => api.delete(`/agent-jobs/${id}`),
};

// Notifications API
export const notificationsApi = {
  // 알림 목록
  list: (params?: {
    page?: number;
    size?: number;
    category?: string;
    include_dismissed?: boolean;
  }) => api.get<PaginatedNotifications>('/notifications/', { params }),

  // 읽지 않은 수
  unreadCount: () => api.get<{ count: number }>('/notifications/unread-count'),

  // 알림 상세
  get: (id: string) => api.get<NotificationItem>(`/notifications/${id}`),

  // 읽음 처리
  markAsRead: (id: string) => api.post(`/notifications/${id}/read`),

  // 전체 읽음
  markAllAsRead: () => api.post('/notifications/read-all'),

  // 숨기기
  dismiss: (id: string) => api.post(`/notifications/${id}/dismiss`),

  // 여러 알림 숨기기
  dismissMany: (notification_ids: string[]) =>
    api.post('/notifications/dismiss-many', { notification_ids }),

  // SSE 스트림 URL
  streamUrl: () => `${API_BASE_URL}/notifications/stream`,
};

// Paper Stats Types
export interface YearCount {
  year: number;
  count: number;
}

export interface PaperStats {
  total: number;
  by_year: YearCount[];
  recent_count: number;
}

// Dashboard API (combines multiple endpoints)
export const dashboardApi = {
  getPaperStats: () =>
    api.get<PaperStats>('/papers/stats').then((res) => res.data),
  getRecentPapers: (limit = 5) =>
    api.get<Paper[]>(`/papers/recent?limit=${limit}`).then((res) => res.data),
  getConversations: (page = 1, size = 1) =>
    api.get<PaginatedConversations>('/ai/conversations', { params: { page, size } }),
  getAgentJobs: (page = 1, size = 1) =>
    api.get<PaginatedAgentJobs>('/agent-jobs/', { params: { page, size } }),
  getPodcastEpisodes: (page = 1, size = 1) =>
    api.get<PaginatedPodcastEpisodes>('/podcast/episodes', { params: { page, size } }),
  getUnreadNotifications: () =>
    api.get<{ count: number }>('/notifications/unread-count'),
  getAgentJobsByStatus: () =>
    api.get<PaginatedAgentJobs>('/agent-jobs/', { params: { page: 1, size: 100 } }),
  getAnalysisPapers: (limit = 500, year_from?: number, year_to?: number, sample_by_year = true) =>
    api.get<Paper[]>('/papers/recent', { params: { limit, year_from, year_to, sample_by_year } }).then((res) => res.data),
};

// Podcast Types
export interface TurnTiming {
  turn_index: number;
  start_time: number;
  end_time: number;
  speaker: string;
}

export interface PodcastDialogueTurn {
  speaker: string;
  text: string;
  citations?: number[];
}

export interface PodcastDialogueScript {
  title: string;
  description: string;
  speakers: string[];
  turns: PodcastDialogueTurn[];
  total_estimated_duration: number;
  turn_timings?: TurnTiming[];
}

export interface PodcastReference {
  index: number;
  paper_id: string;
  title: string;
  authors: string[] | null;
  journal: string | null;
  year: number | null;
  snippet: string;
}

export interface PodcastEpisode {
  id: string;
  user_id: string;
  subscription_id: string | null;
  goal: string;
  duration: string;
  style: string;
  paper_mode: string;
  language: string;
  title: string | null;
  description: string | null;
  script: PodcastDialogueScript | null;
  audio_url: string | null;
  duration_seconds: number | null;
  paper_ids: string[] | null;
  references: PodcastReference[] | null;
  turn_timings: TurnTiming[] | null;
  task_results: Record<string, unknown> | null;
  search_filters: Record<string, unknown> | null;
  status: string;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface PaginatedPodcastEpisodes {
  items: PodcastEpisode[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface PodcastSubscription {
  id: string;
  user_id: string;
  topics: string[];
  frequency: string;
  episode_style: string;
  episode_duration: string;
  language: string;
  is_active: boolean;
  last_generated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PodcastSSEEvent {
  status?: string;
  message?: string;
  task_name?: string;
  task_index?: number;
  total_tasks?: number;
  duration_ms?: number;
  summary?: string;
  gate2_passed?: boolean;
  script?: PodcastDialogueScript;
  references?: PodcastReference[];
  turn_timings?: TurnTiming[];
  episode_id?: string;
  title?: string;
  audio_url?: string;
  duration_seconds?: number;
  error?: string;
}

// ============================================================
// Research Assistant - Vector Graph API
// ============================================================

export interface VectorGraphNode {
  id: string;
  type: "paper" | "author" | "keyword" | "concept";
  label: string;
  cluster?: string;
  metadata?: {
    pmid?: string;
    journal?: string;
    pubdate?: string;
    abstract?: string;
    paper_count?: number;
    certainty_score?: number;
    domain?: string;
  };
}

export interface VectorGraphLink {
  source: string;
  target: string;
  type: "similar" | "authored" | "contains" | "causal" | "correlational" | "hierarchical" | "contradictory";
  similarity?: number;
  weight?: number;
  evidence_hint?: string;
}

export interface VectorGraphResponse {
  nodes: VectorGraphNode[];
  links: VectorGraphLink[];
  query: string;
  total_papers: number;
  total_authors: number;
  total_keywords: number;
}

export interface VectorSearchRequest {
  query: string;
  limit?: number;
  min_similarity?: number;
  include_authors?: boolean;
  include_keywords?: boolean;
}

// Research Assistant API
export const researchAssistantApi = {
  // 벡터 그래프 검색
  searchVectorGraph: (request: VectorSearchRequest) =>
    api.post<VectorGraphResponse>('/ai/research/vector-graph', request)
      .then((res) => res.data),

  // 시맨틱 분해 (질문을 개념 노드로 분해)
  decomposeQuery: (query: string) =>
    api.post<{
      core_question: string;
      concept_nodes: Array<{
        node_id: string;
        label: string;
        domain: string;
        certainty_score: number;
      }>;
      relation_edges: Array<{
        source: string;
        target: string;
        edge_type: string;
        weight: number;
      }>;
    }>('/ai/research/decompose', { query }),
};

// Podcast API
export const podcastApi = {
  // 에피소드 생성 (SSE 스트림)
  generateStreamUrl: () => `${API_BASE_URL}/podcast/generate`,

  // 에피소드 목록
  list: (page = 1, size = 10) =>
    api.get<PaginatedPodcastEpisodes>('/podcast/episodes', { params: { page, size } }),

  // 에피소드 상세
  get: (id: string) => api.get<PodcastEpisode>(`/podcast/episodes/${id}`),

  // 에피소드 삭제
  delete: (id: string) => api.delete(`/podcast/episodes/${id}`),

  // 구독 목록
  listSubscriptions: () => api.get<PodcastSubscription[]>('/podcast/subscriptions'),

  // 구독 생성
  createSubscription: (data: {
    topics: string[];
    frequency?: string;
    episode_style?: string;
    episode_duration?: string;
    language?: string;
  }) => api.post<PodcastSubscription>('/podcast/subscriptions', data),

  // 구독 수정
  updateSubscription: (id: string, data: Partial<{
    topics: string[];
    frequency: string;
    episode_style: string;
    episode_duration: string;
    language: string;
    is_active: boolean;
  }>) => api.put<PodcastSubscription>(`/podcast/subscriptions/${id}`, data),

  // 구독 삭제
  deleteSubscription: (id: string) => api.delete(`/podcast/subscriptions/${id}`),
};
