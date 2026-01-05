'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import {
  Check,
  X,
  Shield,
  Clock,
  User,
  ChevronDown,
  UserX,
  UserCheck,
  MoreVertical,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';
import { ko } from 'date-fns/locale';

interface AdminUser {
  id: string;
  email: string;
  name: string;
  picture: string;
  status: 'pending' | 'approved' | 'rejected';
  role: 'super_admin' | 'admin' | 'viewer';
  isActive: boolean;
  createdAt: string;
  lastLoginAt: string | null;
  approvedAt: string | null;
  approvedBy?: {
    id: string;
    email: string;
    name: string;
  };
  rejectedReason?: string | null;
  deactivatedAt?: string | null;
  deactivatedBy?: {
    id: string;
    email: string;
    name: string;
  };
}

interface AdminListResponse {
  items: AdminUser[];
  total: number;
  pendingCount: number;
}

const ROLES = [
  { value: 'viewer', label: 'Viewer', description: '조회만 가능' },
  { value: 'admin', label: 'Admin', description: '논문 관리, 배치 실행' },
  { value: 'super_admin', label: 'Super Admin', description: '모든 권한' },
];

const STATUS_COLORS = {
  pending: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
};

const STATUS_LABELS = {
  pending: '승인 대기',
  approved: '승인됨',
  rejected: '거절됨',
};

