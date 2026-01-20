'use client';

import { useState } from 'react';
import { Loader2, ChevronDown, ChevronUp, AlertCircle, Clock, Package } from 'lucide-react';
import { EmbedJobState } from '@/lib/api';

interface EmbedJobCardProps {
  job: EmbedJobState;
  onRetry: (jobId: string) => void;
  onCancel: (jobId: string) => void;
  isRetrying?: boolean;
  isCancelling?: boolean;
}

const STATUS_CONFIG = {
  queued: { label: '대기', bg: 'bg-yellow-100', text: 'text-yellow-800', icon: '🟡' },
  processing: { label: '처리중', bg: 'bg-blue-100', text: 'text-blue-800', icon: '🔵' },
  completed: { label: '완료', bg: 'bg-green-100', text: 'text-green-800', icon: '🟢' },
  failed: { label: '실패', bg: 'bg-red-100', text: 'text-red-800', icon: '🔴' },
  cancelled: { label: '취소됨', bg: 'bg-gray-100', text: 'text-gray-800', icon: '⚪' },
} as const;

function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (hours > 0) {
    return `${hours}시간 ${minutes % 60}분`;
  }
  if (minutes > 0) {
    return `${minutes}분 ${seconds % 60}초`;
  }
  return `${seconds}초`;
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  return formatDuration(diffMs) + ' 전';
}

function estimateRemaining(
  progress: number,
  total: number,
  startedAt: string | null
): string {
  if (!startedAt || progress === 0 || total === 0) return '-';

  const started = new Date(startedAt).getTime();
  const now = Date.now();
  const elapsed = now - started;
  const rate = progress / elapsed; // items per ms
  const remaining = total - progress;
  const estimatedMs = remaining / rate;

  if (estimatedMs < 0 || !isFinite(estimatedMs)) return '-';
  return '~' + formatDuration(estimatedMs);
}

export function EmbedJobCard({
  job,
  onRetry,
  onCancel,
  isRetrying = false,
  isCancelling = false,
}: EmbedJobCardProps) {
  const [showDetail, setShowDetail] = useState(false);

  const statusConfig = STATUS_CONFIG[job.status as keyof typeof STATUS_CONFIG] || {
    label: job.status,
    bg: 'bg-gray-100',
    text: 'text-gray-800',
    icon: '⚪',
  };

  const progressPercent = job.total > 0 ? Math.round((job.progress / job.total) * 100) : 0;
  const isActive = job.status === 'processing' || job.status === 'queued';

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      {/* Header Row */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${statusConfig.bg} ${statusConfig.text}`}>
            {statusConfig.icon} {statusConfig.label}
          </span>
          <span className="text-sm font-mono text-gray-600" title={job.jobId}>
            {job.jobId.slice(0, 16)}...
          </span>
          {job.retryCount > 0 && (
            <span className="text-xs text-orange-600 font-medium">
              재시도 {job.retryCount}회
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {(job.status === 'failed' || job.status === 'cancelled') && (
            <button
              onClick={() => onRetry(job.jobId)}
              disabled={isRetrying}
              className="inline-flex items-center gap-1 rounded bg-orange-500 px-2.5 py-1 text-xs font-medium text-white hover:bg-orange-600 disabled:opacity-50"
            >
              {isRetrying && <Loader2 className="h-3 w-3 animate-spin" />}
              재시도
            </button>
          )}
          {job.status === 'processing' && (
            <button
              onClick={() => onCancel(job.jobId)}
              disabled={isCancelling}
              className="inline-flex items-center gap-1 rounded bg-red-500 px-2.5 py-1 text-xs font-medium text-white hover:bg-red-600 disabled:opacity-50"
            >
              {isCancelling && <Loader2 className="h-3 w-3 animate-spin" />}
              취소
            </button>
          )}
          <button
            onClick={() => setShowDetail(!showDetail)}
            className="text-gray-400 hover:text-gray-600"
          >
            {showDetail ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-2">
        <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
          <span>{job.progress}/{job.total} 논문</span>
          <span className="font-medium">{progressPercent}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
          <div
            className={`h-2 rounded-full transition-all duration-500 ${
              job.status === 'failed' ? 'bg-red-500' :
              job.status === 'completed' ? 'bg-green-500' :
              'bg-blue-500'
            }`}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Info Row */}
      <div className="flex items-center gap-4 text-xs text-gray-500">
        {job.chunkCount !== null && job.chunkCount > 0 && (
          <span className="flex items-center gap-1">
            <Package className="h-3 w-3" />
            {job.chunkCount.toLocaleString()} chunks
          </span>
        )}
        {job.startedAt && (
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            시작: {formatRelativeTime(job.startedAt)}
          </span>
        )}
        {isActive && job.startedAt && (
          <span className="text-blue-600 font-medium">
            예상: {estimateRemaining(job.progress, job.total, job.startedAt)}
          </span>
        )}
      </div>

      {/* Error Display */}
      {job.error && (
        <div className="mt-2 flex items-start gap-2 rounded bg-red-50 p-2 text-xs text-red-700">
          <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
          <span className={showDetail ? '' : 'line-clamp-1'}>{job.error}</span>
        </div>
      )}

      {/* Detail Section */}
      {showDetail && (
        <div className="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-500 space-y-1">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="font-medium">Job ID:</span>
              <span className="ml-1 font-mono">{job.jobId}</span>
            </div>
            <div>
              <span className="font-medium">생성:</span>
              <span className="ml-1">{job.createdAt ? new Date(job.createdAt).toLocaleString('ko-KR') : '-'}</span>
            </div>
            <div>
              <span className="font-medium">시작:</span>
              <span className="ml-1">{job.startedAt ? new Date(job.startedAt).toLocaleString('ko-KR') : '-'}</span>
            </div>
            <div>
              <span className="font-medium">완료:</span>
              <span className="ml-1">{job.completedAt ? new Date(job.completedAt).toLocaleString('ko-KR') : '-'}</span>
            </div>
            {job.heartbeat && (
              <div>
                <span className="font-medium">마지막 활동:</span>
                <span className="ml-1">{formatRelativeTime(job.heartbeat)}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
