import { AlertCircle } from 'lucide-react';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { formatDate } from '@/lib/utils';
import { CollectionJob } from '@/lib/api';

interface JobInfoProps {
  job: CollectionJob;
}

export function JobInfo({ job }: JobInfoProps) {
  return (
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
              <span className="ml-2 text-red-500">({job.failedCount} failed)</span>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-sm font-medium text-gray-500">Started</dt>
          <dd className="mt-1 text-sm text-gray-900">{formatDate(job.startedAt)}</dd>
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
              <div className="mt-1 text-sm text-red-700">{job.lastErrorMessage}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
