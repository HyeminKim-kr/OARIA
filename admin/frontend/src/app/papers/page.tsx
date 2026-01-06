'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Search, Play, RotateCcw, Loader2 } from 'lucide-react';
import { papersApi } from '@/lib/api';
import { formatNumber } from '@/lib/utils';
import { PaperListItem, EmbeddingFilterTabs, Pagination } from './_components';

type EmbeddingStatusFilter = 'all' | 'not_started' | 'pending' | 'processing' | 'completed' | 'failed';

export default function PapersPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [embeddingFilter, setEmbeddingFilter] = useState<EmbeddingStatusFilter>('all');
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

  const embedAllMutation = useMutation({
    mutationFn: () => papersApi.triggerEmbedAll(),
    onSuccess: (data) => {
      alert(`임베딩 태스크가 시작되었습니다.\nTask ID: ${data.taskId}\n대기 논문: ${data.pendingCount}개`);
      queryClient.invalidateQueries({ queryKey: ['papers'] });
    },
    onError: (error: any) => {
      alert(`오류: ${error.response?.data?.message || error.message}`);
    },
  });

  const reembedMutation = useMutation({
    mutationFn: () => papersApi.triggerReembed(),
    onSuccess: (data) => {
      alert(`재임베딩 태스크가 시작되었습니다.\nTask ID: ${data.taskId}\n실패 논문: ${data.failedCount}개`);
      queryClient.invalidateQueries({ queryKey: ['papers'] });
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Papers</h1>
          <p className="mt-1 text-sm text-gray-500">Browse collected cancer research papers</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => embedAllMutation.mutate()}
            disabled={embedAllMutation.isPending || !stats?.embedding?.notStarted}
            className="inline-flex items-center gap-2 rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
          >
            {embedAllMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            임베딩 시작
            {stats?.embedding?.notStarted ? ` (${stats.embedding.notStarted})` : ''}
          </button>
          {stats?.embedding?.failed ? (
            <button
              onClick={() => reembedMutation.mutate()}
              disabled={reembedMutation.isPending}
              className="inline-flex items-center gap-2 rounded-md bg-orange-600 px-4 py-2 text-sm font-medium text-white hover:bg-orange-700 disabled:opacity-50"
            >
              {reembedMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RotateCcw className="h-4 w-4" />
              )}
              재시도 ({stats.embedding.failed})
            </button>
          ) : null}
        </div>
      </div>

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
