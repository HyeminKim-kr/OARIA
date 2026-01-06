import { BarChart3, ThumbsUp, History, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { FeedbackStats, TestLogStats } from '@/lib/api';

interface LabStatsPanelProps {
  feedbackStats?: FeedbackStats;
  testLogStats?: TestLogStats;
}

export function LabStatsPanel({ feedbackStats, testLogStats }: LabStatsPanelProps) {
  return (
    <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-5">
      <h3 className="flex items-center gap-2 font-semibold text-emerald-900">
        <BarChart3 className="h-5 w-5" />
        테스트 통계
      </h3>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {/* 피드백 통계 */}
        <div className="rounded-lg bg-white p-4 shadow-sm">
          <h4 className="flex items-center gap-2 font-medium text-gray-900">
            <ThumbsUp className="h-4 w-4 text-green-500" />
            피드백 통계
          </h4>
          {feedbackStats ? (
            <div className="mt-3 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">총 피드백</span>
                <span className="font-semibold text-gray-900">{feedbackStats.total}개</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">좋음 / 나쁨</span>
                <div className="flex items-center gap-2">
                  <span className="rounded bg-green-100 px-2 py-0.5 text-sm text-green-700">
                    {feedbackStats.byRating.good}
                  </span>
                  <span className="rounded bg-red-100 px-2 py-0.5 text-sm text-red-700">
                    {feedbackStats.byRating.bad}
                  </span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">유형별</span>
                <div className="flex items-center gap-2">
                  <span className="rounded bg-blue-100 px-2 py-0.5 text-xs text-blue-700">
                    검색: {feedbackStats.byTestType.search}
                  </span>
                  <span className="rounded bg-purple-100 px-2 py-0.5 text-xs text-purple-700">
                    답변: {feedbackStats.byTestType.generate}
                  </span>
                </div>
              </div>

              {feedbackStats.recentFeedbacks.length > 0 && (
                <div className="mt-3 border-t border-gray-100 pt-3">
                  <p className="mb-2 text-xs font-medium text-gray-500">최근 피드백</p>
                  <div className="space-y-1.5">
                    {feedbackStats.recentFeedbacks.slice(0, 3).map((fb) => (
                      <div key={fb.id} className="flex items-center gap-2 text-xs">
                        <span
                          className={cn(
                            'rounded px-1.5 py-0.5',
                            fb.rating === 'good'
                              ? 'bg-green-50 text-green-600'
                              : 'bg-red-50 text-red-600'
                          )}
                        >
                          {fb.rating === 'good' ? '' : ''}
                        </span>
                        <span className="line-clamp-1 flex-1 text-gray-600">{fb.query}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="mt-3 flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-emerald-500" />
            </div>
          )}
        </div>

        {/* 테스트 로그 통계 */}
        <div className="rounded-lg bg-white p-4 shadow-sm">
          <h4 className="flex items-center gap-2 font-medium text-gray-900">
            <History className="h-4 w-4 text-purple-500" />
            테스트 로그 통계
          </h4>
          {testLogStats ? (
            <div className="mt-3 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">총 테스트</span>
                <span className="font-semibold text-gray-900">{testLogStats.total}개</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">오늘 테스트</span>
                <span className="rounded bg-emerald-100 px-2 py-0.5 text-sm font-medium text-emerald-700">
                  {testLogStats.todayCount}개
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">유형별</span>
                <div className="flex items-center gap-1.5">
                  <span className="rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700">
                    검색: {testLogStats.byTestType.search}
                  </span>
                  <span className="rounded bg-purple-100 px-1.5 py-0.5 text-xs text-purple-700">
                    답변: {testLogStats.byTestType.generate}
                  </span>
                  <span className="rounded bg-orange-100 px-1.5 py-0.5 text-xs text-orange-700">
                    비교: {testLogStats.byTestType.compare}
                  </span>
                </div>
              </div>

              <div className="mt-3 border-t border-gray-100 pt-3">
                <p className="mb-2 text-xs font-medium text-gray-500">평균 응답 시간</p>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="rounded bg-gray-50 px-2 py-1.5">
                    <p className="text-xs text-gray-500">검색</p>
                    <p className="text-sm font-semibold text-gray-900">
                      {testLogStats.avgLatency.search != null
                        ? `${Math.round(testLogStats.avgLatency.search)}ms`
                        : '-'}
                    </p>
                  </div>
                  <div className="rounded bg-green-50 px-2 py-1.5">
                    <p className="text-xs text-green-600">Rerank</p>
                    <p className="text-sm font-semibold text-green-700">
                      {testLogStats.avgLatency.rerank != null
                        ? `${Math.round(testLogStats.avgLatency.rerank)}ms`
                        : '-'}
                    </p>
                  </div>
                  <div className="rounded bg-purple-50 px-2 py-1.5">
                    <p className="text-xs text-purple-600">LLM</p>
                    <p className="text-sm font-semibold text-purple-700">
                      {testLogStats.avgLatency.llm != null
                        ? `${Math.round(testLogStats.avgLatency.llm)}ms`
                        : '-'}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="mt-3 flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-emerald-500" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
