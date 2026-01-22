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
// Study Plan Types
export interface StudyPlanRequest {
  hypothesis: string;
  research_context?: string;
  constraints?: string[];
  preferred_experiment_types?: string[];
}

export interface StudyPlanSummaryResponse {
  success: boolean;
  plan_id?: string;
  final_plan: string;
  executive_summary: string;
  experiment_count: number;
  approval_required: boolean;
  approval_status: string;
  total_duration_ms: number;
  error?: string;
}

// Study Plan SSE 이벤트 데이터 타입
export interface StudyPlanHypothesisEvent {
  original_text: string;
  independent_variable: string;
  dependent_variable: string;
  keywords: string[];
  confidence: number;
}

export interface StudyPlanTestQuestion {
  category: string;
  question: string;
  priority: number;
}

export interface StudyPlanExperiment {
  experiment_id: string;
  experiment_type: string;
  title: string;
  test_category: string;
  estimated_timeline: string;
  estimated_cost_level: string;
}

export interface StudyPlanApprovalChoice {
  choice_id: string;
  label: string;
  description: string;
  estimated_cost: string;
  estimated_timeline: string;
}

// Study Plan 저장 요청
export interface StudyPlanSaveRequest {
  hypothesis_input: string;
  research_context?: string;
  preferred_experiment_types?: string[];

  // 파싱된 가설
  hypothesis_structured?: Record<string, unknown>;
  hypothesis_confidence?: number;

  // 검증 질문
  test_questions?: Record<string, unknown>[];

  // 검색 결과
  search_coverage_score?: number;
  prior_studies_count?: number;

  // Evidence Pack
  evidence_packs?: Record<string, unknown>[];

  // 실험 설계
  experiment_designs?: Record<string, unknown>[];
  experiment_count?: number;

  // Critique
  quality_score?: number;
  revision_count?: number;

  // 측정 항목
  measurements?: Record<string, unknown>[];

  // 실현가능성
  feasibility_assessment?: Record<string, unknown>;

  // 승인 게이트
  approval_required?: boolean;
  approval_status?: string;

  // 최종 결과
  final_plan?: string;
  executive_summary?: string;
  references?: Record<string, unknown>[];

  // 메타
  status?: string;
  total_duration_ms?: number;
  error_message?: string;
}

// Study Plan 목록 아이템
export interface StudyPlanListItem {
  id: string;
  hypothesis_input: string;
  experiment_count: number;
  quality_score: number | null;
  status: string;
  created_at: string;
}

// 페이지네이션된 Study Plan 목록
export interface PaginatedStudyPlans {
  items: StudyPlanListItem[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

// Study Plan 전체 상세 응답
export interface StudyPlanFullResponse {
  id: string;
  user_id: string;

  // 입력
  hypothesis_input: string;
  research_context: string | null;
  preferred_experiment_types: string[];

  // 파싱된 가설
  hypothesis_structured: Record<string, unknown> | null;
  hypothesis_confidence: number | null;

  // 검증 질문
  test_questions: Record<string, unknown>[];

  // 검색 결과
  search_coverage_score: number | null;
  prior_studies_count: number;

  // Evidence Pack
  evidence_packs: Record<string, unknown>[];

  // 실험 설계
  experiment_designs: Record<string, unknown>[];
  experiment_count: number;

  // Critique
  quality_score: number | null;
  revision_count: number;

  // 측정 항목
  measurements: Record<string, unknown>[];

  // 실현가능성
  feasibility_assessment: Record<string, unknown> | null;

  // 승인 게이트
  approval_required: boolean;
  approval_status: string;

  // 최종 결과
  final_plan: string | null;
  executive_summary: string | null;
  references: Record<string, unknown>[];

  // 메타
  status: string;
  total_duration_ms: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

// Study Plan v3 응답 타입 (Plan A/B, Decision Points 포함)
export interface StudyPlanV3Response extends StudyPlanSummaryResponse {
  // Plan A/B
  plan_a?: string;
  plan_b?: string;
  plan_config?: Record<string, unknown>;

  // Decision Points 결과
  dp1_decisions?: Record<string, unknown>[];
  dp2_decision?: string;
  dp3_decision?: string;

  // 3-tier 검색 정보
  highest_tier_used?: number;
  evidence_snippets_v3?: Record<string, unknown>[];
  search_tier_history?: number[];
}

// Study Plan v3 저장 요청 (v3 필드 포함)
export interface StudyPlanV3SaveRequest extends StudyPlanSaveRequest {
  // Plan A/B
  plan_a?: string;
  plan_b?: string;
  plan_config?: Record<string, unknown>;

  // Decision Points 결과
  dp1_decisions?: Record<string, unknown>[];
  dp2_decision?: string;
  dp3_decision?: string;

  // 3-tier 검색 정보
  highest_tier_used?: number;
  evidence_snippets_v3?: Record<string, unknown>[];
  search_tier_history?: number[];
}

// Study Plan API
export const studyPlanApi = {
  // SSE 스트리밍 URL (v2 - 기존)
  generateUrl: () => `${API_BASE_URL}/study-plan/generate`,

  // 동기 실행 (테스트용)
  generateSync: (request: StudyPlanRequest) =>
    api.post<StudyPlanSummaryResponse>('/study-plan/generate-sync', request),

  // v3 동기 실행 (3-tier 검색 + Decision Points)
  generateV3: (request: StudyPlanRequest) =>
    api.post<StudyPlanV3Response>('/study-plan/generate-v3', request),

  // 저장 (v3 필드 포함)
  save: (data: StudyPlanSaveRequest | StudyPlanV3SaveRequest) =>
    api.post<StudyPlanFullResponse>('/study-plan/save', data),

  // 히스토리 목록
  list: (page = 1, size = 10) =>
    api.get<PaginatedStudyPlans>('/study-plan/history', { params: { page, size } }),

  // 상세 조회
  get: (id: string) =>
    api.get<StudyPlanFullResponse>(`/study-plan/${id}`),

  // 삭제
  delete: (id: string) =>
    api.delete(`/study-plan/${id}`),
};

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
