import { SetMetadata, createParamDecorator, ExecutionContext } from '@nestjs/common';
import { AdminRole, AdminUser } from '../../entities';
import { IS_PUBLIC_KEY } from './guards/jwt-auth.guard';
import { ROLES_KEY } from './guards/roles.guard';

/**
 * Public 엔드포인트 마킹
 * JWT 인증 없이 접근 가능
 */
export const Public = () => SetMetadata(IS_PUBLIC_KEY, true);

/**
 * 역할 기반 접근 제어
 * @example @Roles(AdminRole.SUPER_ADMIN)
 */
export const Roles = (...roles: AdminRole[]) => SetMetadata(ROLES_KEY, roles);

/**
 * 현재 로그인한 Admin 정보 주입
 * @example async getMe(@CurrentAdmin() admin: AdminUser)
 */
export const CurrentAdmin = createParamDecorator(
  (data: unknown, ctx: ExecutionContext): AdminUser => {
    const request = ctx.switchToHttp().getRequest();
    return request.user;
  },
);
