import { applyDecorators } from '@nestjs/common';
import { ApiOperation, ApiResponse } from '@nestjs/swagger';

export function ApiLabStatus() {
  return applyDecorators(
    ApiOperation({
      summary: 'User Backend 상태 확인',
      description: 'RAG 서비스가 동작하는 User Backend의 상태를 확인합니다.',
    }),
    ApiResponse({
      status: 200,
      description: 'User Backend 상태 정보',
      schema: {
        type: 'object',
        properties: {
          available: { type: 'boolean' },
          url: { type: 'string' },
          latencyMs: { type: 'number' },
          error: { type: 'string' },
        },
      },
    }),
  );
}

export function ApiLabSearch() {
  return applyDecorators(
    ApiOperation({
      summary: 'RAG 검색 테스트',
      description: '쿼리에 대한 RAG 검색을 수행하고 검색된 청크들을 반환합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '검색 결과',
      schema: {
        type: 'object',
        properties: {
          query: { type: 'string' },
          chunks: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                paperId: { type: 'string' },
                paperTitle: { type: 'string' },
                sectionName: { type: 'string' },
                chunkIndex: { type: 'number' },
                content: { type: 'string' },
                score: { type: 'number' },
              },
            },
          },
          searchLatencyMs: { type: 'number' },
          totalChunks: { type: 'number' },
          parameters: {
            type: 'object',
            properties: {
              limit: { type: 'number' },
              alpha: { type: 'number' },
            },
          },
        },
      },
    }),
  );
}

export function ApiLabGenerate() {
  return applyDecorators(
    ApiOperation({
      summary: 'RAG + LLM 답변 생성 테스트',
      description: 'RAG 검색 후 LLM으로 답변을 생성합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '생성된 답변',
      schema: {
        type: 'object',
        properties: {
          query: { type: 'string' },
          answer: { type: 'string' },
          references: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                paperId: { type: 'string' },
                title: { type: 'string' },
                section: { type: 'string' },
                content: { type: 'string' },
                score: { type: 'number' },
              },
            },
          },
          searchLatencyMs: { type: 'number' },
          llmLatencyMs: { type: 'number' },
          totalLatencyMs: { type: 'number' },
          model: { type: 'string' },
        },
      },
    }),
  );
}

export function ApiLabCompare() {
  return applyDecorators(
    ApiOperation({
      summary: 'A/B 비교 테스트 (Reranker ON vs OFF)',
      description: '같은 쿼리로 Reranker 적용/미적용 결과를 비교합니다.',
    }),
    ApiResponse({
      status: 200,
      description: 'A/B 비교 결과',
      schema: {
        type: 'object',
        properties: {
          withReranker: {
            type: 'object',
            properties: {
              query: { type: 'string' },
              chunks: { type: 'array' },
              searchLatencyMs: { type: 'number' },
              rerankLatencyMs: { type: 'number' },
              totalChunks: { type: 'number' },
            },
          },
          withoutReranker: {
            type: 'object',
            properties: {
              query: { type: 'string' },
              chunks: { type: 'array' },
              searchLatencyMs: { type: 'number' },
              totalChunks: { type: 'number' },
            },
          },
        },
      },
    }),
  );
}

export function ApiLabFeedback() {
  return applyDecorators(
    ApiOperation({
      summary: '피드백 저장',
      description: '검색 또는 답변 품질에 대한 피드백을 저장합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '피드백 저장 결과',
      schema: {
        type: 'object',
        properties: {
          success: { type: 'boolean' },
          feedbackId: { type: 'string' },
          message: { type: 'string' },
        },
      },
    }),
  );
}

export function ApiLabTestLogList() {
  return applyDecorators(
    ApiOperation({
      summary: '테스트 로그 목록 조회',
      description: '테스트 로그 목록을 페이지네이션과 필터링으로 조회합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '테스트 로그 목록',
      schema: {
        type: 'object',
        properties: {
          items: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                id: { type: 'string' },
                testType: { type: 'string' },
                query: { type: 'string' },
                parameters: { type: 'object' },
                searchLatencyMs: { type: 'number', nullable: true },
                rerankLatencyMs: { type: 'number', nullable: true },
                llmLatencyMs: { type: 'number', nullable: true },
                totalLatencyMs: { type: 'number', nullable: true },
                createdAt: { type: 'string' },
                resultSummary: { type: 'object' },
              },
            },
          },
          total: { type: 'number' },
          page: { type: 'number' },
          limit: { type: 'number' },
          totalPages: { type: 'number' },
        },
      },
    }),
  );
}

export function ApiLabTestLogDetail() {
  return applyDecorators(
    ApiOperation({
      summary: '테스트 로그 상세 조회',
      description: '특정 테스트 로그의 전체 결과를 조회합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '테스트 로그 상세',
    }),
    ApiResponse({
      status: 404,
      description: '테스트 로그를 찾을 수 없음',
    }),
  );
}

export function ApiLabTestLogDelete() {
  return applyDecorators(
    ApiOperation({
      summary: '테스트 로그 삭제',
      description: '특정 테스트 로그를 삭제합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '삭제 결과',
      schema: {
        type: 'object',
        properties: {
          success: { type: 'boolean' },
          message: { type: 'string' },
        },
      },
    }),
    ApiResponse({
      status: 404,
      description: '테스트 로그를 찾을 수 없음',
    }),
  );
}
