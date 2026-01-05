import { applyDecorators } from '@nestjs/common';
import {
  ApiOperation,
  ApiResponse,
  ApiParam,
  ApiBearerAuth,
} from '@nestjs/swagger';

/**
 * Search Queries 모듈 Swagger 데코레이터
 */

// ─────────────────────────────────────────────────────────────
// 조회 엔드포인트
// ─────────────────────────────────────────────────────────────

export function ApiQueriesFindAll() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '검색 쿼리 목록 조회',
      description: '등록된 모든 검색 쿼리를 우선순위 순으로 반환합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '검색 쿼리 목록',
    }),
  );
}

export function ApiQueriesFindActive() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '활성 검색 쿼리 목록',
      description: '활성화된 검색 쿼리만 반환합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '활성 검색 쿼리 목록',
    }),
  );
}

export function ApiQueriesGetStats() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '검색 쿼리 통계',
      description: '전체 쿼리 수, 활성 쿼리 수, 총 수집 논문 수를 반환합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '쿼리 통계 정보',
    }),
  );
}

export function ApiQueriesFindOne() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '검색 쿼리 상세 조회',
      description: '특정 검색 쿼리의 상세 정보와 관련 작업 목록을 반환합니다.',
    }),
    ApiParam({
      name: 'id',
      description: '쿼리 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '쿼리 상세 정보',
    }),
    ApiResponse({
      status: 404,
      description: '쿼리를 찾을 수 없음',
    }),
  );
}

export function ApiQueriesPreview() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: 'Europe PMC 검색 결과 미리보기',
      description: '쿼리를 저장하기 전에 예상 결과 수를 확인합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '예상 결과 수 및 실제 쿼리',
    }),
  );
}

// ─────────────────────────────────────────────────────────────
// 생성/수정/삭제 엔드포인트
// ─────────────────────────────────────────────────────────────

export function ApiQueriesCreate() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '검색 쿼리 생성',
      description: '새로운 검색 쿼리를 등록합니다. autoBackfill이 true면 자동으로 수집을 시작합니다.',
    }),
    ApiResponse({
      status: 201,
      description: '생성된 쿼리 정보',
    }),
    ApiResponse({
      status: 400,
      description: '유효하지 않은 요청',
    }),
  );
}

export function ApiQueriesUpdate() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '검색 쿼리 수정',
      description: '기존 검색 쿼리를 수정합니다.',
    }),
    ApiParam({
      name: 'id',
      description: '쿼리 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '수정된 쿼리 정보',
    }),
    ApiResponse({
      status: 404,
      description: '쿼리를 찾을 수 없음',
    }),
  );
}

export function ApiQueriesToggle() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '활성/비활성 토글',
      description: '검색 쿼리의 활성 상태를 토글합니다.',
    }),
    ApiParam({
      name: 'id',
      description: '쿼리 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '토글된 쿼리 정보',
    }),
  );
}

export function ApiQueriesRemove() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '검색 쿼리 삭제',
      description: '검색 쿼리를 삭제합니다.',
    }),
    ApiParam({
      name: 'id',
      description: '쿼리 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '삭제 완료',
    }),
    ApiResponse({
      status: 404,
      description: '쿼리를 찾을 수 없음',
    }),
  );
}

export function ApiQueriesTriggerBackfill() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: 'Backfill 실행 트리거',
      description: '해당 쿼리에 대한 논문 수집 작업을 시작합니다.',
    }),
    ApiParam({
      name: 'id',
      description: '쿼리 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '트리거된 태스크 ID',
    }),
    ApiResponse({
      status: 404,
      description: '쿼리를 찾을 수 없음',
    }),
  );
}
