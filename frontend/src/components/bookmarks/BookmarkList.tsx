"use client";

import { useState } from "react";
import Link from "next/link";
import { Bookmark, Loader2, ChevronLeft, ChevronRight } from "lucide-react";
import { useMyBookmarks, useMyCollections } from "@/hooks";

export function BookmarkList() {
  const [selectedCollectionId, setSelectedCollectionId] = useState<string | undefined>(undefined);
  const [page, setPage] = useState(1);
  const limit = 20;

  const { data: collections } = useMyCollections();
  const { data: bookmarksData, isLoading } = useMyBookmarks(page, limit, selectedCollectionId);

  const totalPages = bookmarksData ? Math.ceil(bookmarksData.total / limit) : 0;

  return (
    <div className="space-y-4">
      {/* Collection Tabs */}
      {collections && collections.items.length > 0 && (
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => { setSelectedCollectionId(undefined); setPage(1); }}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
              !selectedCollectionId
                ? "bg-[var(--oaria-teal)] text-white"
                : "bg-[var(--oaria-border)]/30 text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50"
            }`}
          >
            전체
          </button>
          {collections.items.map((col) => (
            <button
              key={col.id}
              onClick={() => { setSelectedCollectionId(col.id); setPage(1); }}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                selectedCollectionId === col.id
                  ? "bg-[var(--oaria-teal)] text-white"
                  : "bg-[var(--oaria-border)]/30 text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50"
              }`}
            >
              {col.name} ({col.bookmark_count})
            </button>
          ))}
        </div>
      )}

      {/* Bookmark List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-[var(--oaria-teal)]" />
        </div>
      ) : bookmarksData && bookmarksData.items.length > 0 ? (
        <>
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

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-4 pt-4">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50 disabled:opacity-40"
              >
                <ChevronLeft size={16} />
                이전
              </button>
              <span className="text-sm text-[var(--oaria-text-secondary)]">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50 disabled:opacity-40"
              >
                다음
                <ChevronRight size={16} />
              </button>
            </div>
          )}
        </>
      ) : (
        <div className="rounded-xl border-2 border-[var(--oaria-border-strong)] bg-[var(--background)] p-8 text-center">
          <Bookmark size={48} className="mx-auto mb-4 text-[var(--oaria-tagline)]" />
          <p className="text-[var(--oaria-text-secondary)]">북마크한 논문이 없습니다.</p>
        </div>
      )}
    </div>
  );
}
