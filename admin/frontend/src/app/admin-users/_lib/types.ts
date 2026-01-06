export interface AdminUser {
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

export interface AdminListResponse {
  items: AdminUser[];
  total: number;
  pendingCount: number;
}

export interface RoleOption {
  value: string;
  label: string;
  description: string;
}
