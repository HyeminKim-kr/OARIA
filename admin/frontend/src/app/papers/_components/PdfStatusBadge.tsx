import { FileText, Quote } from 'lucide-react';

interface PdfStatusBadgeProps {
  hasPdf: boolean;
  pdfSize?: number | null;
}

interface CitationBadgeProps {
  citationCount: number;
  referenceCount: number;
}

function formatFileSize(bytes: number | null | undefined): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function PdfStatusBadge({ hasPdf, pdfSize }: PdfStatusBadgeProps) {
  if (!hasPdf) {
    return null;
  }

  return (
    <span className="inline-flex items-center gap-1 rounded bg-green-50 px-2 py-0.5 text-xs text-green-700">
      <FileText className="h-3 w-3" />
      PDF
      {pdfSize && <span className="text-green-600">({formatFileSize(pdfSize)})</span>}
    </span>
  );
}

export function CitationBadge({ citationCount, referenceCount }: CitationBadgeProps) {
  if (citationCount === 0 && referenceCount === 0) {
    return null;
  }

  return (
    <span className="inline-flex items-center gap-1 rounded bg-purple-50 px-2 py-0.5 text-xs text-purple-700">
      <Quote className="h-3 w-3" />
      {citationCount > 0 && <span>Cited: {citationCount}</span>}
      {citationCount > 0 && referenceCount > 0 && <span>·</span>}
      {referenceCount > 0 && <span>Refs: {referenceCount}</span>}
    </span>
  );
}
