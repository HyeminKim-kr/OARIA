import { STAGE_LABELS } from '../_lib';

interface ErrorStatsData {
  total: number;
  byStage: Record<string, number>;
  byCode: Record<string, number>;
}

interface ErrorStatsProps {
  stats: ErrorStatsData;
}

export function ErrorStats({ stats }: ErrorStatsProps) {
  if (stats.total === 0) return null;

  return (
    <div className="rounded-lg bg-white p-6 shadow">
      <h2 className="text-lg font-semibold text-gray-900">Error Summary</h2>
      <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="rounded-lg bg-red-50 p-4">
          <div className="text-2xl font-bold text-red-600">{stats.total}</div>
          <div className="text-sm text-red-800">Total Errors</div>
        </div>
        {Object.entries(stats.byStage).map(([stage, count]) => (
          <div key={stage} className="rounded-lg bg-gray-50 p-4">
            <div className="text-2xl font-bold text-gray-900">{count}</div>
            <div className="text-sm text-gray-600">{STAGE_LABELS[stage] || stage}</div>
          </div>
        ))}
      </div>
      {Object.keys(stats.byCode).length > 0 && (
        <div className="mt-4">
          <div className="text-sm font-medium text-gray-500">By Error Code</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {Object.entries(stats.byCode).map(([code, count]) => (
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
  );
}
