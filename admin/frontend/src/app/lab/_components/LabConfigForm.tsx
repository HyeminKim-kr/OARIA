'use client';

import {
  Search,
  MessageSquare,
  Zap,
  Loader2,
  CheckCircle2,
  XCircle,
  HelpCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Tooltip } from './Tooltip';
import { TestMode, LabConfig } from '../_lib';

interface LabConfigFormProps {
  mode: TestMode;
  config: LabConfig;
  isLoading: boolean;
  isAvailable: boolean;
  onModeChange: (mode: TestMode) => void;
  onConfigChange: (updates: Partial<LabConfig>) => void;
  onTest: () => void;
}

export function LabConfigForm({
  mode,
  config,
  isLoading,
  isAvailable,
  onModeChange,
  onConfigChange,
  onTest,
}: LabConfigFormProps) {
  return (
    <div className="rounded-lg bg-white p-6 shadow">
      <div className="space-y-4">
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

        {/* Parameters */}
        <div className="flex flex-wrap gap-6">
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
          <div className="min-w-[200px] flex-1">
            <label className="flex items-center gap-1 text-sm font-medium text-gray-700">
              Alpha (하이브리드 가중치): {config.alpha.toFixed(2)}
              <Tooltip content="0=키워드만, 1=벡터만, 0.7권장(의미70%+키워드30%)">
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
            <p className="mt-1 text-xs text-gray-400">
              키워드: 정확한 단어 매칭 | 벡터: 의미적 유사성 검색
            </p>
          </div>
          {mode !== 'compare' ? (
            <div>
              <label className="flex items-center gap-1 text-sm font-medium text-gray-700">
                Reranker
                <Tooltip content="BGE Reranker로 검색 결과를 재정렬. 관련성이 낮은 결과를 필터링합니다.">
                  <HelpCircle className="h-3.5 w-3.5 cursor-help text-gray-400" />
                </Tooltip>
              </label>
              <button
                onClick={() => onConfigChange({ useReranker: !config.useReranker })}
                className={cn(
                  'mt-1 flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors',
                  config.useReranker
                    ? 'bg-green-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                )}
              >
                {config.useReranker ? (
                  <>
                    <CheckCircle2 className="h-4 w-4" />
                    사용
                  </>
                ) : (
                  <>
                    <XCircle className="h-4 w-4" />
                    미사용
                  </>
                )}
              </button>
              <p className="mt-1 text-xs text-gray-400">
                {config.useReranker ? '관련성 재평가 활성화' : '기본 검색만 사용'}
              </p>
            </div>
          ) : (
            <div className="rounded-lg bg-orange-50 px-4 py-3">
              <p className="text-sm font-medium text-orange-800">A/B 비교 모드</p>
              <p className="mt-1 text-xs text-orange-600">
                같은 쿼리로 Reranker ON vs OFF 결과를 나란히 비교합니다.
              </p>
            </div>
          )}
        </div>

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
