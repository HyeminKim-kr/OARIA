"use client";

import { useState } from "react";
import {
  Search,
  Paperclip,
  History,
  ArrowUp,
  FileText,
  Bot,
  Filter,
  Clock,
  Flame,
  Sparkles,
  ThumbsUp,
  Bookmark,
  Link2,
  ChevronRight,
  MessageSquare,
} from "lucide-react";

// 임시 논문 데이터
const mockPapers = [
  {
    id: 1,
    title:
      "Immunotherapy Response Prediction in Non-Small Cell Lung Cancer Using Deep Learning",
    date: "28 Dec 2025",
    authors: ["Seoul National University", "Samsung Medical Center"],
    summary:
      "A novel deep learning approach for predicting immunotherapy response in NSCLC patients. The model achieves 89% accuracy using CT imaging and genomic data, outperforming traditional biomarkers like PD-L1 expression...",
    tags: ["#immunotherapy", "#lung-cancer", "#deep-learning"],
    likes: 234,
    hasResources: true,
  },
  {
    id: 2,
    title:
      "CAR-T Cell Therapy Optimization for Solid Tumors: A Comprehensive Review",
    date: "26 Dec 2025",
    authors: ["MD Anderson Cancer Center", "Stanford Medicine"],
    summary:
      "This review examines recent advances in CAR-T cell therapy for solid tumors, addressing key challenges including tumor microenvironment immunosuppression, antigen heterogeneity, and T cell exhaustion...",
    tags: ["#car-t", "#solid-tumors", "#immunotherapy"],
    likes: 892,
    hasResources: true,
  },
  {
    id: 3,
    title:
      "Liquid Biopsy for Early Detection of Pancreatic Cancer: Multi-Center Validation Study",
    date: "24 Dec 2025",
    authors: ["Johns Hopkins University", "Mayo Clinic"],
    summary:
      "A multi-center validation study demonstrating the clinical utility of ctDNA-based liquid biopsy for early pancreatic cancer detection. The assay achieved 94% sensitivity and 98% specificity in a cohort of 2,500 patients...",
    tags: ["#liquid-biopsy", "#pancreatic-cancer", "#early-detection"],
    likes: 1205,
    hasResources: false,
  },
];


