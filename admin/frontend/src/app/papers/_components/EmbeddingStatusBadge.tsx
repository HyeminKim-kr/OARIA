import { Clock, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { EmbeddingStatus } from '@/lib/api';

interface EmbeddingStatusBadgeProps {
  status: EmbeddingStatus;
  chunkCount?: number;
}

const statusConfig = {
  pending: { bg: 'bg-yellow-50', text: 'text-yellow-700', icon: Clock, label: '대기' },
  processing: { bg: 'bg-blue-50', text: 'text-blue-700', icon: Loader2, label: '처리중' },
  completed: { bg: 'bg-green-50', text: 'text-green-700', icon: CheckCircle2, label: '완료' },
  failed: { bg: 'bg-red-50', text: 'text-red-700', icon: AlertCircle, label: '실패' },
};

export function EmbeddingStatusBadge({ status, chunkCount }: EmbeddingStatusBadgeProps) {
  if (!status) {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
        <Clock className="h-3 w-3" />
        미시작
      </span>
    );
  }

  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs ${config.bg} ${config.text}`}
    >
      <Icon className={`h-3 w-3 ${status === 'processing' ? 'animate-spin' : ''}`} />
      {config.label}
      {status === 'completed' && chunkCount !== undefined && (
        <span className="ml-1 font-medium">({chunkCount})</span>
      )}
    </span>
  );
}
