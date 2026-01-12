import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:13000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Types
export type QueryType = 'production' | 'sample';

export interface SearchQuery {
  id: string;
  name: string;
  query: string;
  description: string | null;
  queryType: QueryType;
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

// Sample Embedding Types
export type SampleEmbeddingStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface SampleEmbedding {
  id: string;
  queryId: string;
  chunker: string;
  embedder: string;
  pipelineKey: string;
  collectionName: string;
  status: SampleEmbeddingStatus;
  paperCount: number;
  chunkCount: number;
  errorMessage: string | null;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
  searchQuery?: SearchQuery;
}

export interface CreateSampleEmbeddingRequest {
  queryId: string;
  chunker: string;
  embedder: string;
}

export interface SampleEmbeddingStats {
  total: number;
  pending: number;
  processing: number;
  completed: number;
  failed: number;
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
  getAll: (params?: { queryType?: QueryType }) =>
    api.get<SearchQuery[]>('/search-queries', { params }).then((res) => res.data),
  getOne: (id: string) => api.get<SearchQuery>(`/search-queries/${id}`).then((res) => res.data),
  create: (data: Partial<SearchQuery>) => api.post<SearchQuery>('/search-queries', data).then((res) => res.data),
  update: (id: string, data: Partial<SearchQuery>) => api.patch<SearchQuery>(`/search-queries/${id}`, data).then((res) => res.data),
  delete: (id: string) => api.delete(`/search-queries/${id}`),
  triggerBackfill: (id: string) => api.post(`/search-queries/${id}/backfill`).then((res) => res.data),
  preview: (data: PreviewRequest) => api.post<PreviewResponse>('/search-queries/preview', data).then((res) => res.data),
};

// Job Status Response (Redis에서 실시간 조회)
export interface JobStatusResponse {
  job_id: string;
  status: string;
  progress: number;
  total: number;
  retry_count: number;
  error: string | null;
  worker_id: string | null;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  heartbeat: string | null;
  source?: 'redis' | 'database';
}

export interface JobActionResponse {
  success: boolean;
  task_id: string | null;
  message: string;
}

export const sampleEmbeddingsApi = {
  getAll: (params?: { queryId?: string; status?: SampleEmbeddingStatus }) =>
    api.get<SampleEmbedding[]>('/sample-embeddings', { params }).then((res) => res.data),
  getOne: (id: string) =>
    api.get<SampleEmbedding>(`/sample-embeddings/${id}`).then((res) => res.data),
  create: (data: CreateSampleEmbeddingRequest) =>
    api.post<SampleEmbedding>('/sample-embeddings', data).then((res) => res.data),
  delete: (id: string) =>
    api.delete(`/sample-embeddings/${id}`),
  getStats: (queryId: string) =>
    api.get<SampleEmbeddingStats>(`/sample-embeddings/stats/${queryId}`).then((res) => res.data),
  // V2 Job Management API
  getJobStatus: (id: string) =>
    api.get<JobStatusResponse>(`/sample-embeddings/${id}/status`).then((res) => res.data),
  retry: (id: string) =>
    api.post<JobActionResponse>(`/sample-embeddings/${id}/retry`).then((res) => res.data),
  cancel: (id: string) =>
    api.post<JobActionResponse>(`/sample-embeddings/${id}/cancel`).then((res) => res.data),
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

// 분류 테스트 결과
export interface ClassificationTestResult {
  category: string;
  confidence: number;
  isOncology: boolean;
  warning?: string;
  classifierLatencyMs: number;
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
    reranker?: string;
    minRerankScore?: number;
    rerankerModel?: string;
    classifier?: string;
  };
  classification?: ClassificationTestResult;
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
  classification?: ClassificationTestResult;
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
  reranker?: string;
  minRerankScore?: number;
  collectionName?: string;  // 샘플 임베딩 컬렉션 지정
  classifier?: string;  // 분류기 전략 (예: pubmedbert)
}

export interface GenerateTestParams {
  query: string;
  limit?: number;
  alpha?: number;
  useReranker?: boolean;
  reranker?: string;
  collectionName?: string;  // 샘플 임베딩 컬렉션 지정
  classifier?: string;  // 분류기 전략 (예: pubmedbert)
}

export interface CompareSearchConfig {
  limit: number;
  alpha: number;
  reranker: string | null;
  collectionName?: string | null;
}

export interface CompareTestParams {
  query: string;
  configA: CompareSearchConfig;
  configB: CompareSearchConfig;
}

export interface CompareTestResult {
  configA: SearchTestResult;
  configB: SearchTestResult;
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

// RAG 전략 목록
export interface StrategiesResponse {
  chunkers: string[];
  embedders: string[];
  retrievers: string[];
  rerankers: string[];
  classifiers: string[];
  evaluators: string[];
}

// RAG 전략 상세 정보
export interface StrategyInfo {
  name: string;
  class_name: string;
  module: string;
  description: string;
  config?: Record<string, unknown>;
}

export interface StrategiesDetailResponse {
  chunkers: StrategyInfo[];
  embedders: StrategyInfo[];
  retrievers: StrategyInfo[];
  rerankers: StrategyInfo[];
  classifiers: StrategyInfo[];
}

// DB 저장 RAG 전략 정보
export interface DBStrategyInfo {
  id: string;
  category: string;
  name: string;
  description: string | null;
  config: Record<string, unknown> | null;
  location: 'backend' | 'batch';
  is_active: boolean;
}

// DB 기반 RAG 전략 응답
export interface DBStrategiesResponse {
  chunkers: DBStrategyInfo[];
  embedders: DBStrategyInfo[];
  retrievers: DBStrategyInfo[];
  rerankers: DBStrategyInfo[];
}

// RAG 설정
export interface RAGParameters {
  limit?: number;
  alpha?: number;
  minRerankScore?: number;
  temperature?: number;
}

export interface RAGSettings {
  id: string;
  name: string;
  description: string | null;
  chunker: string;
  embedder: string;
  retriever: string;
  reranker: string | null;
  parameters: RAGParameters | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface CreateRAGSettingsRequest {
  name: string;
  description?: string;
  chunker?: string;
  embedder?: string;
  retriever?: string;
  reranker?: string | null;
  parameters?: RAGParameters;
}

export interface UpdateRAGSettingsRequest {
  name?: string;
  description?: string;
  chunker?: string;
  embedder?: string;
  retriever?: string;
  reranker?: string | null;
  parameters?: RAGParameters;
  isActive?: boolean;
}

export const ragSettingsApi = {
  getAll: () => api.get<RAGSettings[]>('/rag-settings').then((res) => res.data),
  getActive: () => api.get<RAGSettings | null>('/rag-settings/active').then((res) => res.data),
  getOne: (id: string) => api.get<RAGSettings>(`/rag-settings/${id}`).then((res) => res.data),
  create: (data: CreateRAGSettingsRequest) =>
    api.post<RAGSettings>('/rag-settings', data).then((res) => res.data),
  update: (id: string, data: UpdateRAGSettingsRequest) =>
    api.put<RAGSettings>(`/rag-settings/${id}`, data).then((res) => res.data),
  activate: (id: string) =>
    api.post<RAGSettings>(`/rag-settings/${id}/activate`).then((res) => res.data),
  delete: (id: string) => api.delete(`/rag-settings/${id}`),
};

export const labApi = {
  getStatus: () => api.get<UserBackendStatus>('/lab/status').then((res) => res.data),
  getStrategies: () => api.get<StrategiesResponse>('/lab/strategies').then((res) => res.data),
  getStrategiesDetail: () => api.get<StrategiesDetailResponse>('/lab/strategies/detail').then((res) => res.data),
  getStrategiesFromDB: (activeOnly: boolean = true) =>
    api.get<DBStrategiesResponse>('/lab/strategies/db', { params: { active_only: activeOnly } }).then((res) => res.data),
  testSearch: (params: SearchTestParams) =>
    api.post<SearchTestResult>('/lab/search', {
      query: params.query,
      limit: params.limit,
      alpha: params.alpha,
      useReranker: params.useReranker,
      reranker: params.reranker,
      minRerankScore: params.minRerankScore,
      collectionName: params.collectionName,
      classifier: params.classifier,
    }).then((res) => res.data),
  testGenerate: (params: GenerateTestParams) =>
    api.post<GenerateTestResult>('/lab/generate', {
      query: params.query,
      limit: params.limit,
      alpha: params.alpha,
      useReranker: params.useReranker,
      reranker: params.reranker,
      collectionName: params.collectionName,
      classifier: params.classifier,
    }).then((res) => res.data),
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

// Job Manager V2 - Papers Embedding Types
export interface EmbedBatchTriggerResponse {
  batchId: string;
  paperCount: number;
  message: string;
}

export interface EmbedJobState {
  jobId: string;
  status: string;
  progress: number;
  total: number;
  retryCount: number;
  error: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface EmbedJobsResponse {
  jobs: EmbedJobState[];
  total: number;
}

export interface EmbedBatchCancelResponse {
  cancelledCount: number;
  message: string;
}

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

  // 임베딩 관련 (레거시)
  triggerEmbedAll: (limit?: number) =>
    api.post<EmbedTriggerResponse>('/papers/embed/all', null, { params: { limit } }).then((res) => res.data),
  triggerEmbedByQuery: (queryId: string, limit?: number) =>
    api.post<EmbedTriggerResponse>(`/papers/embed/query/${queryId}`, null, { params: { limit } }).then((res) => res.data),
  triggerEmbedPaper: (id: string) =>
    api.post<EmbedTriggerResponse>(`/papers/${id}/embed`).then((res) => res.data),
  triggerReembed: (queryId?: string) =>
    api.post<EmbedTriggerResponse>('/papers/embed/retry', null, { params: { queryId } }).then((res) => res.data),

  // Job Manager V2 - 임베딩 배치 관리
  getEmbedJobs: () =>
    api.get<EmbedJobsResponse>('/papers/embedding/jobs').then((res) => res.data),
  triggerEmbedBatch: (limit?: number) =>
    api.post<EmbedBatchTriggerResponse>('/papers/embedding/batch-trigger', null, { params: { limit } }).then((res) => res.data),
  cancelEmbedBatch: () =>
    api.post<EmbedBatchCancelResponse>('/papers/embedding/batch-cancel').then((res) => res.data),
  retryEmbedJob: (jobId: string) =>
    api.post<{ success: boolean }>(`/papers/embedding/jobs/${jobId}/retry`).then((res) => res.data),
  cancelEmbedJob: (jobId: string) =>
    api.post<{ success: boolean }>(`/papers/embedding/jobs/${jobId}/cancel`).then((res) => res.data),
};