export default function AdminUsersPage() {
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuth();
  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const [roleDropdownOpen, setRoleDropdownOpen] = useState<string | null>(null);
  const [actionMenuOpen, setActionMenuOpen] = useState<string | null>(null);
  const [showInactive, setShowInactive] = useState(false);

  const { data, isLoading, error } = useQuery<AdminListResponse>({
    queryKey: ['admin-users'],
    queryFn: () => api.get('/admin/users').then((res) => res.data),
  });

  const approveMutation = useMutation({
    mutationFn: ({ id, role }: { id: string; role?: string }) =>
      api.patch(`/admin/users/${id}/approve`, { role }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) =>
      api.patch(`/admin/users/${id}/reject`, { reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
    },
  });

  const updateRoleMutation = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) =>
      api.patch(`/admin/users/${id}/role`, { role }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      setRoleDropdownOpen(null);
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => api.patch(`/admin/users/${id}/deactivate`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      setActionMenuOpen(null);
    },
  });

  const reactivateMutation = useMutation({
    mutationFn: (id: string) => api.patch(`/admin/users/${id}/reactivate`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      setActionMenuOpen(null);
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center text-red-600 py-8">
        관리자 목록을 불러오는데 실패했습니다.
      </div>
    );
  }

  const pendingUsers = data?.items.filter((u) => u.status === 'pending') || [];
  const otherUsers = data?.items.filter((u) => {
    if (u.status === 'pending') return false;
    if (!showInactive && u.isActive === false) return false;
    return true;
  }) || [];
  const inactiveCount = data?.items.filter((u) => u.isActive === false).length || 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">관리자 관리</h1>
          <p className="text-gray-500">
            관리자 계정을 관리합니다. 총 {data?.total || 0}명
            {data?.pendingCount ? ` (승인 대기: ${data.pendingCount}명)` : ''}
          </p>
        </div>

        {/* 비활성화 사용자 표시 토글 */}
        {inactiveCount > 0 && (
          <label className="flex items-center gap-2 cursor-pointer">
            <span className="text-sm text-gray-600">
              비활성화된 관리자 표시
            </span>
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

      {/* 승인 대기 */}
      {pendingUsers.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <h2 className="text-lg font-semibold text-yellow-800 mb-4 flex items-center gap-2">
            <Clock className="h-5 w-5" />
            승인 대기 ({pendingUsers.length})
          </h2>
          <div className="space-y-3">
            {pendingUsers.map((admin) => (
              <div
                key={admin.id}
                className="bg-white rounded-lg p-4 flex items-center justify-between shadow-sm"
              >
                <div className="flex items-center gap-3">
                  {admin.picture ? (
                    <img
                      src={admin.picture}
                      alt={admin.name}
                      className="h-10 w-10 rounded-full"
                    />
                  ) : (
                    <div className="h-10 w-10 rounded-full bg-gray-200 flex items-center justify-center">
                      <User className="h-5 w-5 text-gray-500" />
                    </div>
                  )}
                  <div>
                    <p className="font-medium text-gray-900">{admin.name || admin.email}</p>
                    <p className="text-sm text-gray-500">{admin.email}</p>
                    <p className="text-xs text-gray-400">
                      {formatDistanceToNow(new Date(admin.createdAt), {
                        addSuffix: true,
                        locale: ko,
                      })}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <select
                    value={selectedRole || 'admin'}
                    onChange={(e) => setSelectedRole(e.target.value)}
                    className="text-sm border rounded px-2 py-1"
                  >
                    {ROLES.map((role) => (
                      <option key={role.value} value={role.value}>
                        {role.label}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() =>
                      approveMutation.mutate({
                        id: admin.id,
                        role: selectedRole || 'admin',
                      })
                    }
                    disabled={approveMutation.isPending}
                    className="flex items-center gap-1 bg-green-600 text-white px-3 py-1.5 rounded hover:bg-green-700 disabled:opacity-50"
                  >
                    <Check className="h-4 w-4" />
                    승인
                  </button>
                  <button
                    onClick={() => {
                      const reason = prompt('거절 사유를 입력하세요 (선택)');
                      rejectMutation.mutate({ id: admin.id, reason: reason || undefined });
                    }}
                    disabled={rejectMutation.isPending}
                    className="flex items-center gap-1 bg-red-600 text-white px-3 py-1.5 rounded hover:bg-red-700 disabled:opacity-50"
                  >
                    <X className="h-4 w-4" />
                    거절
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 전체 목록 */}
      <div className="bg-white shadow rounded-lg overflow-visible">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                User
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Role
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Last Login
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {otherUsers.map((admin) => (
              <tr
                key={admin.id}
                className={cn(
                  'hover:bg-gray-50',
                  admin.isActive === false && 'bg-gray-100'
                )}
              >
                <td className="px-6 py-4 whitespace-nowrap">
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
                      <div className={cn(
                        'h-8 w-8 rounded-full bg-gray-200 flex items-center justify-center',
                        admin.isActive === false && 'opacity-50'
                      )}>
                        <User className="h-4 w-4 text-gray-500" />
                      </div>
                    )}
                    <div>
                      <p className={cn(
                        'font-medium',
                        admin.isActive === false ? 'text-gray-400' : 'text-gray-900'
                      )}>
                        {admin.name || admin.email}
                        {admin.id === currentUser?.id && (
                          <span className="ml-2 text-xs text-blue-600">(나)</span>
                        )}
                      </p>
                      <p className={cn(
                        'text-sm',
                        admin.isActive === false ? 'text-gray-400' : 'text-gray-500'
                      )}>{admin.email}</p>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {admin.isActive === false ? (
                    <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-gray-200 text-gray-700">
                      비활성화됨
                    </span>
                  ) : (
                    <span
                      className={cn(
                        'inline-flex px-2 py-1 text-xs font-semibold rounded-full',
                        STATUS_COLORS[admin.status]
                      )}
                    >
                      {STATUS_LABELS[admin.status]}
                    </span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="relative">
                    {admin.id === currentUser?.id || admin.role === 'super_admin' ? (
                      <div className="flex items-center gap-1">
                        {admin.role === 'super_admin' && (
                          <Shield className="h-4 w-4 text-yellow-500" />
                        )}
                        <span className="text-sm text-gray-900">{admin.role}</span>
                      </div>
                    ) : (
                      <button
                        onClick={() =>
                          setRoleDropdownOpen(
                            roleDropdownOpen === admin.id ? null : admin.id
                          )
                        }
                        className="flex items-center gap-1 text-sm text-gray-900 hover:text-blue-600"
                      >
                        {admin.role}
                        <ChevronDown className="h-4 w-4" />
                      </button>
                    )}
                    {roleDropdownOpen === admin.id && (
                      <div className="absolute z-10 mt-1 w-48 bg-white border rounded-md shadow-lg">
                        {ROLES.filter((r) => r.value !== admin.role).map((role) => (
                          <button
                            key={role.value}
                            onClick={() =>
                              updateRoleMutation.mutate({
                                id: admin.id,
                                role: role.value,
                              })
                            }
                            className="block w-full text-left px-4 py-2 text-sm hover:bg-gray-100"
                          >
                            <span className="font-medium">{role.label}</span>
                            <span className="block text-xs text-gray-500">
                              {role.description}
                            </span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {admin.lastLoginAt
                    ? formatDistanceToNow(new Date(admin.lastLoginAt), {
                        addSuffix: true,
                        locale: ko,
                      })
                    : '-'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  <div className="flex items-center gap-2">
                    {/* 비활성화 또는 승인 정보 */}
                    {admin.isActive === false ? (
                      <span className="text-gray-400 text-xs">
                        비활성화: {admin.deactivatedBy?.name || admin.deactivatedBy?.email || '알 수 없음'}
                      </span>
                    ) : (
                      admin.approvedBy && (
                        <span className="text-gray-400 text-xs">
                          승인: {admin.approvedBy.name || admin.approvedBy.email}
                        </span>
                      )
                    )}

                    {/* 액션 메뉴 (본인과 super_admin은 제외) */}
                    {admin.id !== currentUser?.id && admin.role !== 'super_admin' && (
                      <div className="relative ml-auto">
                        <button
                          onClick={() =>
                            setActionMenuOpen(actionMenuOpen === admin.id ? null : admin.id)
                          }
                          className="p-1 hover:bg-gray-100 rounded"
                        >
                          <MoreVertical className="h-4 w-4 text-gray-500" />
                        </button>
                        {actionMenuOpen === admin.id && (
                          <div className="absolute right-0 z-10 mt-1 w-40 bg-white border rounded-md shadow-lg">
                            {admin.isActive !== false ? (
                              <button
                                onClick={() => {
                                  if (confirm(`${admin.name || admin.email}을(를) 비활성화하시겠습니까?`)) {
                                    deactivateMutation.mutate(admin.id);
                                  }
                                }}
                                disabled={deactivateMutation.isPending}
                                className="flex items-center gap-2 w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                              >
                                <UserX className="h-4 w-4" />
                                비활성화
                              </button>
                            ) : (
                              <button
                                onClick={() => reactivateMutation.mutate(admin.id)}
                                disabled={reactivateMutation.isPending}
                                className="flex items-center gap-2 w-full text-left px-4 py-2 text-sm text-green-600 hover:bg-green-50"
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
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
