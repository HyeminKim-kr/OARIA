"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Search,
  Bot,
  MessageSquare,
  BarChart3,
  ArrowLeft,
  Calendar,
  Beaker,
  Trash2,
  ChevronLeft,
  ChevronRight,
  Loader2,
  AlertCircle,
  FileText,
  Eye,
} from "lucide-react";
import {
  studyPlanApi,
  StudyPlanListItem,
  PaginatedStudyPlans,
  StudyPlanFullResponse,
} from "@/lib/api";

export default function StudyPlanHistoryPage() {
  const [studyPlans, setStudyPlans] = useState<StudyPlanListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pagination, setPagination] = useState({
    page: 1,
    size: 10,
    total: 0,
    pages: 1,
  });

  // 상세 모달
  const [selectedPlan, setSelectedPlan] = useState<StudyPlanFullResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // 삭제 확인
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  // 목록 불러오기
  const fetchStudyPlans = async (page: number = 1) => {
    setLoading(true);
    setError(null);

    try {
      const response = await studyPlanApi.list(page, pagination.size);
      const data: PaginatedStudyPlans = response.data;
      setStudyPlans(data.items);
      setPagination({
        page: data.page,
        size: data.size,
        total: data.total,
        pages: data.pages,
      });
    } catch (err) {
      console.error("Failed to fetch study plans:", err);
      setError("Study Plan 목록을 불러오는데 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  // 상세 조회
  const fetchDetail = async (id: string) => {
    setDetailLoading(true);
    try {
      const response = await studyPlanApi.get(id);
      setSelectedPlan(response.data);
    } catch (err) {
      console.error("Failed to fetch study plan detail:", err);
      alert("상세 정보를 불러오는데 실패했습니다.");
    } finally {
      setDetailLoading(false);
    }
  };

  // 삭제
  const handleDelete = async (id: string) => {
    setDeleting(true);
    try {
      await studyPlanApi.delete(id);
      setDeleteConfirm(null);
      // 목록 새로고침
      fetchStudyPlans(pagination.page);
    } catch (err) {
      console.error("Failed to delete study plan:", err);
      alert("삭제에 실패했습니다.");
    } finally {
      setDeleting(false);
    }
  };

  useEffect(() => {
    fetchStudyPlans();
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

  // 상태 뱃지
  const getStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return (
          <span className="px-2 py-0.5 rounded-full bg-green-500/10 text-green-600 text-xs font-medium">
            완료
          </span>
        );
      case "error":
        return (
          <span className="px-2 py-0.5 rounded-full bg-red-500/10 text-red-600 text-xs font-medium">
            오류
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded-full bg-gray-500/10 text-gray-600 text-xs font-medium">
            {status}
          </span>
        );
    }
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
              Agents로 돌아가기
            </Link>
            <h1 className="font-[family-name:var(--font-outfit)] text-2xl font-semibold">
              Study Plan 기록
            </h1>
            <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] mt-1">
              과거에 생성한 실험 설계 계획서를 확인할 수 있습니다.
            </p>
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
                onClick={() => fetchStudyPlans()}
                className="mt-4 px-4 py-2 rounded-lg bg-[var(--oaria-teal)] text-white text-sm font-medium hover:bg-[var(--oaria-teal-dark)] transition-colors"
              >
                다시 시도
              </button>
            </div>
          )}

          {/* Empty State */}
          {!loading && !error && studyPlans.length === 0 && (
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
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[var(--oaria-teal)] text-white font-[family-name:var(--font-dm-sans)] font-medium hover:bg-[var(--oaria-teal-dark)] transition-colors"
              >
                <Beaker size={18} />
                실험 계획 시작하기
              </Link>
            </div>
          )}

          {/* List */}
          {!loading && !error && studyPlans.length > 0 && (
            <>
              <div className="space-y-3">
                {studyPlans.map((plan) => (
                  <div
                    key={plan.id}
                    className="p-4 rounded-xl border-2 border-[var(--oaria-border)] bg-[var(--background)] hover:border-[var(--oaria-teal)]/30 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-4">
                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          {getStatusBadge(plan.status)}
                          <span className="text-xs text-[var(--oaria-text-secondary)] flex items-center gap-1">
                            <Calendar size={12} />
                            {formatDate(plan.created_at)}
                          </span>
                        </div>
                        <p className="font-[family-name:var(--font-dm-sans)] text-sm font-medium line-clamp-2 mb-2">
                          {plan.hypothesis_input}
                        </p>
                        <div className="flex items-center gap-4 text-xs text-[var(--oaria-text-secondary)]">
                          <span className="flex items-center gap-1">
                            <Beaker size={12} />
                            실험 {plan.experiment_count}개
                          </span>
                          {plan.quality_score && (
                            <span>품질 점수: {(plan.quality_score * 100).toFixed(0)}%</span>
                          )}
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <button
                          type="button"
                          onClick={() => fetchDetail(plan.id)}
                          className="p-2 rounded-lg border border-[var(--oaria-border)] hover:border-[var(--oaria-teal)] hover:text-[var(--oaria-teal)] transition-colors"
                          title="상세 보기"
                        >
                          <Eye size={16} />
                        </button>
                        <button
                          type="button"
                          onClick={() => setDeleteConfirm(plan.id)}
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
                    onClick={() => fetchStudyPlans(pagination.page - 1)}
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
                    onClick={() => fetchStudyPlans(pagination.page + 1)}
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
      {(selectedPlan || detailLoading) && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-[var(--background)] rounded-2xl max-w-3xl w-full max-h-[85vh] overflow-hidden flex flex-col">
            {/* Modal Header */}
            <div className="p-4 border-b border-[var(--oaria-border)] flex items-center justify-between">
              <h2 className="font-[family-name:var(--font-outfit)] text-lg font-semibold">
                Study Plan 상세
              </h2>
              <button
                type="button"
                onClick={() => setSelectedPlan(null)}
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
              ) : selectedPlan ? (
                <div className="space-y-6">
                  {/* Hypothesis */}
                  <div>
                    <h3 className="font-[family-name:var(--font-outfit)] text-sm font-semibold text-[var(--oaria-text-secondary)] mb-2">
                      입력 가설
                    </h3>
                    <p className="font-[family-name:var(--font-dm-sans)] text-sm bg-[var(--oaria-teal)]/5 p-3 rounded-lg">
                      {selectedPlan.hypothesis_input}
                    </p>
                  </div>

                  {/* Executive Summary */}
                  {selectedPlan.executive_summary && (
                    <div>
                      <h3 className="font-[family-name:var(--font-outfit)] text-sm font-semibold text-[var(--oaria-text-secondary)] mb-2">
                        요약
                      </h3>
                      <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] whitespace-pre-wrap">
                        {selectedPlan.executive_summary}
                      </p>
                    </div>
                  )}

                  {/* Statistics */}
                  <div className="grid grid-cols-3 gap-4">
                    <div className="p-3 rounded-lg bg-[var(--oaria-border)]/30 text-center">
                      <p className="text-2xl font-bold text-[var(--oaria-teal)]">
                        {selectedPlan.experiment_count}
                      </p>
                      <p className="text-xs text-[var(--oaria-text-secondary)]">실험 수</p>
                    </div>
                    <div className="p-3 rounded-lg bg-[var(--oaria-border)]/30 text-center">
                      <p className="text-2xl font-bold text-[var(--oaria-teal)]">
                        {selectedPlan.quality_score
                          ? `${(selectedPlan.quality_score * 100).toFixed(0)}%`
                          : "-"}
                      </p>
                      <p className="text-xs text-[var(--oaria-text-secondary)]">품질 점수</p>
                    </div>
                    <div className="p-3 rounded-lg bg-[var(--oaria-border)]/30 text-center">
                      <p className="text-2xl font-bold text-[var(--oaria-teal)]">
                        {selectedPlan.prior_studies_count}
                      </p>
                      <p className="text-xs text-[var(--oaria-text-secondary)]">참고 연구</p>
                    </div>
                  </div>

                  {/* Final Plan */}
                  {selectedPlan.final_plan && (
                    <div>
                      <h3 className="font-[family-name:var(--font-outfit)] text-sm font-semibold text-[var(--oaria-text-secondary)] mb-2">
                        최종 실험 계획
                      </h3>
                      <div className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] whitespace-pre-wrap bg-[var(--oaria-border)]/20 p-4 rounded-lg max-h-[300px] overflow-y-auto">
                        {selectedPlan.final_plan}
                      </div>
                    </div>
                  )}

                  {/* Metadata */}
                  <div className="text-xs text-[var(--oaria-text-secondary)] pt-4 border-t border-[var(--oaria-border)]">
                    <p>생성일: {formatDate(selectedPlan.created_at)}</p>
                    {selectedPlan.total_duration_ms && (
                      <p>소요 시간: {(selectedPlan.total_duration_ms / 1000).toFixed(1)}초</p>
                    )}
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
