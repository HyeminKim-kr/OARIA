'use client';

import { Zap, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SearchTestResult } from '@/lib/api';
import { SCORE_THRESHOLDS, RELEVANCE_STYLES, getRelevanceLevel, CompareResults } from '../_lib';

interface LabCompareResultsProps {
  compareResults: CompareResults;
  isLoading: boolean;
}

function ResultPanel({
  result,
  label,
  colorClass,
  isLoading,
}: {
  result?: SearchTestResult;
  label: string;
  colorClass: {
    border: string;
    bg: string;
    headerBg: string;
    headerText: string;
  };
  isLoading: boolean;
}) {
  const hasReranker = result?.parameters?.useReranker;
  const rerankerName = result?.parameters?.rerankerModel || result?.parameters?.reranker;

  return (
    <div className={cn('rounded-lg bg-white shadow ring-2', colorClass.border)}>
      <div className={cn('border-b px-4 py-3', colorClass.headerBg)}>
        <div className="flex items-center justify-between">
          <h3 className={cn('font-medium', colorClass.headerText)}>{label}</h3>
          {result && (
            <span className="text-xs text-gray-500">
              {result.searchLatencyMs}ms
              {result.rerankLatencyMs !== undefined && (
                <> + rerank: {result.rerankLatencyMs}ms</>
              )}
            </span>
          )}
        </div>
        {result && (
          <div className="mt-1 flex flex-wrap gap-2 text-xs text-gray-500">
            <span>limit={result.parameters?.limit}</span>
            <span>alpha={result.parameters?.alpha?.toFixed(2)}</span>
            <span>reranker={hasReranker ? rerankerName : 'none'}</span>
          </div>
        )}
      </div>
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
        </div>
      ) : result ? (
        <div className="max-h-[500px] overflow-y-auto">
          {result.chunks.slice(0, 5).map((chunk, index) => {
            const score = chunk.rerankScore ?? chunk.score;
            const relevance = hasReranker ? getRelevanceLevel(score) : null;
            const style = relevance ? RELEVANCE_STYLES[relevance] : null;

            return (
              <div
                key={index}
                className={cn(
                  'border-b border-gray-100 p-3 last:border-0',
                  relevance === 'irrelevant' && 'bg-gray-50 opacity-50'
                )}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded bg-blue-100 px-1.5 py-0.5 text-xs font-medium text-blue-700">
                    #{index + 1}
                  </span>
                  {hasReranker && style ? (
                    <span className={cn('rounded px-1.5 py-0.5 text-xs', style.bg, style.text)}>
                      rerank: {score?.toFixed(4) ?? '-'}
                    </span>
                  ) : (
                    <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500">
                      score: {score?.toFixed(4) ?? '-'}
                    </span>
                  )}
                  {chunk.originalScore != null && (
                    <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500">
                      원본: {chunk.originalScore.toFixed(4)}
                    </span>
                  )}
                </div>
                <p className="mt-1 line-clamp-2 text-sm text-gray-700">{chunk.paperTitle}</p>
                <p className="mt-1 line-clamp-2 text-xs text-gray-500">
                  {chunk.content.substring(0, 150)}...
                </p>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

export function LabCompareResults({ compareResults, isLoading }: LabCompareResultsProps) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-orange-200 bg-orange-50 p-4">
        <h2 className="flex items-center gap-2 font-medium text-orange-800">
          <Zap className="h-5 w-5" />
          A/B 비교 결과
        </h2>
        <p className="mt-1 text-sm text-orange-600">
          서로 다른 설정의 검색 결과를 나란히 비교합니다. 결과를 직접 확인하고 어떤 설정이 더 나은지 판단하세요.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Config A */}
        <ResultPanel
          result={compareResults.configA}
          label="설정 A"
          colorClass={{
            border: 'ring-blue-500',
            bg: 'bg-blue-50',
            headerBg: 'border-blue-200 bg-blue-50',
            headerText: 'text-blue-900',
          }}
          isLoading={isLoading}
        />

        {/* Config B */}
        <ResultPanel
          result={compareResults.configB}
          label="설정 B"
          colorClass={{
            border: 'ring-green-500',
            bg: 'bg-green-50',
            headerBg: 'border-green-200 bg-green-50',
            headerText: 'text-green-900',
          }}
          isLoading={isLoading}
        />
      </div>

      {/* Summary */}
      {compareResults.configA && compareResults.configB && (
        <div className="rounded-lg bg-gray-50 p-4">
          <h3 className="font-medium text-gray-900">비교 요약</h3>
          <div className="mt-2 grid gap-4 sm:grid-cols-3">
            <div>
              <p className="text-xs text-gray-500">검색 시간</p>
              <p className="text-sm">
                <span className="text-blue-600">A:</span>{' '}
                <span className="font-medium">
                  {compareResults.configA.searchLatencyMs + (compareResults.configA.rerankLatencyMs || 0)}ms
                </span>
                {' vs '}
                <span className="text-green-600">B:</span>{' '}
                <span className="font-medium">
                  {compareResults.configB.searchLatencyMs + (compareResults.configB.rerankLatencyMs || 0)}ms
                </span>
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">최고 점수</p>
              <p className="text-sm">
                <span className="text-blue-600">A:</span>{' '}
                <span className="font-medium">
                  {(compareResults.configA.chunks[0]?.rerankScore ??
                    compareResults.configA.chunks[0]?.score)?.toFixed(4) || '-'}
                </span>
                {' vs '}
                <span className="text-green-600">B:</span>{' '}
                <span className="font-medium">
                  {(compareResults.configB.chunks[0]?.rerankScore ??
                    compareResults.configB.chunks[0]?.score)?.toFixed(4) || '-'}
                </span>
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">결과 개수</p>
              <p className="text-sm">
                <span className="text-blue-600">A:</span>{' '}
                <span className="font-medium">{compareResults.configA.totalChunks}</span>
                {' vs '}
                <span className="text-green-600">B:</span>{' '}
                <span className="font-medium">{compareResults.configB.totalChunks}</span>
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
