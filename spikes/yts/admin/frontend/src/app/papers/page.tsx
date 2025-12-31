'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Search, ExternalLink, Box, AlertCircle, CheckCircle2, Loader2, Clock, Play, RotateCcw } from 'lucide-react';
import Link from 'next/link';
import { papersApi, EmbeddingStatus } from '@/lib/api';
import { formatDate, formatNumber } from '@/lib/utils';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { useState } from 'react';

type EmbeddingStatusFilter = 'all' | 'not_started' | 'pending' | 'processing' | 'completed' | 'failed';

function EmbeddingStatusBadge({ status, chunkCount }: { status: EmbeddingStatus; chunkCount?: number }) {
  if (!status) {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
        <Clock className="h-3 w-3" />
        미시작
      </span>
    );
  }

  const config = {
    pending: { bg: 'bg-yellow-50', text: 'text-yellow-700', icon: Clock, label: '대기' },
    processing: { bg: 'bg-blue-50', text: 'text-blue-700', icon: Loader2, label: '처리중' },
    completed: { bg: 'bg-green-50', text: 'text-green-700', icon: CheckCircle2, label: '완료' },
    failed: { bg: 'bg-red-50', text: 'text-red-700', icon: AlertCircle, label: '실패' },
  }[status];

  const Icon = config.icon;

  return (
    <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs ${config.bg} ${config.text}`}>
      <Icon className={`h-3 w-3 ${status === 'processing' ? 'animate-spin' : ''}`} />
      {config.label}
      {status === 'completed' && chunkCount !== undefined && (
        <span className="ml-1 font-medium">({chunkCount})</span>
      )}
    </span>
  );
}

export default function PapersPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [embeddingFilter, setEmbeddingFilter] = useState<EmbeddingStatusFilter>('all');
  const limit = 20;

  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['papers', page, search, embeddingFilter],
    queryFn: () => papersApi.getAll({
      page,
      limit,
      search: search || undefined,
      embeddingStatus: embeddingFilter === 'all' ? undefined : embeddingFilter,
    }),
    // 처리중인 논문이 있으면 5초마다 갱신
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
    // 처리중인 논문이 있으면 10초마다 갱신
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Papers</h1>
          <p className="mt-1 text-sm text-gray-500">
            Browse collected cancer research papers
          </p>
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

      {/* 임베딩 상태 필터 */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-500">임베딩 상태:</span>
        <div className="flex gap-1">
          {[
            { value: 'all', label: '전체' },
            { value: 'not_started', label: '미시작' },
            { value: 'pending', label: '대기' },
            { value: 'processing', label: '처리중' },
            { value: 'completed', label: '완료' },
            { value: 'failed', label: '실패' },
          ].map((option) => (
            <button
              key={option.value}
              onClick={() => {
                setEmbeddingFilter(option.value as EmbeddingStatusFilter);
                setPage(1);
              }}
              className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                embeddingFilter === option.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

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
                data.items.map((paper) => (
                  <div key={paper.id} className="p-6 hover:bg-gray-50">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <Link
                          href={`/papers/${paper.id}`}
                          className="font-medium text-gray-900 hover:text-blue-600 hover:underline"
                        >
                          {paper.title}
                        </Link>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-500">
                          {paper.journal && <span>{paper.journal}</span>}
                          {paper.year && <span>({paper.year})</span>}
                          <StatusBadge status={paper.status} />
                          <EmbeddingStatusBadge
                            status={paper.embeddingStatus}
                            chunkCount={paper.embeddingChunkCount}
                          />
                        </div>
                        {paper.abstract && (
                          <p className="mt-2 line-clamp-2 text-sm text-gray-600">
                            {paper.abstract}
                          </p>
                        )}
                        <div className="mt-2 flex flex-wrap gap-2">
                          {paper.pmcid && (
                            <span className="inline-flex items-center rounded bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
                              PMC: {paper.pmcid}
                            </span>
                          )}
                          {paper.pmid && (
                            <span className="inline-flex items-center rounded bg-green-50 px-2 py-0.5 text-xs text-green-700">
                              PMID: {paper.pmid}
                            </span>
                          )}
                          {paper.doi && (
                            <a
                              href={`https://doi.org/${paper.doi}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 rounded bg-purple-50 px-2 py-0.5 text-xs text-purple-700 hover:bg-purple-100"
                            >
                              DOI <ExternalLink className="h-3 w-3" />
                            </a>
                          )}
                        </div>
                      </div>
                      <div className="text-right text-sm text-gray-500">
                        {formatDate(paper.createdAt)}
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="px-6 py-12 text-center text-gray-500">
                  No papers found
                </div>
              )}
            </div>
          </div>

          {data && data.totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="rounded-md border border-gray-300 px-3 py-1.5 text-sm disabled:opacity-50"
              >
                Previous
              </button>
              <span className="text-sm text-gray-500">
                Page {page} of {data.totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(data.totalPages, p + 1))}
                disabled={page === data.totalPages}
                className="rounded-md border border-gray-300 px-3 py-1.5 text-sm disabled:opacity-50"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
