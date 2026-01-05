import { applyDecorators } from '@nestjs/common';
import {
  ApiOperation,
  ApiResponse,
  ApiBearerAuth,
} from '@nestjs/swagger';

/**
 * Auth 모듈 Swagger 데코레이터
 */

// ─────────────────────────────────────────────────────────────
// OAuth 엔드포인트
// ─────────────────────────────────────────────────────────────

export function ApiAuthGoogleLogin() {
  return applyDecorators(
    ApiOperation({
      summary: 'Google OAuth 로그인 시작',
      description: 'Google OAuth 페이지로 리다이렉트됩니다.',
    }),
    ApiResponse({
      status: 302,
      description: 'Google 로그인 페이지로 리다이렉트',
    }),
  );
}

export function ApiAuthGoogleCallback() {
  return applyDecorators(
    ApiOperation({
      summary: 'Google OAuth 콜백',
      description: 'Google OAuth 인증 후 콜백을 처리하고 토큰을 발급합니다.',
    }),
    ApiResponse({
      status: 302,
      description: '프론트엔드로 리다이렉트 (토큰 포함 또는 승인 대기 페이지)',
    }),
  );
}

// ─────────────────────────────────────────────────────────────
// 토큰 관리
// ─────────────────────────────────────────────────────────────

export function ApiAuthRefresh() {
  return applyDecorators(
    ApiOperation({
      summary: 'Access Token 갱신',
      description: 'Refresh Token을 사용하여 새로운 Access Token을 발급받습니다.',
    }),
    ApiResponse({
      status: 200,
      description: '새로운 Access Token 및 Refresh Token',
    }),
    ApiResponse({
      status: 401,
      description: '유효하지 않은 Refresh Token',
    }),
  );
}

export function ApiAuthLogout() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '로그아웃 (현재 세션)',
      description: '현재 Refresh Token을 폐기하여 로그아웃합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '로그아웃 성공',
    }),
  );
}

export function ApiAuthLogoutAll() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '전체 로그아웃 (모든 세션)',
      description: '해당 사용자의 모든 Refresh Token을 폐기합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '로그아웃된 세션 수',
    }),
  );
}

// ─────────────────────────────────────────────────────────────
// 사용자 정보
// ─────────────────────────────────────────────────────────────

export function ApiAuthGetMe() {
  return applyDecorators(
    ApiBearerAuth('access-token'),
    ApiOperation({
      summary: '현재 로그인한 관리자 정보',
      description: 'JWT에서 추출한 현재 사용자의 정보를 반환합니다.',
    }),
    ApiResponse({
      status: 200,
      description: '관리자 정보',
    }),
    ApiResponse({
      status: 401,
      description: '인증되지 않음',
    }),
  );
}
