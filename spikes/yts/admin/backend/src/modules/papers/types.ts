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
 * 임베딩 트리거 결과
 */
export interface EmbedTriggerResult {
  taskId: string;
  pendingCount?: number;
  failedCount?: number;
}

/**
 * 전문 조회 결과
 */
export interface FulltextResult {
  fulltext: string | null;
  rawXml: string | null;
}
