import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:13000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Types
export interface SearchQuery {
  id: string;
  name: string;
  query: string;
  description: string | null;
  isActive: boolean;
  priority: number;
  maxResults: number | null;
  yearFrom: number | null;
  yearTo: number | null;
  openAccessOnly: boolean;
  maxConcurrent: number;
  autoBackfill: boolean;
  totalCollected: number;
  lastBackfillAt: string | null;
  lastIncrementalAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface CollectionJob {
  id: string;
  jobType: 'backfill' | 'incremental' | 'repair';
  queryId: string | null;
  priority: number;
  query: string;
  params: Record<string, unknown> | null;
  apiName: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'delayed' | 'cancelled' | 'partial' | 'retried';
  checkpoint: Record<string, unknown> | null;
  totalCount: number | null;
  processedCount: number;
  successCount: number;
  failedCount: number;
  attemptCount: number;
  maxAttempts: number;
  nextRunAt: string | null;
  lockedAt: string | null;
  lockedBy: string | null;
  lastErrorCode: string | null;
  lastErrorMessage: string | null;
  lastErrorAt: string | null;
  createdAt: string;
  updatedAt: string;
  startedAt: string | null;
  completedAt: string | null;
  durationMs: number | null;
}

export type EmbeddingStatus = 'pending' | 'processing' | 'completed' | 'failed' | null;

export interface Paper {
  id: string;
  paperId: string;
  pmcid: string | null;
  pmid: string | null;
  doi: string | null;
  title: string;
  abstract: string | null;
  journal: string | null;
  year: number | null;
  keywords: string[] | null;
  source: string;
  sourceUrl: string | null;
  isOpenAccess: boolean;
  status: 'collected' | 'chunked' | 'indexed';
  embeddingStatus: EmbeddingStatus;
  embeddingChunkCount: number;
  embeddingError: string | null;
  embeddingAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

export interface PaperStats {
  total: number;
  collected: number;
  chunked: number;
  indexed: number;
  byYear: { year: number; count: number }[];
  recentCount: number;
  embedding: {
    notStarted: number;
    pending: number;
    processing: number;
    completed: number;
    failed: number;
    totalChunks: number;
  };
}

export interface DashboardStats {
  totalPapers: number;
  totalQueries: number;
  activeJobs: number;
  completedJobsToday: number;
  papersCollectedToday: number;
}

export interface ArticleError {
  id: string;
  jobId: string;
  pmcid: string | null;
  pmid: string | null;
  doi: string | null;
  stage: 'search' | 'download' | 'parse' | 'save';
  errorCode: string | null;
  errorMessage: string;
  errorDetail: string | null;
  rawResponse: string | null;
  context: Record<string, unknown> | null;
  createdAt: string;
}

export interface ErrorStats {
  total: number;
  byStage: Record<string, number>;
  byCode: Record<string, number>;
}

// API Functions
export interface PreviewRequest {
  query: string;
  yearFrom?: number;
  yearTo?: number;
  openAccessOnly?: boolean;
}

export interface PreviewResponse {
  hitCount: number;
  fullQuery: string;
}

export const searchQueriesApi = {
  getAll: () => api.get<SearchQuery[]>('/search-queries').then((res) => res.data),
  getOne: (id: string) => api.get<SearchQuery>(`/search-queries/${id}`).then((res) => res.data),
  create: (data: Partial<SearchQuery>) => api.post<SearchQuery>('/search-queries', data).then((res) => res.data),
  update: (id: string, data: Partial<SearchQuery>) => api.patch<SearchQuery>(`/search-queries/${id}`, data).then((res) => res.data),
  delete: (id: string) => api.delete(`/search-queries/${id}`),
  triggerBackfill: (id: string) => api.post(`/search-queries/${id}/backfill`).then((res) => res.data),
  preview: (data: PreviewRequest) => api.post<PreviewResponse>('/search-queries/preview', data).then((res) => res.data),
};

export const collectionJobsApi = {
  getAll: (params?: { status?: string; page?: number; limit?: number }) =>
    api.get<CollectionJob[]>('/collection-jobs', { params }).then((res) => res.data),
  getOne: (id: string) => api.get<CollectionJob>(`/collection-jobs/${id}`).then((res) => res.data),
  cancel: (id: string) => api.patch(`/collection-jobs/${id}/cancel`).then((res) => res.data),
  retry: (id: string) => api.post<{ taskId: string; newJobTriggered: boolean }>(`/collection-jobs/${id}/retry`).then((res) => res.data),
  resume: (id: string) => api.post<{ taskId: string; resumed: boolean }>(`/collection-jobs/${id}/resume`).then((res) => res.data),
  getErrors: (id: string, params?: { stage?: string; limit?: number; offset?: number }) =>
    api.get<{ errors: ArticleError[]; total: number }>(`/collection-jobs/${id}/errors`, { params }).then((res) => res.data),
  getErrorStats: (id: string) =>
    api.get<ErrorStats>(`/collection-jobs/${id}/errors/stats`).then((res) => res.data),
};

export interface PaperFulltext {
  fulltext: string | null;
  rawXml: string | null;
}

export interface EmbedTriggerResponse {
  taskId: string;
  pendingCount?: number;
  failedCount?: number;
}

// System Types
export interface ServiceStatus {
  name: string;
  status: 'healthy' | 'unhealthy' | 'unknown';
  latency?: number;
  message?: string;
  details?: Record<string, unknown>;
}

export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  services: ServiceStatus[];
}

export interface CeleryWorker {
  name: string;
  status: string;
  active: number;
  processed: number;
  queues: string[];
}

export interface CeleryQueue {
  name: string;
  pending: number;
}

export interface TriggerResult {
  success: boolean;
  taskId?: string;
  message?: string;
}

export const systemApi = {
  getHealth: () => api.get<SystemHealth>('/system/health').then((res) => res.data),
  getWorkers: () => api.get<{ workers: CeleryWorker[] }>('/system/workers').then((res) => res.data),
  getQueues: () => api.get<{ queues: CeleryQueue[] }>('/system/queues').then((res) => res.data),
  triggerEmbedding: (limit?: number) =>
    api.post<TriggerResult>('/system/trigger/embedding', { limit }).then((res) => res.data),
  triggerReembedding: (limit?: number) =>
    api.post<TriggerResult>('/system/trigger/reembedding', { limit }).then((res) => res.data),
};

export const papersApi = {
  getAll: (params?: {
    page?: number;
    limit?: number;
    search?: string;
    status?: string;
    embeddingStatus?: 'not_started' | 'pending' | 'processing' | 'completed' | 'failed';
  }) => api.get<PaginatedResponse<Paper>>('/papers', { params }).then((res) => res.data),
  getOne: (id: string) => api.get<Paper>(`/papers/${id}`).then((res) => res.data),
  getFulltext: (id: string) => api.get<PaperFulltext>(`/papers/${id}/fulltext`).then((res) => res.data),
  getStats: () => api.get<PaperStats>('/papers/stats').then((res) => res.data),

  // 임베딩 관련
  triggerEmbedAll: (limit?: number) =>
    api.post<EmbedTriggerResponse>('/papers/embed/all', null, { params: { limit } }).then((res) => res.data),
  triggerEmbedByQuery: (queryId: string, limit?: number) =>
    api.post<EmbedTriggerResponse>(`/papers/embed/query/${queryId}`, null, { params: { limit } }).then((res) => res.data),
  triggerEmbedPaper: (id: string) =>
    api.post<EmbedTriggerResponse>(`/papers/${id}/embed`).then((res) => res.data),
  triggerReembed: (queryId?: string) =>
    api.post<EmbedTriggerResponse>('/papers/embed/retry', null, { params: { queryId } }).then((res) => res.data),
};