export default function ChatPage() {
  const [query, setQuery] = useState("");
  const [searchMode, setSearchMode] = useState<"ask" | "search">("ask");
  const [activeTab, setActiveTab] = useState<"papers" | "agents">("papers");
  const [activeFilter, setActiveFilter] = useState<"recent" | "recommended" | "bookmark">(
    "recent"
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // TODO: 검색 또는 채팅 처리
    console.log("Query:", query);
  };

  return (
    <div className="h-full overflow-y-auto">
      <div style={{ padding: "40px 160px" }}>
        {/* Search Section - 전체 너비 사용 */}
        <div className="mb-10">
            <h1 className="font-[family-name:var(--font-outfit)] text-3xl md:text-4xl font-bold text-center mb-6">
              {searchMode === "ask" ? "Ask AI about research..." : "Search papers..."}
            </h1>

            {/* Ask/Search Toggle */}
            <div className="flex items-center justify-center mb-4">
              <div className="inline-flex items-center bg-[var(--oaria-border)]/30 rounded-full p-1">
                <button
                  type="button"
                  onClick={() => setSearchMode("ask")}
                  className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all ${
                    searchMode === "ask"
                      ? "bg-[var(--oaria-teal)] text-white shadow-sm"
                      : "text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)]"
                  }`}
                >
                  <MessageSquare size={16} />
                  Ask AI
                </button>
                <button
                  type="button"
                  onClick={() => setSearchMode("search")}
                  className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all ${
                    searchMode === "search"
                      ? "bg-[var(--oaria-teal)] text-white shadow-sm"
                      : "text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)]"
                  }`}
                >
                  <Search size={16} />
                  Search Papers
                </button>
              </div>
            </div>

            {/* Search Input */}
            <form onSubmit={handleSubmit}>
              <div
                className="relative bg-[var(--background)] border border-[var(--oaria-border)] rounded-2xl shadow-lg hover:border-[var(--oaria-teal)]/50 focus-within:border-[var(--oaria-teal)] focus-within:ring-2 focus-within:ring-[var(--oaria-teal)]/20 transition-all"
              >
              <div className="flex items-center px-6 py-6">
                {searchMode === "ask" ? (
                  <MessageSquare size={24} className="text-[var(--oaria-teal)] mr-4" />
                ) : (
                  <Search size={24} className="text-[var(--oaria-tagline)] mr-4" />
                )}
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={
                    searchMode === "ask"
                      ? "폐암 면역치료 최신 연구 동향 알려줘..."
                      : "Search by title, author, PMID..."
                  }
                  className="flex-1 bg-transparent font-[family-name:var(--font-dm-sans)] text-lg outline-none placeholder:text-[var(--oaria-tagline)]"
                />
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
                  disabled={!query.trim()}
                  className="w-10 h-10 rounded-full bg-[var(--oaria-teal)] hover:bg-[var(--oaria-light-teal)] disabled:bg-[var(--oaria-border)] disabled:cursor-not-allowed flex items-center justify-center transition-colors"
                >
                  <ArrowUp size={20} className="text-white" />
                </button>
              </div>
              </div>
            </form>
          </div>

          {/* Tabs */}
          <div className="flex items-center justify-center gap-6 mb-4 border-b border-[var(--oaria-border)]">
            <button
              onClick={() => setActiveTab("papers")}
              className={`flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-sm font-medium border-b-2 transition-colors ${
                activeTab === "papers"
                  ? "border-[var(--oaria-teal)] text-[var(--oaria-teal)]"
                  : "border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)]"
              }`}
            >
              <FileText size={18} />
              Papers
            </button>
            <button
              onClick={() => setActiveTab("agents")}
              className={`flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-sm font-medium border-b-2 transition-colors ${
                activeTab === "agents"
                  ? "border-[var(--oaria-teal)] text-[var(--oaria-teal)]"
                  : "border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)]"
              }`}
            >
              <Bot size={18} />
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
            {mockPapers.map((paper) => (
              <article
                key={paper.id}
                className="relative bg-[var(--background)] border border-[var(--oaria-border)] rounded-xl p-5 hover:border-[var(--oaria-teal)]/30 transition-colors group"
              >
                <div className="flex gap-6">
                  <div className="flex-1">
                    <h2 className="font-[family-name:var(--font-outfit)] text-lg font-semibold text-[var(--foreground)] mb-2 group-hover:text-[var(--oaria-teal)] transition-colors cursor-pointer">
                      {paper.title}
                    </h2>
                    <div className="flex items-center gap-3 mb-3 text-sm text-[var(--oaria-tagline)]">
                      <span>{paper.date}</span>
                      <span className="flex items-center gap-1">
                        <span className="text-[var(--oaria-coral)]">•</span>
                        {paper.authors.join(" · ")}
                      </span>
                    </div>
                    <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] mb-4 line-clamp-2">
                      {paper.summary}
                    </p>
                    <div className="flex flex-wrap gap-2 mb-4">
                      {paper.tags.map((tag) => (
                        <span
                          key={tag}
                          className="text-xs text-[var(--oaria-teal)] hover:underline cursor-pointer"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                    <div className="flex items-center gap-4">
                      <button className="flex items-center gap-1.5 text-sm text-[var(--oaria-text-secondary)] hover:text-[var(--oaria-teal)] transition-colors">
                        <ThumbsUp size={16} />
                        {paper.likes}
                      </button>
                      <button className="flex items-center gap-1.5 text-sm text-[var(--oaria-text-secondary)] hover:text-[var(--oaria-teal)] transition-colors">
                        <Bookmark size={16} />
                        Bookmark
                      </button>
                      {paper.hasResources && (
                        <button className="flex items-center gap-1.5 text-sm text-[var(--oaria-text-secondary)] hover:text-[var(--oaria-teal)] transition-colors">
                          <Link2 size={16} />
                          Resources
                        </button>
                      )}
                    </div>
                  </div>
                  {/* Paper Thumbnail */}
                  <div className="hidden md:block w-32 h-40 bg-[var(--oaria-border)]/30 rounded-lg flex-shrink-0 relative overflow-hidden">
                    <div className="absolute top-2 right-2 bg-[var(--oaria-coral)] text-white text-xs px-2 py-0.5 rounded-full flex items-center gap-1">
                      <Flame size={10} />
                      {paper.likes}
                    </div>
                    <div className="h-full flex items-center justify-center">
                      <FileText
                        size={32}
                        className="text-[var(--oaria-tagline)]"
                      />
                    </div>
                  </div>
                </div>
                {/* Arrow Button */}
                <button className="absolute right-4 bottom-4 w-8 h-8 rounded-full bg-[var(--oaria-teal)] text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                  <ChevronRight size={18} />
                </button>
              </article>
            ))}
          </div>
        </div>
      </div>
  );
}
