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

export interface DisplayParagraph {
  text: string;
}

export interface DisplaySection {
  name: string;
  title: string;
  paragraphs: DisplayParagraph[];
}

export interface DisplayData {
  sections: DisplaySection[];
}

export interface PaperFulltext {
  fulltext: string | null;
  rawXml: string | null;
  display: DisplayData | null;
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

// Lab Types
export interface SearchedChunk {
  paperId: string;
  paperTitle: string;
  sectionName: string;
  chunkIndex: number;
  content: string;
  score: number;
  rerankScore?: number;
  originalScore?: number;
  metadata?: Record<string, unknown>;
}

export interface SearchTestResult {
  query: string;
  chunks: SearchedChunk[];
  searchLatencyMs: number;
  rerankLatencyMs?: number;
  totalChunks: number;
  parameters: {
    limit: number;
    alpha: number;
    useReranker?: boolean;
    minRerankScore?: number;
    rerankerModel?: string;
  };
}

export interface LabReference {
  paperId: string;
  title: string;
  section: string;
  content: string;
  score: number;
}

export interface GenerateTestResult {
  query: string;
  answer: string;
  references: LabReference[];
  searchLatencyMs: number;
  rerankLatencyMs?: number;
  llmLatencyMs: number;
  totalLatencyMs: number;
  model: string;
  tokensUsed?: {
    prompt: number;
    completion: number;
  };
  useReranker?: boolean;
}

export interface UserBackendStatus {
  available: boolean;
  url: string;
  latencyMs?: number;
  error?: string;
}

export interface FeedbackResult {
  success: boolean;
  feedbackId?: string;
  message: string;
}

export interface FeedbackParameters {
  limit: number;
  alpha: number;
  useReranker?: boolean;
  minRerankScore?: number;
  rerankerModel?: string;
}

export interface FeedbackResultSummary {
  totalChunks: number;
  topScore: number;
  relevantCount?: number;
  lowRelevanceCount?: number;
  model?: string;
  tokensUsed?: {
    prompt: number;
    completion: number;
  };
}

export interface FeedbackParams {
  type: 'search' | 'generate';
  query: string;
  rating: 'good' | 'bad';
  parameters: FeedbackParameters;
  comment?: string;
  resultSummary?: FeedbackResultSummary;
  searchLatencyMs?: number;
  rerankLatencyMs?: number;
  llmLatencyMs?: number;
}

export interface SearchTestParams {
  query: string;
  limit?: number;
  alpha?: number;
  useReranker?: boolean;
  minRerankScore?: number;
}

export interface GenerateTestParams {
  query: string;
  limit?: number;
  alpha?: number;
  useReranker?: boolean;
}

export interface CompareTestParams {
  query: string;
  limit?: number;
  alpha?: number;
}

export interface CompareTestResult {
  withReranker: SearchTestResult;
  withoutReranker: SearchTestResult;
}

// Test Log Types
export interface TestLogItem {
  id: string;
  testType: 'search' | 'generate' | 'compare';
  query: string;
  parameters: FeedbackParameters;
  searchLatencyMs: number | null;
  rerankLatencyMs: number | null;
  llmLatencyMs: number | null;
  totalLatencyMs: number | null;
  createdAt: string;
  resultSummary: Record<string, unknown>;
}

export interface TestLogListResult {
  items: TestLogItem[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

export interface TestLogDetail extends TestLogItem {
  results: SearchTestResult | GenerateTestResult | {
    withReranker: SearchTestResult;
    withoutReranker: SearchTestResult;
  };
}

export interface TestLogQueryParams {
  page?: number;
  limit?: number;
  testType?: 'search' | 'generate' | 'compare';
  query?: string;
}

export interface FeedbackStats {
  total: number;
  byRating: { good: number; bad: number };
  byTestType: { search: number; generate: number };
  recentFeedbacks: Array<{
    id: string;
    testType: string;
    query: string;
    rating: string;
    createdAt: string;
  }>;
}

export interface TestLogStats {
  total: number;
  byTestType: { search: number; generate: number; compare: number };
  avgLatency: {
    search: number | null;
    rerank: number | null;
    llm: number | null;
  };
  todayCount: number;
}

export const labApi = {
  getStatus: () => api.get<UserBackendStatus>('/lab/status').then((res) => res.data),
  testSearch: (params: SearchTestParams) =>
    api.post<SearchTestResult>('/lab/search', params).then((res) => res.data),
  testGenerate: (params: GenerateTestParams) =>
    api.post<GenerateTestResult>('/lab/generate', params).then((res) => res.data),
  testCompare: (params: CompareTestParams) =>
    api.post<CompareTestResult>('/lab/compare', params).then((res) => res.data),
  saveFeedback: (params: FeedbackParams) =>
    api.post<FeedbackResult>('/lab/feedback', params).then((res) => res.data),

  // Test Logs
  getTestLogs: (params?: TestLogQueryParams) =>
    api.get<TestLogListResult>('/lab/logs', { params }).then((res) => res.data),
  getTestLog: (id: string) =>
    api.get<TestLogDetail>(`/lab/logs/${id}`).then((res) => res.data),
  deleteTestLog: (id: string) =>
    api.delete<{ success: boolean; message: string }>(`/lab/logs/${id}`).then((res) => res.data),

  // Stats
  getFeedbackStats: () =>
    api.get<FeedbackStats>('/lab/stats/feedback').then((res) => res.data),
  getTestLogStats: () =>
    api.get<TestLogStats>('/lab/stats/logs').then((res) => res.data),
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
