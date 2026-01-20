/**
 * System 모듈 타입 정의
 */

/**
 * 서비스 상태 enum
 */
export enum ServiceHealthStatus {
  HEALTHY = 'healthy',
  UNHEALTHY = 'unhealthy',
  UNKNOWN = 'unknown',
}

/**
 * 전체 시스템 상태 enum
 */
export enum SystemHealthStatus {
  HEALTHY = 'healthy',
  DEGRADED = 'degraded',
  UNHEALTHY = 'unhealthy',
}

/**
 * Celery 워커 상태 enum
 */
export enum CeleryWorkerStatus {
  ONLINE = 'online',
  OFFLINE = 'offline',
}

/**
 * 서비스 이름 enum
 */
export enum ServiceName {
  POSTGRESQL = 'PostgreSQL',
  REDIS = 'Redis',
  WEAVIATE = 'Weaviate',
  MINIO = 'MinIO',
  CELERY_FLOWER = 'Celery (Flower)',
  CELERY_BACKFILL = 'Celery (Backfill)',
  CELERY_EMBED = 'Celery (Embed)',
}

/**
 * 개별 서비스 상태
 */
export interface ServiceStatus {
  name: ServiceName | string;
  status: ServiceHealthStatus;
  latency?: number;
  message?: string;
  details?: Record<string, unknown>;
}

/**
 * 전체 시스템 헬스 체크 응답
 */
export interface SystemHealth {
  status: SystemHealthStatus;
  timestamp: string;
  services: ServiceStatus[];
}

/**
 * Celery 워커 정보
 */
export interface CeleryWorkerInfo {
  name: string;
  status: CeleryWorkerStatus;
  active: number;
  processed: number;
  queues: string[];
}

/**
 * Celery 큐 정보
 */
export interface CeleryQueueInfo {
  name: string;
  pending: number;
}

/**
 * 태스크 트리거 결과
 */
export interface TaskTriggerResult {
  success: boolean;
  taskId?: string;
  message?: string;
}
