'use client';

import { History, Trash2, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { TestLogItem, TestLogDetail } from '@/lib/api';

interface LabHistoryPanelProps {
  page: number;
  typeFilter?: 'search' | 'generate' | 'compare';
  testLogs?: {
    items: TestLogItem[];
    total: number;
    totalPages: number;
  };
  selectedLogId: string | null;
  selectedLogDetail?: TestLogDetail;
  isLoadingLogDetail: boolean;
  isDeleting: boolean;
  onPageChange: (page: number) => void;
  onTypeFilterChange: (filter: 'search' | 'generate' | 'compare' | undefined) => void;
  onLogSelect: (logId: string) => void;
  onLogDelete: (logId: string) => void;
}

export function LabHistoryPanel({
  page,
  typeFilter,
  testLogs,
  selectedLogId,
  selectedLogDetail,
  isLoadingLogDetail,
  isDeleting,
  onPageChange,
  onTypeFilterChange,
  onLogSelect,
  onLogDelete,
}: LabHistoryPanelProps) {
  return (
    <div className="rounded-lg border border-purple-200 bg-purple-50 p-5">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 font-semibold text-purple-900">
          <History className="h-5 w-5" />
          테스트 히스토리
        </h3>
        <div className="flex items-center gap-2">
          <select
            value={typeFilter || ''}
            onChange={(e) =>
              onTypeFilterChange(
                (e.target.value as 'search' | 'generate' | 'compare') || undefined
              )
            }
            className="rounded-md border border-purple-300 bg-white px-2 py-1 text-sm text-purple-700"
          >
            <option value="">전체</option>
            <option value="search">검색</option>
            <option value="generate">답변생성</option>
            <option value="compare">A/B 비교</option>
          </select>
        </div>
      </div>

      {testLogs?.items.length === 0 ? (
        <div className="mt-4 text-center text-sm text-purple-600">
          저장된 테스트 기록이 없습니다.
        </div>
      ) : (
        <>
          <div className="mt-4 space-y-2">
            {testLogs?.items.map((log: TestLogItem) => (
              <div
                key={log.id}
                onClick={() => onLogSelect(log.id)}
                className={cn(
                  'cursor-pointer rounded-lg bg-white p-3 shadow-sm transition-all',
                  selectedLogId === log.id ? 'ring-2 ring-purple-500' : 'hover:bg-gray-50'
                )}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={cn(
                          'rounded px-2 py-0.5 text-xs font-medium',
                          log.testType === 'search' && 'bg-blue-100 text-blue-700',
                          log.testType === 'generate' && 'bg-purple-100 text-purple-700',
                          log.testType === 'compare' && 'bg-orange-100 text-orange-700'
                        )}
                      >
                        {log.testType === 'search'
                          ? '검색'
                          : log.testType === 'generate'
                            ? '답변생성'
                            : 'A/B 비교'}
                      </span>
                      {log.parameters.useReranker && (
                        <span className="rounded bg-green-100 px-1.5 py-0.5 text-xs text-green-700">
                          Reranker
                        </span>
                      )}
                      <span className="text-xs text-gray-400">
                        {new Date(log.createdAt).toLocaleString('ko-KR', {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>
                    <p className="mt-1 line-clamp-1 text-sm text-gray-700">{log.query}</p>
                    <div className="mt-1 flex items-center gap-3 text-xs text-gray-500">
                      {log.searchLatencyMs && <span>검색: {log.searchLatencyMs}ms</span>}
                      {log.rerankLatencyMs && (
                        <span className="text-green-600">Rerank: {log.rerankLatencyMs}ms</span>
                      )}
                      {log.llmLatencyMs && <span>LLM: {log.llmLatencyMs}ms</span>}
                      {log.resultSummary.totalChunks !== undefined && (
                        <span>{log.resultSummary.totalChunks as number}개 청크</span>
                      )}
                      {log.resultSummary.answerLength !== undefined && (
                        <span>답변: {log.resultSummary.answerLength as number}자</span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onLogDelete(log.id);
                    }}
                    disabled={isDeleting}
                    className="ml-2 rounded p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-500 disabled:opacity-50"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>

                {/* 선택된 로그 상세 보기 */}
                {selectedLogId === log.id && (
                  <div className="mt-3 border-t border-gray-200 pt-3">
                    {isLoadingLogDetail ? (
                      <div className="flex items-center justify-center py-4">
                        <Loader2 className="h-5 w-5 animate-spin text-purple-500" />
                      </div>
                    ) : selectedLogDetail ? (
                      <div className="space-y-2">
                        {log.testType === 'search' && 'chunks' in selectedLogDetail.results && (
                          <div className="max-h-[300px] overflow-y-auto">
                            <p className="mb-2 text-xs font-medium text-gray-600">
                              검색 결과 ({selectedLogDetail.results.chunks.length}개)
                            </p>
                            {selectedLogDetail.results.chunks.map((chunk, idx) => (
                              <div key={idx} className="mb-2 rounded bg-gray-50 p-2 text-xs">
                                <div className="flex items-center gap-2">
                                  <span className="rounded bg-blue-100 px-1.5 py-0.5 text-blue-700">
                                    #{idx + 1}
                                  </span>
                                  {chunk.rerankScore != null ? (
                                    <span className="text-green-600">
                                      rerank: {chunk.rerankScore.toFixed(4)}
                                    </span>
                                  ) : (
                                    <span className="text-gray-500">
                                      score: {chunk.score?.toFixed(4) ?? '-'}
                                    </span>
                                  )}
                                </div>
                                <p className="mt-1 font-medium text-gray-800">
                                  {chunk.paperTitle}
                                </p>
                                <p className="text-gray-500">섹션: {chunk.sectionName}</p>
                                <p className="mt-1 line-clamp-3 text-gray-600">{chunk.content}</p>
                              </div>
                            ))}
                          </div>
                        )}

                        {log.testType === 'generate' && 'answer' in selectedLogDetail.results && (
                          <div className="max-h-[300px] overflow-y-auto">
                            <p className="mb-2 text-xs font-medium text-gray-600">생성된 답변</p>
                            <div className="rounded bg-gray-50 p-3 text-sm text-gray-700">
                              <p className="whitespace-pre-wrap">
                                {selectedLogDetail.results.answer}
                              </p>
                            </div>
                            {'references' in selectedLogDetail.results && (
                              <div className="mt-3">
                                <p className="mb-2 text-xs font-medium text-gray-600">
                                  참조 문헌 ({selectedLogDetail.results.references.length}개)
                                </p>
                                {selectedLogDetail.results.references.map((ref, idx) => (
                                  <div key={idx} className="mb-2 rounded bg-gray-50 p-2 text-xs">
                                    <span className="rounded bg-purple-100 px-1.5 py-0.5 text-purple-700">
                                      [{idx + 1}]
                                    </span>
                                    <span className="ml-2 font-medium text-gray-800">
                                      {ref.title}
                                    </span>
                                    <p className="mt-1 line-clamp-2 text-gray-600">
                                      {ref.content}
                                    </p>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ) : null}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Pagination */}
          {testLogs && testLogs.totalPages > 1 && (
            <div className="mt-4 flex items-center justify-center gap-2">
              <button
                onClick={() => onPageChange(Math.max(1, page - 1))}
                disabled={page === 1}
                className="rounded-md border border-purple-300 p-1.5 text-purple-700 hover:bg-purple-100 disabled:opacity-50"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="text-sm text-purple-700">
                {page} / {testLogs.totalPages}
              </span>
              <button
                onClick={() => onPageChange(Math.min(testLogs.totalPages, page + 1))}
                disabled={page === testLogs.totalPages}
                className="rounded-md border border-purple-300 p-1.5 text-purple-700 hover:bg-purple-100 disabled:opacity-50"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}

          <p className="mt-3 text-center text-xs text-purple-600">
            총 {testLogs?.total ?? 0}개의 테스트 기록
          </p>
        </>
      )}
    </div>
  );
}
