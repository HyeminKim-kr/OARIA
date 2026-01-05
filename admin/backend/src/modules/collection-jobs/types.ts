/**
 * Collection Jobs 모듈 타입 정의
 */

/**
 * Job 타입 enum
 */
export enum JobTypeEnum {
  BACKFILL = 'backfill',
  INCREMENTAL = 'incremental',
  REPAIR = 'repair',
}

/**
 * Job 상태 enum
 */
export enum JobStatusEnum {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  PARTIAL = 'partial',
  DELAYED = 'delayed',
  CANCELLED = 'cancelled',
  RETRIED = 'retried',
}

/**
 * 에러 스테이지 enum
 */
export enum ErrorStageEnum {
  SEARCH = 'search',
  DOWNLOAD = 'download',
  PARSE = 'parse',
  SAVE = 'save',
}

/**
 * Job 검색 옵션
 */
export interface JobSearchOptions {
  status?: JobStatusEnum;
  jobType?: JobTypeEnum;
  limit?: number;
}

/**
 * Job 에러 검색 옵션
 */
export interface JobErrorOptions {
  stage?: ErrorStageEnum;
  limit?: number;
  offset?: number;
}

/**
 * Job 통계
 */
export interface JobStats {
  total: number;
  pending: number;
  running: number;
  completed: number;
  failed: number;
  todayCollected: number;
}

/**
 * 에러 통계
 */
export interface JobErrorStats {
  total: number;
  byStage: Record<string, number>;
  byCode: Record<string, number>;
}

/**
 * 태스크 트리거 결과
 */
export interface TaskTriggerResult {
  taskId: string;
  newJobTriggered?: boolean;
  resumed?: boolean;
}
