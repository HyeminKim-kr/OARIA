"use client";

import { useState, useEffect, useRef } from "react";
import { X, FileText, Loader2, FileType } from "lucide-react";
import { fetchWithAuth } from "@/lib/api";
import { PDFViewerModal } from "@/components/pdf/PDFViewerModal";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Reference {
  paper_id: string;
  title: string;
  journal: string;
  year: number;
  section: string;
  offset_start: number;
  offset_end: number;
}

interface Paragraph {
  text: string;
  offset_start: number;
  offset_end: number;
}

interface SectionContent {
  paper_id: string;
  section: string;
  section_title: string;
  title: string;
  journal: string | null;
  year: number | null;
  paragraphs: Paragraph[];
  total_text: string;
  section_fulltext_offset: number;  // fulltext 기준 섹션 시작 위치
}

interface ReferenceModalProps {
  reference: Reference;
  onClose: () => void;
}

export function ReferenceModal({ reference, onClose }: ReferenceModalProps) {
  const [sectionContent, setSectionContent] = useState<SectionContent | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasPdf, setHasPdf] = useState(false);
  const [showPdfViewer, setShowPdfViewer] = useState(false);
  const highlightRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  // PDF 존재 여부 확인
  useEffect(() => {
    const checkPdfAvailability = async () => {
      try {
        const response = await fetchWithAuth(
          `${API_BASE_URL}/papers/by-paper-id/${encodeURIComponent(reference.paper_id)}/has-pdf`
        );
        if (response.ok) {
          const data = await response.json();
          setHasPdf(data.has_pdf);
        }
      } catch (err) {
        // PDF 확인 실패 시 무시 (버튼만 숨김)
        console.debug("PDF availability check failed:", err);
      }
    };

    checkPdfAvailability();
  }, [reference.paper_id]);

  useEffect(() => {
    const fetchSectionContent = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetchWithAuth(
          `${API_BASE_URL}/papers/${encodeURIComponent(reference.paper_id)}/sections/${encodeURIComponent(reference.section)}`
        );

        if (!response.ok) {
          throw new Error("섹션 텍스트를 불러올 수 없습니다.");
        }

        const data = await response.json();
        setSectionContent(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "오류가 발생했습니다.");
      } finally {
        setIsLoading(false);
      }
    };

    fetchSectionContent();
  }, [reference.paper_id, reference.section]);

  // 데이터 로드 후 하이라이트로 자동 스크롤
  useEffect(() => {
    if (sectionContent && highlightRef.current && contentRef.current) {
      setTimeout(() => {
        highlightRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "center",
        });
      }, 100);
    }
  }, [sectionContent]);

  // 단락이 하이라이트 범위와 겹치는지 확인
  // reference의 offset은 fulltext 기준, paragraph의 offset은 섹션 기준
  // 따라서 reference offset에서 section_fulltext_offset을 빼서 섹션 기준으로 변환
  const isHighlighted = (paragraph: Paragraph): boolean => {
    if (!sectionContent) return false;

    // fulltext 기준 오프셋을 섹션 기준으로 변환
    const sectionOffset = sectionContent.section_fulltext_offset;
    const adjustedStart = reference.offset_start - sectionOffset;
    const adjustedEnd = reference.offset_end - sectionOffset;

    // 단락과 하이라이트 범위가 겹치는지 확인
    return (
      adjustedStart < paragraph.offset_end &&
      adjustedEnd > paragraph.offset_start
    );
  };

  // 단락 내에서 하이라이트할 텍스트 분리
  const renderParagraphContent = (paragraph: Paragraph) => {
    if (!sectionContent) return <span>{paragraph.text}</span>;

    // fulltext 기준 오프셋을 섹션 기준으로 변환
    const sectionOffset = sectionContent.section_fulltext_offset;
    const adjustedStart = reference.offset_start - sectionOffset;
    const adjustedEnd = reference.offset_end - sectionOffset;

    // 하이라이트 범위가 이 단락과 겹치지 않으면 그냥 텍스트 반환
    if (adjustedStart >= paragraph.offset_end || adjustedEnd <= paragraph.offset_start) {
      return <span>{paragraph.text}</span>;
    }

    // 단락 내 상대 오프셋 계산
    const relativeStart = Math.max(0, adjustedStart - paragraph.offset_start);
    const relativeEnd = Math.min(paragraph.text.length, adjustedEnd - paragraph.offset_start);

    const before = paragraph.text.slice(0, relativeStart);
    const highlighted = paragraph.text.slice(relativeStart, relativeEnd);
    const after = paragraph.text.slice(relativeEnd);

    return (
      <>
        {before && <span>{before}</span>}
        {highlighted && (
          <mark className="bg-yellow-300/80 text-[var(--foreground)] px-0.5 rounded">
            {highlighted}
          </mark>
        )}
        {after && <span>{after}</span>}
      </>
    );
  };

  // ESC 키로 닫기
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl max-h-[85vh] mx-4 bg-[var(--background)] rounded-2xl shadow-2xl overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-[var(--oaria-border)]">
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <div className="w-10 h-10 rounded-full bg-[var(--oaria-teal)]/10 flex items-center justify-center flex-shrink-0">
              <FileText size={20} className="text-[var(--oaria-teal)]" />
            </div>
            <div className="min-w-0">
              <h2 className="font-[family-name:var(--font-outfit)] text-lg font-semibold text-[var(--foreground)] line-clamp-2">
                {reference.title}
              </h2>
              <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] mt-1">
                {reference.journal} ({reference.year}) · {reference.section}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {/* PDF 보기 버튼 */}
            {hasPdf && (
              <button
                onClick={() => setShowPdfViewer(true)}
                className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--oaria-teal)]/10 hover:bg-[var(--oaria-teal)]/20 text-[var(--oaria-teal)] transition-colors"
                title="PDF 원문 보기"
              >
                <FileType size={18} />
                <span className="font-[family-name:var(--font-dm-sans)] text-sm font-medium">
                  PDF
                </span>
              </button>
            )}
            <button
              onClick={onClose}
              className="p-2 rounded-full hover:bg-[var(--oaria-border)]/50 transition-colors"
            >
              <X size={20} className="text-[var(--oaria-text-secondary)]" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div ref={contentRef} className="flex-1 overflow-y-auto p-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={32} className="animate-spin text-[var(--oaria-teal)]" />
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <p className="text-[var(--oaria-text-secondary)]">{error}</p>
            </div>
          ) : sectionContent ? (
            <div className="space-y-4">
              {/* 섹션 제목 */}
              <h3 className="font-[family-name:var(--font-outfit)] text-xl font-semibold text-[var(--oaria-teal)] border-b border-[var(--oaria-border)] pb-3 mb-6">
                {sectionContent.section_title}
              </h3>

              {/* 단락들 */}
              {sectionContent.paragraphs.map((paragraph, idx) => {
                const highlighted = isHighlighted(paragraph);

                return (
                  <div
                    key={idx}
                    ref={highlighted ? highlightRef : undefined}
                    className={`font-[family-name:var(--font-dm-sans)] text-base leading-relaxed ${
                      highlighted
                        ? "bg-yellow-50 border-l-4 border-yellow-400 pl-4 py-2 -ml-4 rounded-r"
                        : "text-[var(--foreground)]"
                    }`}
                  >
                    {renderParagraphContent(paragraph)}
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-[var(--oaria-border)] bg-[var(--oaria-border)]/20">
          <p className="font-[family-name:var(--font-dm-sans)] text-xs text-[var(--oaria-tagline)] text-center">
            하이라이트된 부분이 AI 답변의 근거로 사용되었습니다.
          </p>
        </div>
      </div>

      {/* PDF Viewer Modal */}
      {showPdfViewer && (
        <PDFViewerModal
          paperId={reference.paper_id}
          title={reference.title}
          onClose={() => setShowPdfViewer(false)}
        />
      )}
    </div>
  );
}
