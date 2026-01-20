'use client';

import { useState } from 'react';
import {
  Clock,
  Zap,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  ThumbsUp,
  ThumbsDown,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { SearchTestResult } from '@/lib/api';
import { Tooltip } from './Tooltip';
import { SCORE_THRESHOLDS, RELEVANCE_STYLES, getRelevanceLevel, FeedbackState } from '../_lib';

interface LabSearchResultsProps {
  result: SearchTestResult;
  feedbackSubmitted: FeedbackState;
  feedbackPending: boolean;
  onFeedback: (type: 'search', rating: 'good' | 'bad') => void;
}

export function LabSearchResults({
  result,
  feedbackSubmitted,
  feedbackPending,
  onFeedback,
}: LabSearchResultsProps) {
  const [expandedChunks, setExpandedChunks] = useState<Set<number>>(new Set());

  const toggleChunkExpand = (index: number) => {
    const newExpanded = new Set(expandedChunks);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedChunks(newExpanded);
  };

  const hasReranker = result.parameters.useReranker;
  const isOffDomain = result.classification && !result.classification.isOncology;

  const relevantChunks = hasReranker
    ? result.chunks.filter((c) => (c.rerankScore ?? c.score) >= SCORE_THRESHOLDS.LOW)
    : result.chunks;
  const lowRelevanceChunks = hasReranker
    ? result.chunks.filter((c) => (c.rerankScore ?? c.score) < SCORE_THRESHOLDS.LOW)
    : [];
  const allLowRelevance = hasReranker && relevantChunks.length === 0;
  const topScore = result.chunks[0]
    ? result.chunks[0].rerankScore ?? result.chunks[0].score
    : 0;

  return (
    <div className="space-y-4">
      {/* Off-domain Classification Warning */}
      {isOffDomain && result.classification && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 flex-shrink-0 text-amber-600" />
            <div>
              <h3 className="font-medium text-amber-800">
                Off-domain 쿼리 ({result.classification.category}, {(result.classification.confidence * 100).toFixed(0)}%)
              </h3>
              <p className="mt-1 text-sm text-amber-700">
                {result.classification.warning || '이 질문은 종양학(Oncology) 분야가 아닙니다. OARIA는 종양학 전문 AI입니다.'}
              </p>
              <p className="mt-2 text-xs text-amber-600">
                분류 소요시간: {result.classification.classifierLatencyMs}ms
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 관련 결과 없음 경고 */}
      {allLowRelevance && (
        <div className="rounded-lg border border-orange-200 bg-orange-50 p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 flex-shrink-0 text-orange-500" />
            <div>
              <h3 className="font-medium text-orange-800">관련성 높은 결과 없음</h3>
              <p className="mt-1 text-sm text-orange-700">
                모든 검색 결과의 Rerank Score가 {SCORE_THRESHOLDS.LOW} 미만입니다. 질문과
                관련된 논문이 DB에 없거나, 다른 검색어를 시도해보세요.
              </p>
              <p className="mt-2 text-xs text-orange-600">
                최고 점수: {topScore.toFixed(4)} (기준: {SCORE_THRESHOLDS.LOW} 이상)
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="rounded-lg bg-white shadow">
        <div className="border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="flex items-center gap-2 font-medium text-gray-900">
                검색 결과
                {hasReranker && (
                  <span className="rounded bg-green-100 px-2 py-0.5 text-xs text-green-700">
                    Reranker 적용됨
                  </span>
                )}
                {hasReranker && !allLowRelevance && lowRelevanceChunks.length > 0 && (
                  <span className="rounded bg-orange-100 px-2 py-0.5 text-xs text-orange-700">
                    {lowRelevanceChunks.length}개 낮은 관련성
                  </span>
                )}
                {result.classification && (
                  <span
                    className={cn(
                      'rounded px-2 py-0.5 text-xs',
                      result.classification.isOncology
                        ? 'bg-blue-100 text-blue-700'
                        : 'bg-amber-100 text-amber-700'
                    )}
                  >
                    {result.classification.isOncology ? 'Oncology' : 'Off-domain'}
                  </span>
                )}
              </h2>
              <p className="mt-0.5 text-xs text-gray-500">
                {hasReranker
                  ? `Rerank Score 기준: 0.7↑ 높음, 0.5↑ 중간, 0.3↑ 낮음, 0.3↓ 관련없음`
                  : 'Score가 높을수록 관련성이 높습니다.'}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500">
              <Tooltip content="검색에 걸린 시간 (낮을수록 좋음)">
                <span className="flex cursor-help items-center gap-1">
                  <Clock className="h-4 w-4" />
                  검색 {result.searchLatencyMs}ms
                </span>
              </Tooltip>
              {result.rerankLatencyMs !== undefined && (
                <Tooltip content="Reranker가 결과를 재정렬하는데 걸린 시간">
                  <span className="flex cursor-help items-center gap-1 text-green-600">
                    <Zap className="h-4 w-4" />
                    Rerank {result.rerankLatencyMs}ms
                  </span>
                </Tooltip>
              )}
              <Tooltip content="검색된 문서 조각 개수">
                <span className="cursor-help">{result.totalChunks}개 청크</span>
              </Tooltip>
            </div>
          </div>
        </div>
        <div className="divide-y divide-gray-200">
          {result.chunks.map((chunk, index) => {
            const score = chunk.rerankScore ?? chunk.score;
            const relevance = hasReranker ? getRelevanceLevel(score) : null;
            const isLowRelevance = relevance === 'low' || relevance === 'irrelevant';
            const style = relevance ? RELEVANCE_STYLES[relevance] : null;

            return (
              <div
                key={index}
                className={cn(
                  'p-4 transition-opacity',
                  isLowRelevance && 'bg-gray-50 opacity-60'
                )}
              >
                <div
                  className="flex cursor-pointer items-start justify-between gap-4"
                  onClick={() => toggleChunkExpand(index)}
                >
                  <div className="flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                        #{index + 1}
                      </span>
                      {chunk.rerankScore != null ? (
                        <>
                          <Tooltip content={`Reranker 관련성: ${style?.label || '알수없음'}`}>
                            <span
                              className={cn(
                                'cursor-help rounded px-2 py-0.5 text-xs',
                                style?.bg,
                                style?.text
                              )}
                            >
                              rerank: {chunk.rerankScore.toFixed(4)}
                            </span>
                          </Tooltip>
                          {chunk.originalScore != null && (
                            <Tooltip content="원본 벡터 검색 점수">
                              <span className="cursor-help rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
                                원본: {chunk.originalScore.toFixed(4)}
                              </span>
                            </Tooltip>
                          )}
                          {isLowRelevance && (
                            <Tooltip content="관련성이 낮아 실제 서비스에서는 필터링될 수 있습니다">
                              <span className="flex cursor-help items-center gap-1 text-xs text-orange-600">
                                <AlertTriangle className="h-3 w-3" />
                                {style?.label}
                              </span>
                            </Tooltip>
                          )}
                        </>
                      ) : (
                        <Tooltip content="유사도 점수 (0~1, 높을수록 관련성 높음)">
                          <span className="cursor-help rounded bg-green-100 px-2 py-0.5 text-xs text-green-700">
                            score: {chunk.score?.toFixed(4) ?? '-'}
                          </span>
                        </Tooltip>
                      )}
                      <span
                        className={cn(
                          'text-sm font-medium',
                          isLowRelevance ? 'text-gray-500' : 'text-gray-900'
                        )}
                      >
                        {chunk.paperTitle}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-gray-500">
                      섹션: {chunk.sectionName} | 청크 #{chunk.chunkIndex}
                    </div>
                  </div>
                  {expandedChunks.has(index) ? (
                    <ChevronUp className="h-5 w-5 text-gray-400" />
                  ) : (
                    <ChevronDown className="h-5 w-5 text-gray-400" />
                  )}
                </div>
                {expandedChunks.has(index) && (
                  <div className="mt-3 rounded bg-gray-50 p-3 text-sm text-gray-700">
                    <pre className="whitespace-pre-wrap font-sans">{chunk.content}</pre>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Feedback Buttons */}
        <div className="border-t border-gray-200 px-6 py-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">검색 결과 품질:</span>
            {feedbackSubmitted.search ? (
              <span
                className={cn(
                  'flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm',
                  feedbackSubmitted.search === 'good'
                    ? 'bg-green-100 text-green-700'
                    : 'bg-red-100 text-red-700'
                )}
              >
                {feedbackSubmitted.search === 'good' ? (
                  <>
                    <ThumbsUp className="h-4 w-4" />
                    피드백 완료: 좋음
                  </>
                ) : (
                  <>
                    <ThumbsDown className="h-4 w-4" />
                    피드백 완료: 나쁨
                  </>
                )}
              </span>
            ) : (
              <>
                <button
                  onClick={() => onFeedback('search', 'good')}
                  disabled={feedbackPending}
                  className="flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:border-green-300 hover:bg-green-50 hover:text-green-700 disabled:opacity-50"
                >
                  <ThumbsUp className="h-4 w-4" />
                  좋음
                </button>
                <button
                  onClick={() => onFeedback('search', 'bad')}
                  disabled={feedbackPending}
                  className="flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:border-red-300 hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
                >
                  <ThumbsDown className="h-4 w-4" />
                  나쁨
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
