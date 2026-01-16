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
