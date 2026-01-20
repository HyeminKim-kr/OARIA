import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { AdminListResponse } from '../_lib';

export function useAdminUsers() {
  const queryClient = useQueryClient();

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
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => api.patch(`/admin/users/${id}/deactivate`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
    },
  });

  const reactivateMutation = useMutation({
    mutationFn: (id: string) => api.patch(`/admin/users/${id}/reactivate`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
    },
  });

  return {
    data,
    isLoading,
    error,
    approveMutation,
    rejectMutation,
    updateRoleMutation,
    deactivateMutation,
    reactivateMutation,
  };
}
