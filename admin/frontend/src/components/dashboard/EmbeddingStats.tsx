'use client';

import { useQuery } from '@tanstack/react-query';
import {
  Clock,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Layers,
  FileText,
} from 'lucide-react';
import Link from 'next/link';
import { papersApi } from '@/lib/api';
import { formatNumber } from '@/lib/utils';

export function EmbeddingStats() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['papers', 'stats'],
    queryFn: papersApi.getStats,
    // 처리중인 논문이 있으면 10초마다 갱신
    refetchInterval: (query) => {
      const embedding = query.state.data?.embedding;
      if (embedding?.processing && embedding.processing > 0) {
        return 10000;
      }
      return false;
    },
  });

  if (isLoading) {
    return (
      <div className="rounded-lg bg-white p-6 shadow">
        <div className="animate-pulse">
          <div className="h-6 w-40 rounded bg-gray-200" />
          <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-20 rounded bg-gray-100" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  const embedding = stats?.embedding;

  const embeddingItems = [
    {
      label: '미시작',
      value: embedding?.notStarted ?? 0,
      icon: FileText,
      color: 'text-gray-500',
      bgColor: 'bg-gray-50',
      filterValue: 'not_started',
    },
    {
      label: '대기',
      value: embedding?.pending ?? 0,
      icon: Clock,
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-50',
      filterValue: 'pending',
    },
    {
      label: '처리중',
      value: embedding?.processing ?? 0,
      icon: Loader2,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
      filterValue: 'processing',
    },
    {
      label: '완료',
      value: embedding?.completed ?? 0,
      icon: CheckCircle2,
      color: 'text-green-600',
      bgColor: 'bg-green-50',
      filterValue: 'completed',
    },
    {
      label: '실패',
      value: embedding?.failed ?? 0,
      icon: AlertCircle,
      color: 'text-red-600',
      bgColor: 'bg-red-50',
      filterValue: 'failed',
    },
    {
      label: '총 청크',
      value: embedding?.totalChunks ?? 0,
      icon: Layers,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50',
      filterValue: null,
    },
  ];

  const total = stats?.total ?? 0;
  const completedPercent = total > 0
    ? Math.round(((embedding?.completed ?? 0) / total) * 100)
    : 0;

  return (
    <div className="rounded-lg bg-white p-6 shadow">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">임베딩 현황</h2>
        <Link
          href="/papers"
          className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
        >
          전체 보기
        </Link>
      </div>

      {/* Progress bar */}
      {total > 0 ? (
        <div className="mt-4">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">
              임베딩 진행률 ({formatNumber(embedding?.completed ?? 0)} / {formatNumber(total)})
            </span>
            <span className="font-medium text-gray-900">{completedPercent}%</span>
          </div>
          <div className="mt-2 h-3 overflow-hidden rounded-full bg-gray-100">
            <div className="flex h-full">
              {(embedding?.completed ?? 0) > 0 && (
                <div
                  className="bg-green-500 transition-all"
                  style={{ width: `${((embedding?.completed ?? 0) / total) * 100}%` }}
                />
              )}
              {(embedding?.processing ?? 0) > 0 && (
                <div
                  className="bg-blue-500 transition-all"
                  style={{ width: `${((embedding?.processing ?? 0) / total) * 100}%` }}
                />
              )}
              {(embedding?.pending ?? 0) > 0 && (
                <div
                  className="bg-yellow-400 transition-all"
                  style={{ width: `${((embedding?.pending ?? 0) / total) * 100}%` }}
                />
              )}
              {(embedding?.failed ?? 0) > 0 && (
                <div
                  className="bg-red-500 transition-all"
                  style={{ width: `${((embedding?.failed ?? 0) / total) * 100}%` }}
                />
              )}
            </div>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-green-500" /> 완료
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-blue-500" /> 처리중
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-yellow-400" /> 대기
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-red-500" /> 실패
            </span>
          </div>
        </div>
      ) : (
        <div className="mt-4 rounded-lg bg-gray-50 p-4 text-center text-sm text-gray-500">
          아직 수집된 논문이 없습니다
        </div>
      )}

      {/* Stats grid */}
      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {embeddingItems.map((item) => {
          const Icon = item.icon;
          const content = (
            <div
              className={`rounded-lg p-4 ${item.bgColor} ${
                item.filterValue ? 'cursor-pointer hover:opacity-80' : ''
              }`}
            >
              <div className="flex items-center gap-2">
                <Icon
                  className={`h-4 w-4 ${item.color} ${
                    item.label === '처리중' ? 'animate-spin' : ''
                  }`}
                />
                <span className={`text-sm font-medium ${item.color}`}>
                  {item.label}
                </span>
              </div>
              <div className="mt-2 text-2xl font-bold text-gray-900">
                {formatNumber(item.value)}
              </div>
            </div>
          );

          if (item.filterValue) {
            return (
              <Link
                key={item.label}
                href={`/papers?embeddingStatus=${item.filterValue}`}
              >
                {content}
              </Link>
            );
          }

          return <div key={item.label}>{content}</div>;
        })}
      </div>
    </div>
  );
}
