"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Search,
  Bot,
  MessageSquare,
  BarChart3,
  ArrowLeft,
  Calendar,
  BookOpen,
  Beaker,
  Trash2,
  ChevronLeft,
  ChevronRight,
  Loader2,
  AlertCircle,
  FileText,
  Eye,
  Clock,
  RotateCcw,
} from "lucide-react";
import {
  agentJobsApi,
  AgentJobListItem,
  AgentJobDetailResponse,
  PaginatedAgentJobs,
} from "@/lib/api";
import { JobStatusBadge, JobProgress, RetryButton } from "@/components/jobs";

export default function StudyPlanHistoryPage() {
  const [jobs, setJobs] = useState<AgentJobListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pagination, setPagination] = useState({
    page: 1,
    size: 10,
    total: 0,
    pages: 1,
  });

  // 상세 모달
  const [selectedJob, setSelectedJob] = useState<AgentJobDetailResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // 삭제 확인
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  // 버전 필터 (null = 전체)
  const [versionFilter, setVersionFilter] = useState<string | null>(null);

  // 목록 불러오기
  const fetchJobs = async (page: number = 1, version?: string | null) => {
    setLoading(true);
    setError(null);

    // version 파라미터가 undefined면 현재 필터 사용
    const filterVersion = version !== undefined ? version : versionFilter;

    try {
      const response = await agentJobsApi.list({
        page,
        size: pagination.size,
        // study_plan으로 시작하는 모든 타입을 가져오려면 필터 없이 조회 후 클라이언트에서 필터링
        // 또는 백엔드에서 prefix 매칭 지원 필요
        agent_type: filterVersion || undefined,
      });
      const data: PaginatedAgentJobs = response.data;

      // study_plan 관련 작업만 필터링 (서버에서 필터 없이 조회한 경우)
      let filteredItems = data.items;
      if (!filterVersion) {
        filteredItems = data.items.filter((job) =>
          job.agent_type.startsWith("study_plan")
        );
      }

      setJobs(filteredItems);
      setPagination({
        page: data.page,
        size: data.size,
        total: filterVersion ? data.total : filteredItems.length,
        pages: data.pages,
      });
    } catch (err) {
      console.error("Failed to fetch agent jobs:", err);
      setError("작업 목록을 불러오는데 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  // 버전 필터 변경
  const handleVersionFilterChange = (version: string | null) => {
    setVersionFilter(version);
    fetchJobs(1, version);
  };

  // 상세 조회
  const fetchDetail = async (id: string) => {
    setDetailLoading(true);
    try {
      const response = await agentJobsApi.get(id);
      setSelectedJob(response.data);
    } catch (err) {
      console.error("Failed to fetch job detail:", err);
      alert("상세 정보를 불러오는데 실패했습니다.");
    } finally {
      setDetailLoading(false);
    }
  };

  // 삭제
  const handleDelete = async (id: string) => {
    setDeleting(true);
    try {
      await agentJobsApi.delete(id);
      setDeleteConfirm(null);
      // 목록 새로고침
      fetchJobs(pagination.page);
    } catch (err) {
      console.error("Failed to delete job:", err);
      alert("삭제에 실패했습니다.");
    } finally {
      setDeleting(false);
    }
  };

  // 재시도
  const handleRetry = async (id: string) => {
    try {
      await agentJobsApi.retry(id);
      fetchJobs(pagination.page);
    } catch (err) {
      console.error("Failed to retry job:", err);
      alert("재시도에 실패했습니다.");
    }
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  // 날짜 포맷
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString("ko-KR", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // 소요 시간 포맷
  const formatDuration = (ms: number | null) => {
    if (!ms) return "-";
    const seconds = ms / 1000;
    if (seconds < 60) return `${seconds.toFixed(1)}초`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}분 ${remainingSeconds.toFixed(0)}초`;
  };

  // input_data에서 가설 추출
  const getHypothesis = (job: AgentJobListItem | AgentJobDetailResponse) => {
    if ("input_data" in job && job.input_data) {
      return (job.input_data as Record<string, unknown>).hypothesis as string || job.job_name || "제목 없음";
    }
    return job.job_name || "제목 없음";
  };

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header with Tabs - Fixed */}
      <div className="bg-[var(--background)]">
        <div className="flex items-center justify-center">
          <div className="flex items-center gap-6">
            <Link
              href="/ask"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
            >
              <MessageSquare size={20} />
              Ask AI
            </Link>
            <Link
              href="/main"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
            >
              <Search size={20} />
              Search Papers
            </Link>
            <Link
              href="/agents"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-[var(--oaria-teal)] text-[var(--oaria-teal)]"
            >
              <Bot size={20} />
              Agents
            </Link>
            <Link
              href="/dashboard"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
            >
              <BarChart3 size={20} />
              Dashboard
            </Link>
          </div>
        </div>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-6 py-8">
          {/* Back Link & Title */}
          <div className="mb-8">
            <Link
              href="/agents"
              className="inline-flex items-center gap-1 text-sm text-[var(--oaria-text-secondary)] hover:text-[var(--oaria-teal)] transition-colors mb-4"
            >
              <ArrowLeft size={16} />
              모든 에이전트
            </Link>
            <h1 className="font-[family-name:var(--font-outfit)] text-2xl font-semibold">
              Study Plan 기록
            </h1>
            <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] mt-1">
              과거에 생성한 실험 설계 계획서를 확인할 수 있습니다.
            </p>

            {/* 버전 필터 */}
            {/* 버전 필터 제거 - v4 ReAct만 사용 */}
          </div>

          {/* Loading */}
          {loading && (
            <div className="flex items-center justify-center py-16">
              <Loader2 size={32} className="animate-spin text-[var(--oaria-teal)]" />
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <AlertCircle size={48} className="text-red-500 mb-4" />
              <p className="text-[var(--oaria-text-secondary)]">{error}</p>
              <button
                type="button"
                onClick={() => fetchJobs()}
                className="mt-4 px-4 py-2 rounded-lg bg-[var(--oaria-teal)] text-white text-sm font-medium hover:bg-[var(--oaria-teal)]/80 transition-colors"
              >
                다시 시도
              </button>
            </div>
          )}

          {/* Empty State */}
          {!loading && !error && jobs.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="w-16 h-16 rounded-full bg-[var(--oaria-teal)]/10 flex items-center justify-center mb-4">
                <FileText size={28} className="text-[var(--oaria-teal)]" />
              </div>
              <h3 className="font-[family-name:var(--font-outfit)] text-lg font-semibold mb-2">
                아직 기록이 없습니다
              </h3>
              <p className="text-sm text-[var(--oaria-text-secondary)] mb-6">
                Study Plan Agent로 첫 번째 실험 계획을 생성해보세요.
              </p>
              <Link
                href="/agents/study-plan"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[var(--oaria-teal)] text-white font-[family-name:var(--font-dm-sans)] font-medium hover:bg-[var(--oaria-teal)]/80 transition-colors"
              >
                <BookOpen size={18} />
                실험 계획 시작하기
              </Link>
            </div>
          )}

          {/* List */}
          {!loading && !error && jobs.length > 0 && (
            <>
              <div className="space-y-3">
                {jobs.map((job) => (
                  <div
                    key={job.id}
                    className="p-4 rounded-xl border-2 border-[var(--oaria-border)] bg-[var(--background)] hover:border-[var(--oaria-teal)]/30 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-4">
                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2 flex-wrap">
                          <JobStatusBadge status={job.status} size="sm" />
                          <span className="px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700">
                            ReAct
                          </span>
                          <span className="text-xs text-[var(--oaria-text-secondary)] flex items-center gap-1">
                            <Calendar size={12} />
                            {formatDate(job.created_at)}
                          </span>
                        </div>
                        <p className="font-[family-name:var(--font-dm-sans)] text-sm font-medium line-clamp-2 mb-2">
                          {job.job_name || "제목 없음"}
                        </p>

                        {/* Progress for running jobs */}
                        {job.status === "running" && (
                          <div className="mb-2">
                            <JobProgress percent={job.progress_percent} size="sm" />
                          </div>
                        )}

                        <div className="flex items-center gap-4 text-xs text-[var(--oaria-text-secondary)]">
                          <span className="flex items-center gap-1">
                            <Beaker size={12} />
                            실험 {job.experiment_count}개
                          </span>
                          {job.approval_required && (
                            <span className="text-yellow-600">승인 필요</span>
                          )}
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2 flex-shrink-0">
                        {job.status === "failed" && (
                          <RetryButton onRetry={() => handleRetry(job.id)} size="sm" />
                        )}
                        <button
                          type="button"
                          onClick={() => fetchDetail(job.id)}
                          className="p-2 rounded-lg border border-[var(--oaria-border)] hover:border-[var(--oaria-teal)] hover:text-[var(--oaria-teal)] transition-colors"
                          title="상세 보기"
                        >
                          <Eye size={16} />
                        </button>
                        <button
                          type="button"
                          onClick={() => setDeleteConfirm(job.id)}
                          className="p-2 rounded-lg border border-[var(--oaria-border)] hover:border-red-500 hover:text-red-500 transition-colors"
                          title="삭제"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Pagination */}
              {pagination.pages > 1 && (
                <div className="flex items-center justify-center gap-2 mt-8">
                  <button
                    type="button"
                    onClick={() => fetchJobs(pagination.page - 1)}
                    disabled={pagination.page <= 1}
                    className="p-2 rounded-lg border border-[var(--oaria-border)] disabled:opacity-50 disabled:cursor-not-allowed hover:border-[var(--oaria-teal)] transition-colors"
                  >
                    <ChevronLeft size={18} />
                  </button>
                  <span className="px-4 py-2 text-sm font-medium">
                    {pagination.page} / {pagination.pages}
                  </span>
                  <button
                    type="button"
                    onClick={() => fetchJobs(pagination.page + 1)}
                    disabled={pagination.page >= pagination.pages}
                    className="p-2 rounded-lg border border-[var(--oaria-border)] disabled:opacity-50 disabled:cursor-not-allowed hover:border-[var(--oaria-teal)] transition-colors"
                  >
                    <ChevronRight size={18} />
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Detail Modal */}
      {(selectedJob || detailLoading) && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-[var(--background)] rounded-2xl max-w-3xl w-full max-h-[85vh] overflow-hidden flex flex-col">
            {/* Modal Header */}
            <div className="p-4 border-b border-[var(--oaria-border)] flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h2 className="font-[family-name:var(--font-outfit)] text-lg font-semibold">
                  Study Plan 상세
                </h2>
                {selectedJob && <JobStatusBadge status={selectedJob.status} />}
              </div>
              <button
                type="button"
                onClick={() => setSelectedJob(null)}
                className="p-2 rounded-lg hover:bg-[var(--oaria-border)] transition-colors"
              >
                &times;
              </button>
            </div>

            {/* Modal Content */}
            <div className="flex-1 overflow-y-auto p-4">
              {detailLoading ? (
                <div className="flex items-center justify-center py-16">
                  <Loader2 size={32} className="animate-spin text-[var(--oaria-teal)]" />
                </div>
              ) : selectedJob ? (
                <div className="space-y-6">
                  {/* Hypothesis */}
                  <div>
                    <h3 className="font-[family-name:var(--font-outfit)] text-sm font-semibold text-[var(--oaria-text-secondary)] mb-2">
                      입력 가설
                    </h3>
                    <p className="font-[family-name:var(--font-dm-sans)] text-sm bg-[var(--oaria-teal)]/5 p-3 rounded-lg">
                      {getHypothesis(selectedJob)}
                    </p>
                  </div>

                  {/* Executive Summary */}
                  {selectedJob.executive_summary && (
                    <div>
                      <h3 className="font-[family-name:var(--font-outfit)] text-sm font-semibold text-[var(--oaria-text-secondary)] mb-2">
                        요약
                      </h3>
                      <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] whitespace-pre-wrap">
                        {selectedJob.executive_summary}
                      </p>
                    </div>
                  )}

                  {/* Progress for running jobs */}
                  {selectedJob.status === "running" ? (
                    <div>
                      <h3 className="font-[family-name:var(--font-outfit)] text-sm font-semibold text-[var(--oaria-text-secondary)] mb-2">
                        진행 상황
                      </h3>
                      <JobProgress
                        percent={selectedJob.progress_percent}
                        detail={selectedJob.progress_detail ?? selectedJob.current_step ?? undefined}
                      />
                    </div>
                  ) : null}

                  {/* Error for failed jobs */}
                  {selectedJob.status === "failed" && selectedJob.last_error_message && (
                    <div className="p-4 rounded-lg bg-red-50 border border-red-200">
                      <div className="flex items-center gap-2 text-red-600 mb-2">
                        <AlertCircle size={16} />
                        <span className="font-medium">오류 발생</span>
                      </div>
                      <p className="text-sm text-red-700">{selectedJob.last_error_message}</p>
                      {selectedJob.attempt_count > 0 && (
                        <p className="text-xs text-red-600 mt-2">
                          시도 횟수: {selectedJob.attempt_count} / {selectedJob.max_attempts}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Statistics */}
                  <div className="grid grid-cols-3 gap-4">
                    <div className="p-3 rounded-lg bg-[var(--oaria-border)]/30 text-center">
                      <p className="text-2xl font-bold text-[var(--oaria-teal)]">
                        {selectedJob.experiment_count}
                      </p>
                      <p className="text-xs text-[var(--oaria-text-secondary)]">실험 수</p>
                    </div>
                    <div className="p-3 rounded-lg bg-[var(--oaria-border)]/30 text-center">
                      <p className="text-2xl font-bold text-[var(--oaria-teal)]">
                        {selectedJob.progress_percent}%
                      </p>
                      <p className="text-xs text-[var(--oaria-text-secondary)]">진행률</p>
                    </div>
                    <div className="p-3 rounded-lg bg-[var(--oaria-border)]/30 text-center">
                      <p className="text-2xl font-bold text-[var(--oaria-teal)]">
                        {formatDuration(selectedJob.total_duration_ms)}
                      </p>
                      <p className="text-xs text-[var(--oaria-text-secondary)]">소요 시간</p>
                    </div>
                  </div>

                  {/* Final Plan */}
                  {(() => {
                    const resultData = selectedJob.result_data as Record<string, string> | null;
                    if (!resultData?.final_plan) return null;
                    return (
                      <div>
                        <h3 className="font-[family-name:var(--font-outfit)] text-sm font-semibold text-[var(--oaria-text-secondary)] mb-2">
                          최종 실험 계획
                        </h3>
                        <div className="font-[family-name:var(--font-dm-sans)] text-sm bg-[var(--oaria-border)]/20 p-4 rounded-lg max-h-[300px] overflow-y-auto prose prose-sm max-w-none">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {resultData.final_plan}
                          </ReactMarkdown>
                        </div>
                      </div>
                    );
                  })()}

                  {/* Plan A/B */}
                  {(() => {
                    const resultData = selectedJob.result_data as Record<string, string> | null;
                    if (!resultData?.plan_a) return null;
                    return (
                      <div className="space-y-4">
                        <div>
                          <h3 className="font-[family-name:var(--font-outfit)] text-sm font-semibold text-[var(--oaria-text-secondary)] mb-2">
                            Plan A (이상적 설계)
                          </h3>
                          <div className="font-[family-name:var(--font-dm-sans)] text-sm bg-green-50 p-4 rounded-lg max-h-[200px] overflow-y-auto prose prose-sm max-w-none">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {resultData.plan_a}
                            </ReactMarkdown>
                          </div>
                        </div>
                        {resultData.plan_b && (
                          <div>
                            <h3 className="font-[family-name:var(--font-outfit)] text-sm font-semibold text-[var(--oaria-text-secondary)] mb-2">
                              Plan B (현실적 대안)
                            </h3>
                            <div className="font-[family-name:var(--font-dm-sans)] text-sm bg-blue-50 p-4 rounded-lg max-h-[200px] overflow-y-auto prose prose-sm max-w-none">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {resultData.plan_b}
                              </ReactMarkdown>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })()}

                  {/* Metadata */}
                  <div className="text-xs text-[var(--oaria-text-secondary)] pt-4 border-t border-[var(--oaria-border)]">
                    <div className="grid grid-cols-2 gap-2">
                      <p>생성일: {formatDate(selectedJob.created_at)}</p>
                      {selectedJob.started_at && (
                        <p>시작: {formatDate(selectedJob.started_at)}</p>
                      )}
                      {selectedJob.completed_at && (
                        <p>완료: {formatDate(selectedJob.completed_at)}</p>
                      )}
                      <p>에이전트: {selectedJob.agent_type}</p>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirm Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-[var(--background)] rounded-2xl max-w-sm w-full p-6 text-center">
            <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center mx-auto mb-4">
              <Trash2 size={24} className="text-red-500" />
            </div>
            <h3 className="font-[family-name:var(--font-outfit)] text-lg font-semibold mb-2">
              삭제하시겠습니까?
            </h3>
            <p className="text-sm text-[var(--oaria-text-secondary)] mb-6">
              이 작업은 되돌릴 수 없습니다.
            </p>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setDeleteConfirm(null)}
                disabled={deleting}
                className="flex-1 px-4 py-2.5 rounded-xl border-2 border-[var(--oaria-border)] font-medium hover:bg-[var(--oaria-border)]/50 transition-colors disabled:opacity-50"
              >
                취소
              </button>
              <button
                type="button"
                onClick={() => handleDelete(deleteConfirm)}
                disabled={deleting}
                className="flex-1 px-4 py-2.5 rounded-xl bg-red-500 text-white font-medium hover:bg-red-600 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {deleting && <Loader2 size={16} className="animate-spin" />}
                삭제
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
