'use client';

import { Zap, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SearchTestResult } from '@/lib/api';
import { SCORE_THRESHOLDS, RELEVANCE_STYLES, getRelevanceLevel, CompareResults } from '../_lib';

interface LabCompareResultsProps {
  compareResults: CompareResults;
  isLoading: boolean;
}

export function LabCompareResults({ compareResults, isLoading }: LabCompareResultsProps) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-orange-200 bg-orange-50 p-4">
        <h2 className="flex items-center gap-2 font-medium text-orange-800">
          <Zap className="h-5 w-5" />
          A/B 비교 결과: Reranker ON vs OFF
        </h2>
        <p className="mt-1 text-sm text-orange-600">
          같은 쿼리로 Reranker 적용 여부에 따른 결과 차이를 비교합니다.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Without Reranker */}
        <div className="rounded-lg bg-white shadow">
          <div className="border-b border-gray-200 bg-gray-50 px-4 py-3">
            <div className="flex items-center justify-between">
              <h3 className="flex items-center gap-2 font-medium text-gray-900">
                <XCircle className="h-4 w-4 text-gray-500" />
                Reranker OFF
              </h3>
              {compareResults.withoutReranker && (
                <span className="text-xs text-gray-500">
                  {compareResults.withoutReranker.searchLatencyMs}ms
                </span>
              )}
            </div>
          </div>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
            </div>
          ) : compareResults.withoutReranker ? (
            <div className="max-h-[500px] overflow-y-auto">
              {compareResults.withoutReranker.chunks.slice(0, 5).map((chunk, index) => (
                <div key={index} className="border-b border-gray-100 p-3 last:border-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded bg-blue-100 px-1.5 py-0.5 text-xs font-medium text-blue-700">
                      #{index + 1}
                    </span>
                    <span className="rounded bg-gray-200 px-1.5 py-0.5 text-xs text-gray-600">
                      -
                    </span>
                    <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500">
                      원본: {chunk.score.toFixed(4)}
                    </span>
                  </div>
                  <p className="mt-1 line-clamp-2 text-sm text-gray-700">{chunk.paperTitle}</p>
                  <p className="mt-1 line-clamp-2 text-xs text-gray-500">
                    {chunk.content.substring(0, 150)}...
                  </p>
                </div>
              ))}
            </div>
          ) : null}
        </div>

        {/* With Reranker */}
        <div className="rounded-lg bg-white shadow ring-2 ring-green-500">
          <div className="border-b border-green-200 bg-green-50 px-4 py-3">
            <div className="flex items-center justify-between">
              <h3 className="flex items-center gap-2 font-medium text-green-900">
                <CheckCircle2 className="h-4 w-4 text-green-600" />
                Reranker ON
              </h3>
              {compareResults.withReranker && (
                <span className="text-xs text-green-600">
                  검색: {compareResults.withReranker.searchLatencyMs}ms
                  {compareResults.withReranker.rerankLatencyMs !== undefined && (
                    <> + rerank: {compareResults.withReranker.rerankLatencyMs}ms</>
                  )}
                </span>
              )}
            </div>
          </div>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-green-500" />
            </div>
          ) : compareResults.withReranker ? (
            <div className="max-h-[500px] overflow-y-auto">
              {compareResults.withReranker.chunks.slice(0, 5).map((chunk, index) => {
                const score = chunk.rerankScore ?? chunk.score;
                const relevance = getRelevanceLevel(score);
                const style = RELEVANCE_STYLES[relevance];

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
                      <span className={cn('rounded px-1.5 py-0.5 text-xs', style.bg, style.text)}>
                        rerank: {score.toFixed(4)}
                      </span>
                      {chunk.originalScore !== undefined && (
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
      </div>

      {/* Summary */}
      {compareResults.withReranker && compareResults.withoutReranker && (
        <div className="rounded-lg bg-gray-50 p-4">
          <h3 className="font-medium text-gray-900">비교 요약</h3>
          <div className="mt-2 grid gap-4 sm:grid-cols-3">
            <div>
              <p className="text-xs text-gray-500">검색 시간</p>
              <p className="text-sm">
                <span className="text-gray-500">OFF:</span>{' '}
                <span className="font-medium">
                  {compareResults.withoutReranker.searchLatencyMs}ms
                </span>
                {' → '}
                <span className="text-green-600">ON:</span>{' '}
                <span className="font-medium">
                  {compareResults.withReranker.searchLatencyMs +
                    (compareResults.withReranker.rerankLatencyMs || 0)}
                  ms
                </span>
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">최고 점수</p>
              <p className="text-sm">
                <span className="text-gray-500">OFF:</span>{' '}
                <span className="font-medium">
                  {compareResults.withoutReranker.chunks[0]?.score.toFixed(4) || '-'}
                </span>
                {' → '}
                <span className="text-green-600">ON:</span>{' '}
                <span className="font-medium">
                  {(
                    compareResults.withReranker.chunks[0]?.rerankScore ??
                    compareResults.withReranker.chunks[0]?.score
                  )?.toFixed(4) || '-'}
                </span>
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">관련성 높은 결과 (0.3+)</p>
              <p className="text-sm">
                <span className="text-gray-500">OFF:</span>{' '}
                <span className="font-medium">-</span>
                {' → '}
                <span className="text-green-600">ON:</span>{' '}
                <span className="font-medium">
                  {
                    compareResults.withReranker.chunks.filter(
                      (c) => (c.rerankScore ?? c.score) >= SCORE_THRESHOLDS.LOW
                    ).length
                  }
                  /{compareResults.withReranker.chunks.length}
                </span>
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
