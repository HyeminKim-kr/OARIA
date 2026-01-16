"use client";

import { useState, useEffect, useCallback } from "react";
import { X, FileText, Loader2, AlertCircle } from "lucide-react";
import { PDFViewer } from "./PDFViewer";
import { fetchWithAuth } from "@/lib/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface PDFViewerModalProps {
  paperId: string;  // string paper_id (예: "pmc:PMC12345678")
  title: string;
  onClose: () => void;
}

export function PDFViewerModal({ paperId, title, onClose }: PDFViewerModalProps) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // PDF URL 조회
  useEffect(() => {
    const fetchPdfUrl = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // string paper_id를 사용하는 엔드포인트 호출
        const response = await fetchWithAuth(
          `${API_BASE_URL}/papers/by-paper-id/${encodeURIComponent(paperId)}/pdf/url`
        );

        if (!response.ok) {
          if (response.status === 404) {
            throw new Error("이 논문의 PDF는 아직 수집되지 않았습니다.");
          }
          throw new Error("PDF URL을 불러오는데 실패했습니다.");
        }

        const data = await response.json();
        setPdfUrl(data.url);
      } catch (err) {
        setError(err instanceof Error ? err.message : "오류가 발생했습니다.");
      } finally {
        setIsLoading(false);
      }
    };

    fetchPdfUrl();
  }, [paperId]);

  // ESC 키로 닫기
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [onClose]);

  const handleDownload = useCallback(() => {
    if (pdfUrl) {
      window.open(pdfUrl, "_blank");
    }
  }, [pdfUrl]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-6xl h-[90vh] mx-4 bg-[var(--background)] rounded-2xl shadow-2xl overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--oaria-border)] bg-[var(--background)]">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <div className="w-10 h-10 rounded-full bg-[var(--oaria-teal)]/10 flex items-center justify-center flex-shrink-0">
              <FileText size={20} className="text-[var(--oaria-teal)]" />
            </div>
            <div className="min-w-0">
              <h2 className="font-[family-name:var(--font-outfit)] text-lg font-semibold text-[var(--foreground)] line-clamp-1">
                {title}
              </h2>
              <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)]">
                PDF Viewer
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-[var(--oaria-border)]/50 transition-colors flex-shrink-0"
          >
            <X size={20} className="text-[var(--oaria-text-secondary)]" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center h-full">
              <Loader2 size={48} className="animate-spin text-[var(--oaria-teal)] mb-4" />
              <p className="font-[family-name:var(--font-dm-sans)] text-[var(--oaria-text-secondary)]">
                PDF를 불러오는 중...
              </p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center h-full">
              <AlertCircle size={48} className="text-red-500 mb-4" />
              <p className="font-[family-name:var(--font-dm-sans)] text-[var(--oaria-text-secondary)] mb-4">
                {error}
              </p>
              <button
                onClick={onClose}
                className="px-4 py-2 bg-[var(--oaria-teal)] text-white rounded-lg hover:bg-[var(--oaria-teal)]/90 transition-colors"
              >
                닫기
              </button>
            </div>
          ) : pdfUrl ? (
            <PDFViewer url={pdfUrl} title={title} onDownload={handleDownload} />
          ) : null}
        </div>
      </div>
    </div>
  );
}
