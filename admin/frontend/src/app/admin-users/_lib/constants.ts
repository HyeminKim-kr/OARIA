import { RoleOption } from './types';

export const ROLES: RoleOption[] = [
  { value: 'viewer', label: 'Viewer', description: '조회만 가능' },
  { value: 'admin', label: 'Admin', description: '논문 관리, 배치 실행' },
  { value: 'super_admin', label: 'Super Admin', description: '모든 권한' },
];

export const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
};

export const STATUS_LABELS: Record<string, string> = {
  pending: '승인 대기',
  approved: '승인됨',
  rejected: '거절됨',
};
