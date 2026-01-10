'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Search, Play, RotateCcw, Loader2, Square, RefreshCw } from 'lucide-react';
import { papersApi, EmbedJobState } from '@/lib/api';
import { formatNumber } from '@/lib/utils';
import { PaperListItem, EmbeddingFilterTabs, Pagination } from './_components';

type EmbeddingStatusFilter = 'all' | 'not_started' | 'pending' | 'processing' | 'completed' | 'failed';

export default function PapersPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [embeddingFilter, setEmbeddingFilter] = useState<EmbeddingStatusFilter>('all');
  const [showJobs, setShowJobs] = useState(false);
  const limit = 20;

  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['papers', page, search, embeddingFilter],
    queryFn: () =>
      papersApi.getAll({
        page,
        limit,
        search: search || undefined,
        embeddingStatus: embeddingFilter === 'all' ? undefined : embeddingFilter,
      }),
    refetchInterval: (query) => {
      const items = query.state.data?.items;
      if (items?.some((p) => p.embeddingStatus === 'processing' || p.embeddingStatus === 'pending')) {
        return 5000;
      }
      return false;
    },
  });

  const { data: stats } = useQuery({
    queryKey: ['papers', 'stats'],
    queryFn: () => papersApi.getStats(),
    refetchInterval: (query) => {
      const embedding = query.state.data?.embedding;
      if (embedding?.processing && embedding.processing > 0) {
        return 10000;
      }
      return false;
    },
  });

  // Job Manager V2 - 현재 작업 목록 조회
  const { data: jobsData, refetch: refetchJobs } = useQuery({
    queryKey: ['papers', 'embedding', 'jobs'],
    queryFn: () => papersApi.getEmbedJobs(),
    enabled: showJobs,
    refetchInterval: showJobs ? 5000 : false,
  });

  // Job Manager V2 - 배치 임베딩 시작
  const triggerBatchMutation = useMutation({
    mutationFn: (limit?: number) => papersApi.triggerEmbedBatch(limit),
    onSuccess: (data) => {
      alert(`배치 임베딩이 시작되었습니다.\nBatch ID: ${data.batchId}\n논문 수: ${data.paperCount}개`);
      queryClient.invalidateQueries({ queryKey: ['papers'] });
      refetchJobs();
    },
    onError: (error: any) => {
      alert(`오류: ${error.response?.data?.message || error.message}`);
    },
  });

  // Job Manager V2 - 배치 임베딩 전체 취소
  const cancelBatchMutation = useMutation({
    mutationFn: () => papersApi.cancelEmbedBatch(),
    onSuccess: (data) => {
      alert(`${data.cancelledCount}개의 작업이 취소되었습니다.`);
      queryClient.invalidateQueries({ queryKey: ['papers'] });
      refetchJobs();
    },
    onError: (error: any) => {
      alert(`오류: ${error.response?.data?.message || error.message}`);
    },
  });

  // Job Manager V2 - 개별 작업 재시도
  const retryJobMutation = useMutation({
    mutationFn: (jobId: string) => papersApi.retryEmbedJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['papers'] });
      refetchJobs();
    },
    onError: (error: any) => {
      alert(`오류: ${error.response?.data?.message || error.message}`);
    },
  });

  // Job Manager V2 - 개별 작업 취소
  const cancelJobMutation = useMutation({
    mutationFn: (jobId: string) => papersApi.cancelEmbedJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['papers'] });
      refetchJobs();
    },
    onError: (error: any) => {
      alert(`오류: ${error.response?.data?.message || error.message}`);
    },
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  };

  const handleFilterChange = (filter: EmbeddingStatusFilter) => {
    setEmbeddingFilter(filter);
    setPage(1);
  };

  // 대기 중인 논문 수 (not_started + pending + failed)
  const pendingCount = (stats?.embedding?.notStarted || 0) + (stats?.embedding?.pending || 0) + (stats?.embedding?.failed || 0);
  const hasProcessingJobs = (stats?.embedding?.processing || 0) > 0;

  const getJobStatusBadge = (status: string) => {
    switch (status) {
      case 'processing':
        return 'bg-blue-100 text-blue-800';
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      case 'cancelled':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-yellow-100 text-yellow-800';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Papers</h1>
          <p className="mt-1 text-sm text-gray-500">Browse collected cancer research papers</p>
        </div>
        <div className="flex gap-2">
          {/* Job Manager V2 - 배치 임베딩 시작 */}
          <button
            onClick={() => triggerBatchMutation.mutate(100)}
            disabled={triggerBatchMutation.isPending || pendingCount === 0}
            className="inline-flex items-center gap-2 rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
          >
            {triggerBatchMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            배치 임베딩 시작
            {pendingCount > 0 ? ` (${pendingCount})` : ''}
          </button>

          {/* Job Manager V2 - 배치 취소 */}
          {hasProcessingJobs && (
            <button
              onClick={() => cancelBatchMutation.mutate()}
              disabled={cancelBatchMutation.isPending}
              className="inline-flex items-center gap-2 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              {cancelBatchMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Square className="h-4 w-4" />
              )}
              배치 취소
            </button>
          )}

          {/* 작업 목록 토글 */}
          <button
            onClick={() => setShowJobs(!showJobs)}
            className={`inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium ${
              showJobs
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            <RefreshCw className="h-4 w-4" />
            작업 현황
          </button>
        </div>
      </div>

      {/* Job Manager V2 - 작업 목록 패널 */}
      {showJobs && (
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-900">
              진행 중인 임베딩 작업 ({jobsData?.total || 0})
            </h3>
            <button
              onClick={() => refetchJobs()}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              새로고침
            </button>
          </div>

          {jobsData?.jobs && jobsData.jobs.length > 0 ? (
            <div className="space-y-2">
              {jobsData.jobs.map((job: EmbedJobState) => (
                <div
                  key={job.jobId}
                  className="flex items-center justify-between rounded-md border border-gray-100 bg-gray-50 p-3"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${getJobStatusBadge(
                        job.status
                      )}`}
                    >
                      {job.status}
                    </span>
                    <span className="text-sm text-gray-600">
                      {job.jobId.slice(0, 20)}...
                    </span>
                    <span className="text-sm text-gray-500">
                      진행: {job.progress}/{job.total}
                    </span>
                    {job.retryCount > 0 && (
                      <span className="text-xs text-orange-600">
                        재시도: {job.retryCount}
                      </span>
                    )}
                    {job.error && (
                      <span className="text-xs text-red-600" title={job.error}>
                        오류 있음
                      </span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    {(job.status === 'failed' || job.status === 'cancelled') && (
                      <button
                        onClick={() => retryJobMutation.mutate(job.jobId)}
                        disabled={retryJobMutation.isPending}
                        className="rounded bg-orange-500 px-2 py-1 text-xs text-white hover:bg-orange-600 disabled:opacity-50"
                      >
                        재시도
                      </button>
                    )}
                    {job.status === 'processing' && (
                      <button
                        onClick={() => cancelJobMutation.mutate(job.jobId)}
                        disabled={cancelJobMutation.isPending}
                        className="rounded bg-red-500 px-2 py-1 text-xs text-white hover:bg-red-600 disabled:opacity-50"
                      >
                        취소
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500">현재 진행 중인 작업이 없습니다.</p>
          )}
        </div>
      )}

      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search papers by title, abstract, or keywords..."
            className="w-full rounded-md border border-gray-300 py-2 pl-10 pr-4 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <button
          type="submit"
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Search
        </button>
      </form>

      <EmbeddingFilterTabs value={embeddingFilter} onChange={handleFilterChange} />

      {isLoading ? (
        <div className="animate-pulse space-y-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-32 rounded-lg bg-gray-200" />
          ))}
        </div>
      ) : (
        <>
          <div className="rounded-lg bg-white shadow">
            <div className="border-b border-gray-200 px-6 py-4">
              <p className="text-sm text-gray-500">
                Showing {formatNumber((page - 1) * limit + 1)} -{' '}
                {formatNumber(Math.min(page * limit, data?.total ?? 0))} of{' '}
                {formatNumber(data?.total ?? 0)} papers
              </p>
            </div>
            <div className="divide-y divide-gray-200">
              {data?.items && data.items.length > 0 ? (
                data.items.map((paper) => <PaperListItem key={paper.id} paper={paper} />)
              ) : (
                <div className="px-6 py-12 text-center text-gray-500">No papers found</div>
              )}
            </div>
          </div>

          <Pagination
            page={page}
            totalPages={data?.totalPages ?? 1}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}
