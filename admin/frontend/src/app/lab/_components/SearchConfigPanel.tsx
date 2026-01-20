'use client';

import { HelpCircle } from 'lucide-react';
import { Tooltip } from './Tooltip';
import { DataSourceSelector } from './DataSourceSelector';
import { SearchConfig, DataSourceConfig } from '../_lib';
import { SampleEmbedding } from '@/lib/api';

interface SearchConfigPanelProps {
  config: SearchConfig;
  sampleEmbeddings?: SampleEmbedding[];
  label?: string;
  onChange: (updates: Partial<SearchConfig>) => void;
}

export function SearchConfigPanel({
  config,
  sampleEmbeddings,
  label,
  onChange,
}: SearchConfigPanelProps) {
  const handleDataSourceChange = (dataSource: DataSourceConfig) => {
    onChange({ dataSource });
  };

  return (
    <div className="space-y-3">
      {label && (
        <div className="text-sm font-semibold text-gray-800 border-b pb-2">
          {label}
        </div>
      )}

      {/* 데이터 소스 선택 (컴팩트 모드) */}
      <DataSourceSelector
        dataSource={config.dataSource}
        sampleEmbeddings={sampleEmbeddings}
        onDataSourceChange={handleDataSourceChange}
        compact
      />

      <div className="grid grid-cols-2 gap-3">
        {/* Limit */}
        <div>
          <label className="flex items-center gap-1 text-xs font-medium text-gray-600">
            결과 개수
            <Tooltip content="검색할 문서 조각 개수">
              <HelpCircle className="h-3 w-3 cursor-help text-gray-400" />
            </Tooltip>
          </label>
          <input
            type="number"
            value={config.limit}
            onChange={(e) => onChange({ limit: Number(e.target.value) })}
            min={1}
            max={50}
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {/* Alpha */}
        <div>
          <label className="flex items-center gap-1 text-xs font-medium text-gray-600">
            Alpha
            <Tooltip content="0=키워드, 1=벡터">
              <HelpCircle className="h-3 w-3 cursor-help text-gray-400" />
            </Tooltip>
          </label>
          <div className="mt-1 flex items-center gap-2">
            <input
              type="range"
              value={config.alpha}
              onChange={(e) => onChange({ alpha: Number(e.target.value) })}
              min={0}
              max={1}
              step={0.05}
              className="flex-1"
            />
            <span className="text-xs font-mono text-gray-600 w-8">
              {config.alpha.toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {/* 현재 설정 요약 */}
      <div className="text-xs text-gray-500 bg-gray-50 rounded px-2 py-1.5">
        <p>
          limit={config.limit}, alpha={config.alpha.toFixed(2)}
        </p>
        <p className="mt-0.5 truncate">
          {config.dataSource.chunker} + {config.dataSource.embedder}
        </p>
      </div>
    </div>
  );
}
