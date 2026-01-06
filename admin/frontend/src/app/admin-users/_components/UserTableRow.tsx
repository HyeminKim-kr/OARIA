'use client';

import { User, Shield, ChevronDown, MoreVertical, UserX, UserCheck } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { ko } from 'date-fns/locale';
import { cn } from '@/lib/utils';
import { AdminUser, ROLES, STATUS_COLORS, STATUS_LABELS } from '../_lib';

interface UserTableRowProps {
  admin: AdminUser;
  currentUserId?: string;
  roleDropdownOpen: boolean;
  actionMenuOpen: boolean;
  onRoleDropdownToggle: () => void;
  onActionMenuToggle: () => void;
  onRoleChange: (role: string) => void;
  onDeactivate: () => void;
  onReactivate: () => void;
  isDeactivating: boolean;
  isReactivating: boolean;
}

export function UserTableRow({
  admin,
  currentUserId,
  roleDropdownOpen,
  actionMenuOpen,
  onRoleDropdownToggle,
  onActionMenuToggle,
  onRoleChange,
  onDeactivate,
  onReactivate,
  isDeactivating,
  isReactivating,
}: UserTableRowProps) {
  const isCurrentUser = admin.id === currentUserId;
  const isSuperAdmin = admin.role === 'super_admin';
  const canEditRole = !isCurrentUser && !isSuperAdmin;
  const canManage = !isCurrentUser && !isSuperAdmin;

  return (
    <tr className={cn('hover:bg-gray-50', admin.isActive === false && 'bg-gray-100')}>
      {/* User Info */}
      <td className="whitespace-nowrap px-6 py-4">
        <div className="flex items-center gap-3">
          {admin.picture ? (
            <img
              src={admin.picture}
              alt={admin.name}
              className={cn(
                'h-8 w-8 rounded-full',
                admin.isActive === false && 'grayscale opacity-50'
              )}
            />
          ) : (
            <div
              className={cn(
                'flex h-8 w-8 items-center justify-center rounded-full bg-gray-200',
                admin.isActive === false && 'opacity-50'
              )}
            >
              <User className="h-4 w-4 text-gray-500" />
            </div>
          )}
          <div>
            <p
              className={cn(
                'font-medium',
                admin.isActive === false ? 'text-gray-400' : 'text-gray-900'
              )}
            >
              {admin.name || admin.email}
              {isCurrentUser && <span className="ml-2 text-xs text-blue-600">(나)</span>}
            </p>
            <p
              className={cn(
                'text-sm',
                admin.isActive === false ? 'text-gray-400' : 'text-gray-500'
              )}
            >
              {admin.email}
            </p>
          </div>
        </div>
      </td>

      {/* Status */}
      <td className="whitespace-nowrap px-6 py-4">
        {admin.isActive === false ? (
          <span className="inline-flex rounded-full bg-gray-200 px-2 py-1 text-xs font-semibold text-gray-700">
            비활성화됨
          </span>
        ) : (
          <span
            className={cn(
              'inline-flex rounded-full px-2 py-1 text-xs font-semibold',
              STATUS_COLORS[admin.status]
            )}
          >
            {STATUS_LABELS[admin.status]}
          </span>
        )}
      </td>

      {/* Role */}
      <td className="whitespace-nowrap px-6 py-4">
        <div className="relative">
          {!canEditRole ? (
            <div className="flex items-center gap-1">
              {isSuperAdmin && <Shield className="h-4 w-4 text-yellow-500" />}
              <span className="text-sm text-gray-900">{admin.role}</span>
            </div>
          ) : (
            <button
              onClick={onRoleDropdownToggle}
              className="flex items-center gap-1 text-sm text-gray-900 hover:text-blue-600"
            >
              {admin.role}
              <ChevronDown className="h-4 w-4" />
            </button>
          )}
          {roleDropdownOpen && (
            <div className="absolute z-10 mt-1 w-48 rounded-md border bg-white shadow-lg">
              {ROLES.filter((r) => r.value !== admin.role).map((role) => (
                <button
                  key={role.value}
                  onClick={() => onRoleChange(role.value)}
                  className="block w-full px-4 py-2 text-left text-sm hover:bg-gray-100"
                >
                  <span className="font-medium">{role.label}</span>
                  <span className="block text-xs text-gray-500">{role.description}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </td>

      {/* Last Login */}
      <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
        {admin.lastLoginAt
          ? formatDistanceToNow(new Date(admin.lastLoginAt), { addSuffix: true, locale: ko })
          : '-'}
      </td>

      {/* Actions */}
      <td className="whitespace-nowrap px-6 py-4 text-sm">
        <div className="flex items-center gap-2">
          {admin.isActive === false ? (
            <span className="text-xs text-gray-400">
              비활성화: {admin.deactivatedBy?.name || admin.deactivatedBy?.email || '알 수 없음'}
            </span>
          ) : (
            admin.approvedBy && (
              <span className="text-xs text-gray-400">
                승인: {admin.approvedBy.name || admin.approvedBy.email}
              </span>
            )
          )}

          {canManage && (
            <div className="relative ml-auto">
              <button onClick={onActionMenuToggle} className="rounded p-1 hover:bg-gray-100">
                <MoreVertical className="h-4 w-4 text-gray-500" />
              </button>
              {actionMenuOpen && (
                <div className="absolute right-0 z-10 mt-1 w-40 rounded-md border bg-white shadow-lg">
                  {admin.isActive !== false ? (
                    <button
                      onClick={onDeactivate}
                      disabled={isDeactivating}
                      className="flex w-full items-center gap-2 px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50"
                    >
                      <UserX className="h-4 w-4" />
                      비활성화
                    </button>
                  ) : (
                    <button
                      onClick={onReactivate}
                      disabled={isReactivating}
                      className="flex w-full items-center gap-2 px-4 py-2 text-left text-sm text-green-600 hover:bg-green-50"
                    >
                      <UserCheck className="h-4 w-4" />
                      다시 활성화
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </td>
    </tr>
  );
}
