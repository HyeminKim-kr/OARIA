import { applyDecorators } from '@nestjs/common';
import {
  ApiOperation,
  ApiResponse,
  ApiParam,
  ApiBearerAuth,
} from '@nestjs/swagger';

/**
 * Admin Users 모듈 Swagger 데코레이터
 */

// ─────────────────────────────────────────────────────────────
// 조회 엔드포인트
// ─────────────────────────────────────────────────────────────

export function ApiAdminUsersFindAll() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '관리자 목록 조회',
      description: '모든 관리자 목록을 반환합니다. (Super Admin만 접근 가능)',
    }),
    ApiResponse({
      status: 200,
      description: '관리자 목록, 총 수, 승인 대기 수',
    }),
    ApiResponse({
      status: 403,
      description: '권한 없음',
    }),
  );
}

export function ApiAdminUsersFindPending() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '승인 대기 관리자 목록',
      description: '승인 대기 중인 관리자 목록을 반환합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '승인 대기 관리자 목록',
    }),
  );
}

export function ApiAdminUsersFindOne() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '관리자 상세 조회',
      description: '특정 관리자의 상세 정보를 반환합니다.',
    }),
    ApiParam({
      name: 'id',
      description: '관리자 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '관리자 상세 정보',
    }),
    ApiResponse({
      status: 404,
      description: '관리자를 찾을 수 없음',
    }),
  );
}

// ─────────────────────────────────────────────────────────────
// 승인/거절 엔드포인트
// ─────────────────────────────────────────────────────────────

export function ApiAdminUsersApprove() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '관리자 승인',
      description: '승인 대기 중인 관리자를 승인합니다. 역할을 지정할 수 있습니다.',
    }),
    ApiParam({
      name: 'id',
      description: '관리자 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '승인된 관리자 정보',
    }),
    ApiResponse({
      status: 400,
      description: '승인 대기 상태가 아님',
    }),
    ApiResponse({
      status: 403,
      description: '권한 없음',
    }),
  );
}

export function ApiAdminUsersReject() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '관리자 거절',
      description: '승인 대기 중인 관리자를 거절합니다.',
    }),
    ApiParam({
      name: 'id',
      description: '관리자 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '거절된 관리자 정보',
    }),
    ApiResponse({
      status: 400,
      description: '승인 대기 상태가 아님',
    }),
  );
}

// ─────────────────────────────────────────────────────────────
// 역할/상태 관리 엔드포인트
// ─────────────────────────────────────────────────────────────

export function ApiAdminUsersUpdateRole() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '관리자 역할 변경',
      description: '관리자의 역할을 변경합니다. 자신의 역할은 변경할 수 없습니다.',
    }),
    ApiParam({
      name: 'id',
      description: '관리자 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '역할이 변경된 관리자 정보',
    }),
    ApiResponse({
      status: 400,
      description: '자신의 역할은 변경 불가',
    }),
  );
}

export function ApiAdminUsersDeactivate() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '관리자 비활성화',
      description: '관리자 계정을 비활성화합니다. 모든 토큰이 폐기됩니다.',
    }),
    ApiParam({
      name: 'id',
      description: '관리자 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '비활성화된 관리자 정보',
    }),
    ApiResponse({
      status: 400,
      description: '자신 또는 Super Admin은 비활성화 불가',
    }),
  );
}

export function ApiAdminUsersReactivate() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '관리자 재활성화',
      description: '비활성화된 관리자 계정을 다시 활성화합니다.',
    }),
    ApiParam({
      name: 'id',
      description: '관리자 UUID',
      type: 'string',
      format: 'uuid',
    }),
    ApiResponse({
      status: 200,
      description: '재활성화된 관리자 정보',
    }),
  );
}
