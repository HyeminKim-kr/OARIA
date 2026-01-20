import Link from 'next/link';
import { ExternalLink } from 'lucide-react';
import { Paper } from '@/lib/api';
import { formatDate } from '@/lib/utils';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { EmbeddingStatusBadge } from './EmbeddingStatusBadge';
import { PdfStatusBadge, CitationBadge } from './PdfStatusBadge';

interface PaperListItemProps {
  paper: Paper;
}

export function PaperListItem({ paper }: PaperListItemProps) {
  return (
    <div className="p-6 hover:bg-gray-50">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <Link
            href={`/papers/${paper.id}`}
            className="font-medium text-gray-900 hover:text-blue-600 hover:underline"
          >
            {paper.title}
          </Link>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-500">
            {paper.journal && <span>{paper.journal}</span>}
            {paper.year && <span>({paper.year})</span>}
            <StatusBadge status={paper.status} />
            <EmbeddingStatusBadge
              status={paper.embeddingStatus}
              chunkCount={paper.embeddingChunkCount}
            />
            <PdfStatusBadge hasPdf={paper.hasPdf} pdfSize={paper.pdfSize} />
            <CitationBadge
              citationCount={paper.citationCount}
              referenceCount={paper.referenceCount}
            />
          </div>
          {paper.abstract && (
            <p className="mt-2 line-clamp-2 text-sm text-gray-600">{paper.abstract}</p>
          )}
          <div className="mt-2 flex flex-wrap gap-2">
            {paper.pmcid && (
              <span className="inline-flex items-center rounded bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
                PMC: {paper.pmcid}
              </span>
            )}
            {paper.pmid && (
              <span className="inline-flex items-center rounded bg-green-50 px-2 py-0.5 text-xs text-green-700">
                PMID: {paper.pmid}
              </span>
            )}
            {paper.doi && (
              <a
                href={`https://doi.org/${paper.doi}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded bg-purple-50 px-2 py-0.5 text-xs text-purple-700 hover:bg-purple-100"
              >
                DOI <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </div>
        <div className="text-right text-sm text-gray-500">{formatDate(paper.createdAt)}</div>
      </div>
    </div>
  );
}
