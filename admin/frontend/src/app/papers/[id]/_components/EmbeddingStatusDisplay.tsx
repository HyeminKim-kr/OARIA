import { Clock, Loader2, CheckCircle2, AlertCircle, Layers } from 'lucide-react';
import { EmbeddingStatus } from '@/lib/api';
import { formatDate } from '@/lib/utils';

interface EmbeddingStatusDisplayProps {
  status: EmbeddingStatus;
  chunkCount?: number;
  error?: string | null;
  embeddingAt?: string | null;
}

const statusConfig = {
  pending: { bg: 'bg-yellow-50', text: 'text-yellow-700', icon: Clock, label: '대기중' },
  processing: { bg: 'bg-blue-50', text: 'text-blue-700', icon: Loader2, label: '처리중' },
  completed: { bg: 'bg-green-50', text: 'text-green-700', icon: CheckCircle2, label: '완료' },
  failed: { bg: 'bg-red-50', text: 'text-red-700', icon: AlertCircle, label: '실패' },
};

export function EmbeddingStatusDisplay({
  status,
  chunkCount,
  error,
  embeddingAt,
}: EmbeddingStatusDisplayProps) {
  if (!status) {
    return (
      <div className="rounded-lg bg-gray-50 p-4">
        <div className="flex items-center gap-2 text-gray-600">
          <Clock className="h-4 w-4" />
          <span className="font-medium">임베딩 미시작</span>
        </div>
        <p className="mt-1 text-sm text-gray-500">아직 임베딩 작업이 시작되지 않았습니다.</p>
      </div>
    );
  }

  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <div className={`rounded-lg ${config.bg} p-4`}>
      <div className={`flex items-center gap-2 ${config.text}`}>
        <Icon className={`h-4 w-4 ${status === 'processing' ? 'animate-spin' : ''}`} />
        <span className="font-medium">{config.label}</span>
      </div>

      {status === 'completed' && (
        <div className="mt-2 flex items-center gap-4 text-sm">
          <div className="flex items-center gap-1 text-green-700">
            <Layers className="h-4 w-4" />
            <span>{chunkCount}개 청크</span>
          </div>
          {embeddingAt && <span className="text-green-600">{formatDate(embeddingAt)}</span>}
        </div>
      )}

      {status === 'failed' && error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}
