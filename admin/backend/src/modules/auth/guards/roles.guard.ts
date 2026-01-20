import { Injectable, CanActivate, ExecutionContext } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { AdminRole, AdminUser } from '../../../entities';

export const ROLES_KEY = 'roles';

@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    const requiredRoles = this.reflector.getAllAndOverride<AdminRole[]>(
      ROLES_KEY,
      [context.getHandler(), context.getClass()],
    );

    if (!requiredRoles) {
      return true;
    }

    const { user } = context.switchToHttp().getRequest();
    const admin = user as AdminUser;

    if (!admin) {
      return false;
    }

    // super_admin can do anything
    if (admin.role === AdminRole.SUPER_ADMIN) {
      return true;
    }

    return requiredRoles.includes(admin.role);
  }
}
