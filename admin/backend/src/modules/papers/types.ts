/**
 * Papers 모듈 타입 정의
 */

/**
 * 논문 상태 enum
 */
export enum PaperStatusEnum {
  COLLECTED = 'collected',
  CHUNKED = 'chunked',
  INDEXED = 'indexed',
}

/**
 * 임베딩 상태 enum
 */
export enum EmbeddingStatusEnum {
  NOT_STARTED = 'not_started',
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

/**
 * 논문 검색 옵션
 */
export interface PaperSearchOptions {
  search?: string;
  status?: PaperStatusEnum;
  embeddingStatus?: EmbeddingStatusEnum;
  yearFrom?: number;
  yearTo?: number;
  page?: number;
  limit?: number;
}

/**
 * 페이지네이션 결과
 */
export interface PaginatedResult<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

/**
 * 논문 통계
 */
export interface PaperStats {
  total: number;
  collected: number;
  chunked: number;
  indexed: number;
  byYear: { year: number; count: number }[];
  recentCount: number;
  embedding: EmbeddingStats;
}

/**
 * 임베딩 통계
 */
export interface EmbeddingStats {
  notStarted: number;
  pending: number;
  processing: number;
  completed: number;
  failed: number;
  totalChunks: number;
}

/**
 * 임베딩 트리거 결과 (구버전 - 단일 Celery 태스크)
 */
export interface EmbedTriggerResult {
  taskId: string;
  pendingCount?: number;
  failedCount?: number;
}

/**
 * 임베딩 배치 트리거 결과 (신버전 - Job Manager V2)
 */
export interface EmbedBatchTriggerResult {
  batchId: string;
  paperCount: number;
  message: string;
}

/**
 * 임베딩 작업 상태
 */
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

/**
 * 임베딩 작업 목록 결과
 */
export interface EmbedJobsResult {
  jobs: EmbedJobState[];
  total: number;
}

/**
 * 임베딩 배치 취소 결과
 */
export interface EmbedBatchCancelResult {
  cancelledCount: number;
  message: string;
}

/**
 * Display JSON 섹션
 */
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

/**
 * 전문 조회 결과
 */
export interface FulltextResult {
  fulltext: string | null;
  rawXml: string | null;
  display: DisplayData | null;
}
