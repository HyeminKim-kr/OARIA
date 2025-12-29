'use client';

import { useQuery } from '@tanstack/react-query';
import { Search, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import { papersApi } from '@/lib/api';
import { formatDate, formatNumber } from '@/lib/utils';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { useState } from 'react';

export default function PapersPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const limit = 20;

  const { data, isLoading } = useQuery({
    queryKey: ['papers', page, search],
    queryFn: () => papersApi.getAll({ page, limit, search: search || undefined }),
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Papers</h1>
        <p className="mt-1 text-sm text-gray-500">
          Browse collected cancer research papers
        </p>
      </div>

      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search papers by title, abstract, or keywords..."
            className="w-full rounded-md border border-gray-300 py-2 pl-10 pr-4 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <button
          type="submit"
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Search
        </button>
      </form>

      {isLoading ? (
        <div className="animate-pulse space-y-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-32 rounded-lg bg-gray-200" />
          ))}
        </div>
      ) : (
        <>
          <div className="rounded-lg bg-white shadow">
            <div className="border-b border-gray-200 px-6 py-4">
              <p className="text-sm text-gray-500">
                Showing {formatNumber((page - 1) * limit + 1)} -{' '}
                {formatNumber(Math.min(page * limit, data?.total ?? 0))} of{' '}
                {formatNumber(data?.total ?? 0)} papers
              </p>
            </div>
            <div className="divide-y divide-gray-200">
              {data?.items && data.items.length > 0 ? (
                data.items.map((paper) => (
                  <div key={paper.id} className="p-6 hover:bg-gray-50">
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
                        </div>
                        {paper.abstract && (
                          <p className="mt-2 line-clamp-2 text-sm text-gray-600">
                            {paper.abstract}
                          </p>
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
                      <div className="text-right text-sm text-gray-500">
                        {formatDate(paper.createdAt)}
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="px-6 py-12 text-center text-gray-500">
                  No papers found
                </div>
              )}
            </div>
          </div>

          {data && data.totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="rounded-md border border-gray-300 px-3 py-1.5 text-sm disabled:opacity-50"
              >
                Previous
              </button>
              <span className="text-sm text-gray-500">
                Page {page} of {data.totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(data.totalPages, p + 1))}
                disabled={page === data.totalPages}
                className="rounded-md border border-gray-300 px-3 py-1.5 text-sm disabled:opacity-50"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
