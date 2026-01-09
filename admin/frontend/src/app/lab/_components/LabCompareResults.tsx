'use client';

import { Zap, Loader2, Trophy, TrendingUp, Clock, Layers, BarChart3 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SearchTestResult } from '@/lib/api';
import { SCORE_THRESHOLDS, RELEVANCE_STYLES, getRelevanceLevel, CompareResults } from '../_lib';

// 비교 지표 계산 함수들
interface CompareMetrics {
  avgScore: number;
  top3Avg: number;
  dropOffRate: number;  // 1위 대비 5위 점수 비율 (높을수록 좋음)
  uniquePapers: number;
  totalLatency: number;
}

function calculateMetrics(result: SearchTestResult): CompareMetrics {
  const chunks = result.chunks;
  const scores = chunks.map(c => c.rerankScore ?? c.score);

  // 평균 점수
  const avgScore = scores.length > 0
    ? scores.reduce((a, b) => a + b, 0) / scores.length
    : 0;

  // Top-3 평균
  const top3Scores = scores.slice(0, 3);
  const top3Avg = top3Scores.length > 0
    ? top3Scores.reduce((a, b) => a + b, 0) / top3Scores.length
    : 0;

  // 점수 하락률 (1위 대비 5위, 높을수록 일관성 있음)
  const firstScore = scores[0] || 0;
  const fifthScore = scores[4] || scores[scores.length - 1] || 0;
  const dropOffRate = firstScore > 0 ? fifthScore / firstScore : 0;

  // 고유 논문 수
  const uniquePapers = new Set(chunks.map(c => c.paperId)).size;

  // 총 지연시간
  const totalLatency = result.searchLatencyMs + (result.rerankLatencyMs || 0);

  return { avgScore, top3Avg, dropOffRate, uniquePapers, totalLatency };
}

type Winner = 'A' | 'B' | 'tie';

function determineWinner(
  valueA: number,
  valueB: number,
  higherIsBetter: boolean = true
): Winner {
  const threshold = 0.01; // 1% 이내 차이는 동점
  const diff = Math.abs(valueA - valueB) / Math.max(valueA, valueB, 0.0001);

  if (diff < threshold) return 'tie';

  if (higherIsBetter) {
    return valueA > valueB ? 'A' : 'B';
  } else {
    return valueA < valueB ? 'A' : 'B';
  }
}

function WinnerBadge({ winner }: { winner: Winner }) {
  if (winner === 'tie') {
    return <span className="text-xs text-gray-400">동점</span>;
  }
  return (
    <span className={cn(
      'inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-xs font-medium',
      winner === 'A' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'
    )}>
      <Trophy className="h-3 w-3" />
      {winner}
    </span>
  );
}

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

      {/* Enhanced Comparison Summary */}
      {compareResults.configA && compareResults.configB && (
        <ComparisonSummaryPanel
          resultA={compareResults.configA}
          resultB={compareResults.configB}
        />
      )}
    </div>
  );
}

