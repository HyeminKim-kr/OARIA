'use client';

import { useState } from 'react';
import { Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';
import { useAdminUsers } from './_hooks';
import { PendingUserCard, UserTableRow } from './_components';

export default function AdminUsersPage() {
  const { user: currentUser } = useAuth();
  const [selectedRole, setSelectedRole] = useState<string>('admin');
  const [roleDropdownOpen, setRoleDropdownOpen] = useState<string | null>(null);
  const [actionMenuOpen, setActionMenuOpen] = useState<string | null>(null);
  const [showInactive, setShowInactive] = useState(false);

  const {
    data,
    isLoading,
    error,
    approveMutation,
    rejectMutation,
    updateRoleMutation,
    deactivateMutation,
    reactivateMutation,
  } = useAdminUsers();

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-blue-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-8 text-center text-red-600">
        관리자 목록을 불러오는데 실패했습니다.
      </div>
    );
  }

  const pendingUsers = data?.items.filter((u) => u.status === 'pending') || [];
  const otherUsers =
    data?.items.filter((u) => {
      if (u.status === 'pending') return false;
      if (!showInactive && u.isActive === false) return false;
      return true;
    }) || [];
  const inactiveCount = data?.items.filter((u) => u.isActive === false).length || 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">관리자 관리</h1>
          <p className="text-gray-500">
            관리자 계정을 관리합니다. 총 {data?.total || 0}명
            {data?.pendingCount ? ` (승인 대기: ${data.pendingCount}명)` : ''}
          </p>
        </div>

        {inactiveCount > 0 && (
          <label className="flex cursor-pointer items-center gap-2">
            <span className="text-sm text-gray-600">비활성화된 관리자 표시</span>
            <button
              type="button"
              role="switch"
              aria-checked={showInactive}
              onClick={() => setShowInactive(!showInactive)}
              className={cn(
                'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
                showInactive ? 'bg-blue-600' : 'bg-gray-200'
              )}
            >
              <span
                className={cn(
                  'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out',
                  showInactive ? 'translate-x-5' : 'translate-x-0'
                )}
              />
            </button>
          </label>
        )}
      </div>

      {/* Pending Users */}
      {pendingUsers.length > 0 && (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-yellow-800">
            <Clock className="h-5 w-5" />
            승인 대기 ({pendingUsers.length})
          </h2>
          <div className="space-y-3">
            {pendingUsers.map((admin) => (
              <PendingUserCard
                key={admin.id}
                admin={admin}
                selectedRole={selectedRole}
                onRoleChange={setSelectedRole}
                onApprove={() => approveMutation.mutate({ id: admin.id, role: selectedRole })}
                onReject={() => {
                  const reason = prompt('거절 사유를 입력하세요 (선택)');
                  rejectMutation.mutate({ id: admin.id, reason: reason || undefined });
                }}
                isApproving={approveMutation.isPending}
                isRejecting={rejectMutation.isPending}
              />
            ))}
          </div>
        </div>
      )}

      {/* User Table */}
      <div className="overflow-visible rounded-lg bg-white shadow">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                User
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Role
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Last Login
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {otherUsers.map((admin) => (
              <UserTableRow
                key={admin.id}
                admin={admin}
                currentUserId={currentUser?.id}
                roleDropdownOpen={roleDropdownOpen === admin.id}
                actionMenuOpen={actionMenuOpen === admin.id}
                onRoleDropdownToggle={() =>
                  setRoleDropdownOpen(roleDropdownOpen === admin.id ? null : admin.id)
                }
                onActionMenuToggle={() =>
                  setActionMenuOpen(actionMenuOpen === admin.id ? null : admin.id)
                }
                onRoleChange={(role) => {
                  updateRoleMutation.mutate({ id: admin.id, role });
                  setRoleDropdownOpen(null);
                }}
                onDeactivate={() => {
                  if (confirm(`${admin.name || admin.email}을(를) 비활성화하시겠습니까?`)) {
                    deactivateMutation.mutate(admin.id);
                    setActionMenuOpen(null);
                  }
                }}
                onReactivate={() => {
                  reactivateMutation.mutate(admin.id);
                  setActionMenuOpen(null);
                }}
                isDeactivating={deactivateMutation.isPending}
                isReactivating={reactivateMutation.isPending}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
