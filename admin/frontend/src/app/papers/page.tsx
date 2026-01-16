'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Search, Play, Loader2, Square, RefreshCw } from 'lucide-react';
import { papersApi } from '@/lib/api';
import { formatNumber } from '@/lib/utils';
import { PaperListItem, EmbeddingFilterTabs, Pagination, EmbedJobCard } from './_components';

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

  // 처리 중인 작업이 있으면 자동으로 패널 열기
  useEffect(() => {
    if (stats?.embedding?.processing && stats.embedding.processing > 0) {
      setShowJobs(true);
    }
  }, [stats?.embedding?.processing]);

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
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-900">
              임베딩 작업 현황 ({jobsData?.total || 0})
            </h3>
            <button
              onClick={() => refetchJobs()}
              className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800"
            >
              <RefreshCw className="h-3 w-3" />
              새로고침
            </button>
          </div>

          {jobsData?.jobs && jobsData.jobs.length > 0 ? (
            <div className="space-y-3">
              {jobsData.jobs.map((job) => (
                <EmbedJobCard
                  key={job.jobId}
                  job={job}
                  onRetry={(jobId) => retryJobMutation.mutate(jobId)}
                  onCancel={(jobId) => cancelJobMutation.mutate(jobId)}
                  isRetrying={retryJobMutation.isPending}
                  isCancelling={cancelJobMutation.isPending}
                />
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-gray-300 bg-white p-6 text-center text-sm text-gray-500">
              현재 진행 중인 작업이 없습니다.
            </div>
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
