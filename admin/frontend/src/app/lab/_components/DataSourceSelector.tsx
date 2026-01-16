'use client';

import { Database, FlaskConical, HelpCircle, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Tooltip } from './Tooltip';
import { DataSourceConfig } from '../_lib';
import { SampleEmbedding } from '@/lib/api';
import { DEFAULT_PRODUCTION_DATA_SOURCE } from '../_lib/constants';

interface DataSourceSelectorProps {
  dataSource: DataSourceConfig;
  sampleEmbeddings?: SampleEmbedding[];
  onDataSourceChange: (config: DataSourceConfig) => void;
  compact?: boolean;  // A/B 비교용 컴팩트 모드
}

export function DataSourceSelector({
  dataSource,
  sampleEmbeddings,
  onDataSourceChange,
  compact = false,
}: DataSourceSelectorProps) {
  const completedEmbeddings = sampleEmbeddings?.filter((e) => e.status === 'completed') ?? [];
  const hasSampleData = completedEmbeddings.length > 0;

  const handleProductionSelect = () => {
    onDataSourceChange({ ...DEFAULT_PRODUCTION_DATA_SOURCE });
  };

  const handleSampleSelect = (embedding: SampleEmbedding) => {
    onDataSourceChange({
      type: 'sample',
      collectionName: embedding.collectionName,
      chunker: embedding.chunker,
      embedder: embedding.embedder,
      queryName: embedding.searchQuery?.name,
    });
  };

  const isSelected = (type: 'production' | 'sample', collectionName?: string) => {
    if (type === 'production') return dataSource.type === 'production';
    return dataSource.type === 'sample' && dataSource.collectionName === collectionName;
  };

  if (compact) {
    // A/B 비교용 컴팩트 모드
    return (
      <div className="space-y-2">
        <div className="text-xs font-medium text-gray-500 mb-2">데이터 소스</div>

        {/* Production */}
        <label
          className={cn(
            'flex items-center gap-2 rounded-md border p-2 cursor-pointer transition-colors',
            isSelected('production')
              ? 'border-green-500 bg-green-50'
              : 'border-gray-200 hover:border-gray-300'
          )}
        >
          <input
            type="radio"
            name="dataSource"
            checked={isSelected('production')}
            onChange={handleProductionSelect}
            className="sr-only"
          />
          <div
            className={cn(
              'flex h-4 w-4 items-center justify-center rounded-full border',
              isSelected('production')
                ? 'border-green-500 bg-green-500'
                : 'border-gray-300'
            )}
          >
            {isSelected('production') && <Check className="h-3 w-3 text-white" />}
          </div>
          <Database className="h-4 w-4 text-green-600" />
          <span className="text-sm font-medium">프로덕션</span>
        </label>

        {/* Sample Embeddings */}
        {completedEmbeddings.map((embedding) => (
          <label
            key={embedding.id}
            className={cn(
              'flex items-start gap-2 rounded-md border p-2 cursor-pointer transition-colors',
              isSelected('sample', embedding.collectionName)
                ? 'border-purple-500 bg-purple-50'
                : 'border-gray-200 hover:border-gray-300'
            )}
          >
            <input
              type="radio"
              name="dataSource"
              checked={isSelected('sample', embedding.collectionName)}
              onChange={() => handleSampleSelect(embedding)}
              className="sr-only"
            />
            <div
              className={cn(
                'flex h-4 w-4 items-center justify-center rounded-full border mt-0.5',
                isSelected('sample', embedding.collectionName)
                  ? 'border-purple-500 bg-purple-500'
                  : 'border-gray-300'
              )}
            >
              {isSelected('sample', embedding.collectionName) && (
                <Check className="h-3 w-3 text-white" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1">
                <FlaskConical className="h-3.5 w-3.5 text-purple-600" />
                <span className="text-sm font-medium truncate">
                  {embedding.searchQuery?.name || '샘플'}
                </span>
              </div>
              <p className="text-xs text-gray-500 truncate mt-0.5">
                {embedding.chunker} + {embedding.embedder}
              </p>
            </div>
          </label>
        ))}

        {!hasSampleData && (
          <p className="text-xs text-gray-400">샘플 임베딩이 없습니다</p>
        )}
      </div>
    );
  }

  // 기본 모드 (전체 뷰)
  return (
    <div className="rounded-lg bg-white p-4 shadow">
      <div className="flex items-center gap-2 mb-3">
        <Database className="h-4 w-4 text-gray-500" />
        <h3 className="text-sm font-medium text-gray-700">데이터 소스</h3>
        <Tooltip content="프로덕션 데이터 또는 샘플 임베딩을 선택합니다. 각 데이터 소스는 특정 Chunker와 Embedder 조합으로 생성됩니다.">
          <HelpCircle className="h-3.5 w-3.5 cursor-help text-gray-400" />
        </Tooltip>
      </div>

      <div className="space-y-2">
        {/* Production Option */}
        <label
          className={cn(
            'flex items-center gap-3 rounded-lg border-2 p-3 cursor-pointer transition-colors',
            isSelected('production')
              ? 'border-green-500 bg-green-50'
              : 'border-gray-200 hover:border-gray-300'
          )}
        >
          <input
            type="radio"
            name="dataSource"
            checked={isSelected('production')}
            onChange={handleProductionSelect}
            className="sr-only"
          />
          <div
            className={cn(
              'flex h-5 w-5 items-center justify-center rounded-full border-2',
              isSelected('production')
                ? 'border-green-500 bg-green-500'
                : 'border-gray-300'
            )}
          >
            {isSelected('production') && <Check className="h-3 w-3 text-white" />}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-green-600" />
              <span className="text-sm font-medium text-gray-900">프로덕션</span>
            </div>
            <p className="mt-1 text-xs text-gray-500">
              {DEFAULT_PRODUCTION_DATA_SOURCE.chunker} + {DEFAULT_PRODUCTION_DATA_SOURCE.embedder}
            </p>
          </div>
        </label>

        {/* Sample Embeddings */}
        {completedEmbeddings.map((embedding) => (
          <label
            key={embedding.id}
            className={cn(
              'flex items-center gap-3 rounded-lg border-2 p-3 cursor-pointer transition-colors',
              isSelected('sample', embedding.collectionName)
                ? 'border-purple-500 bg-purple-50'
                : 'border-gray-200 hover:border-gray-300'
            )}
          >
            <input
              type="radio"
              name="dataSource"
              checked={isSelected('sample', embedding.collectionName)}
              onChange={() => handleSampleSelect(embedding)}
              className="sr-only"
            />
            <div
              className={cn(
                'flex h-5 w-5 items-center justify-center rounded-full border-2',
                isSelected('sample', embedding.collectionName)
                  ? 'border-purple-500 bg-purple-500'
                  : 'border-gray-300'
              )}
            >
              {isSelected('sample', embedding.collectionName) && (
                <Check className="h-3 w-3 text-white" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <FlaskConical className="h-4 w-4 text-purple-600" />
                <span className="text-sm font-medium text-gray-900">
                  샘플: {embedding.searchQuery?.name || embedding.collectionName}
                </span>
              </div>
              <p className="mt-1 text-xs text-gray-500">
                {embedding.chunker} + {embedding.embedder}
              </p>
              <p className="text-xs text-gray-400">
                {embedding.paperCount}개 논문, {embedding.chunkCount}개 청크
              </p>
            </div>
          </label>
        ))}

        {/* No Sample Data Message */}
        {!hasSampleData && (
          <div className="rounded-lg border border-dashed border-gray-300 p-3 text-center">
            <p className="text-sm text-gray-500">
              아직 생성된 샘플 임베딩이 없습니다
            </p>
            <p className="mt-1 text-xs text-gray-400">
              임베딩 관리에서 새로운 Chunker/Embedder 조합을 테스트해보세요
            </p>
          </div>
        )}
      </div>

      {/* Current Selection Summary */}
      <div className="mt-3 rounded-md bg-gray-50 p-2">
        <p className="text-xs text-gray-500">
          선택된 전략:
          <span className="ml-1 font-medium text-gray-700">
            {dataSource.chunker} + {dataSource.embedder}
          </span>
        </p>
      </div>
    </div>
  );
}
