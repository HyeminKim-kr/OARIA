'use client';

import { useParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft,
  ExternalLink,
  Bookmark,
  Download,
  Share2,
  ZoomIn,
  ZoomOut,
  FileText,
  Loader2,
  AlertCircle,
  Calendar,
  ThumbsUp,
} from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { papersApi } from '@/lib/api';
import { PaperFigure, FigureGallery } from '@/components/papers/PaperFigure';
import { SimilarPapers } from '@/components/papers/SimilarPapers';
import { PaperChatPanel } from '@/components/paper-chat';
import { useAuth } from '@/contexts/AuthContext';
import { usePaperInteractions, useToggleLike, useToggleBookmark } from '@/hooks';
import { LoginPromptModal } from '@/components/common/LoginPromptModal';

// 하이라이트 정보 타입
interface HighlightInfo {
  section: string;
  offset_start: number;
  offset_end: number;
}

export default function PaperDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const { isAuthenticated } = useAuth();
  const [activeTab, setActiveTab] = useState<'assistant' | 'notes' | 'similar'>('assistant');
  const [selectedText, setSelectedText] = useState<string>('');
  const [showLoginModal, setShowLoginModal] = useState(false);

  // Interaction hooks
  const { data: interactionData } = usePaperInteractions(id ? [id] : []);
  const toggleLike = useToggleLike();
  const toggleBookmark = useToggleBookmark();

  const interactionStatus = interactionData?.statuses?.[id];
  const isLiked = interactionStatus?.is_liked ?? false;
  const isBookmarked = interactionStatus?.is_bookmarked ?? false;

  const handleLikeClick = () => {
    if (!isAuthenticated) { setShowLoginModal(true); return; }
    toggleLike.mutate(id);
  };

  const handleBookmarkClick = () => {
    if (!isAuthenticated) { setShowLoginModal(true); return; }
    toggleBookmark.mutate({ paperId: id });
  };

  // 하이라이트 상태
  const [highlightInfo, setHighlightInfo] = useState<HighlightInfo | null>(null);
  const highlightRefs = useRef<Map<string, HTMLElement>>(new Map());

  // 하이라이트 요청 핸들러
  const handleHighlightRequest = (info: HighlightInfo) => {
    setHighlightInfo(info);
  };

  // 하이라이트 섹션으로 스크롤
  useEffect(() => {
    if (highlightInfo) {
      const sectionElement = highlightRefs.current.get(highlightInfo.section.toLowerCase());
      if (sectionElement) {
        sectionElement.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
        });
        // 3초 후 하이라이트 제거
        const timer = setTimeout(() => setHighlightInfo(null), 5000);
        return () => clearTimeout(timer);
      }
    }
  }, [highlightInfo]);

  // 섹션 ref 등록
  const setSectionRef = (sectionName: string) => (el: HTMLElement | null) => {
    if (el) {
      highlightRefs.current.set(sectionName.toLowerCase(), el);
    }
  };

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

  // 섹션 수 계산
  const sectionCount = display?.sections?.length || 0;

  // 텍스트 선택 핸들러
  const handleTextSelection = () => {
    const selection = window.getSelection();
    if (selection && selection.toString().trim()) {
      setSelectedText(selection.toString().trim());
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Sub Header - Back & External Links */}
      <div className="flex h-12 items-center justify-between border-b border-[var(--oaria-border)] px-4">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-sm text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)]"
        >
          <ArrowLeft size={18} />
          <span>뒤로</span>
        </button>

        <div className="flex items-center gap-2">
          {paper.doi && (
            <a
              href={`https://doi.org/${paper.doi}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 rounded-lg border border-[var(--oaria-border)] px-3 py-1.5 text-sm text-[var(--oaria-text-secondary)] hover:border-[var(--oaria-teal)] hover:text-[var(--oaria-teal)]"
            >
              <ExternalLink size={14} />
              DOI
            </a>
          )}
          {paper.pmcid && (
            <a
              href={`https://www.ncbi.nlm.nih.gov/pmc/articles/${paper.pmcid}/`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 rounded-lg border border-[var(--oaria-border)] px-3 py-1.5 text-sm text-[var(--oaria-text-secondary)] hover:border-[var(--oaria-teal)] hover:text-[var(--oaria-teal)]"
            >
              <ExternalLink size={14} />
              PMC
            </a>
          )}
        </div>
      </div>

      {/* Main Layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Toolbar */}
        <div className="flex w-14 flex-shrink-0 flex-col items-center gap-1 border-r border-[var(--oaria-border)] py-4">
          <button
            onClick={handleLikeClick}
            title="좋아요"
            className={`flex h-10 w-10 items-center justify-center rounded-lg transition-colors ${
              isLiked
                ? 'text-[var(--oaria-coral)] bg-[var(--oaria-coral)]/10'
                : 'text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50 hover:text-[var(--oaria-coral)]'
            }`}
          >
            <ThumbsUp size={20} fill={isLiked ? 'currentColor' : 'none'} />
          </button>
          <button
            onClick={handleBookmarkClick}
            title="북마크"
            className={`flex h-10 w-10 items-center justify-center rounded-lg transition-colors ${
              isBookmarked
                ? 'text-[var(--oaria-teal)] bg-[var(--oaria-teal)]/10'
                : 'text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50 hover:text-[var(--oaria-teal)]'
            }`}
          >
            <Bookmark size={20} fill={isBookmarked ? 'currentColor' : 'none'} />
          </button>
          <button className="flex h-10 w-10 items-center justify-center rounded-lg text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50 hover:text-[var(--oaria-teal)]">
            <Download size={20} />
          </button>
          <button className="flex h-10 w-10 items-center justify-center rounded-lg text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50 hover:text-[var(--oaria-teal)]">
            <Share2 size={20} />
          </button>

          <div className="my-2 text-xs text-[var(--oaria-tagline)]">
            <span>1</span>
            <span className="mx-0.5">/</span>
            <span>{sectionCount || '?'}</span>
          </div>

          <button className="flex h-10 w-10 items-center justify-center rounded-lg text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50 hover:text-[var(--oaria-teal)]">
            <ZoomIn size={20} />
          </button>
          <button className="flex h-10 w-10 items-center justify-center rounded-lg text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50 hover:text-[var(--oaria-teal)]">
            <ZoomOut size={20} />
          </button>
        </div>

        {/* Main Content */}
        <main
          className="flex-1 overflow-y-auto bg-[#f5f5f5] dark:bg-[#1a1a1a]"
          onMouseUp={handleTextSelection}
        >
          <div className="mx-auto max-w-4xl p-8">
            {/* Paper Card */}
            <article className="rounded-xl bg-[var(--background)] p-8 shadow-sm">
              {/* Journal & Year */}
              <div className="mb-6 flex items-center gap-3">
                {paper.journal && (
                  <span className="flex items-center gap-1.5 rounded-full border border-[var(--oaria-teal)] px-3 py-1 text-sm text-[var(--oaria-teal)]">
                    <FileText size={14} />
                    {paper.journal}
                  </span>
                )}
                {paper.year && (
                  <span className="flex items-center gap-1.5 text-sm text-[var(--oaria-tagline)]">
                    <Calendar size={14} />
                    {paper.year}
                  </span>
                )}
              </div>

              {/* Title */}
              <h1 className="mb-6 font-[family-name:var(--font-outfit)] text-2xl font-bold leading-tight text-[var(--foreground)] md:text-3xl">
                {paper.title}
              </h1>

              {/* Authors */}
              {paper.authors.length > 0 && (
                <div className="mb-8 text-[var(--oaria-teal)]">
                  {paper.authors
                    .sort((a, b) => a.author_order - b.author_order)
                    .map((author, idx) => (
                      <span key={idx}>
                        {author.author_name}
                        {author.is_corresponding && <span className="text-[var(--oaria-coral)]">*</span>}
                        {idx < paper.authors.length - 1 && ', '}
                      </span>
                    ))}
                </div>
              )}

              <hr className="mb-8 border-[var(--oaria-border)]" />

              {/* Abstract */}
              {paper.abstract && (
                <section
                  className={`mb-8 transition-all duration-500 ${
                    highlightInfo?.section.toLowerCase() === 'abstract'
                      ? 'bg-yellow-50 border-l-4 border-yellow-400 pl-4 -ml-4 rounded-r'
                      : ''
                  }`}
                  ref={setSectionRef('abstract')}
                >
                  <h2 className="mb-4 font-[family-name:var(--font-outfit)] text-sm font-semibold uppercase tracking-wider text-[var(--oaria-teal)]">
                    Abstract
                  </h2>
                  <p className="text-justify font-[family-name:var(--font-dm-sans)] leading-relaxed text-[var(--oaria-text-secondary)]">
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

              {/* Fulltext Sections */}
              {displayLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-6 w-6 animate-spin text-[var(--oaria-teal)]" />
                  <span className="ml-2 text-[var(--oaria-text-secondary)]">
                    본문 로딩 중...
                  </span>
                </div>
              ) : display?.sections ? (
                <div className="space-y-8">
                  {display.sections
                    .filter((section) => section.name !== 'abstract')  // Abstract 중복 방지
                    .map((section, idx) => {
                      const isHighlighted = highlightInfo?.section.toLowerCase() === section.name.toLowerCase();
                      return (
                    <section
                      key={idx}
                      ref={setSectionRef(section.name)}
                      className={`transition-all duration-500 ${
                        isHighlighted
                          ? 'bg-yellow-50 border-l-4 border-yellow-400 pl-4 -ml-4 rounded-r'
                          : ''
                      }`}
                    >
                      <h2 className="mb-4 font-[family-name:var(--font-outfit)] text-sm font-semibold uppercase tracking-wider text-[var(--oaria-teal)]">
                        {section.title}
                      </h2>
                      <div className="space-y-4">
                        {/* contents가 있으면 XML 순서대로 렌더링 (Figure 인라인 배치) */}
                        {section.contents && section.contents.length > 0 ? (
                          section.contents.map((content, cIdx) => {
                            if (content.type === 'figure') {
                              // Figure 렌더링
                              return paper.pmcid && content.graphic_href ? (
                                <div key={cIdx} className="my-6">
                                  <PaperFigure
                                    pmcid={paper.pmcid}
                                    figure={{
                                      id: content.id || '',
                                      label: content.label || '',
                                      caption: content.caption,
                                      graphic_href: content.graphic_href,
                                    }}
                                  />
                                </div>
                              ) : null;
                            }
                            // 문단 렌더링
                            const text = content.text || '';
                            // **text** 패턴은 서브섹션 제목으로 렌더링
                            const subsectionMatch = text.match(/^\*\*(.+)\*\*$/);
                            if (subsectionMatch) {
                              return (
                                <h3
                                  key={cIdx}
                                  className="mt-8 mb-4 font-[family-name:var(--font-outfit)] text-lg font-semibold text-[var(--oaria-teal)]"
                                >
                                  {subsectionMatch[1]}
                                </h3>
                              );
                            }
                            return (
                              <p
                                key={cIdx}
                                className="text-justify font-[family-name:var(--font-dm-sans)] leading-relaxed text-[var(--oaria-text-secondary)]"
                              >
                                {text}
                              </p>
                            );
                          })
                        ) : (
                          /* Legacy: paragraphs + figures 별도 렌더링 */
                          <>
                            {section.paragraphs?.map((para, pIdx) => {
                              // **text** 패턴은 서브섹션 제목으로 렌더링
                              const subsectionMatch = para.text.match(/^\*\*(.+)\*\*$/);
                              if (subsectionMatch) {
                                return (
                                  <h3
                                    key={pIdx}
                                    className="mt-8 mb-4 font-[family-name:var(--font-outfit)] text-lg font-semibold text-[var(--oaria-teal)]"
                                  >
                                    {subsectionMatch[1]}
                                  </h3>
                                );
                              }
                              return (
                                <p
                                  key={pIdx}
                                  className="text-justify font-[family-name:var(--font-dm-sans)] leading-relaxed text-[var(--oaria-text-secondary)]"
                                >
                                  {para.text}
                                </p>
                              );
                            })}
                            {/* 섹션 끝에 Figure (Legacy) */}
                            {section.figures && section.figures.length > 0 && paper.pmcid && (
                              <div className="my-6 space-y-4">
                                {section.figures.map((figure) => (
                                  <PaperFigure
                                    key={figure.id}
                                    pmcid={paper.pmcid!}
                                    figure={figure}
                                  />
                                ))}
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    </section>
                      );
                    })}

                  {/* Fallback: 섹션에 연결되지 않은 전체 Figure 목록 (하위 호환) */}
                  {display.figures && display.figures.length > 0 && paper.pmcid && (
                    <section className="mt-12 border-t border-[var(--oaria-border)] pt-8">
                      <FigureGallery
                        pmcid={paper.pmcid}
                        figures={display.figures}
                      />
                    </section>
                  )}
                </div>
              ) : null}
            </article>
          </div>
        </main>

        {/* Right Sidebar */}
        <aside className="hidden w-96 flex-shrink-0 flex-col border-l border-[var(--oaria-border)] bg-[var(--background)] lg:flex">
          {/* Tabs */}
          <div className="flex border-b border-[var(--oaria-border)]">
            <button
              onClick={() => setActiveTab('assistant')}
              className={`flex-1 py-3 text-sm font-medium transition-colors ${
                activeTab === 'assistant'
                  ? 'border-b-2 border-[var(--oaria-teal)] text-[var(--oaria-teal)]'
                  : 'text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)]'
              }`}
            >
              AI Assistant
            </button>
            <button
              onClick={() => setActiveTab('notes')}
              className={`flex-1 py-3 text-sm font-medium transition-colors ${
                activeTab === 'notes'
                  ? 'border-b-2 border-[var(--oaria-teal)] text-[var(--oaria-teal)]'
                  : 'text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)]'
              }`}
            >
              내 노트
            </button>
            <button
              onClick={() => setActiveTab('similar')}
              className={`flex-1 py-3 text-sm font-medium transition-colors ${
                activeTab === 'similar'
                  ? 'border-b-2 border-[var(--oaria-teal)] text-[var(--oaria-teal)]'
                  : 'text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)]'
              }`}
            >
              유사 논문
            </button>
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-hidden p-4">
            {activeTab === 'assistant' && (
              <PaperChatPanel
                paper={paper}
                selectedText={selectedText}
                onClearSelectedText={() => setSelectedText('')}
                onHighlightRequest={handleHighlightRequest}
              />
            )}

            {activeTab === 'notes' && (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[var(--oaria-border)]/50">
                  <FileText size={32} className="text-[var(--oaria-tagline)]" />
                </div>
                <p className="text-[var(--oaria-text-secondary)]">아직 작성된 노트가 없습니다</p>
                <p className="mt-1 text-sm text-[var(--oaria-tagline)]">
                  텍스트를 선택하여 노트를 추가하세요
                </p>
              </div>
            )}

            {activeTab === 'similar' && (
              <SimilarPapers paperId={id} />
            )}
          </div>
        </aside>
      </div>

      {/* Login Prompt Modal */}
      <LoginPromptModal
        isOpen={showLoginModal}
        onClose={() => setShowLoginModal(false)}
      />
    </div>
  );
}
