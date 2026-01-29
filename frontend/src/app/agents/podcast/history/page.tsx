"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  Search,
  Bot,
  MessageSquare,
  BarChart3,
  Loader2,
  ArrowLeft,
  Mic2,
  Clock,
  Trash2,
  ChevronLeft,
  ChevronRight,
  FileText,
  Calendar,
  AlertCircle,
} from "lucide-react";
import { podcastApi, PodcastEpisode } from "@/lib/api";

export default function PodcastHistoryPage() {
  const [episodes, setEpisodes] = useState<PodcastEpisode[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  // Fetch episodes
  useEffect(() => {
    const fetchEpisodes = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await podcastApi.list(page, 10);
        setEpisodes(response.data.items);
        setTotalPages(response.data.pages);
      } catch (err) {
        console.error("Failed to fetch episodes:", err);
        setError("에피소드를 불러오는 중 오류가 발생했습니다.");
      } finally {
        setIsLoading(false);
      }
    };

    fetchEpisodes();
  }, [page]);

  // Delete episode
  const handleDelete = async (id: string) => {
    try {
      await podcastApi.delete(id);
      setEpisodes(prev => prev.filter(ep => ep.id !== id));
      setDeleteConfirm(null);
    } catch (err) {
      console.error("Failed to delete episode:", err);
    }
  };

  // Format date
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString("ko-KR", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // Format duration
  const formatDuration = (seconds: number | null) => {
    if (!seconds) return "-";
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // Get status badge
  const getStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return (
          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-500/20 text-green-500">
            완료
          </span>
        );
      case "generating":
      case "pending":
        return (
          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-500/20 text-yellow-500">
            생성 중
          </span>
        );
      case "failed":
        return (
          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-500/20 text-red-500">
            실패
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-[var(--oaria-border)] text-[var(--oaria-text-secondary)]">
            {status}
          </span>
        );
    }
  };

  // Get style label
  const getStyleLabel = (style: string) => {
    switch (style) {
      case "two_hosts":
        return "두 호스트 대화";
      case "interview":
        return "인터뷰";
      case "solo":
        return "단독 발표";
      default:
        return style;
    }
  };

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Navigation Tabs */}
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
              className="inline-flex items-center gap-1 text-sm text-[var(--oaria-text-secondary)] hover:text-[var(--oaria-coral)] transition-colors mb-4"
            >
              <ArrowLeft size={16} />
              모든 에이전트
            </Link>
            <div className="flex items-center justify-between">
              <div>
                <h1 className="font-[family-name:var(--font-outfit)] text-2xl font-semibold">
                  Podcast 기록
                </h1>
                <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] mt-1">
                  생성된 팟캐스트 에피소드를 확인할 수 있습니다.
                </p>
              </div>
              <Link
                href="/agents/podcast"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[var(--oaria-coral)] text-white font-[family-name:var(--font-dm-sans)] font-medium hover:bg-[var(--oaria-coral)]/80 transition-colors"
              >
                <Mic2 size={18} />
                새 에피소드 만들기
              </Link>
            </div>
          </div>

          {/* Loading State */}
          {isLoading && (
            <div className="flex items-center justify-center py-20">
              <Loader2 size={32} className="animate-spin text-[var(--oaria-coral)]" />
            </div>
          )}

          {/* Error State */}
          {error && !isLoading && (
            <div className="p-6 rounded-xl border-2 border-red-500/30 bg-red-500/5 text-center">
              <AlertCircle size={32} className="mx-auto mb-3 text-red-500" />
              <p className="font-[family-name:var(--font-dm-sans)] text-sm text-red-500">
                {error}
              </p>
            </div>
          )}

          {/* Empty State */}
          {!isLoading && !error && episodes.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="w-16 h-16 rounded-full bg-[var(--oaria-coral)]/10 flex items-center justify-center mb-4">
                <FileText size={28} className="text-[var(--oaria-coral)]" />
              </div>
              <h3 className="font-[family-name:var(--font-outfit)] text-lg font-semibold mb-2">
                아직 기록이 없습니다
              </h3>
              <p className="text-sm text-[var(--oaria-text-secondary)] mb-6">
                Podcast Agent로 첫 번째 에피소드를 생성해보세요.
              </p>
              <Link
                href="/agents/podcast"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[var(--oaria-coral)] text-white font-[family-name:var(--font-dm-sans)] font-medium hover:bg-[var(--oaria-coral)]/80 transition-colors"
              >
                <Mic2 size={18} />
                팟캐스트 만들기
              </Link>
            </div>
          )}

          {/* Episode List */}
          {!isLoading && !error && episodes.length > 0 && (
            <div className="space-y-3">
              {episodes.map((episode) => (
                <div
                  key={episode.id}
                  className="p-4 rounded-xl border-2 border-[var(--oaria-border)] bg-[var(--background)] hover:border-[var(--oaria-coral)]/30 transition-colors group"
                >
                  <div className="flex items-start justify-between gap-4">
                    {/* Left: Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        {getStatusBadge(episode.status)}
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-[var(--oaria-coral)]/20 text-[var(--oaria-coral)]">
                          {getStyleLabel(episode.style)}
                        </span>
                      </div>
                      <h3 className="font-[family-name:var(--font-outfit)] font-semibold mb-1 truncate">
                        {episode.title || episode.goal}
                      </h3>
                      <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] line-clamp-2 mb-3">
                        {episode.description || episode.goal}
                      </p>
                      <div className="flex items-center gap-4 text-xs text-[var(--oaria-text-secondary)]">
                        <span className="flex items-center gap-1">
                          <Calendar size={12} />
                          {formatDate(episode.created_at)}
                        </span>
                        {episode.duration_seconds && (
                          <span className="flex items-center gap-1">
                            <Clock size={12} />
                            {formatDuration(episode.duration_seconds)}
                          </span>
                        )}
                        {episode.paper_ids && episode.paper_ids.length > 0 && (
                          <span className="flex items-center gap-1">
                            <FileText size={12} />
                            {episode.paper_ids.length}개 논문
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Right: Actions */}
                    <div className="flex items-center gap-2">
                      {deleteConfirm === episode.id ? (
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleDelete(episode.id)}
                            className="px-3 py-1.5 rounded-lg bg-red-500 text-white text-xs font-medium hover:bg-red-600 transition-colors"
                          >
                            삭제
                          </button>
                          <button
                            onClick={() => setDeleteConfirm(null)}
                            className="px-3 py-1.5 rounded-lg border border-[var(--oaria-border)] text-xs font-medium hover:bg-[var(--oaria-border)]/50 transition-colors"
                          >
                            취소
                          </button>
                        </div>
                      ) : (
                        <>
                          <button
                            onClick={() => setDeleteConfirm(episode.id)}
                            className="p-2 rounded-lg text-[var(--oaria-text-secondary)] hover:text-red-500 hover:bg-red-500/10 transition-colors opacity-0 group-hover:opacity-100"
                          >
                            <Trash2 size={16} />
                          </button>
                          <Link
                            href={`/agents/podcast/${episode.id}`}
                            className="p-2 rounded-lg text-[var(--oaria-text-secondary)] hover:text-[var(--oaria-coral)] hover:bg-[var(--oaria-coral)]/10 transition-colors"
                          >
                            <ChevronRight size={20} />
                          </Link>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-8">
              <button
                type="button"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-2 rounded-lg border border-[var(--oaria-border)] disabled:opacity-50 disabled:cursor-not-allowed hover:border-[var(--oaria-coral)] transition-colors"
              >
                <ChevronLeft size={18} />
              </button>
              <span className="px-4 py-2 text-sm font-medium">
                {page} / {totalPages}
              </span>
              <button
                type="button"
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="p-2 rounded-lg border border-[var(--oaria-border)] disabled:opacity-50 disabled:cursor-not-allowed hover:border-[var(--oaria-coral)] transition-colors"
              >
                <ChevronRight size={18} />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
