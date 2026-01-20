'use client';

import { Check, X, User } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { ko } from 'date-fns/locale';
import { AdminUser, ROLES } from '../_lib';

interface PendingUserCardProps {
  admin: AdminUser;
  selectedRole: string;
  onRoleChange: (role: string) => void;
  onApprove: () => void;
  onReject: () => void;
  isApproving: boolean;
  isRejecting: boolean;
}

export function PendingUserCard({
  admin,
  selectedRole,
  onRoleChange,
  onApprove,
  onReject,
  isApproving,
  isRejecting,
}: PendingUserCardProps) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-white p-4 shadow-sm">
      <div className="flex items-center gap-3">
        {admin.picture ? (
          <img src={admin.picture} alt={admin.name} className="h-10 w-10 rounded-full" />
        ) : (
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gray-200">
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
          value={selectedRole}
          onChange={(e) => onRoleChange(e.target.value)}
          className="rounded border px-2 py-1 text-sm"
        >
          {ROLES.map((role) => (
            <option key={role.value} value={role.value}>
              {role.label}
            </option>
          ))}
        </select>
        <button
          onClick={onApprove}
          disabled={isApproving}
          className="flex items-center gap-1 rounded bg-green-600 px-3 py-1.5 text-white hover:bg-green-700 disabled:opacity-50"
        >
          <Check className="h-4 w-4" />
          승인
        </button>
        <button
          onClick={onReject}
          disabled={isRejecting}
          className="flex items-center gap-1 rounded bg-red-600 px-3 py-1.5 text-white hover:bg-red-700 disabled:opacity-50"
        >
          <X className="h-4 w-4" />
          거절
        </button>
      </div>
    </div>
  );
}
