'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { XCircle, RefreshCw, PlayCircle, Eye, AlertTriangle } from 'lucide-react';
import Link from 'next/link';
import { collectionJobsApi } from '@/lib/api';
import { formatDate, formatDuration } from '@/lib/utils';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { useState } from 'react';

const statusFilters = ['all', 'pending', 'running', 'completed', 'failed', 'partial', 'delayed', 'cancelled', 'retried'];

export default function JobsPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState('all');

  const { data: jobs, isLoading } = useQuery({
    queryKey: ['collection-jobs', statusFilter],
    queryFn: () =>
      collectionJobsApi.getAll({
        status: statusFilter === 'all' ? undefined : statusFilter,
        limit: 50,
      }),
    refetchInterval: 5000,
  });

  const cancelMutation = useMutation({
    mutationFn: collectionJobsApi.cancel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collection-jobs'] });
    },
  });

  const retryMutation = useMutation({
    mutationFn: collectionJobsApi.retry,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collection-jobs'] });
    },
  });

  const resumeMutation = useMutation({
    mutationFn: collectionJobsApi.resume,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collection-jobs'] });
    },
  });

  const handleCancel = (id: string) => {
    if (confirm('Are you sure you want to cancel this job?')) {
      cancelMutation.mutate(id);
    }
  };

  const handleRetry = (id: string) => {
    if (confirm('Retry this failed job?')) {
      retryMutation.mutate(id);
    }
  };

  const handleResume = (id: string) => {
    if (confirm('Resume this job? (continues processing pending articles)')) {
      resumeMutation.mutate(id);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Collection Jobs</h1>
        <p className="mt-1 text-sm text-gray-500">
          Monitor and manage paper collection jobs
        </p>
      </div>

      <div className="flex gap-2">
        {statusFilters.map((status) => (
          <button
            key={status}
            onClick={() => setStatusFilter(status)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium capitalize transition-colors ${
              statusFilter === status
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {status}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="animate-pulse space-y-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-20 rounded-lg bg-gray-200" />
          ))}
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg bg-white shadow">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Query
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Progress
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Duration
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Started
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {jobs && jobs.length > 0 ? (
                jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-gray-50">
                    <td className="whitespace-nowrap px-6 py-4">
                      <span className="inline-flex rounded-full bg-gray-100 px-2 py-1 text-xs font-medium text-gray-800">
                        {job.jobType}
                      </span>
                    </td>
                    <td className="max-w-xs px-6 py-4">
                      <div className="truncate text-sm text-gray-900">
                        {job.query}
                      </div>
                      {job.lastErrorMessage && (
                        <div className="mt-1 truncate text-xs text-red-500">
                          {job.lastErrorMessage}
                        </div>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4">
                      <StatusBadge status={job.status} />
                    </td>
                    <td className="whitespace-nowrap px-6 py-4">
                      <div className="text-sm text-gray-900">
                        {job.processedCount} / {job.totalCount ?? '?'}
                      </div>
                      {job.totalCount && job.totalCount > 0 && (
                        <div className="mt-1 h-2 w-24 overflow-hidden rounded-full bg-gray-200">
                          <div
                            className="h-full bg-blue-500 transition-all"
                            style={{
                              width: `${Math.min(100, (job.processedCount / job.totalCount) * 100)}%`,
                            }}
                          />
                        </div>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                      {formatDuration(job.durationMs)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                      {formatDate(job.startedAt)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-right text-sm">
                      <div className="flex items-center justify-end gap-2">
                        <Link
                          href={`/jobs/${job.id}`}
                          className="rounded p-1 text-gray-600 hover:bg-gray-100"
                          title="View Details"
                        >
                          {job.failedCount > 0 ? (
                            <AlertTriangle className="h-4 w-4 text-amber-500" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </Link>
                        {(job.status === 'pending' || job.status === 'running') && (
                          <button
                            onClick={() => handleCancel(job.id)}
                            className="rounded p-1 text-red-600 hover:bg-red-50"
                            title="Cancel"
                          >
                            <XCircle className="h-4 w-4" />
                          </button>
                        )}
                        {(job.status === 'partial' || job.status === 'failed') && (
                          <button
                            onClick={() => handleResume(job.id)}
                            className="rounded p-1 text-green-600 hover:bg-green-50"
                            title="Resume (continue pending articles)"
                          >
                            <PlayCircle className="h-4 w-4" />
                          </button>
                        )}
                        {(job.status === 'failed' || job.status === 'cancelled') && (
                          <button
                            onClick={() => handleRetry(job.id)}
                            className="rounded p-1 text-blue-600 hover:bg-blue-50"
                            title="Retry (create new job)"
                          >
                            <RefreshCw className="h-4 w-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td
                    colSpan={7}
                    className="px-6 py-8 text-center text-sm text-gray-500"
                  >
                    No jobs found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
