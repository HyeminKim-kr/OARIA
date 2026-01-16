'use client';

import Link from 'next/link';
import {
  ThumbsUp,
  Bookmark,
  Link2,
  ChevronRight,
  FileText,
  Flame,
} from 'lucide-react';
import type { Paper } from '@/lib/api';

interface PaperCardProps {
  paper: Paper;
}

/**
 * ISO datetime을 "DD Mon YYYY" 형식으로 변환
 */
function formatDate(isoDate: string): string {
  const date = new Date(isoDate);
  const day = date.getDate();
  const months = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
  ];
  const month = months[date.getMonth()];
  const year = date.getFullYear();
  return `${day} ${month} ${year}`;
}

export function PaperCard({ paper }: PaperCardProps) {
  // Date formatting: created_at → "DD Mon YYYY"
  const formattedDate = formatDate(paper.created_at);

  // Authors → affiliations (unique, max 2)
  const affiliations = [
    ...new Set(
      paper.authors
        .map((a) => a.affiliation)
        .filter((aff): aff is string => Boolean(aff))
    ),
  ].slice(0, 2);

  // Keywords → tags with # prefix
  const tags = (paper.keywords || []).map((k) => `#${k}`);

  // likes는 추후 기능 추가 예정, 현재 0으로 표시
  const likes = 0;

  // hasResources는 has_pdf 기반
  const hasResources = paper.has_pdf ?? false;

  return (
    <Link href={`/papers/${paper.id}`}>
      <article className="group relative rounded-xl border-2 border-[var(--oaria-border-strong)] bg-[var(--background)] p-5 transition-colors hover:border-[var(--oaria-teal)]/50 cursor-pointer">
        <div className="flex gap-6">
          <div className="flex-1">
            <h2 className="mb-2 font-[family-name:var(--font-outfit)] text-lg font-semibold text-[var(--foreground)] transition-colors group-hover:text-[var(--oaria-teal)]">
              {paper.title}
            </h2>
          <div className="mb-3 flex items-center gap-3 text-sm text-[var(--oaria-tagline)]">
            <span>{formattedDate}</span>
            {affiliations.length > 0 && (
              <span className="flex items-center gap-1">
                <span className="text-[var(--oaria-coral)]">•</span>
                {affiliations.join(' · ')}
              </span>
            )}
          </div>
          {paper.abstract && (
            <p className="mb-4 line-clamp-2 font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)]">
              {paper.abstract}
            </p>
          )}
          {tags.length > 0 && (
            <div className="mb-4 flex flex-wrap gap-2">
              {tags.slice(0, 5).map((tag, index) => (
                <span
                  key={`${tag}-${index}`}
                  className="cursor-pointer text-xs text-[var(--oaria-teal)] hover:underline"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
          <div className="flex items-center gap-4">
            <button className="flex items-center gap-1.5 text-sm text-[var(--oaria-text-secondary)] transition-colors hover:text-[var(--oaria-teal)]">
              <ThumbsUp size={16} />
              {likes}
            </button>
            <button className="flex items-center gap-1.5 text-sm text-[var(--oaria-text-secondary)] transition-colors hover:text-[var(--oaria-teal)]">
              <Bookmark size={16} />
              Bookmark
            </button>
            {hasResources && (
              <button className="flex items-center gap-1.5 text-sm text-[var(--oaria-text-secondary)] transition-colors hover:text-[var(--oaria-teal)]">
                <Link2 size={16} />
                Resources
              </button>
            )}
          </div>
        </div>
        {/* Paper Thumbnail */}
        <div className="relative hidden h-40 w-32 flex-shrink-0 overflow-hidden rounded-lg bg-[var(--oaria-border)]/30 md:block">
          <div className="absolute right-2 top-2 flex items-center gap-1 rounded-full bg-[var(--oaria-coral)] px-2 py-0.5 text-xs text-white">
            <Flame size={10} />
            {likes}
          </div>
          <div className="flex h-full items-center justify-center">
            <FileText size={32} className="text-[var(--oaria-tagline)]" />
          </div>
        </div>
      </div>
        {/* Arrow Button */}
        <div className="absolute bottom-4 right-4 flex h-8 w-8 items-center justify-center rounded-full bg-[var(--oaria-teal)] text-white opacity-0 transition-opacity group-hover:opacity-100">
          <ChevronRight size={18} />
        </div>
      </article>
    </Link>
  );
}
