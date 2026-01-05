import { DashboardStats } from '@/components/dashboard/DashboardStats';
import { EmbeddingStats } from '@/components/dashboard/EmbeddingStats';
import { RecentJobs } from '@/components/dashboard/RecentJobs';
import { SystemStatus } from '@/components/dashboard/SystemStatus';

export default function HomePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Cancer Paper Collection Service Overview
        </p>
      </div>
      <SystemStatus />
      <DashboardStats />
      <EmbeddingStats />
      <RecentJobs />
    </div>
  );
}
