import { applyDecorators } from '@nestjs/common';
import {
  ApiOperation,
  ApiResponse,
  ApiParam,
  ApiBearerAuth,
} from '@nestjs/swagger';

/**
 * Collection Jobs 모듈 Swagger 데코레이터
 */

// ─────────────────────────────────────────────────────────────
// 조회 엔드포인트
// ─────────────────────────────────────────────────────────────

export function ApiJobsFindAll() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '배치 작업 목록',
      description: '상태, 작업 타입으로 필터링 가능한 수집 작업 목록을 반환합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '배치 작업 목록',
    }),
  );
}

export function ApiJobsGetRunning() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '실행 중인 작업',
      description: '현재 실행 중인 수집 작업 목록을 반환합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '실행 중인 작업 목록',
    }),
  );
}

export function ApiJobsGetStats() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '배치 작업 통계',
      description: '전체, 상태별 작업 수 및 오늘 수집된 논문 수를 반환합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '작업 통계 정보',
    }),
  );
}

export function ApiJobsFindOne() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '배치 작업 상세',
      description: '특정 수집 작업의 상세 정보를 반환합니다.',
    }),
    ApiParam({
      name: 'id',
      description: '작업 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '작업 상세 정보',
    }),
    ApiResponse({
      status: 404,
      description: '작업을 찾을 수 없음',
    }),
  );
}

// ─────────────────────────────────────────────────────────────
// 작업 제어 엔드포인트
// ─────────────────────────────────────────────────────────────

export function ApiJobsCancel() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '작업 취소',
      description: '실행 중이거나 대기 중인 작업을 취소합니다.',
    }),
    ApiParam({
      name: 'id',
      description: '작업 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '취소된 작업 정보',
    }),
    ApiResponse({
      status: 400,
      description: '취소할 수 없는 상태의 작업',
    }),
    ApiResponse({
      status: 404,
      description: '작업을 찾을 수 없음',
    }),
  );
}

export function ApiJobsRetry() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '작업 재시도 (새 Job 생성)',
      description: '실패하거나 취소된 작업을 새로운 Job으로 다시 시작합니다.',
    }),
    ApiParam({
      name: 'id',
      description: '작업 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '새로 생성된 태스크 ID',
    }),
    ApiResponse({
      status: 400,
      description: '재시도할 수 없는 상태의 작업',
    }),
  );
}

export function ApiJobsResume() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '작업 재개 (기존 Job 이어서)',
      description: 'Partial 또는 Failed 상태의 작업을 이어서 실행합니다.',
    }),
    ApiParam({
      name: 'id',
      description: '작업 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '재개된 태스크 ID',
    }),
    ApiResponse({
      status: 400,
      description: '재개할 수 없는 상태의 작업',
    }),
  );
}

// ─────────────────────────────────────────────────────────────
// 에러 관련 엔드포인트
// ─────────────────────────────────────────────────────────────

export function ApiJobsGetErrors() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: 'Job 에러 목록',
      description: '특정 작업에서 발생한 에러 목록을 반환합니다.',
    }),
    ApiParam({
      name: 'id',
      description: '작업 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '에러 목록 및 총 개수',
    }),
  );
}

export function ApiJobsGetErrorStats() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: 'Job 에러 통계',
      description: '특정 작업의 에러를 스테이지별, 코드별로 집계합니다.',
    }),
    ApiParam({
      name: 'id',
      description: '작업 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '에러 통계 정보',
    }),
  );
}
