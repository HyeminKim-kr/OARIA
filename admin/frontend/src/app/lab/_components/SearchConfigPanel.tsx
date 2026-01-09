'use client';

import { HelpCircle, ChevronDown, Database } from 'lucide-react';
import { Tooltip } from './Tooltip';
import { SearchConfig } from '../_lib';
import { SampleEmbedding } from '@/lib/api';

interface SearchConfigPanelProps {
  config: SearchConfig;
  rerankerOptions: string[];
  sampleEmbeddings?: SampleEmbedding[];
  label?: string;
  compact?: boolean;
  onChange: (updates: Partial<SearchConfig>) => void;
}

export function SearchConfigPanel({
  config,
  rerankerOptions,
  sampleEmbeddings,
  label,
  compact = false,
  onChange,
}: SearchConfigPanelProps) {
  const hasReranker = config.reranker !== null;
  const hasCollections = sampleEmbeddings && sampleEmbeddings.length > 0;

  // 컬렉션 이름에서 표시명 추출 (파이프라인 키 또는 축약)
  const getCollectionDisplayName = (collectionName: string) => {
    // MedicalChunks_sample_semantic_section_700t_openai_3small -> semantic_700t_openai
    const match = collectionName.match(/sample_([^_]+)_([^_]+)_(\d+)t_([^_]+)/);
    if (match) {
      return `${match[1]}_${match[3]}t_${match[4]}`;
    }
    return collectionName.length > 30 ? collectionName.slice(0, 30) + '...' : collectionName;
  };

  return (
    <div className={compact ? 'space-y-3' : 'space-y-4'}>
      {label && (
        <div className="text-sm font-semibold text-gray-800 border-b pb-2">
          {label}
        </div>
      )}

      {/* 데이터 소스 선택 (샘플 임베딩 있을 때만 표시) */}
      {hasCollections && (
        <div>
          <label className="flex items-center gap-1 text-xs font-medium text-gray-600">
            <Database className="h-3 w-3" />
            데이터 소스
            <Tooltip content="프로덕션 또는 샘플 임베딩 선택">
              <HelpCircle className="h-3 w-3 cursor-help text-gray-400" />
            </Tooltip>
          </label>
          <div className="relative mt-1">
            <select
              value={config.collectionName ?? 'production'}
              onChange={(e) => {
                const value = e.target.value;
                onChange({ collectionName: value === 'production' ? null : value });
              }}
              className="w-full appearance-none rounded-md border border-gray-300 bg-white px-2 py-1.5 pr-8 text-xs focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="production">프로덕션</option>
              {sampleEmbeddings.map((embedding) => (
                <option key={embedding.id} value={embedding.collectionName}>
                  {getCollectionDisplayName(embedding.collectionName)}
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          </div>
        </div>
      )}

      <div className={compact ? 'grid grid-cols-2 gap-3' : 'flex flex-wrap gap-4'}>
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

        {/* Reranker */}
        <div className={compact ? 'col-span-2' : ''}>
          <label className="flex items-center gap-1 text-xs font-medium text-gray-600">
            Reranker
            <Tooltip content="검색 결과 재정렬 모델">
              <HelpCircle className="h-3 w-3 cursor-help text-gray-400" />
            </Tooltip>
          </label>
          <div className="relative mt-1">
            <select
              value={config.reranker ?? 'none'}
              onChange={(e) => {
                const value = e.target.value;
                onChange({ reranker: value === 'none' ? null : value });
              }}
              className="w-full appearance-none rounded-md border border-gray-300 bg-white px-2 py-1.5 pr-8 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="none">미사용</option>
              {rerankerOptions.filter(r => r !== 'none').map((reranker) => (
                <option key={reranker} value={reranker}>
                  {reranker.toUpperCase()}
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          </div>
        </div>
      </div>

      {/* 현재 설정 요약 */}
      <div className="text-xs text-gray-500 bg-gray-50 rounded px-2 py-1.5">
        limit={config.limit}, alpha={config.alpha.toFixed(2)}, reranker={config.reranker ?? 'none'}
        {config.collectionName && `, collection=${getCollectionDisplayName(config.collectionName)}`}
      </div>
    </div>
  );
}
