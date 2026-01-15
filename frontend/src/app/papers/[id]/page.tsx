'use client';

import { useParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft,
  FileText,
  BookOpen,
  ExternalLink,
  Calendar,
  Building2,
  Users,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import Link from 'next/link';
import { papersApi } from '@/lib/api';

export default function PaperDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  // 논문 메타데이터 조회
  const {
    data: paper,
    isLoading: paperLoading,
    error: paperError,
  } = useQuery({
    queryKey: ['paper', id],
    queryFn: () => papersApi.getOne(id),
    enabled: !!id,
  });

  // 논문 본문 (display.json) 조회
  const {
    data: display,
    isLoading: displayLoading,
    error: displayError,
  } = useQuery({
    queryKey: ['paper-display', id],
    queryFn: () => papersApi.getDisplay(id),
    enabled: !!id,
  });

  // 로딩 상태
  if (paperLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[var(--oaria-teal)]" />
      </div>
    );
  }

  // 에러 상태
  if (paperError || !paper) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4">
        <AlertCircle className="h-12 w-12 text-red-500" />
        <p className="text-lg text-[var(--oaria-text-secondary)]">
          논문을 찾을 수 없습니다
        </p>
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 rounded-lg bg-[var(--oaria-teal)] px-4 py-2 text-white"
        >
          <ArrowLeft size={16} />
          돌아가기
        </button>
      </div>
    );
  }

  // 저자 정보 그룹화
  const affiliations = [
    ...new Set(
      paper.authors
        .map((a) => a.affiliation)
        .filter((aff): aff is string => Boolean(aff))
    ),
  ];

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[var(--background)]">
      {/* Header */}
      <header className="flex items-center gap-4 border-b border-[var(--oaria-border)] px-6 py-4">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 rounded-lg px-3 py-2 text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50"
        >
          <ArrowLeft size={20} />
          <span className="hidden sm:inline">뒤로</span>
        </button>

        <div className="flex-1" />

        {/* 외부 링크 */}
        {paper.doi && (
          <a
            href={`https://doi.org/${paper.doi}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50"
          >
            <ExternalLink size={16} />
            DOI
          </a>
        )}
        {paper.pmcid && (
          <a
            href={`https://www.ncbi.nlm.nih.gov/pmc/articles/${paper.pmcid}/`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50"
          >
            <ExternalLink size={16} />
            PMC
          </a>
        )}
      </header>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Paper Content */}
        <main className="flex-1 overflow-y-auto">
          <article className="mx-auto max-w-4xl px-6 py-8">
            {/* Title */}
            <h1 className="mb-6 font-[family-name:var(--font-outfit)] text-2xl font-bold leading-tight text-[var(--foreground)] md:text-3xl">
              {paper.title}
            </h1>

            {/* Meta Info */}
            <div className="mb-6 flex flex-wrap items-center gap-4 text-sm text-[var(--oaria-text-secondary)]">
              {paper.journal && (
                <span className="flex items-center gap-1.5">
                  <BookOpen size={14} />
                  {paper.journal}
                </span>
              )}
              {paper.year && (
                <span className="flex items-center gap-1.5">
                  <Calendar size={14} />
                  {paper.year}
                </span>
              )}
            </div>

            {/* Authors */}
            {paper.authors.length > 0 && (
              <div className="mb-6">
                <div className="flex flex-wrap gap-2 text-sm">
                  {paper.authors
                    .sort((a, b) => a.author_order - b.author_order)
                    .map((author, idx) => (
                      <span key={idx} className="text-[var(--foreground)]">
                        {author.author_name}
                        {author.is_corresponding && (
                          <span className="text-[var(--oaria-coral)]">*</span>
                        )}
                        {idx < paper.authors.length - 1 && ', '}
                      </span>
                    ))}
                </div>
                {affiliations.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-[var(--oaria-tagline)]">
                    {affiliations.map((aff, idx) => (
                      <span key={idx} className="flex items-center gap-1">
                        <Building2 size={12} />
                        {aff}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Abstract */}
            {paper.abstract && (
              <section className="mb-8 rounded-lg bg-[var(--oaria-border)]/20 p-6">
                <h2 className="mb-3 font-[family-name:var(--font-outfit)] text-lg font-semibold text-[var(--foreground)]">
                  Abstract
                </h2>
                <p className="font-[family-name:var(--font-dm-sans)] leading-relaxed text-[var(--oaria-text-secondary)]">
                  {paper.abstract}
                </p>
              </section>
            )}

            {/* Keywords */}
            {paper.keywords && paper.keywords.length > 0 && (
              <div className="mb-8 flex flex-wrap gap-2">
                {paper.keywords.map((keyword, idx) => (
                  <span
                    key={idx}
                    className="rounded-full bg-[var(--oaria-teal)]/10 px-3 py-1 text-xs text-[var(--oaria-teal)]"
                  >
                    #{keyword}
                  </span>
                ))}
              </div>
            )}

            {/* Fulltext Content */}
            {displayLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-[var(--oaria-teal)]" />
                <span className="ml-2 text-[var(--oaria-text-secondary)]">
                  본문 로딩 중...
                </span>
              </div>
            ) : displayError ? (
              <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-6 text-center">
                <FileText className="mx-auto mb-2 h-8 w-8 text-yellow-500" />
                <p className="text-yellow-700">
                  본문 데이터를 불러올 수 없습니다
                </p>
                <p className="mt-1 text-sm text-yellow-600">
                  초록(Abstract) 정보만 표시됩니다
                </p>
              </div>
            ) : display ? (
              <div className="space-y-8">
                {display.sections.map((section, idx) => (
                  <section key={idx}>
                    <h2 className="mb-4 border-b border-[var(--oaria-border)] pb-2 font-[family-name:var(--font-outfit)] text-xl font-semibold text-[var(--foreground)]">
                      {section.title}
                    </h2>
                    <div className="space-y-4">
                      {section.paragraphs.map((para, pIdx) => (
                        <p
                          key={pIdx}
                          className="font-[family-name:var(--font-dm-sans)] leading-relaxed text-[var(--oaria-text-secondary)]"
                        >
                          {para.text}
                        </p>
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            ) : null}
          </article>
        </main>

        {/* Right: Sidebar */}
        <aside className="hidden w-80 flex-shrink-0 border-l border-[var(--oaria-border)] bg-[var(--background)] lg:block">
          <div className="p-6">
            {/* AI Assistant placeholder */}
            <div className="mb-6 rounded-xl bg-gradient-to-br from-[var(--oaria-teal)]/10 to-[var(--oaria-coral)]/10 p-6 text-center">
              <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--oaria-teal)]/20">
                <Users size={24} className="text-[var(--oaria-teal)]" />
              </div>
              <h3 className="mb-2 font-semibold text-[var(--foreground)]">
                AI Assistant
              </h3>
              <p className="text-sm text-[var(--oaria-text-secondary)]">
                논문에 대해 질문하거나 요약을 요청하세요
              </p>
              <Link
                href={`/ask?paper=${id}`}
                className="mt-4 inline-flex items-center gap-2 rounded-lg bg-[var(--oaria-teal)] px-4 py-2 text-sm font-medium text-white"
              >
                질문하기
              </Link>
            </div>

            {/* Paper Info */}
            <div className="space-y-4">
              <h4 className="font-semibold text-[var(--foreground)]">
                논문 정보
              </h4>

              {paper.journal && (
                <div>
                  <dt className="text-xs text-[var(--oaria-tagline)]">저널</dt>
                  <dd className="text-sm text-[var(--foreground)]">
                    {paper.journal}
                  </dd>
                </div>
              )}

              {paper.year && (
                <div>
                  <dt className="text-xs text-[var(--oaria-tagline)]">출판 연도</dt>
                  <dd className="text-sm text-[var(--foreground)]">
                    {paper.year}
                  </dd>
                </div>
              )}

              {paper.doi && (
                <div>
                  <dt className="text-xs text-[var(--oaria-tagline)]">DOI</dt>
                  <dd className="text-sm text-[var(--oaria-teal)]">
                    <a
                      href={`https://doi.org/${paper.doi}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:underline"
                    >
                      {paper.doi}
                    </a>
                  </dd>
                </div>
              )}

              {paper.pmcid && (
                <div>
                  <dt className="text-xs text-[var(--oaria-tagline)]">PMC ID</dt>
                  <dd className="text-sm text-[var(--foreground)]">
                    {paper.pmcid}
                  </dd>
                </div>
              )}

              {paper.is_open_access && (
                <div className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-1 text-xs text-green-700">
                  <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                  Open Access
                </div>
              )}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
