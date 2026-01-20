import { ExternalLink } from 'lucide-react';
import { formatDate } from '@/lib/utils';
import { Paper } from '@/lib/api';

interface PaperMetaProps {
  paper: Paper;
}

export function PaperMeta({ paper }: PaperMetaProps) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
      {paper.pmcid && (
        <div className="rounded-lg bg-white p-4 shadow">
          <p className="text-xs text-gray-500">PMC ID</p>
          <p className="font-medium text-blue-600">{paper.pmcid}</p>
        </div>
      )}
      {paper.pmid && (
        <div className="rounded-lg bg-white p-4 shadow">
          <p className="text-xs text-gray-500">PMID</p>
          <p className="font-medium text-green-600">{paper.pmid}</p>
        </div>
      )}
      {paper.doi && (
        <div className="rounded-lg bg-white p-4 shadow">
          <p className="text-xs text-gray-500">DOI</p>
          <a
            href={`https://doi.org/${paper.doi}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 font-medium text-purple-600 hover:underline"
          >
            {paper.doi}
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      )}
      <div className="rounded-lg bg-white p-4 shadow">
        <p className="text-xs text-gray-500">Collected</p>
        <p className="font-medium">{formatDate(paper.createdAt)}</p>
      </div>
    </div>
  );
}
