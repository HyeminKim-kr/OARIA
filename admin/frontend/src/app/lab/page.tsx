'use client';

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  FlaskConical,
  Search,
  MessageSquare,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  ThumbsUp,
  ThumbsDown,
  ChevronDown,
  ChevronUp,
  Zap,
  AlertTriangle,
  HelpCircle,
  Info,
  BookOpen,
  History,
  Trash2,
  ChevronLeft,
  ChevronRight,
  BarChart3,
} from 'lucide-react';
import Link from 'next/link';
import { labApi, SearchTestResult, FeedbackParams, TestLogItem } from '@/lib/api';
import { cn } from '@/lib/utils';

type TestMode = 'search' | 'generate' | 'compare';

// 점수 임계값 상수
const SCORE_THRESHOLDS = {
  HIGH: 0.7,      // 높은 관련성
  MEDIUM: 0.5,    // 중간 관련성
  LOW: 0.3,       // 낮은 관련성 (경고)
  IRRELEVANT: 0.1 // 관련 없음
};

// 관련성 레벨 판단
function getRelevanceLevel(score: number): 'high' | 'medium' | 'low' | 'irrelevant' {
  if (score >= SCORE_THRESHOLDS.HIGH) return 'high';
  if (score >= SCORE_THRESHOLDS.MEDIUM) return 'medium';
  if (score >= SCORE_THRESHOLDS.LOW) return 'low';
  return 'irrelevant';
}

// 관련성 레벨별 스타일
const relevanceStyles = {
  high: { bg: 'bg-green-100', text: 'text-green-700', label: '높음' },
  medium: { bg: 'bg-yellow-100', text: 'text-yellow-700', label: '중간' },
  low: { bg: 'bg-orange-100', text: 'text-orange-700', label: '낮음' },
  irrelevant: { bg: 'bg-red-100', text: 'text-red-700', label: '관련없음' },
};

// 툴팁 컴포넌트
function Tooltip({ children, content }: { children: React.ReactNode; content: string }) {
  return (
    <span className="group relative inline-flex items-center">
      {children}
      <span className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 -translate-x-1/2 whitespace-nowrap rounded bg-gray-900 px-2 py-1 text-xs text-white opacity-0 transition-opacity group-hover:opacity-100">
        {content}
        <span className="absolute left-1/2 top-full -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
      </span>
    </span>
  );
}

