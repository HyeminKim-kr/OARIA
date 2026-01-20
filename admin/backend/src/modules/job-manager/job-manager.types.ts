/**
 * 작업 유형 상수
 * - batch/src/job_manager.py의 JobType과 동일해야 함
 */
export const JobType = {
  EMBED: 'embed', // sample_embeddings용
  PAPER_EMBED: 'paper', // papers.embedding_status용
} as const;

export type JobTypeValue = (typeof JobType)[keyof typeof JobType];

/**
 * 작업 상태 상수
 * - batch/src/job_manager.py의 JobStatus와 동일해야 함
 */
export const JobStatus = {
  PENDING: 'pending',
  QUEUED: 'queued',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
} as const;

export type JobStatusValue = (typeof JobStatus)[keyof typeof JobStatus];

/**
 * 작업 상태 정보 (Redis Hash에 저장되는 데이터)
 */
export interface JobState {
  status: JobStatusValue;
  progress: number;
  total: number;
  retry_count: number;
  error: string;
  worker_id: string;
  created_at: string;
  queued_at: string;
  started_at: string;
  completed_at: string;
  heartbeat: string;
  result?: string; // JSON 문자열
  synced_from_db?: string;
  // 추가 메타데이터
  [key: string]: string | number | undefined;
}

/**
 * 작업 생성 옵션
 */
export interface CreateJobOptions {
  jobId: string;
  jobType: JobTypeValue;
  metadata?: Record<string, string | number>;
}

/**
 * 작업 상태 조회 결과
 */
export interface JobStateResult {
  status: JobStatusValue;
  progress: number;
  total: number;
  retryCount: number;
  error: string;
  workerId: string;
  createdAt: string | null;
  queuedAt: string | null;
  startedAt: string | null;
  completedAt: string | null;
  heartbeat: string | null;
  // 추가 필드 (2026-01-15)
  chunkCount: number | null;
}

/**
 * JobManager 상수
 */
export const JOB_MANAGER_CONSTANTS = {
  HEARTBEAT_INTERVAL: 30, // 초
  HEARTBEAT_TIMEOUT: 120, // 초
  LOCK_TIMEOUT: 600, // 초 (10분)
  MAX_RETRIES: 3,
} as const;
