'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'next/navigation';
import { Loader2, Play } from 'lucide-react';
import { papersApi } from '@/lib/api';
import {
  PaperHeader,
  PaperMeta,
  EmbeddingStatusDisplay,
  FulltextTabs,
} from './_components';

export default function PaperDetailPage() {
  const params = useParams();
  const queryClient = useQueryClient();
  const id = params.id as string;

  const { data: paper, isLoading: paperLoading } = useQuery({
    queryKey: ['paper', id],
    queryFn: () => papersApi.getOne(id),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.embeddingStatus === 'processing' || data?.embeddingStatus === 'pending') {
        return 5000;
      }
      return false;
    },
  });

  const { data: fulltext, isLoading: fulltextLoading } = useQuery({
    queryKey: ['paper-fulltext', id],
    queryFn: () => papersApi.getFulltext(id),
    enabled: !!id,
  });

  const embedMutation = useMutation({
    mutationFn: () => papersApi.triggerEmbedPaper(id),
    onSuccess: (data) => {
      alert(`임베딩 태스크가 시작되었습니다.\nTask ID: ${data.taskId}`);
      queryClient.invalidateQueries({ queryKey: ['paper', id] });
    },
    onError: (error: any) => {
      alert(`오류: ${error.response?.data?.message || error.message}`);
    },
  });

  if (paperLoading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 w-64 rounded bg-gray-200" />
        <div className="h-64 rounded-lg bg-gray-200" />
      </div>
    );
  }

  if (!paper) {
    return (
      <div className="py-12 text-center">
        <p className="text-gray-500">Paper not found</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PaperHeader paper={paper} />

      <PaperMeta paper={paper} />

      {/* Abstract */}
      {paper.abstract && (
        <div className="rounded-lg bg-white p-6 shadow">
          <h2 className="mb-3 font-semibold text-gray-900">Abstract</h2>
          <p className="text-sm leading-relaxed text-gray-700">{paper.abstract}</p>
        </div>
      )}

      {/* Keywords */}
      {paper.keywords && paper.keywords.length > 0 && (
        <div className="rounded-lg bg-white p-6 shadow">
          <h2 className="mb-3 font-semibold text-gray-900">Keywords</h2>
          <div className="flex flex-wrap gap-2">
            {paper.keywords.map((keyword, idx) => (
              <span key={idx} className="rounded-full bg-gray-100 px-3 py-1 text-sm text-gray-700">
                {keyword}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Embedding Status */}
      <div className="rounded-lg bg-white p-6 shadow">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">임베딩 상태</h2>
          {(!paper.embeddingStatus || paper.embeddingStatus === 'failed') && (
            <button
              onClick={() => embedMutation.mutate()}
              disabled={embedMutation.isPending}
              className="inline-flex items-center gap-2 rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
            >
              {embedMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              {paper.embeddingStatus === 'failed' ? '재시도' : '임베딩 시작'}
            </button>
          )}
        </div>
        <EmbeddingStatusDisplay
          status={paper.embeddingStatus}
          chunkCount={paper.embeddingChunkCount}
          error={paper.embeddingError}
          embeddingAt={paper.embeddingAt}
        />
      </div>

      <FulltextTabs data={fulltext} isLoading={fulltextLoading} />
    </div>
  );
}
