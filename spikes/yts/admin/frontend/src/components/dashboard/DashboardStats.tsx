'use client';

import { useQuery } from '@tanstack/react-query';
import { FileText, Search, Clock, CheckCircle } from 'lucide-react';
import { papersApi } from '@/lib/api';
import { formatNumber } from '@/lib/utils';

export function DashboardStats() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: papersApi.getStats,
  });

  const statItems = [
    {
      name: 'Total Papers',
      value: stats?.totalPapers ?? 0,
      icon: FileText,
      color: 'bg-blue-500',
    },
    {
      name: 'Search Queries',
      value: stats?.totalQueries ?? 0,
      icon: Search,
      color: 'bg-green-500',
    },
    {
      name: 'Active Jobs',
      value: stats?.activeJobs ?? 0,
      icon: Clock,
      color: 'bg-yellow-500',
    },
    {
      name: 'Completed Today',
      value: stats?.completedJobsToday ?? 0,
      icon: CheckCircle,
      color: 'bg-purple-500',
    },
  ];

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <div
            key={i}
            className="h-32 animate-pulse rounded-lg bg-gray-200"
          />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
      {statItems.map((item) => (
        <div
          key={item.name}
          className="overflow-hidden rounded-lg bg-white shadow"
        >
          <div className="p-5">
            <div className="flex items-center">
              <div className={`flex-shrink-0 rounded-md ${item.color} p-3`}>
                <item.icon className="h-6 w-6 text-white" />
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="truncate text-sm font-medium text-gray-500">
                    {item.name}
                  </dt>
                  <dd className="text-2xl font-semibold text-gray-900">
                    {formatNumber(item.value)}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
