'use client';

import { Clock, ThumbsUp, ThumbsDown, HelpCircle, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { GenerateTestResult } from '@/lib/api';
import { Tooltip } from './Tooltip';
import { FeedbackState } from '../_lib';

interface LabGenerateResultsProps {
  result: GenerateTestResult;
  feedbackSubmitted: FeedbackState;
  feedbackPending: boolean;
  onFeedback: (type: 'generate', rating: 'good' | 'bad') => void;
}

export function LabGenerateResults({
  result,
  feedbackSubmitted,
  feedbackPending,
  onFeedback,
}: LabGenerateResultsProps) {
  const isOffDomain = result.classification && !result.classification.isOncology;

  return (
    <div className="space-y-6">
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
                분류 소요시간: {result.classification.classifierLatencyMs}ms | RAG 파이프라인이 스킵되어 비용이 절약되었습니다.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Answer */}
      <div className="rounded-lg bg-white shadow">
        <div className="border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="flex items-center gap-2 font-medium text-gray-900">
                생성된 답변
                {result.useReranker && (
                  <span className="rounded bg-green-100 px-2 py-0.5 text-xs text-green-700">
                    Reranker 적용됨
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
                검색된 문서를 바탕으로 AI가 생성한 답변입니다.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-sm text-gray-500">
              <Tooltip content="전체 소요 시간 (검색 + AI 생성)">
                <span className="flex cursor-help items-center gap-1">
                  <Clock className="h-4 w-4" />총 {result.totalLatencyMs}ms
                </span>
              </Tooltip>
              <Tooltip content="문서 검색에 걸린 시간">
                <span className="cursor-help">검색: {result.searchLatencyMs}ms</span>
              </Tooltip>
              {result.rerankLatencyMs !== undefined && (
                <Tooltip content="Reranker가 결과를 재정렬하는데 걸린 시간">
                  <span className="cursor-help text-green-600">
                    Rerank: {result.rerankLatencyMs}ms
                  </span>
                </Tooltip>
              )}
              <Tooltip content="AI가 답변을 생성하는데 걸린 시간">
                <span className="cursor-help">LLM: {result.llmLatencyMs}ms</span>
              </Tooltip>
              <Tooltip content="사용된 AI 모델">
                <span className="cursor-help rounded bg-purple-100 px-2 py-0.5 text-xs text-purple-700">
                  {result.model}
                </span>
              </Tooltip>
            </div>
          </div>
        </div>
        <div className="p-6">
          <div className="prose max-w-none">
            <p className="whitespace-pre-wrap text-gray-700">{result.answer}</p>
          </div>

          {/* Feedback Buttons */}
          <div className="mt-4 flex items-center gap-2 border-t border-gray-200 pt-4">
            <span className="text-sm text-gray-500">답변 품질:</span>
            {feedbackSubmitted.generate ? (
              <span
                className={cn(
                  'flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm',
                  feedbackSubmitted.generate === 'good'
                    ? 'bg-green-100 text-green-700'
                    : 'bg-red-100 text-red-700'
                )}
              >
                {feedbackSubmitted.generate === 'good' ? (
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
                  onClick={() => onFeedback('generate', 'good')}
                  disabled={feedbackPending}
                  className="flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:border-green-300 hover:bg-green-50 hover:text-green-700 disabled:opacity-50"
                >
                  <ThumbsUp className="h-4 w-4" />
                  좋음
                </button>
                <button
                  onClick={() => onFeedback('generate', 'bad')}
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

      {/* References */}
      <div className="rounded-lg bg-white shadow">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="font-medium text-gray-900">
            참조 문헌 ({result.references.length})
          </h2>
          <p className="mt-0.5 text-xs text-gray-500">
            답변 생성에 사용된 논문 출처입니다. AI가 이 내용들을 참고하여 답변했습니다.
          </p>
        </div>
        <div className="divide-y divide-gray-200">
          {result.references.map((ref, index) => (
            <div key={index} className="p-4">
              <div className="flex items-start gap-2">
                <span className="rounded bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700">
                  [{index + 1}]
                </span>
                <div className="flex-1">
                  <div className="font-medium text-gray-900">{ref.title}</div>
                  <div className="mt-1 text-xs text-gray-500">
                    섹션: {ref.section} | score: {ref.score?.toFixed(4) ?? '-'}
                  </div>
                  <div className="mt-2 rounded bg-gray-50 p-2 text-sm text-gray-600">
                    {ref.content.length > 300
                      ? ref.content.substring(0, 300) + '...'
                      : ref.content}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Token Usage */}
      {result.tokensUsed && (
        <div className="rounded-lg bg-gray-50 px-6 py-4 text-sm text-gray-600">
          <div className="flex items-center gap-1">
            <span className="font-medium">토큰 사용량</span>
            <Tooltip content="LLM API 사용량 - 토큰이 많을수록 비용 증가">
              <HelpCircle className="h-3.5 w-3.5 cursor-help text-gray-400" />
            </Tooltip>
            <span className="ml-1">:</span>
          </div>
          <div className="mt-1 flex items-center gap-4">
            <Tooltip content="질문 + 검색된 문서 내용 (입력)">
              <span className="cursor-help">
                Prompt: {result.tokensUsed.prompt.toLocaleString()}
              </span>
            </Tooltip>
            <Tooltip content="AI가 생성한 답변 (출력)">
              <span className="cursor-help">
                Completion: {result.tokensUsed.completion.toLocaleString()}
              </span>
            </Tooltip>
            <span className="font-medium">
              Total:{' '}
              {(result.tokensUsed.prompt + result.tokensUsed.completion).toLocaleString()}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
