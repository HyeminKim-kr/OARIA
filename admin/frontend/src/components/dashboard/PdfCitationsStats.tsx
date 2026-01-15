'use client';

import { useQuery } from '@tanstack/react-query';
import { FileText, HardDrive, Quote, TrendingUp } from 'lucide-react';
import { papersApi } from '@/lib/api';
import { formatNumber } from '@/lib/utils';

function formatFileSize(bytes: number | null | undefined): string {
  if (!bytes) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function PdfCitationsStats() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['papers', 'stats'],
    queryFn: papersApi.getStats,
  });

  if (isLoading) {
    return (
      <div className="rounded-lg bg-white p-6 shadow">
        <div className="animate-pulse">
          <div className="h-6 w-40 rounded bg-gray-200" />
          <div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 rounded bg-gray-100" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  const pdf = stats?.pdf;
  const citations = stats?.citations;
  const total = stats?.total ?? 1;

  const pdfPercent = total > 0 ? Math.round(((pdf?.withPdf ?? 0) / total) * 100) : 0;

  const statsItems = [
    {
      label: 'PDF 보유',
      value: pdf?.withPdf ?? 0,
      subValue: `${pdfPercent}%`,
      icon: FileText,
      color: 'text-green-600',
      bgColor: 'bg-green-50',
    },
    {
      label: '총 PDF 용량',
      value: formatFileSize(pdf?.totalSize),
      subValue: `${formatNumber(pdf?.withPdf ?? 0)}개 파일`,
      icon: HardDrive,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
      isText: true,
    },
    {
      label: '총 인용 관계',
      value: citations?.total ?? 0,
      subValue: 'citations + references',
      icon: Quote,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50',
    },
    {
      label: '평균 인용 수',
      value: (citations?.avgPerPaper ?? 0).toFixed(1),
      subValue: '논문당 평균',
      icon: TrendingUp,
      color: 'text-orange-600',
      bgColor: 'bg-orange-50',
      isText: true,
    },
  ];

  return (
    <div className="rounded-lg bg-white p-6 shadow">
      <h2 className="text-lg font-semibold text-gray-900">PDF & 인용 현황</h2>

      {/* Progress bar for PDF */}
      {total > 0 && (
        <div className="mt-4">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">
              PDF 보유율 ({formatNumber(pdf?.withPdf ?? 0)} / {formatNumber(total)})
            </span>
            <span className="font-medium text-gray-900">{pdfPercent}%</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-gray-100">
            <div
              className="h-full bg-green-500 transition-all"
              style={{ width: `${pdfPercent}%` }}
            />
          </div>
        </div>
      )}

      {/* Stats grid */}
      <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {statsItems.map((item) => {
          const Icon = item.icon;
          return (
            <div
              key={item.label}
              className={`rounded-lg p-4 ${item.bgColor}`}
            >
              <div className="flex items-center gap-2">
                <Icon className={`h-4 w-4 ${item.color}`} />
                <span className={`text-sm font-medium ${item.color}`}>
                  {item.label}
                </span>
              </div>
              <div className="mt-2 text-2xl font-bold text-gray-900">
                {item.isText ? item.value : formatNumber(item.value as number)}
              </div>
              <div className="mt-1 text-xs text-gray-500">{item.subValue}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
