import { applyDecorators } from '@nestjs/common';
import {
  ApiOperation,
  ApiResponse,
  ApiBearerAuth,
} from '@nestjs/swagger';

/**
 * System 모듈 Swagger 데코레이터
 */

// ─────────────────────────────────────────────────────────────
// 헬스 체크
// ─────────────────────────────────────────────────────────────

export function ApiSystemHealth() {
  return applyDecorators(
    ApiOperation({
      summary: '시스템 전체 상태 확인',
      description: 'PostgreSQL, Redis, Weaviate, MinIO, Celery 등 모든 인프라 서비스의 상태를 확인합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '시스템 상태 정보 (healthy, degraded, unhealthy)',
    }),
  );
}

// ─────────────────────────────────────────────────────────────
// Celery 모니터링
// ─────────────────────────────────────────────────────────────

export function ApiSystemWorkers() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: 'Celery 워커 상태 조회',
      description: '활성 Celery 워커 목록과 각 워커의 상태, 처리량을 반환합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '워커 목록',
    }),
  );
}

export function ApiSystemQueues() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: 'Celery 큐 상태 조회',
      description: '각 큐의 대기 중인 작업 수를 반환합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '큐 정보 (backfill, embed, celery)',
    }),
  );
}

// ─────────────────────────────────────────────────────────────
// 작업 트리거
// ─────────────────────────────────────────────────────────────

export function ApiSystemTriggerEmbedding() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '임베딩 작업 수동 트리거',
      description: '대기 중인 논문에 대해 임베딩 작업을 수동으로 트리거합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '트리거 결과 (태스크 ID, 메시지)',
    }),
    ApiResponse({
      status: 500,
      description: '트리거 실패',
    }),
  );
}

export function ApiSystemTriggerReembedding() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '실패한 임베딩 재처리 트리거',
      description: '임베딩에 실패한 논문들을 재처리합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '트리거 결과 (태스크 ID, 메시지)',
    }),
    ApiResponse({
      status: 500,
      description: '트리거 실패',
    }),
  );
}
