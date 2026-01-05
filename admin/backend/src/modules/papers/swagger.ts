import { applyDecorators } from '@nestjs/common';
import {
  ApiOperation,
  ApiResponse,
  ApiParam,
  ApiBearerAuth,
} from '@nestjs/swagger';

/**
 * Papers 모듈 Swagger 데코레이터
 */

// ─────────────────────────────────────────────────────────────
// 조회 엔드포인트
// ─────────────────────────────────────────────────────────────

export function ApiPapersFindAll() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '논문 목록 조회',
      description: '검색어, 상태, 임베딩 상태, 연도 범위로 필터링 가능한 논문 목록을 페이지네이션하여 반환합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '논문 목록 및 페이지네이션 정보',
    }),
  );
}

export function ApiPapersGetStats() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '논문 통계',
      description: '전체 논문 수, 상태별 분포, 연도별 분포, 임베딩 상태 통계를 반환합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '논문 통계 정보',
    }),
  );
}

export function ApiPapersGetRecent() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '최근 수집된 논문',
      description: '가장 최근에 수집된 논문 목록을 반환합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '최근 논문 목록',
    }),
  );
}

export function ApiPapersFindOne() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '논문 상세 조회',
      description: '특정 논문의 상세 정보를 반환합니다.',
    }),
    ApiParam({
      name: 'id',
      description: '논문 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '논문 상세 정보',
    }),
    ApiResponse({
      status: 404,
      description: '논문을 찾을 수 없음',
    }),
  );
}

export function ApiPapersGetFulltext() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '논문 전문 조회',
      description: '논문의 전문 텍스트와 원본 XML을 조회합니다.',
    }),
    ApiParam({
      name: 'id',
      description: '논문 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '전문 텍스트 및 원본 XML',
    }),
    ApiResponse({
      status: 404,
      description: '논문을 찾을 수 없음',
    }),
  );
}

// ─────────────────────────────────────────────────────────────
// 임베딩 트리거 엔드포인트
// ─────────────────────────────────────────────────────────────

export function ApiPapersTriggerEmbedAll() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '전체 논문 임베딩 시작',
      description: '대기 중인 모든 논문에 대해 임베딩 작업을 트리거합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '트리거된 태스크 ID 및 대기 중인 논문 수',
    }),
  );
}

export function ApiPapersTriggerEmbedByQuery() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '쿼리별 논문 임베딩',
      description: '특정 검색 쿼리로 수집된 논문들의 임베딩 작업을 트리거합니다.',
    }),
    ApiParam({
      name: 'queryId',
      description: '검색 쿼리 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '트리거된 태스크 ID',
    }),
  );
}

export function ApiPapersTriggerEmbedPaper() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '단일 논문 임베딩',
      description: '특정 논문 하나에 대해 임베딩 작업을 트리거합니다.',
    }),
    ApiParam({
      name: 'id',
      description: '논문 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '트리거된 태스크 ID',
    }),
    ApiResponse({
      status: 404,
      description: '논문을 찾을 수 없음',
    }),
  );
}

export function ApiPapersTriggerReembed() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '실패한 논문 재임베딩',
      description: '임베딩에 실패한 논문들을 재처리합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '트리거된 태스크 ID 및 실패한 논문 수',
    }),
  );
}
