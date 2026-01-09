'use client';

import { Database, FlaskConical, ChevronDown, HelpCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Tooltip } from './Tooltip';
import { DataSource } from '../_lib';
import { SampleEmbedding } from '@/lib/api';

interface DataSourceSelectorProps {
  dataSource: DataSource;
  collectionName: string | null;
  sampleEmbeddings?: SampleEmbedding[];
  onDataSourceChange: (dataSource: DataSource, collectionName: string | null) => void;
}

export function DataSourceSelector({
  dataSource,
  collectionName,
  sampleEmbeddings,
  onDataSourceChange,
}: DataSourceSelectorProps) {
  const completedEmbeddings = sampleEmbeddings?.filter((e) => e.status === 'completed') ?? [];
  const hasSampleData = completedEmbeddings.length > 0;

  return (
    <div className="rounded-lg bg-white p-4 shadow">
      <div className="flex items-center gap-2 mb-3">
        <Database className="h-4 w-4 text-gray-500" />
        <h3 className="text-sm font-medium text-gray-700">데이터 소스</h3>
        <Tooltip content="프로덕션 데이터 또는 샘플 임베딩을 선택하여 테스트할 수 있습니다">
          <HelpCircle className="h-3.5 w-3.5 cursor-help text-gray-400" />
        </Tooltip>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        {/* Data Source Toggle */}
        <div className="flex gap-2">
          <button
            onClick={() => onDataSourceChange('production', null)}
            className={cn(
              'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              dataSource === 'production'
                ? 'bg-green-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            )}
          >
            <Database className="h-4 w-4" />
            프로덕션
          </button>
          <button
            onClick={() => {
              if (hasSampleData) {
                onDataSourceChange('sample', completedEmbeddings[0]?.collectionName ?? null);
              }
            }}
            disabled={!hasSampleData}
            className={cn(
              'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              dataSource === 'sample'
                ? 'bg-purple-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
              !hasSampleData && 'cursor-not-allowed opacity-50'
            )}
          >
            <FlaskConical className="h-4 w-4" />
            샘플 임베딩
          </button>
        </div>

        {/* Sample Embedding Selection */}
        {dataSource === 'sample' && hasSampleData && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">컬렉션:</span>
            <div className="relative">
              <select
                value={collectionName ?? ''}
                onChange={(e) => onDataSourceChange('sample', e.target.value)}
                className="appearance-none rounded-md border border-gray-300 bg-white px-3 py-2 pr-8 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
              >
                {completedEmbeddings.map((embedding) => (
                  <option key={embedding.id} value={embedding.collectionName}>
                    {embedding.chunker} + {embedding.embedder}
                    {embedding.searchQuery ? ` (${embedding.searchQuery.name})` : ''}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            </div>
          </div>
        )}

        {/* No Sample Data Message */}
        {dataSource === 'production' && !hasSampleData && (
          <p className="text-xs text-gray-400">
            샘플 임베딩을 생성하면 다른 청킹/임베딩 전략을 테스트할 수 있습니다
          </p>
        )}
      </div>

      {/* Current Selection Info */}
      {dataSource === 'sample' && collectionName && (
        <div className="mt-3 rounded-md bg-purple-50 p-2 text-sm">
          <div className="flex items-center gap-2 text-purple-700">
            <FlaskConical className="h-4 w-4" />
            <span className="font-medium">샘플 데이터 사용 중</span>
          </div>
          <p className="mt-1 text-xs text-purple-600 font-mono">{collectionName}</p>
        </div>
      )}
    </div>
  );
}
