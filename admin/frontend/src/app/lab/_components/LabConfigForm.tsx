'use client';

import {
  Search,
  MessageSquare,
  Zap,
  Loader2,
  HelpCircle,
  ChevronDown,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Tooltip } from './Tooltip';
import { SearchConfigPanel } from './SearchConfigPanel';
import { TestMode, LabConfig, SearchConfig } from '../_lib';
import { StrategiesResponse, SampleEmbedding } from '@/lib/api';

interface LabConfigFormProps {
  mode: TestMode;
  config: LabConfig;
  isLoading: boolean;
  isAvailable: boolean;
  strategies?: StrategiesResponse;
  sampleEmbeddings?: SampleEmbedding[];
  onModeChange: (mode: TestMode) => void;
  onConfigChange: (updates: Partial<LabConfig>) => void;
  onConfigAChange: (updates: Partial<SearchConfig>) => void;
  onConfigBChange: (updates: Partial<SearchConfig>) => void;
  onTest: () => void;
}

export function LabConfigForm({
  mode,
  config,
  isLoading,
  isAvailable,
  strategies,
  sampleEmbeddings,
  onModeChange,
  onConfigChange,
  onConfigAChange,
  onConfigBChange,
  onTest,
}: LabConfigFormProps) {
  const rerankerOptions = strategies?.rerankers ?? ['bge', 'none'];

  return (
    <div className="rounded-lg bg-white p-6 shadow">
      <div className="space-y-5">
        {/* Mode Toggle */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => onModeChange('search')}
            className={cn(
              'flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors',
              mode === 'search'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            )}
          >
            <Search className="h-4 w-4" />
            검색 테스트
          </button>
          <button
            onClick={() => onModeChange('generate')}
            className={cn(
              'flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors',
              mode === 'generate'
                ? 'bg-purple-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            )}
          >
            <MessageSquare className="h-4 w-4" />
            답변 생성 테스트
          </button>
          <button
            onClick={() => onModeChange('compare')}
            className={cn(
              'flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors',
              mode === 'compare'
                ? 'bg-orange-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            )}
          >
            <Zap className="h-4 w-4" />
            A/B 비교
          </button>
        </div>

        {/* Query Input */}
        <div>
          <label className="block text-sm font-medium text-gray-700">질문 / 쿼리</label>
          <textarea
            value={config.query}
            onChange={(e) => onConfigChange({ query: e.target.value })}
            placeholder="테스트할 질문을 입력하세요..."
            rows={3}
            className="mt-1 w-full rounded-md border border-gray-300 p-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {/* Single Mode Config (search/generate) */}
        {mode !== 'compare' && (
          <div className="rounded-lg border border-gray-200 p-4">
            <h3 className="text-sm font-medium text-gray-700 mb-3">검색 파라미터</h3>
            <div className="flex flex-wrap gap-6">
              {/* Limit */}
              <div>
                <label className="flex items-center gap-1 text-sm font-medium text-gray-700">
                  결과 개수 (limit)
                  <Tooltip content="검색할 문서 조각 개수. 많으면 정확도↑ 속도↓">
                    <HelpCircle className="h-3.5 w-3.5 cursor-help text-gray-400" />
                  </Tooltip>
                </label>
                <input
                  type="number"
                  value={config.limit}
                  onChange={(e) => onConfigChange({ limit: Number(e.target.value) })}
                  min={1}
                  max={50}
                  className="mt-1 w-24 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              {/* Alpha */}
              <div className="min-w-[200px] flex-1">
                <label className="flex items-center gap-1 text-sm font-medium text-gray-700">
                  Alpha: {config.alpha.toFixed(2)}
                  <Tooltip content="0=키워드만, 1=벡터만, 0.7권장">
                    <HelpCircle className="h-3.5 w-3.5 cursor-help text-gray-400" />
                  </Tooltip>
                </label>
                <div className="mt-1 flex items-center gap-3">
                  <span className="text-xs text-gray-500">키워드</span>
                  <input
                    type="range"
                    value={config.alpha}
                    onChange={(e) => onConfigChange({ alpha: Number(e.target.value) })}
                    min={0}
                    max={1}
                    step={0.05}
                    className="flex-1"
                  />
                  <span className="text-xs text-gray-500">벡터</span>
                </div>
              </div>

              {/* Reranker */}
              <div>
                <label className="flex items-center gap-1 text-sm font-medium text-gray-700">
                  Reranker
                  <Tooltip content="검색 결과 재정렬 모델">
                    <HelpCircle className="h-3.5 w-3.5 cursor-help text-gray-400" />
                  </Tooltip>
                </label>
                <div className="relative mt-1">
                  <select
                    value={config.useReranker ? config.reranker : 'none'}
                    onChange={(e) => {
                      const value = e.target.value;
                      if (value === 'none') {
                        onConfigChange({ useReranker: false });
                      } else {
                        onConfigChange({ useReranker: true, reranker: value });
                      }
                    }}
                    className="appearance-none rounded-md border border-gray-300 bg-white px-3 py-2 pr-8 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
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
          </div>
        )}

        {/* A/B Comparison Mode */}
        {mode === 'compare' && (
          <div className="grid grid-cols-2 gap-4">
            {/* Config A */}
            <div className="rounded-lg border-2 border-blue-200 bg-blue-50/50 p-4">
              <SearchConfigPanel
                config={config.configA}
                rerankerOptions={rerankerOptions}
                sampleEmbeddings={sampleEmbeddings}
                label="설정 A"
                compact
                onChange={onConfigAChange}
              />
            </div>

            {/* Config B */}
            <div className="rounded-lg border-2 border-green-200 bg-green-50/50 p-4">
              <SearchConfigPanel
                config={config.configB}
                rerankerOptions={rerankerOptions}
                sampleEmbeddings={sampleEmbeddings}
                label="설정 B"
                compact
                onChange={onConfigBChange}
              />
            </div>
          </div>
        )}

        {/* Test Button */}
        <button
          onClick={onTest}
          disabled={!config.query.trim() || isLoading || !isAvailable}
          className={cn(
            'flex w-full items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-medium text-white transition-colors',
            mode === 'search'
              ? 'bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300'
              : mode === 'generate'
                ? 'bg-purple-600 hover:bg-purple-700 disabled:bg-purple-300'
                : 'bg-orange-600 hover:bg-orange-700 disabled:bg-orange-300'
          )}
        >
          {isLoading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              {mode === 'compare' ? 'A/B 비교 중...' : '테스트 중...'}
            </>
          ) : (
            <>
              <Zap className="h-4 w-4" />
              {mode === 'search'
                ? '검색 테스트 실행'
                : mode === 'generate'
                  ? '답변 생성 테스트 실행'
                  : 'A/B 비교 테스트 실행'}
            </>
          )}
        </button>
      </div>
    </div>
  );
}
