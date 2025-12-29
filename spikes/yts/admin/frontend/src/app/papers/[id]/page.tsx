'use client';

import { useQuery } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, ExternalLink, FileText, Code } from 'lucide-react';
import { papersApi } from '@/lib/api';
import { formatDate } from '@/lib/utils';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { useState } from 'react';

export default function PaperDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [activeTab, setActiveTab] = useState<'fulltext' | 'xml'>('fulltext');

  const { data: paper, isLoading: paperLoading } = useQuery({
    queryKey: ['paper', id],
    queryFn: () => papersApi.getOne(id),
    enabled: !!id,
  });

  const { data: fulltext, isLoading: fulltextLoading } = useQuery({
    queryKey: ['paper-fulltext', id],
    queryFn: () => papersApi.getFulltext(id),
    enabled: !!id,
  });

  if (paperLoading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 w-64 rounded bg-gray-200" />
        <div className="h-64 rounded-lg bg-gray-200" />
      </div>
    );
  }

  if (!paper) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Paper not found</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.back()}
          className="rounded-full p-2 hover:bg-gray-100"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-xl font-bold text-gray-900">{paper.title}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-500">
            {paper.journal && <span>{paper.journal}</span>}
            {paper.year && <span>({paper.year})</span>}
            <StatusBadge status={paper.status} />
          </div>
        </div>
      </div>

      {/* Meta Info */}
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

      {/* Abstract */}
      {paper.abstract && (
        <div className="rounded-lg bg-white p-6 shadow">
          <h2 className="mb-3 font-semibold text-gray-900">Abstract</h2>
          <p className="text-sm leading-relaxed text-gray-700">{paper.abstract}</p>
        </div>
      )}

      {/* Keywords */}
      {paper.keywords && paper.keywords.length > 0 && (
        <div className="rounded-lg bg-white p-6 shadow">
          <h2 className="mb-3 font-semibold text-gray-900">Keywords</h2>
          <div className="flex flex-wrap gap-2">
            {paper.keywords.map((keyword, idx) => (
              <span
                key={idx}
                className="rounded-full bg-gray-100 px-3 py-1 text-sm text-gray-700"
              >
                {keyword}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Fulltext / XML Tabs */}
      <div className="rounded-lg bg-white shadow">
        <div className="border-b border-gray-200">
          <nav className="flex">
            <button
              onClick={() => setActiveTab('fulltext')}
              className={`flex items-center gap-2 px-6 py-3 text-sm font-medium ${
                activeTab === 'fulltext'
                  ? 'border-b-2 border-blue-500 text-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <FileText className="h-4 w-4" />
              Full Text
            </button>
            <button
              onClick={() => setActiveTab('xml')}
              className={`flex items-center gap-2 px-6 py-3 text-sm font-medium ${
                activeTab === 'xml'
                  ? 'border-b-2 border-blue-500 text-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <Code className="h-4 w-4" />
              Raw XML
            </button>
          </nav>
        </div>

        <div className="p-6">
          {fulltextLoading ? (
            <div className="animate-pulse">
              <div className="h-4 w-full rounded bg-gray-200 mb-2" />
              <div className="h-4 w-5/6 rounded bg-gray-200 mb-2" />
              <div className="h-4 w-4/6 rounded bg-gray-200" />
            </div>
          ) : activeTab === 'fulltext' ? (
            fulltext?.fulltext ? (
              <pre className="max-h-[600px] overflow-auto whitespace-pre-wrap text-sm text-gray-700 font-sans leading-relaxed">
                {fulltext.fulltext}
              </pre>
            ) : (
              <p className="text-gray-500 text-center py-8">
                Full text not available
              </p>
            )
          ) : fulltext?.rawXml ? (
            <pre className="max-h-[600px] overflow-auto text-xs text-gray-700 font-mono bg-gray-50 p-4 rounded">
              {fulltext.rawXml}
            </pre>
          ) : (
            <p className="text-gray-500 text-center py-8">
              Raw XML not available
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
