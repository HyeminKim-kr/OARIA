'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  ExternalLink,
  FileText,
  Code,
  Loader2,
  Clock,
  CheckCircle2,
  AlertCircle,
  Play,
  Layers,
} from 'lucide-react';
import { papersApi, EmbeddingStatus } from '@/lib/api';
import { formatDate } from '@/lib/utils';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { useState } from 'react';

function EmbeddingStatusDisplay({ status, chunkCount, error, embeddingAt }: {
  status: EmbeddingStatus;
  chunkCount?: number;
  error?: string | null;
  embeddingAt?: string | null;
}) {
  const config = {
    pending: { bg: 'bg-yellow-50', text: 'text-yellow-700', icon: Clock, label: '대기중' },
    processing: { bg: 'bg-blue-50', text: 'text-blue-700', icon: Loader2, label: '처리중' },
    completed: { bg: 'bg-green-50', text: 'text-green-700', icon: CheckCircle2, label: '완료' },
    failed: { bg: 'bg-red-50', text: 'text-red-700', icon: AlertCircle, label: '실패' },
  };

  if (!status) {
    return (
      <div className="rounded-lg bg-gray-50 p-4">
        <div className="flex items-center gap-2 text-gray-600">
          <Clock className="h-4 w-4" />
          <span className="font-medium">임베딩 미시작</span>
        </div>
        <p className="mt-1 text-sm text-gray-500">
          아직 임베딩 작업이 시작되지 않았습니다.
        </p>
      </div>
    );
  }

  const { bg, text, icon: Icon, label } = config[status];

  return (
    <div className={`rounded-lg ${bg} p-4`}>
      <div className={`flex items-center gap-2 ${text}`}>
        <Icon className={`h-4 w-4 ${status === 'processing' ? 'animate-spin' : ''}`} />
        <span className="font-medium">{label}</span>
      </div>

      {status === 'completed' && (
        <div className="mt-2 flex items-center gap-4 text-sm">
          <div className="flex items-center gap-1 text-green-700">
            <Layers className="h-4 w-4" />
            <span>{chunkCount}개 청크</span>
          </div>
          {embeddingAt && (
            <span className="text-green-600">{formatDate(embeddingAt)}</span>
          )}
        </div>
      )}

      {status === 'failed' && error && (
        <p className="mt-2 text-sm text-red-600">{error}</p>
      )}
    </div>
  );
}

export default function PaperDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const id = params.id as string;
  const [activeTab, setActiveTab] = useState<'fulltext' | 'xml'>('fulltext');

  const { data: paper, isLoading: paperLoading } = useQuery({
    queryKey: ['paper', id],
    queryFn: () => papersApi.getOne(id),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data;
      // 처리중일 때만 5초마다 갱신
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
      <div className="text-center py-12">
        <p className="text-gray-500">Paper not found</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.back()}
          className="rounded-full p-2 hover:bg-gray-100"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-xl font-bold text-gray-900">{paper.title}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-500">
            {paper.journal && <span>{paper.journal}</span>}
            {paper.year && <span>({paper.year})</span>}
            <StatusBadge status={paper.status} />
          </div>
        </div>
      </div>

      {/* Meta Info */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {paper.pmcid && (
          <div className="rounded-lg bg-white p-4 shadow">
            <p className="text-xs text-gray-500">PMC ID</p>
            <p className="font-medium text-blue-600">{paper.pmcid}</p>
          </div>
        )}
        {paper.pmid && (
          <div className="rounded-lg bg-white p-4 shadow">
            <p className="text-xs text-gray-500">PMID</p>
            <p className="font-medium text-green-600">{paper.pmid}</p>
          </div>
        )}
        {paper.doi && (
          <div className="rounded-lg bg-white p-4 shadow">
            <p className="text-xs text-gray-500">DOI</p>
            <a
              href={`https://doi.org/${paper.doi}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 font-medium text-purple-600 hover:underline"
            >
              {paper.doi}
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        )}
        <div className="rounded-lg bg-white p-4 shadow">
          <p className="text-xs text-gray-500">Collected</p>
          <p className="font-medium">{formatDate(paper.createdAt)}</p>
        </div>
      </div>

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
              <span
                key={idx}
                className="rounded-full bg-gray-100 px-3 py-1 text-sm text-gray-700"
              >
                {keyword}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Embedding Status */}
      <div className="rounded-lg bg-white p-6 shadow">
        <div className="flex items-center justify-between mb-4">
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

      {/* Fulltext / XML Tabs */}
      <div className="rounded-lg bg-white shadow">
        <div className="border-b border-gray-200">
          <nav className="flex">
            <button
              onClick={() => setActiveTab('fulltext')}
              className={`flex items-center gap-2 px-6 py-3 text-sm font-medium ${
                activeTab === 'fulltext'
                  ? 'border-b-2 border-blue-500 text-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <FileText className="h-4 w-4" />
              Full Text
            </button>
            <button
              onClick={() => setActiveTab('xml')}
              className={`flex items-center gap-2 px-6 py-3 text-sm font-medium ${
                activeTab === 'xml'
                  ? 'border-b-2 border-blue-500 text-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <Code className="h-4 w-4" />
              Raw XML
            </button>
          </nav>
        </div>

        <div className="p-6">
          {fulltextLoading ? (
            <div className="animate-pulse">
              <div className="h-4 w-full rounded bg-gray-200 mb-2" />
              <div className="h-4 w-5/6 rounded bg-gray-200 mb-2" />
              <div className="h-4 w-4/6 rounded bg-gray-200" />
            </div>
          ) : activeTab === 'fulltext' ? (
            fulltext?.fulltext ? (
              <pre className="max-h-[600px] overflow-auto whitespace-pre-wrap text-sm text-gray-700 font-sans leading-relaxed">
                {fulltext.fulltext}
              </pre>
            ) : (
              <p className="text-gray-500 text-center py-8">
                Full text not available
              </p>
            )
          ) : fulltext?.rawXml ? (
            <pre className="max-h-[600px] overflow-auto text-xs text-gray-700 font-mono bg-gray-50 p-4 rounded">
              {fulltext.rawXml}
            </pre>
          ) : (
            <p className="text-gray-500 text-center py-8">
              Raw XML not available
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
