"use client";

import { useState, useEffect } from "react";
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
} from "lucide-react";
import { papersApi } from "@/lib/api";
import { PaperCard } from "@/components/papers";

export default function MainPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [activeTab, setActiveTab] = useState<"papers" | "agents">("papers");
  const [activeFilter, setActiveFilter] = useState<"recent" | "recommended" | "bookmark">(
    "recent"
  );

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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // 검색은 debounce로 자동 처리됨
  };

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header with Toggle - Fixed */}
      <div className="bg-[var(--background)]">
        <div className="flex items-center justify-center py-4">
          {/* Ask/Search Toggle */}
          <div className="inline-flex items-center bg-[var(--oaria-border)]/50 rounded-full p-1">
            <Link
              href="/ask"
              className="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-all"
            >
              <MessageSquare size={16} />
              Ask AI
            </Link>
            <button
              type="button"
              className="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium bg-[var(--oaria-teal)] text-white shadow-sm"
            >
              <Search size={16} />
              Search Papers
            </button>
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

          {/* Tabs */}
          <div className="flex items-center justify-center gap-6 mb-4 border-b-2 border-[var(--oaria-border-strong)]">
            <button
              onClick={() => setActiveTab("papers")}
              className={`flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 transition-colors ${
                activeTab === "papers"
                  ? "border-[var(--oaria-teal)] text-[var(--oaria-teal)]"
                  : "border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)]"
              }`}
            >
              <FileText size={20} />
              Papers
            </button>
            <button
              onClick={() => setActiveTab("agents")}
              className={`flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 transition-colors ${
                activeTab === "agents"
                  ? "border-[var(--oaria-teal)] text-[var(--oaria-teal)]"
                  : "border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)]"
              }`}
            >
              <Bot size={20} />
              에이전트
            </button>
          </div>

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
          <div className="space-y-3">
            {isLoading ? (
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
            ) : error ? (
              // Error state
              <div className="rounded-xl border-2 border-red-200 bg-red-50 p-8 text-center">
                <p className="text-red-600">논문을 불러오는 중 오류가 발생했습니다.</p>
                <p className="mt-2 text-sm text-red-400">잠시 후 다시 시도해 주세요.</p>
              </div>
            ) : papers && papers.length > 0 ? (
              // Paper list
              papers.map((paper) => <PaperCard key={paper.id} paper={paper} />)
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
    </div>
  );
}
