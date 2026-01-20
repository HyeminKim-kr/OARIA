'use client';

import { useMutation } from '@tanstack/react-query';
import { FileText, Download, ExternalLink, Loader2 } from 'lucide-react';
import { Paper, papersApi } from '@/lib/api';

interface PdfSectionProps {
  paper: Paper;
}

function formatFileSize(bytes: number | null | undefined): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateString: string | null): string {
  if (!dateString) return '-';
  return new Date(dateString).toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function PdfSection({ paper }: PdfSectionProps) {
  const downloadMutation = useMutation({
    mutationFn: () => papersApi.getPdfUrl(paper.id),
    onSuccess: (data) => {
      window.open(data.url, '_blank');
    },
    onError: (error: any) => {
      alert(`PDF 다운로드 오류: ${error.response?.data?.message || error.message}`);
    },
  });

  if (!paper.hasPdf) {
    return (
      <div className="rounded-lg bg-white p-6 shadow">
        <h2 className="mb-4 font-semibold text-gray-900">PDF</h2>
        <div className="flex items-center gap-3 text-gray-500">
          <FileText className="h-8 w-8 text-gray-300" />
          <span>PDF 파일이 없습니다.</span>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg bg-white p-6 shadow">
      <h2 className="mb-4 font-semibold text-gray-900">PDF</h2>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-green-50">
            <FileText className="h-6 w-6 text-green-600" />
          </div>
          <div>
            <p className="font-medium text-gray-900">PDF 원문</p>
            <div className="mt-1 flex items-center gap-3 text-sm text-gray-500">
              {paper.pdfSize && <span>{formatFileSize(paper.pdfSize)}</span>}
              {paper.pdfDownloadedAt && (
                <>
                  <span>·</span>
                  <span>다운로드: {formatDate(paper.pdfDownloadedAt)}</span>
                </>
              )}
            </div>
          </div>
        </div>
        <button
          onClick={() => downloadMutation.mutate()}
          disabled={downloadMutation.isPending}
          className="inline-flex items-center gap-2 rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
        >
          {downloadMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          다운로드
        </button>
      </div>
    </div>
  );
}