// 확장된 비교 요약 패널
function ComparisonSummaryPanel({
  resultA,
  resultB,
}: {
  resultA: SearchTestResult;
  resultB: SearchTestResult;
}) {
  const metricsA = calculateMetrics(resultA);
  const metricsB = calculateMetrics(resultB);

  // 각 지표별 승자 결정
  const winners = {
    avgScore: determineWinner(metricsA.avgScore, metricsB.avgScore, true),
    top3Avg: determineWinner(metricsA.top3Avg, metricsB.top3Avg, true),
    dropOff: determineWinner(metricsA.dropOffRate, metricsB.dropOffRate, true),
    diversity: determineWinner(metricsA.uniquePapers, metricsB.uniquePapers, true),
    latency: determineWinner(metricsA.totalLatency, metricsB.totalLatency, false),
  };

  // 종합 승자 계산
  const aWins = Object.values(winners).filter(w => w === 'A').length;
  const bWins = Object.values(winners).filter(w => w === 'B').length;
  const overallWinner: Winner = aWins > bWins ? 'A' : bWins > aWins ? 'B' : 'tie';

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between border-b border-gray-100 pb-3">
        <h3 className="flex items-center gap-2 font-semibold text-gray-900">
          <BarChart3 className="h-5 w-5 text-orange-500" />
          비교 결과 요약
        </h3>
        {overallWinner !== 'tie' && (
          <div className={cn(
            'flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium',
            overallWinner === 'A' ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800'
          )}>
            <Trophy className="h-4 w-4" />
            설정 {overallWinner} 권장 ({overallWinner === 'A' ? aWins : bWins}:{overallWinner === 'A' ? bWins : aWins})
          </div>
        )}
      </div>

      {/* 지표 비교 테이블 */}
      <div className="mt-4 overflow-hidden rounded-lg border border-gray-100">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left font-medium text-gray-600">지표</th>
              <th className="px-4 py-2 text-center font-medium text-blue-600">설정 A</th>
              <th className="px-4 py-2 text-center font-medium text-green-600">설정 B</th>
              <th className="px-4 py-2 text-center font-medium text-gray-600">승자</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {/* 평균 점수 */}
            <tr className="hover:bg-gray-50">
              <td className="px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-gray-400" />
                  <span>평균 점수</span>
                </div>
                <p className="mt-0.5 text-xs text-gray-400">전체 결과의 평균 관련도</p>
              </td>
              <td className="px-4 py-2.5 text-center font-mono">{metricsA.avgScore.toFixed(4)}</td>
              <td className="px-4 py-2.5 text-center font-mono">{metricsB.avgScore.toFixed(4)}</td>
              <td className="px-4 py-2.5 text-center"><WinnerBadge winner={winners.avgScore} /></td>
            </tr>

            {/* Top-3 평균 */}
            <tr className="hover:bg-gray-50">
              <td className="px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <Trophy className="h-4 w-4 text-gray-400" />
                  <span>Top-3 평균</span>
                </div>
                <p className="mt-0.5 text-xs text-gray-400">상위 3개 결과의 품질</p>
              </td>
              <td className="px-4 py-2.5 text-center font-mono">{metricsA.top3Avg.toFixed(4)}</td>
              <td className="px-4 py-2.5 text-center font-mono">{metricsB.top3Avg.toFixed(4)}</td>
              <td className="px-4 py-2.5 text-center"><WinnerBadge winner={winners.top3Avg} /></td>
            </tr>

            {/* 점수 일관성 */}
            <tr className="hover:bg-gray-50">
              <td className="px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-gray-400" />
                  <span>점수 일관성</span>
                </div>
                <p className="mt-0.5 text-xs text-gray-400">1위 대비 5위 점수 비율 (높을수록 좋음)</p>
              </td>
              <td className="px-4 py-2.5 text-center font-mono">{(metricsA.dropOffRate * 100).toFixed(1)}%</td>
              <td className="px-4 py-2.5 text-center font-mono">{(metricsB.dropOffRate * 100).toFixed(1)}%</td>
              <td className="px-4 py-2.5 text-center"><WinnerBadge winner={winners.dropOff} /></td>
            </tr>

            {/* 다양성 */}
            <tr className="hover:bg-gray-50">
              <td className="px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <Layers className="h-4 w-4 text-gray-400" />
                  <span>결과 다양성</span>
                </div>
                <p className="mt-0.5 text-xs text-gray-400">고유 논문 수 (다양할수록 좋음)</p>
              </td>
              <td className="px-4 py-2.5 text-center">{metricsA.uniquePapers}개 논문</td>
              <td className="px-4 py-2.5 text-center">{metricsB.uniquePapers}개 논문</td>
              <td className="px-4 py-2.5 text-center"><WinnerBadge winner={winners.diversity} /></td>
            </tr>

            {/* 응답 속도 */}
            <tr className="hover:bg-gray-50">
              <td className="px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-gray-400" />
                  <span>응답 속도</span>
                </div>
                <p className="mt-0.5 text-xs text-gray-400">검색 + 리랭킹 총 시간</p>
              </td>
              <td className="px-4 py-2.5 text-center">{metricsA.totalLatency}ms</td>
              <td className="px-4 py-2.5 text-center">{metricsB.totalLatency}ms</td>
              <td className="px-4 py-2.5 text-center"><WinnerBadge winner={winners.latency} /></td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* 해석 가이드 */}
      <div className="mt-4 rounded-lg bg-amber-50 p-3 text-xs text-amber-800">
        <p className="font-medium">💡 해석 가이드</p>
        <ul className="mt-1 space-y-0.5 text-amber-700">
          <li>• <strong>평균/Top-3 점수</strong>: 높을수록 쿼리와 관련성 높은 결과</li>
          <li>• <strong>점수 일관성</strong>: 100%에 가까울수록 전체 결과가 고르게 좋음</li>
          <li>• <strong>다양성</strong>: 여러 논문에서 결과가 나오면 더 포괄적</li>
          <li>• <strong>응답 속도</strong>: 프로덕션 환경에서는 속도도 중요</li>
        </ul>
      </div>
    </div>
  );
}
