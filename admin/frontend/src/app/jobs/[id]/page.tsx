'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { collectionJobsApi } from '@/lib/api';
import { JobInfo, ErrorStats, ErrorList } from './_components';

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.id as string;
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
        <button onClick={() => router.back()} className="rounded p-2 hover:bg-gray-100">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Job Details</h1>
          <p className="mt-1 text-sm text-gray-500">{job.id}</p>
        </div>
      </div>

      <JobInfo job={job} />

      {errorStats && <ErrorStats stats={errorStats} />}

      <ErrorList
        errors={errorsData?.errors || []}
        total={errorsData?.total ?? 0}
        stageFilter={stageFilter}
        onStageFilterChange={setStageFilter}
        isLoading={errorsLoading}
      />
    </div>
  );
}
