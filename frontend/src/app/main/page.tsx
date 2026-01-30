"use client";

import { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Search,
  Paperclip,
  History,
  ArrowUp,
  FileText,
  Bot,
  Filter,
  Clock,
  Sparkles,
  Bookmark,
  MessageSquare,
  Loader2,
  BarChart3,
  LogIn,
} from "lucide-react";
import { papersApi } from "@/lib/api";
import { PaperCard } from "@/components/papers";
import { useAuth } from "@/contexts/AuthContext";
import {
  usePaperInteractions,
  useToggleLike,
  useToggleBookmark,
  useMyBookmarks,
} from "@/hooks";
import { LoginPromptModal } from "@/components/common/LoginPromptModal";

export default function MainPage() {
  const { isAuthenticated, login } = useAuth();
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<"recent" | "recommended" | "bookmark">(
    "recent"
  );
  const [showLoginModal, setShowLoginModal] = useState(false);

  // Debounce search query (300ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // 검색어가 있으면 search API, 없으면 recent API
  const { data: papers, isLoading, error } = useQuery({
    queryKey: ["papers", debouncedQuery],
    queryFn: async () => {
      if (debouncedQuery.trim()) {
        const result = await papersApi.search({ q: debouncedQuery, limit: 20 });
        return result.items;
      }
      return papersApi.getRecent(10);
    },
  });

  // 북마크 탭: 내 북마크 목록
  const { data: bookmarksData, isLoading: bookmarksLoading } = useMyBookmarks(
    1,
    20,
    undefined
  );

  // paper IDs for bulk interaction status (only for non-bookmark tabs)
  const paperIds = useMemo(
    () => (papers || []).map((p) => p.id),
    [papers]
  );

  // Bulk interaction status
  const { data: interactionData } = usePaperInteractions(paperIds);

  // Interaction mutations
  const toggleLike = useToggleLike();
  const toggleBookmark = useToggleBookmark();

  const handleLikeClick = (paperId: string) => {
    if (!isAuthenticated) {
      setShowLoginModal(true);
      return;
    }
    toggleLike.mutate(paperId);
  };

  const handleBookmarkClick = (paperId: string) => {
    if (!isAuthenticated) {
      setShowLoginModal(true);
      return;
    }
    toggleBookmark.mutate({ paperId });
  };

  // Build interaction status map (statuses is Record<paper_id, PaperInteractionStatus>)
  const interactionMap = useMemo(() => {
    const map: Record<string, { is_liked: boolean; is_bookmarked: boolean }> = {};
    if (interactionData?.statuses) {
      for (const [paperId, s] of Object.entries(interactionData.statuses)) {
        map[paperId] = { is_liked: s.is_liked, is_bookmarked: s.is_bookmarked };
      }
    }
    return map;
  }, [interactionData]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // 검색은 debounce로 자동 처리됨
  };

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header with Tabs - Fixed */}
      <div className="bg-[var(--background)]">
        <div className="flex items-center justify-center">
          {/* Navigation Tabs */}
          <div className="flex items-center gap-6">
            <Link
              href="/ask"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
            >
              <MessageSquare size={20} />
              Ask AI
            </Link>
            <button
              type="button"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-[var(--oaria-teal)] text-[var(--oaria-teal)]"
            >
              <Search size={20} />
              Search Papers
            </button>
            <Link
              href="/agents"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
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
        <div className="max-w-5xl mx-auto px-6 py-6">
          {/* Search Input */}
          <form onSubmit={handleSubmit} className="mb-8">
              <div
                className="relative bg-[var(--background)] border-2 border-[var(--oaria-border-strong)] rounded-2xl shadow-lg hover:border-[var(--oaria-teal)]/50 focus-within:border-[var(--oaria-teal)] focus-within:ring-2 focus-within:ring-[var(--oaria-teal)]/20 transition-all"
              >
              <div className="flex items-center px-6 py-6">
                <Search size={24} className="text-[var(--oaria-tagline)] mr-4" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search by title, author, PMID..."
                  className="flex-1 bg-transparent font-[family-name:var(--font-dm-sans)] text-lg outline-none placeholder:text-[var(--oaria-tagline)]"
                />
                {isLoading && (
                  <Loader2 size={20} className="animate-spin text-[var(--oaria-teal)] mr-2" />
                )}
              </div>
              <div className="flex items-center justify-between px-6 pb-5">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50 transition-colors"
                  >
                    <Paperclip size={16} />
                  </button>
                  <button
                    type="button"
                    className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50 transition-colors border border-[var(--oaria-border)]"
                  >
                    <History size={16} />
                    History
                  </button>
                </div>
                <button
                  type="submit"
                  disabled={!searchQuery.trim()}
                  className="w-10 h-10 rounded-full bg-[var(--oaria-teal)] hover:bg-[var(--oaria-light-teal)] disabled:bg-[var(--oaria-border)] disabled:cursor-not-allowed flex items-center justify-center transition-colors"
                >
                  <ArrowUp size={20} className="text-white" />
                </button>
              </div>
              </div>
            </form>

          {/* Filters */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <button className="p-2 rounded-lg hover:bg-[var(--oaria-border)]/50 transition-colors text-[var(--oaria-text-secondary)]">
                <Filter size={18} />
              </button>
              <div className="flex items-center bg-[var(--oaria-border)]/30 rounded-lg p-1">
                <button
                  onClick={() => setActiveFilter("recent")}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    activeFilter === "recent"
                      ? "bg-[var(--background)] text-[var(--oaria-teal)] shadow-sm"
                      : "text-[var(--oaria-text-secondary)]"
                  }`}
                >
                  <Clock size={14} />
                  최근
                </button>
                <button
                  onClick={() => setActiveFilter("recommended")}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    activeFilter === "recommended"
                      ? "bg-[var(--background)] text-[var(--oaria-teal)] shadow-sm"
                      : "text-[var(--oaria-text-secondary)]"
                  }`}
                >
                  <Sparkles size={14} />
                  추천
                </button>
                <button
                  onClick={() => setActiveFilter("bookmark")}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    activeFilter === "bookmark"
                      ? "bg-[var(--background)] text-[var(--oaria-teal)] shadow-sm"
                      : "text-[var(--oaria-text-secondary)]"
                  }`}
                >
                  <Bookmark size={14} />
                  북마크
                </button>
              </div>
            </div>
          </div>

          {/* Paper Cards */}
          <div className="space-y-5">
            {activeFilter === "bookmark" && !isAuthenticated ? (
              // 비로그인 상태에서 북마크 탭
              <div className="rounded-xl border-2 border-[var(--oaria-border-strong)] bg-[var(--background)] p-8 text-center">
                <Bookmark size={48} className="mx-auto mb-4 text-[var(--oaria-tagline)]" />
                <p className="mb-2 text-[var(--oaria-text-secondary)]">
                  북마크한 논문을 확인하려면 로그인이 필요합니다.
                </p>
                <button
                  onClick={login}
                  className="mt-4 inline-flex items-center gap-2 rounded-xl bg-[var(--oaria-teal)] px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[var(--oaria-light-teal)]"
                >
                  <LogIn size={16} />
                  로그인
                </button>
              </div>
            ) : (isLoading || (activeFilter === "bookmark" && bookmarksLoading)) ? (
              // Loading skeleton
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="animate-pulse rounded-xl border-2 border-[var(--oaria-border-strong)] bg-[var(--background)] p-5"
                  >
                    <div className="flex gap-6">
                      <div className="flex-1 space-y-3">
                        <div className="h-6 w-3/4 rounded bg-[var(--oaria-border)]" />
                        <div className="h-4 w-1/2 rounded bg-[var(--oaria-border)]" />
                        <div className="space-y-2">
                          <div className="h-4 w-full rounded bg-[var(--oaria-border)]" />
                          <div className="h-4 w-2/3 rounded bg-[var(--oaria-border)]" />
                        </div>
                      </div>
                      <div className="hidden h-40 w-32 rounded-lg bg-[var(--oaria-border)] md:block" />
                    </div>
                  </div>
                ))}
              </div>
            ) : activeFilter === "bookmark" ? (
              // 북마크 탭 (로그인된 상태)
              bookmarksData && bookmarksData.items.length > 0 ? (
                <div className="flex flex-col gap-5">
                  {bookmarksData.items.map((item) => (
                    <Link key={item.bookmark_id} href={`/papers/${item.paper_id}`}>
                      <article className="group relative rounded-xl border-2 border-[var(--oaria-border-strong)] bg-[var(--background)] p-5 transition-colors hover:border-[var(--oaria-teal)]/50 cursor-pointer">
                        <h2 className="mb-2 font-[family-name:var(--font-outfit)] text-lg font-semibold text-[var(--foreground)] transition-colors group-hover:text-[var(--oaria-teal)]">
                          {item.title}
                        </h2>
                        <div className="mb-2 flex items-center gap-3 text-sm text-[var(--oaria-tagline)]">
                          {item.journal && <span>{item.journal}</span>}
                          {item.year && <span>{item.year}</span>}
                          {item.collection_name && (
                            <span className="rounded bg-[var(--oaria-teal)]/10 px-2 py-0.5 text-xs text-[var(--oaria-teal)]">
                              {item.collection_name}
                            </span>
                          )}
                        </div>
                        {item.abstract && (
                          <p className="line-clamp-2 font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)]">
                            {item.abstract}
                          </p>
                        )}
                      </article>
                    </Link>
                  ))}
                </div>
              ) : (
                <div className="rounded-xl border-2 border-[var(--oaria-border-strong)] bg-[var(--background)] p-8 text-center">
                  <Bookmark size={48} className="mx-auto mb-4 text-[var(--oaria-tagline)]" />
                  <p className="text-[var(--oaria-text-secondary)]">북마크한 논문이 없습니다.</p>
                </div>
              )
            ) : error ? (
              // Error state
              <div className="rounded-xl border-2 border-red-200 bg-red-50 p-8 text-center">
                <p className="text-red-600">논문을 불러오는 중 오류가 발생했습니다.</p>
                <p className="mt-2 text-sm text-red-400">잠시 후 다시 시도해 주세요.</p>
              </div>
            ) : papers && papers.length > 0 ? (
              // Paper list
              <div className="flex flex-col gap-5">
                {papers.map((paper) => (
                  <PaperCard
                    key={paper.id}
                    paper={paper}
                    isLiked={interactionMap[paper.id]?.is_liked}
                    isBookmarked={interactionMap[paper.id]?.is_bookmarked}
                    likeCount={paper.like_count}
                    onLikeClick={handleLikeClick}
                    onBookmarkClick={handleBookmarkClick}
                  />
                ))}
              </div>
            ) : (
              // Empty state
              <div className="rounded-xl border-2 border-[var(--oaria-border-strong)] bg-[var(--background)] p-8 text-center">
                <FileText size={48} className="mx-auto mb-4 text-[var(--oaria-tagline)]" />
                <p className="text-[var(--oaria-text-secondary)]">
                  {debouncedQuery
                    ? `"${debouncedQuery}"에 대한 검색 결과가 없습니다.`
                    : "수집된 논문이 없습니다."}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Login Prompt Modal */}
      <LoginPromptModal
        isOpen={showLoginModal}
        onClose={() => setShowLoginModal(false)}
      />
    </div>
  );
}