export default function LabPage() {
  const [mode, setMode] = useState<TestMode>('search');
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(10);
  const [alpha, setAlpha] = useState(0.7);
  const [useReranker, setUseReranker] = useState(false);
  const [expandedChunks, setExpandedChunks] = useState<Set<number>>(new Set());
  const [showHelp, setShowHelp] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyTypeFilter, setHistoryTypeFilter] = useState<'search' | 'generate' | 'compare' | undefined>();
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null);
  const [showStats, setShowStats] = useState(false);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState<{
    search?: 'good' | 'bad';
    generate?: 'good' | 'bad';
  }>({});

  // A/B 비교 모드 상태
  const [compareResults, setCompareResults] = useState<{
    withReranker?: SearchTestResult;
    withoutReranker?: SearchTestResult;
  }>({});

  // User Backend 상태 확인
  const { data: status } = useQuery({
    queryKey: ['lab', 'status'],
    queryFn: () => labApi.getStatus(),
    refetchInterval: 30000, // 30초마다 갱신
  });

  // 검색 테스트
  const searchMutation = useMutation({
    mutationFn: () => labApi.testSearch({ query, limit, alpha, useReranker }),
  });

  // 답변 생성 테스트
  const generateMutation = useMutation({
    mutationFn: () => labApi.testGenerate({ query, limit, alpha, useReranker }),
  });

  // 피드백 저장
  const feedbackMutation = useMutation({
    mutationFn: (params: FeedbackParams) => labApi.saveFeedback(params),
    onSuccess: (_, variables) => {
      setFeedbackSubmitted((prev) => ({
        ...prev,
        [variables.type]: variables.rating,
      }));
    },
  });

  // A/B 비교 테스트 (단일 API로 두 검색 수행)
  const compareMutation = useMutation({
    mutationFn: () => labApi.testCompare({ query, limit, alpha }),
    onSuccess: (data) => {
      setCompareResults({
        withReranker: data.withReranker,
        withoutReranker: data.withoutReranker,
      });
    },
  });

  // 테스트 로그 히스토리 조회
  const { data: testLogs, refetch: refetchLogs } = useQuery({
    queryKey: ['lab', 'logs', historyPage, historyTypeFilter],
    queryFn: () => labApi.getTestLogs({ page: historyPage, limit: 10, testType: historyTypeFilter }),
    enabled: showHistory,
  });

  // 테스트 로그 삭제
  const deleteLogMutation = useMutation({
    mutationFn: (id: string) => labApi.deleteTestLog(id),
    onSuccess: () => {
      refetchLogs();
      if (selectedLogId) setSelectedLogId(null);
    },
  });

  // 선택된 테스트 로그 상세 조회
  const { data: selectedLogDetail, isLoading: isLoadingLogDetail } = useQuery({
    queryKey: ['lab', 'log', selectedLogId],
    queryFn: () => labApi.getTestLog(selectedLogId!),
    enabled: !!selectedLogId,
  });

  // 피드백 통계 조회
  const { data: feedbackStats } = useQuery({
    queryKey: ['lab', 'stats', 'feedback'],
    queryFn: () => labApi.getFeedbackStats(),
    enabled: showStats,
  });

  // 테스트 로그 통계 조회
  const { data: testLogStats } = useQuery({
    queryKey: ['lab', 'stats', 'logs'],
    queryFn: () => labApi.getTestLogStats(),
    enabled: showStats,
  });

  const handleTest = () => {
    if (!query.trim()) return;

    // 새 테스트 시 피드백 상태 초기화
    setFeedbackSubmitted({});

    if (mode === 'search') {
      searchMutation.mutate();
    } else if (mode === 'generate') {
      generateMutation.mutate();
    } else if (mode === 'compare') {
      // A/B 비교: 단일 API로 두 검색 수행
      setCompareResults({});
      compareMutation.mutate();
    }
  };

  // 피드백 제출 핸들러
  const handleFeedback = (type: 'search' | 'generate', rating: 'good' | 'bad') => {
    const result = type === 'search' ? searchResult : generateResult;
    if (!result) return;

    // 관련성 통계 계산 (검색 결과의 경우)
    let relevantCount: number | undefined;
    let lowRelevanceCount: number | undefined;

    if (type === 'search' && searchResult) {
      const chunks = searchResult.chunks;
      if (searchResult.parameters.useReranker) {
        relevantCount = chunks.filter(c => (c.rerankScore ?? c.score) >= SCORE_THRESHOLDS.LOW).length;
        lowRelevanceCount = chunks.filter(c => (c.rerankScore ?? c.score) < SCORE_THRESHOLDS.LOW).length;
      }
    }

    const topScore = type === 'search' && searchResult?.chunks[0]
      ? (searchResult.chunks[0].rerankScore ?? searchResult.chunks[0].score)
      : generateResult?.references[0]?.score ?? 0;

    const feedbackParams: FeedbackParams = {
      type,
      query,
      rating,
      parameters: {
        limit,
        alpha,
        useReranker,
        rerankerModel: type === 'search' ? searchResult?.parameters.rerankerModel : undefined,
      },
      resultSummary: {
        totalChunks: type === 'search' ? (searchResult?.totalChunks ?? 0) : (generateResult?.references.length ?? 0),
        topScore,
        relevantCount,
        lowRelevanceCount,
        model: type === 'generate' ? generateResult?.model : undefined,
        tokensUsed: type === 'generate' ? generateResult?.tokensUsed : undefined,
      },
      searchLatencyMs: type === 'search' ? searchResult?.searchLatencyMs : generateResult?.searchLatencyMs,
      rerankLatencyMs: type === 'search' ? searchResult?.rerankLatencyMs : generateResult?.rerankLatencyMs,
      llmLatencyMs: type === 'generate' ? generateResult?.llmLatencyMs : undefined,
    };

    feedbackMutation.mutate(feedbackParams);
  };

  const toggleChunkExpand = (index: number) => {
    const newExpanded = new Set(expandedChunks);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedChunks(newExpanded);
  };

  const isLoading = searchMutation.isPending || generateMutation.isPending ||
    compareMutation.isPending;
  const searchResult = searchMutation.data;
  const generateResult = generateMutation.data;

  // 에러 메시지 추출
  const getErrorInfo = () => {
    const error = searchMutation.error || generateMutation.error ||
      compareMutation.error;
    if (!error) return null;

    // axios 에러에서 상세 정보 추출
    const axiosError = error as { response?: { data?: { detail?: { error?: string; message?: string } | string } } };
    const detail = axiosError.response?.data?.detail;

    if (typeof detail === 'object' && detail?.error === 'no_embedding_data') {
      return {
        type: 'no_data',
        message: detail.message,
      };
    }

    return {
      type: 'error',
      message: typeof detail === 'string' ? detail : '알 수 없는 오류가 발생했습니다.',
    };
  };

  const errorInfo = getErrorInfo();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900">
            <FlaskConical className="h-6 w-6" />
            RAG Lab
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            RAG 검색 및 답변 품질을 테스트합니다
          </p>
        </div>

        {/* Status Badge & Help/History/Stats Buttons */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              setShowStats(!showStats);
              if (!showStats) {
                setShowHistory(false);
                setShowHelp(false);
              }
            }}
            className={cn(
              'flex items-center gap-1 rounded-full px-3 py-1 text-sm transition-colors',
              showStats
                ? 'bg-emerald-100 text-emerald-700'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
          >
            <BarChart3 className="h-4 w-4" />
            통계
          </button>
          <button
            onClick={() => {
              setShowHistory(!showHistory);
              if (!showHistory) {
                setShowHelp(false);
                setShowStats(false);
              }
            }}
            className={cn(
              'flex items-center gap-1 rounded-full px-3 py-1 text-sm transition-colors',
              showHistory
                ? 'bg-purple-100 text-purple-700'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
          >
            <History className="h-4 w-4" />
            히스토리
          </button>
          <button
            onClick={() => {
              setShowHelp(!showHelp);
              if (!showHelp) {
                setShowHistory(false);
                setShowStats(false);
              }
            }}
            className={cn(
              'flex items-center gap-1 rounded-full px-3 py-1 text-sm transition-colors',
              showHelp
                ? 'bg-blue-100 text-blue-700'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
          >
            <BookOpen className="h-4 w-4" />
            도움말
          </button>
          {status?.available ? (
            <span className="flex items-center gap-1 rounded-full bg-green-100 px-3 py-1 text-sm text-green-700">
              <CheckCircle2 className="h-4 w-4" />
              Backend 연결됨
              {status.latencyMs && (
                <span className="text-green-600">({status.latencyMs}ms)</span>
              )}
            </span>
          ) : (
            <span className="flex items-center gap-1 rounded-full bg-red-100 px-3 py-1 text-sm text-red-700">
              <XCircle className="h-4 w-4" />
              Backend 연결 실패
            </span>
          )}
        </div>
      </div>

      {/* Stats Panel */}
      {showStats && (
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
                        👍 {feedbackStats.byRating.good}
                      </span>
                      <span className="rounded bg-red-100 px-2 py-0.5 text-sm text-red-700">
                        👎 {feedbackStats.byRating.bad}
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
                            <span className={cn(
                              'rounded px-1.5 py-0.5',
                              fb.rating === 'good' ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'
                            )}>
                              {fb.rating === 'good' ? '👍' : '👎'}
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
                          {testLogStats.avgLatency.search
                            ? `${Math.round(testLogStats.avgLatency.search)}ms`
                            : '-'}
                        </p>
                      </div>
                      <div className="rounded bg-green-50 px-2 py-1.5">
                        <p className="text-xs text-green-600">Rerank</p>
                        <p className="text-sm font-semibold text-green-700">
                          {testLogStats.avgLatency.rerank
                            ? `${Math.round(testLogStats.avgLatency.rerank)}ms`
                            : '-'}
                        </p>
                      </div>
                      <div className="rounded bg-purple-50 px-2 py-1.5">
                        <p className="text-xs text-purple-600">LLM</p>
                        <p className="text-sm font-semibold text-purple-700">
                          {testLogStats.avgLatency.llm
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
      )}

      {/* Help Panel */}
      {showHelp && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-5">
          <h3 className="flex items-center gap-2 font-semibold text-blue-900">
            <Info className="h-5 w-5" />
            RAG (Retrieval-Augmented Generation) 이란?
          </h3>
          <p className="mt-2 text-sm text-blue-800">
            RAG는 질문에 답변하기 전에 관련 문서를 먼저 검색하여, 그 내용을 바탕으로 AI가 답변을 생성하는 기술입니다.
            이를 통해 AI가 최신 정보나 특정 도메인 지식을 활용할 수 있습니다.
          </p>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div className="rounded-lg bg-white p-4">
              <h4 className="font-medium text-gray-900">검색 테스트</h4>
              <p className="mt-1 text-sm text-gray-600">
                질문과 관련된 논문 조각(청크)을 찾아 보여줍니다. 검색 품질을 확인할 수 있습니다.
              </p>
              <ul className="mt-2 space-y-1 text-xs text-gray-500">
                <li><strong>Score</strong>: 유사도 점수 (높을수록 관련성 높음)</li>
                <li><strong>Chunk</strong>: 논문에서 잘린 텍스트 조각</li>
                <li><strong>Latency</strong>: 검색 소요 시간</li>
              </ul>
            </div>
            <div className="rounded-lg bg-white p-4">
              <h4 className="font-medium text-gray-900">답변 생성 테스트</h4>
              <p className="mt-1 text-sm text-gray-600">
                검색된 문서를 바탕으로 AI가 답변을 생성합니다. 답변의 품질과 출처를 확인할 수 있습니다.
              </p>
              <ul className="mt-2 space-y-1 text-xs text-gray-500">
                <li><strong>References</strong>: 답변에 사용된 출처 문서</li>
                <li><strong>Token</strong>: LLM API 사용량 (비용과 직결)</li>
                <li><strong>LLM Latency</strong>: AI 답변 생성 시간</li>
              </ul>
            </div>
          </div>

          <div className="mt-4 rounded-lg bg-white p-4">
            <h4 className="font-medium text-gray-900">파라미터 설명</h4>
            <div className="mt-2 grid gap-2 text-sm md:grid-cols-3">
              <div>
                <strong className="text-gray-700">Limit (결과 개수)</strong>
                <p className="text-xs text-gray-500">검색할 문서 조각 개수. 많으면 정확도↑, 속도↓</p>
              </div>
              <div>
                <strong className="text-gray-700">Alpha (하이브리드 가중치)</strong>
                <p className="text-xs text-gray-500">
                  0 = 키워드 검색만, 1 = 벡터(의미) 검색만<br/>
                  0.7 권장: 의미 70% + 키워드 30% 조합
                </p>
              </div>
              <div>
                <strong className="text-gray-700">Reranker</strong>
                <p className="text-xs text-gray-500">
                  BGE Cross-Encoder로 검색 결과 재평가<br/>
                  관련 없는 결과 필터링, 정확도↑, 속도↓
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* History Panel */}
      {showHistory && (
        <div className="rounded-lg border border-purple-200 bg-purple-50 p-5">
          <div className="flex items-center justify-between">
            <h3 className="flex items-center gap-2 font-semibold text-purple-900">
              <History className="h-5 w-5" />
              테스트 히스토리
            </h3>
            <div className="flex items-center gap-2">
              <select
                value={historyTypeFilter || ''}
                onChange={(e) => {
                  setHistoryTypeFilter(e.target.value as 'search' | 'generate' | 'compare' | undefined || undefined);
                  setHistoryPage(1);
                }}
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
                    onClick={() => setSelectedLogId(selectedLogId === log.id ? null : log.id)}
                    className={cn(
                      'cursor-pointer rounded-lg bg-white p-3 shadow-sm transition-all',
                      selectedLogId === log.id
                        ? 'ring-2 ring-purple-500'
                        : 'hover:bg-gray-50'
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={cn(
                            'rounded px-2 py-0.5 text-xs font-medium',
                            log.testType === 'search' && 'bg-blue-100 text-blue-700',
                            log.testType === 'generate' && 'bg-purple-100 text-purple-700',
                            log.testType === 'compare' && 'bg-orange-100 text-orange-700',
                          )}>
                            {log.testType === 'search' ? '검색' : log.testType === 'generate' ? '답변생성' : 'A/B 비교'}
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
                        <p className="mt-1 line-clamp-1 text-sm text-gray-700">
                          {log.query}
                        </p>
                        <div className="mt-1 flex items-center gap-3 text-xs text-gray-500">
                          {log.searchLatencyMs && (
                            <span>검색: {log.searchLatencyMs}ms</span>
                          )}
                          {log.rerankLatencyMs && (
                            <span className="text-green-600">Rerank: {log.rerankLatencyMs}ms</span>
                          )}
                          {log.llmLatencyMs && (
                            <span>LLM: {log.llmLatencyMs}ms</span>
                          )}
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
                          if (confirm('이 테스트 기록을 삭제하시겠습니까?')) {
                            deleteLogMutation.mutate(log.id);
                          }
                        }}
                        disabled={deleteLogMutation.isPending}
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
                            {/* 검색 결과 */}
                            {log.testType === 'search' && 'chunks' in selectedLogDetail.results && (
                              <div className="max-h-[300px] overflow-y-auto">
                                <p className="mb-2 text-xs font-medium text-gray-600">
                                  검색 결과 ({(selectedLogDetail.results as { chunks: unknown[] }).chunks.length}개)
                                </p>
                                {(selectedLogDetail.results as { chunks: Array<{
                                  paperId: string;
                                  paperTitle: string;
                                  sectionName: string;
                                  content: string;
                                  score: number;
                                  rerankScore?: number;
                                }> }).chunks.map((chunk, idx) => (
                                  <div key={idx} className="mb-2 rounded bg-gray-50 p-2 text-xs">
                                    <div className="flex items-center gap-2">
                                      <span className="rounded bg-blue-100 px-1.5 py-0.5 text-blue-700">#{idx + 1}</span>
                                      {chunk.rerankScore !== undefined ? (
                                        <span className="text-green-600">rerank: {chunk.rerankScore.toFixed(4)}</span>
                                      ) : (
                                        <span className="text-gray-500">score: {chunk.score.toFixed(4)}</span>
                                      )}
                                    </div>
                                    <p className="mt-1 font-medium text-gray-800">{chunk.paperTitle}</p>
                                    <p className="text-gray-500">섹션: {chunk.sectionName}</p>
                                    <p className="mt-1 line-clamp-3 text-gray-600">{chunk.content}</p>
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* 답변 생성 결과 */}
                            {log.testType === 'generate' && 'answer' in selectedLogDetail.results && (
                              <div className="max-h-[300px] overflow-y-auto">
                                <p className="mb-2 text-xs font-medium text-gray-600">생성된 답변</p>
                                <div className="rounded bg-gray-50 p-3 text-sm text-gray-700">
                                  <p className="whitespace-pre-wrap">{(selectedLogDetail.results as { answer: string }).answer}</p>
                                </div>
                                {'references' in selectedLogDetail.results && (
                                  <div className="mt-3">
                                    <p className="mb-2 text-xs font-medium text-gray-600">
                                      참조 문헌 ({(selectedLogDetail.results as { references: unknown[] }).references.length}개)
                                    </p>
                                    {(selectedLogDetail.results as { references: Array<{
                                      paperId: string;
                                      title: string;
                                      section: string;
                                      content: string;
                                      score: number;
                                    }> }).references.map((ref, idx) => (
                                      <div key={idx} className="mb-2 rounded bg-gray-50 p-2 text-xs">
                                        <span className="rounded bg-purple-100 px-1.5 py-0.5 text-purple-700">[{idx + 1}]</span>
                                        <span className="ml-2 font-medium text-gray-800">{ref.title}</span>
                                        <p className="mt-1 line-clamp-2 text-gray-600">{ref.content}</p>
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
                    onClick={() => setHistoryPage((p) => Math.max(1, p - 1))}
                    disabled={historyPage === 1}
                    className="rounded-md border border-purple-300 p-1.5 text-purple-700 hover:bg-purple-100 disabled:opacity-50"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <span className="text-sm text-purple-700">
                    {historyPage} / {testLogs.totalPages}
                  </span>
                  <button
                    onClick={() => setHistoryPage((p) => Math.min(testLogs.totalPages, p + 1))}
                    disabled={historyPage === testLogs.totalPages}
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
      )}

      {/* Test Configuration */}
      <div className="rounded-lg bg-white p-6 shadow">
        <div className="space-y-4">
          {/* Mode Toggle */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setMode('search')}
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
              onClick={() => setMode('generate')}
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
              onClick={() => setMode('compare')}
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
            <label className="block text-sm font-medium text-gray-700">
              질문 / 쿼리
            </label>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
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
                  <HelpCircle className="h-3.5 w-3.5 text-gray-400 cursor-help" />
                </Tooltip>
              </label>
              <input
                type="number"
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                min={1}
                max={50}
                className="mt-1 w-24 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div className="flex-1 min-w-[200px]">
              <label className="flex items-center gap-1 text-sm font-medium text-gray-700">
                Alpha (하이브리드 가중치): {alpha.toFixed(2)}
                <Tooltip content="0=키워드만, 1=벡터만, 0.7권장(의미70%+키워드30%)">
                  <HelpCircle className="h-3.5 w-3.5 text-gray-400 cursor-help" />
                </Tooltip>
              </label>
              <div className="mt-1 flex items-center gap-3">
                <span className="text-xs text-gray-500">키워드</span>
                <input
                  type="range"
                  value={alpha}
                  onChange={(e) => setAlpha(Number(e.target.value))}
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
                    <HelpCircle className="h-3.5 w-3.5 text-gray-400 cursor-help" />
                  </Tooltip>
                </label>
                <button
                  onClick={() => setUseReranker(!useReranker)}
                  className={cn(
                    'mt-1 flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors',
                    useReranker
                      ? 'bg-green-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  )}
                >
                  {useReranker ? (
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
                {useReranker ? '관련성 재평가 활성화' : '기본 검색만 사용'}
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
            onClick={handleTest}
            disabled={!query.trim() || isLoading || !status?.available}
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

      {/* Search Results */}
      {mode === 'search' && searchResult && (() => {
        // Reranker 사용 시에만 관련성 분석
        const hasReranker = searchResult.parameters.useReranker;
        const relevantChunks = hasReranker
          ? searchResult.chunks.filter(c => (c.rerankScore ?? c.score) >= SCORE_THRESHOLDS.LOW)
          : searchResult.chunks;
        const lowRelevanceChunks = hasReranker
          ? searchResult.chunks.filter(c => (c.rerankScore ?? c.score) < SCORE_THRESHOLDS.LOW)
          : [];
        const allLowRelevance = hasReranker && relevantChunks.length === 0;
        const topScore = searchResult.chunks[0]
          ? (searchResult.chunks[0].rerankScore ?? searchResult.chunks[0].score)
          : 0;

        return (
          <div className="space-y-4">
            {/* 관련 결과 없음 경고 */}
            {allLowRelevance && (
              <div className="rounded-lg border border-orange-200 bg-orange-50 p-4">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 flex-shrink-0 text-orange-500" />
                  <div>
                    <h3 className="font-medium text-orange-800">관련성 높은 결과 없음</h3>
                    <p className="mt-1 text-sm text-orange-700">
                      모든 검색 결과의 Rerank Score가 {SCORE_THRESHOLDS.LOW} 미만입니다.
                      질문과 관련된 논문이 DB에 없거나, 다른 검색어를 시도해보세요.
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
                    </h2>
                    <p className="mt-0.5 text-xs text-gray-500">
                      {hasReranker
                        ? `Rerank Score 기준: 0.7↑ 높음, 0.5↑ 중간, 0.3↑ 낮음, 0.3↓ 관련없음`
                        : 'Score가 높을수록 관련성이 높습니다.'}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500">
                    <Tooltip content="검색에 걸린 시간 (낮을수록 좋음)">
                      <span className="flex items-center gap-1 cursor-help">
                        <Clock className="h-4 w-4" />
                        검색 {searchResult.searchLatencyMs}ms
                      </span>
                    </Tooltip>
                    {searchResult.rerankLatencyMs !== undefined && (
                      <Tooltip content="Reranker가 결과를 재정렬하는데 걸린 시간">
                        <span className="flex items-center gap-1 cursor-help text-green-600">
                          <Zap className="h-4 w-4" />
                          Rerank {searchResult.rerankLatencyMs}ms
                        </span>
                      </Tooltip>
                    )}
                    <Tooltip content="검색된 문서 조각 개수">
                      <span className="cursor-help">{searchResult.totalChunks}개 청크</span>
                    </Tooltip>
                  </div>
                </div>
              </div>
              <div className="divide-y divide-gray-200">
                {searchResult.chunks.map((chunk, index) => {
                  const score = chunk.rerankScore ?? chunk.score;
                  const relevance = hasReranker ? getRelevanceLevel(score) : null;
                  const isLowRelevance = relevance === 'low' || relevance === 'irrelevant';
                  const style = relevance ? relevanceStyles[relevance] : null;

                  return (
                    <div
                      key={index}
                      className={cn(
                        'p-4 transition-opacity',
                        isLowRelevance && 'opacity-60 bg-gray-50'
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
                                  <span className={cn(
                                    'rounded px-2 py-0.5 text-xs cursor-help',
                                    style?.bg,
                                    style?.text
                                  )}>
                                    rerank: {chunk.rerankScore.toFixed(4)}
                                  </span>
                                </Tooltip>
                                {chunk.originalScore != null && (
                                  <Tooltip content="원본 벡터 검색 점수">
                                    <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-500 cursor-help">
                                      원본: {chunk.originalScore.toFixed(4)}
                                    </span>
                                  </Tooltip>
                                )}
                                {isLowRelevance && (
                                  <Tooltip content="관련성이 낮아 실제 서비스에서는 필터링될 수 있습니다">
                                    <span className="flex items-center gap-1 text-xs text-orange-600 cursor-help">
                                      <AlertTriangle className="h-3 w-3" />
                                      {style?.label}
                                    </span>
                                  </Tooltip>
                                )}
                              </>
                            ) : (
                              <Tooltip content="유사도 점수 (0~1, 높을수록 관련성 높음)">
                                <span className="rounded bg-green-100 px-2 py-0.5 text-xs text-green-700 cursor-help">
                                  score: {chunk.score.toFixed(4)}
                                </span>
                              </Tooltip>
                            )}
                            <span className={cn(
                              'text-sm font-medium',
                              isLowRelevance ? 'text-gray-500' : 'text-gray-900'
                            )}>
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

              {/* Search Feedback Buttons */}
              <div className="border-t border-gray-200 px-6 py-4">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-500">검색 결과 품질:</span>
                  {feedbackSubmitted.search ? (
                    <span className={cn(
                      'flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm',
                      feedbackSubmitted.search === 'good'
                        ? 'bg-green-100 text-green-700'
                        : 'bg-red-100 text-red-700'
                    )}>
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
                        onClick={() => handleFeedback('search', 'good')}
                        disabled={feedbackMutation.isPending}
                        className="flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-green-50 hover:border-green-300 hover:text-green-700 disabled:opacity-50"
                      >
                        <ThumbsUp className="h-4 w-4" />
                        좋음
                      </button>
                      <button
                        onClick={() => handleFeedback('search', 'bad')}
                        disabled={feedbackMutation.isPending}
                        className="flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-red-50 hover:border-red-300 hover:text-red-700 disabled:opacity-50"
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
      })()}

      {/* Generate Results */}
      {mode === 'generate' && generateResult && (
        <div className="space-y-6">
          {/* Answer */}
          <div className="rounded-lg bg-white shadow">
            <div className="border-b border-gray-200 px-6 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="flex items-center gap-2 font-medium text-gray-900">
                    생성된 답변
                    {generateResult.useReranker && (
                      <span className="rounded bg-green-100 px-2 py-0.5 text-xs text-green-700">
                        Reranker 적용됨
                      </span>
                    )}
                  </h2>
                  <p className="mt-0.5 text-xs text-gray-500">
                    검색된 문서를 바탕으로 AI가 생성한 답변입니다.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-3 text-sm text-gray-500">
                  <Tooltip content="전체 소요 시간 (검색 + AI 생성)">
                    <span className="flex items-center gap-1 cursor-help">
                      <Clock className="h-4 w-4" />
                      총 {generateResult.totalLatencyMs}ms
                    </span>
                  </Tooltip>
                  <Tooltip content="문서 검색에 걸린 시간">
                    <span className="cursor-help">검색: {generateResult.searchLatencyMs}ms</span>
                  </Tooltip>
                  {generateResult.rerankLatencyMs !== undefined && (
                    <Tooltip content="Reranker가 결과를 재정렬하는데 걸린 시간">
                      <span className="cursor-help text-green-600">Rerank: {generateResult.rerankLatencyMs}ms</span>
                    </Tooltip>
                  )}
                  <Tooltip content="AI가 답변을 생성하는데 걸린 시간">
                    <span className="cursor-help">LLM: {generateResult.llmLatencyMs}ms</span>
                  </Tooltip>
                  <Tooltip content="사용된 AI 모델">
                    <span className="rounded bg-purple-100 px-2 py-0.5 text-xs text-purple-700 cursor-help">
                      {generateResult.model}
                    </span>
                  </Tooltip>
                </div>
              </div>
            </div>
            <div className="p-6">
              <div className="prose max-w-none">
                <p className="whitespace-pre-wrap text-gray-700">{generateResult.answer}</p>
              </div>

              {/* Feedback Buttons */}
              <div className="mt-4 flex items-center gap-2 border-t border-gray-200 pt-4">
                <span className="text-sm text-gray-500">답변 품질:</span>
                {feedbackSubmitted.generate ? (
                  <span className={cn(
                    'flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm',
                    feedbackSubmitted.generate === 'good'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-red-100 text-red-700'
                  )}>
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
                      onClick={() => handleFeedback('generate', 'good')}
                      disabled={feedbackMutation.isPending}
                      className="flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-green-50 hover:border-green-300 hover:text-green-700 disabled:opacity-50"
                    >
                      <ThumbsUp className="h-4 w-4" />
                      좋음
                    </button>
                    <button
                      onClick={() => handleFeedback('generate', 'bad')}
                      disabled={feedbackMutation.isPending}
                      className="flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-red-50 hover:border-red-300 hover:text-red-700 disabled:opacity-50"
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
                참조 문헌 ({generateResult.references.length})
              </h2>
              <p className="mt-0.5 text-xs text-gray-500">
                답변 생성에 사용된 논문 출처입니다. AI가 이 내용들을 참고하여 답변했습니다.
              </p>
            </div>
            <div className="divide-y divide-gray-200">
              {generateResult.references.map((ref, index) => (
                <div key={index} className="p-4">
                  <div className="flex items-start gap-2">
                    <span className="rounded bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700">
                      [{index + 1}]
                    </span>
                    <div className="flex-1">
                      <div className="font-medium text-gray-900">{ref.title}</div>
                      <div className="mt-1 text-xs text-gray-500">
                        섹션: {ref.section} | score: {ref.score.toFixed(4)}
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
          {generateResult.tokensUsed && (
            <div className="rounded-lg bg-gray-50 px-6 py-4 text-sm text-gray-600">
              <div className="flex items-center gap-1">
                <span className="font-medium">토큰 사용량</span>
                <Tooltip content="LLM API 사용량 - 토큰이 많을수록 비용 증가">
                  <HelpCircle className="h-3.5 w-3.5 text-gray-400 cursor-help" />
                </Tooltip>
                <span className="ml-1">:</span>
              </div>
              <div className="mt-1 flex items-center gap-4">
                <Tooltip content="질문 + 검색된 문서 내용 (입력)">
                  <span className="cursor-help">Prompt: {generateResult.tokensUsed.prompt.toLocaleString()}</span>
                </Tooltip>
                <Tooltip content="AI가 생성한 답변 (출력)">
                  <span className="cursor-help">Completion: {generateResult.tokensUsed.completion.toLocaleString()}</span>
                </Tooltip>
                <span className="font-medium">
                  Total: {(generateResult.tokensUsed.prompt + generateResult.tokensUsed.completion).toLocaleString()}
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* A/B Compare Results */}
      {mode === 'compare' && (compareResults.withReranker || compareResults.withoutReranker) && (
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
              {compareMutation.isPending ? (
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
                      <p className="mt-1 line-clamp-2 text-sm text-gray-700">
                        {chunk.paperTitle}
                      </p>
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
              {compareMutation.isPending ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-6 w-6 animate-spin text-green-500" />
                </div>
              ) : compareResults.withReranker ? (
                <div className="max-h-[500px] overflow-y-auto">
                  {compareResults.withReranker.chunks.slice(0, 5).map((chunk, index) => {
                    const score = chunk.rerankScore ?? chunk.score;
                    const relevance = getRelevanceLevel(score);
                    const style = relevanceStyles[relevance];

                    return (
                      <div key={index} className={cn(
                        'border-b border-gray-100 p-3 last:border-0',
                        relevance === 'irrelevant' && 'opacity-50 bg-gray-50'
                      )}>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded bg-blue-100 px-1.5 py-0.5 text-xs font-medium text-blue-700">
                            #{index + 1}
                          </span>
                          <span className={cn(
                            'rounded px-1.5 py-0.5 text-xs',
                            style.bg,
                            style.text
                          )}>
                            rerank: {score.toFixed(4)}
                          </span>
                          {chunk.originalScore !== undefined && (
                            <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500">
                              원본: {chunk.originalScore.toFixed(4)}
                            </span>
                          )}
                        </div>
                        <p className="mt-1 line-clamp-2 text-sm text-gray-700">
                          {chunk.paperTitle}
                        </p>
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
                    <span className="font-medium">{compareResults.withoutReranker.searchLatencyMs}ms</span>
                    {' → '}
                    <span className="text-green-600">ON:</span>{' '}
                    <span className="font-medium">
                      {compareResults.withReranker.searchLatencyMs +
                        (compareResults.withReranker.rerankLatencyMs || 0)}ms
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
                      {(compareResults.withReranker.chunks[0]?.rerankScore ??
                        compareResults.withReranker.chunks[0]?.score)?.toFixed(4) || '-'}
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
                      {compareResults.withReranker.chunks.filter(
                        (c) => (c.rerankScore ?? c.score) >= SCORE_THRESHOLDS.LOW
                      ).length}
                      /{compareResults.withReranker.chunks.length}
                    </span>
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Error State */}
      {errorInfo && (
        <div className={cn(
          'rounded-lg p-6',
          errorInfo.type === 'no_data' ? 'bg-yellow-50 border border-yellow-200' : 'bg-red-50 border border-red-200'
        )}>
          <div className="flex items-start gap-3">
            <AlertTriangle className={cn(
              'h-6 w-6 flex-shrink-0',
              errorInfo.type === 'no_data' ? 'text-yellow-600' : 'text-red-600'
            )} />
            <div>
              <h3 className={cn(
                'font-medium',
                errorInfo.type === 'no_data' ? 'text-yellow-800' : 'text-red-800'
              )}>
                {errorInfo.type === 'no_data' ? '데이터 준비 필요' : '오류 발생'}
              </h3>
              <p className={cn(
                'mt-1 text-sm',
                errorInfo.type === 'no_data' ? 'text-yellow-700' : 'text-red-700'
              )}>
                {errorInfo.message}
              </p>
              {errorInfo.type === 'no_data' && (
                <Link
                  href="/papers"
                  className="mt-3 inline-flex items-center gap-1 rounded-md bg-yellow-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-yellow-700"
                >
                  Papers 페이지로 이동
                </Link>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!searchResult && !generateResult && !compareResults.withReranker && !compareResults.withoutReranker && !isLoading && !errorInfo && (
        <div className="rounded-lg bg-gray-50 py-12 text-center">
          <FlaskConical className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-4 text-lg font-medium text-gray-900">
            테스트 준비 완료
          </h3>
          <p className="mt-2 text-sm text-gray-500">
            위에서 질문을 입력하고 테스트를 실행하세요
          </p>
        </div>
      )}
    </div>
  );
}
