"use client";

import { useState, useCallback } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import {
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Download,
  Loader2,
  AlertCircle,
} from "lucide-react";

// PDF.js worker 설정
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PDFViewerProps {
  url: string;
  title?: string;
  onDownload?: () => void;
}

export function PDFViewer({ url, title, onDownload }: PDFViewerProps) {
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(1.0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const onDocumentLoadSuccess = useCallback(({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setIsLoading(false);
  }, []);

  const onDocumentLoadError = useCallback((error: Error) => {
    console.error("PDF load error:", error);
    setError("PDF를 불러오는데 실패했습니다.");
    setIsLoading(false);
  }, []);

  const goToPrevPage = () => {
    setPageNumber((prev) => Math.max(prev - 1, 1));
  };

  const goToNextPage = () => {
    setPageNumber((prev) => Math.min(prev + 1, numPages || 1));
  };

  const zoomIn = () => {
    setScale((prev) => Math.min(prev + 0.25, 3.0));
  };

  const zoomOut = () => {
    setScale((prev) => Math.max(prev - 0.25, 0.5));
  };

  const handleDownload = () => {
    if (onDownload) {
      onDownload();
    } else {
      window.open(url, "_blank");
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-3 bg-[var(--oaria-border)]/30 border-b border-[var(--oaria-border)]">
        {/* Page Navigation */}
        <div className="flex items-center gap-2">
          <button
            onClick={goToPrevPage}
            disabled={pageNumber <= 1}
            className="p-2 rounded-lg hover:bg-[var(--oaria-border)]/50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            title="이전 페이지"
          >
            <ChevronLeft size={20} />
          </button>
          <span className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--foreground)] min-w-[100px] text-center">
            {numPages ? `${pageNumber} / ${numPages}` : "-"}
          </span>
          <button
            onClick={goToNextPage}
            disabled={pageNumber >= (numPages || 1)}
            className="p-2 rounded-lg hover:bg-[var(--oaria-border)]/50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            title="다음 페이지"
          >
            <ChevronRight size={20} />
          </button>
        </div>

        {/* Zoom & Download */}
        <div className="flex items-center gap-2">
          <button
            onClick={zoomOut}
            disabled={scale <= 0.5}
            className="p-2 rounded-lg hover:bg-[var(--oaria-border)]/50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            title="축소"
          >
            <ZoomOut size={20} />
          </button>
          <span className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--foreground)] min-w-[60px] text-center">
            {Math.round(scale * 100)}%
          </span>
          <button
            onClick={zoomIn}
            disabled={scale >= 3.0}
            className="p-2 rounded-lg hover:bg-[var(--oaria-border)]/50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            title="확대"
          >
            <ZoomIn size={20} />
          </button>
          <div className="w-px h-6 bg-[var(--oaria-border)] mx-2" />
          <button
            onClick={handleDownload}
            className="p-2 rounded-lg hover:bg-[var(--oaria-border)]/50 transition-colors"
            title="다운로드"
          >
            <Download size={20} />
          </button>
        </div>
      </div>

      {/* PDF Content */}
      <div className="flex-1 overflow-auto bg-gray-100 flex justify-center">
        {isLoading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 size={48} className="animate-spin text-[var(--oaria-teal)]" />
          </div>
        )}

        {error && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <AlertCircle size={48} className="text-red-500 mb-4" />
            <p className="text-[var(--oaria-text-secondary)]">{error}</p>
          </div>
        )}

        <Document
          file={url}
          onLoadSuccess={onDocumentLoadSuccess}
          onLoadError={onDocumentLoadError}
          loading={null}
          error={null}
          className={isLoading || error ? "hidden" : "py-4"}
        >
          <Page
            pageNumber={pageNumber}
            scale={scale}
            renderTextLayer={true}
            renderAnnotationLayer={true}
            className="shadow-lg"
          />
        </Document>
      </div>
    </div>
  );
}
