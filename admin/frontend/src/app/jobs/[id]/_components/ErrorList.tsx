'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { ArticleError } from '@/lib/api';
import { formatDate } from '@/lib/utils';
import { STAGE_LABELS, STAGE_COLORS } from '../_lib';

interface ErrorListProps {
  errors: ArticleError[];
  total: number;
  stageFilter: string;
  onStageFilterChange: (stage: string) => void;
  isLoading: boolean;
}

export function ErrorList({
  errors,
  total,
  stageFilter,
  onStageFilterChange,
  isLoading,
}: ErrorListProps) {
  const [expandedErrors, setExpandedErrors] = useState<Set<string>>(new Set());

  const toggleExpand = (errorId: string) => {
    const newSet = new Set(expandedErrors);
    if (newSet.has(errorId)) {
      newSet.delete(errorId);
    } else {
      newSet.add(errorId);
    }
    setExpandedErrors(newSet);
  };

  return (
    <div className="rounded-lg bg-white p-6 shadow">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Error Logs ({total})</h2>
        <div className="flex gap-2">
          {['all', 'search', 'download', 'parse', 'save'].map((stage) => (
            <button
              key={stage}
              onClick={() => onStageFilterChange(stage)}
              className={`rounded-full px-3 py-1 text-sm font-medium capitalize ${
                stageFilter === stage
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {stage}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="mt-4 animate-pulse space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 rounded bg-gray-100" />
          ))}
        </div>
      ) : errors.length > 0 ? (
        <div className="mt-4 space-y-2">
          {errors.map((error) => (
            <div key={error.id} className="rounded-lg border border-gray-200 bg-gray-50">
              <div
                className="flex cursor-pointer items-center justify-between p-4"
                onClick={() => toggleExpand(error.id)}
              >
                <div className="flex items-center gap-4">
                  <span
                    className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${
                      STAGE_COLORS[error.stage] || 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {STAGE_LABELS[error.stage] || error.stage}
                  </span>
                  <span className="font-mono text-sm text-gray-600">
                    {error.pmcid || error.pmid || error.doi || '-'}
                  </span>
                  {error.errorCode && (
                    <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800">
                      {error.errorCode}
                    </span>
                  )}
                  <span className="max-w-md truncate text-sm text-gray-900">
                    {error.errorMessage}
                  </span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-xs text-gray-500">{formatDate(error.createdAt)}</span>
                  {expandedErrors.has(error.id) ? (
                    <ChevronUp className="h-4 w-4 text-gray-400" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-gray-400" />
                  )}
                </div>
              </div>
              {expandedErrors.has(error.id) && (
                <div className="border-t border-gray-200 bg-white p-4">
                  <div className="space-y-4">
                    <div>
                      <div className="text-xs font-medium text-gray-500">Error Message</div>
                      <div className="mt-1 text-sm text-gray-900">{error.errorMessage}</div>
                    </div>
                    {error.errorDetail && (
                      <div>
                        <div className="text-xs font-medium text-gray-500">Stack Trace</div>
                        <pre className="mt-1 max-h-60 overflow-auto rounded bg-gray-900 p-3 text-xs text-gray-100">
                          {error.errorDetail}
                        </pre>
                      </div>
                    )}
                    {error.rawResponse && (
                      <div>
                        <div className="text-xs font-medium text-gray-500">
                          Raw Response (first 1000 chars)
                        </div>
                        <pre className="mt-1 max-h-40 overflow-auto rounded bg-gray-100 p-3 text-xs text-gray-700">
                          {error.rawResponse.slice(0, 1000)}
                          {error.rawResponse.length > 1000 && '...'}
                        </pre>
                      </div>
                    )}
                    {error.context && Object.keys(error.context).length > 0 && (
                      <div>
                        <div className="text-xs font-medium text-gray-500">Context</div>
                        <pre className="mt-1 rounded bg-gray-100 p-3 text-xs text-gray-700">
                          {JSON.stringify(error.context, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-8 text-center text-gray-500">No errors found for this job</div>
      )}
    </div>
  );
}
