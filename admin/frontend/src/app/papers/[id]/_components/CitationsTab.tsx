'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Quote, ExternalLink, Loader2, BookOpen, ArrowRight } from 'lucide-react';
import { papersApi, CitationItem } from '@/lib/api';

interface CitationsTabProps {
  paperId: string;
  citationCount: number;
  referenceCount: number;
}

function CitationItemCard({ item, type }: { item: CitationItem; type: 'citation' | 'reference' }) {
  const label = type === 'citation' ? '인용한 논문' : '참조된 논문';

  return (
    <div className="flex items-center justify-between border-b border-gray-100 py-3 last:border-0">
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm text-gray-900">{item.paperId}</span>
          {item.pmcid && (
            <a
              href={`https://www.ncbi.nlm.nih.gov/pmc/articles/${item.pmcid}/`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded bg-blue-50 px-2 py-0.5 text-xs text-blue-700 hover:bg-blue-100"
            >
              PMC <ExternalLink className="h-3 w-3" />
            </a>
          )}
          {item.pmid && (
            <a
              href={`https://pubmed.ncbi.nlm.nih.gov/${item.pmid}/`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded bg-green-50 px-2 py-0.5 text-xs text-green-700 hover:bg-green-100"
            >
              PMID <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
        <p className="mt-1 text-xs text-gray-500">
          수집 출처: {item.collectedFrom} · {new Date(item.createdAt).toLocaleDateString('ko-KR')}
        </p>
      </div>
    </div>
  );
}

export function CitationsTab({ paperId, citationCount, referenceCount }: CitationsTabProps) {
  const [activeTab, setActiveTab] = useState<'citations' | 'references'>('citations');

  const { data: citations, isLoading: citationsLoading } = useQuery({
    queryKey: ['paper', paperId, 'citations'],
    queryFn: () => papersApi.getCitations(paperId),
    enabled: activeTab === 'citations',
  });

  const { data: references, isLoading: referencesLoading } = useQuery({
    queryKey: ['paper', paperId, 'references'],
    queryFn: () => papersApi.getReferences(paperId),
    enabled: activeTab === 'references',
  });

  if (citationCount === 0 && referenceCount === 0) {
    return (
      <div className="rounded-lg bg-white p-6 shadow">
        <h2 className="mb-4 font-semibold text-gray-900">인용 관계</h2>
        <div className="flex items-center gap-3 text-gray-500">
          <Quote className="h-8 w-8 text-gray-300" />
          <span>인용 관계 정보가 없습니다.</span>
        </div>
      </div>
    );
  }

  const isLoading = activeTab === 'citations' ? citationsLoading : referencesLoading;
  const items = activeTab === 'citations' ? citations?.items : references?.items;
  const total = activeTab === 'citations' ? citations?.total : references?.total;

  return (
    <div className="rounded-lg bg-white p-6 shadow">
      <h2 className="mb-4 font-semibold text-gray-900">인용 관계</h2>

      {/* Tab buttons */}
      <div className="mb-4 flex gap-2 border-b border-gray-200">
        <button
          onClick={() => setActiveTab('citations')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'citations'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <ArrowRight className="h-4 w-4 rotate-180" />
          이 논문을 인용한 논문 ({citationCount})
        </button>
        <button
          onClick={() => setActiveTab('references')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'references'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <BookOpen className="h-4 w-4" />
          이 논문이 인용한 논문 ({referenceCount})
        </button>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
        </div>
      ) : items && items.length > 0 ? (
        <div className="max-h-96 overflow-y-auto">
          {items.map((item) => (
            <CitationItemCard
              key={item.id}
              item={item}
              type={activeTab === 'citations' ? 'citation' : 'reference'}
            />
          ))}
          {total && items.length < total && (
            <p className="mt-4 text-center text-sm text-gray-500">
              총 {total}개 중 {items.length}개 표시
            </p>
          )}
        </div>
      ) : (
        <div className="py-8 text-center text-gray-500">
          {activeTab === 'citations'
            ? '이 논문을 인용한 논문이 없습니다.'
            : '이 논문이 인용한 논문이 없습니다.'}
        </div>
      )}
    </div>
  );
}
