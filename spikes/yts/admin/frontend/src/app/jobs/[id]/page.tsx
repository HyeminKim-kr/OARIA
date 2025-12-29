'use client';

import { useQuery } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { collectionJobsApi } from '@/lib/api';
import { formatDate } from '@/lib/utils';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { useState } from 'react';

const stageLabels: Record<string, string> = {
  search: 'Search',
  download: 'Download',
  parse: 'Parse',
  save: 'Save',
};

const stageColors: Record<string, string> = {
  search: 'bg-blue-100 text-blue-800',
  download: 'bg-yellow-100 text-yellow-800',
  parse: 'bg-purple-100 text-purple-800',
  save: 'bg-green-100 text-green-800',
};

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.id as string;

  const [expandedErrors, setExpandedErrors] = useState<Set<string>>(new Set());
  const [stageFilter, setStageFilter] = useState<string>('all');

  const { data: job, isLoading: jobLoading } = useQuery({
    queryKey: ['collection-job', jobId],
    queryFn: () => collectionJobsApi.getOne(jobId),
    refetchInterval: 5000,
  });

  const { data: errorStats } = useQuery({
    queryKey: ['job-error-stats', jobId],
    queryFn: () => collectionJobsApi.getErrorStats(jobId),
    refetchInterval: 10000,
  });

  const { data: errorsData, isLoading: errorsLoading } = useQuery({
    queryKey: ['job-errors', jobId, stageFilter],
    queryFn: () =>
      collectionJobsApi.getErrors(jobId, {
        stage: stageFilter === 'all' ? undefined : stageFilter,
        limit: 100,
      }),
    refetchInterval: 10000,
  });

  const toggleExpand = (errorId: string) => {
    const newSet = new Set(expandedErrors);
    if (newSet.has(errorId)) {
      newSet.delete(errorId);
    } else {
      newSet.add(errorId);
    }
    setExpandedErrors(newSet);
  };

  if (jobLoading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 w-48 rounded bg-gray-200" />
        <div className="h-40 rounded-lg bg-gray-200" />
      </div>
    );
  }

  if (!job) {
    return <div>Job not found</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.back()}
          className="rounded p-2 hover:bg-gray-100"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Job Details</h1>
          <p className="mt-1 text-sm text-gray-500">{job.id}</p>
        </div>
      </div>

      {/* Job Info */}
      <div className="rounded-lg bg-white p-6 shadow">
        <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
          <div>
            <dt className="text-sm font-medium text-gray-500">Status</dt>
            <dd className="mt-1">
              <StatusBadge status={job.status} />
            </dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">Type</dt>
            <dd className="mt-1 text-sm text-gray-900">{job.jobType}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">Progress</dt>
            <dd className="mt-1 text-sm text-gray-900">
              {job.processedCount} / {job.totalCount ?? '?'}
              {job.failedCount > 0 && (
                <span className="ml-2 text-red-500">
                  ({job.failedCount} failed)
                </span>
              )}
            </dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">Started</dt>
            <dd className="mt-1 text-sm text-gray-900">
              {formatDate(job.startedAt)}
            </dd>
          </div>
        </div>
        <div className="mt-4">
          <dt className="text-sm font-medium text-gray-500">Query</dt>
          <dd className="mt-1 text-sm text-gray-900">{job.query}</dd>
        </div>
        {job.lastErrorMessage && (
          <div className="mt-4 rounded-lg bg-red-50 p-4">
            <div className="flex items-start gap-2">
              <AlertCircle className="mt-0.5 h-4 w-4 text-red-500" />
              <div>
                <div className="text-sm font-medium text-red-800">
                  Last Error: {job.lastErrorCode}
                </div>
                <div className="mt-1 text-sm text-red-700">
                  {job.lastErrorMessage}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Error Stats */}
      {errorStats && errorStats.total > 0 && (
        <div className="rounded-lg bg-white p-6 shadow">
          <h2 className="text-lg font-semibold text-gray-900">Error Summary</h2>
          <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
            <div className="rounded-lg bg-red-50 p-4">
              <div className="text-2xl font-bold text-red-600">
                {errorStats.total}
              </div>
              <div className="text-sm text-red-800">Total Errors</div>
            </div>
            {Object.entries(errorStats.byStage).map(([stage, count]) => (
              <div key={stage} className="rounded-lg bg-gray-50 p-4">
                <div className="text-2xl font-bold text-gray-900">{count}</div>
                <div className="text-sm text-gray-600">
                  {stageLabels[stage] || stage}
                </div>
              </div>
            ))}
          </div>
          {Object.keys(errorStats.byCode).length > 0 && (
            <div className="mt-4">
              <div className="text-sm font-medium text-gray-500">By Error Code</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {Object.entries(errorStats.byCode).map(([code, count]) => (
                  <span
                    key={code}
                    className="inline-flex items-center rounded-full bg-gray-100 px-3 py-1 text-sm"
                  >
                    <span className="font-medium">{code}</span>
                    <span className="ml-2 text-gray-500">{count}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Error List */}
      <div className="rounded-lg bg-white p-6 shadow">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            Error Logs ({errorsData?.total ?? 0})
          </h2>
          <div className="flex gap-2">
            {['all', 'search', 'download', 'parse', 'save'].map((stage) => (
              <button
                key={stage}
                onClick={() => setStageFilter(stage)}
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

        {errorsLoading ? (
          <div className="mt-4 animate-pulse space-y-2">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-16 rounded bg-gray-100" />
            ))}
          </div>
        ) : errorsData && errorsData.errors.length > 0 ? (
          <div className="mt-4 space-y-2">
            {errorsData.errors.map((error) => (
              <div
                key={error.id}
                className="rounded-lg border border-gray-200 bg-gray-50"
              >
                <div
                  className="flex cursor-pointer items-center justify-between p-4"
                  onClick={() => toggleExpand(error.id)}
                >
                  <div className="flex items-center gap-4">
                    <span
                      className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${stageColors[error.stage] || 'bg-gray-100 text-gray-800'}`}
                    >
                      {stageLabels[error.stage] || error.stage}
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
                    <span className="text-xs text-gray-500">
                      {formatDate(error.createdAt)}
                    </span>
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
                        <div className="text-xs font-medium text-gray-500">
                          Error Message
                        </div>
                        <div className="mt-1 text-sm text-gray-900">
                          {error.errorMessage}
                        </div>
                      </div>
                      {error.errorDetail && (
                        <div>
                          <div className="text-xs font-medium text-gray-500">
                            Stack Trace
                          </div>
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
                          <div className="text-xs font-medium text-gray-500">
                            Context
                          </div>
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
          <div className="mt-8 text-center text-gray-500">
            No errors found for this job
          </div>
        )}
      </div>
    </div>
  );
}
