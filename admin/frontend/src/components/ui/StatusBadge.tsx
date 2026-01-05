import { cn } from '@/lib/utils';

interface StatusBadgeProps {
  status: string;
}

const statusStyles: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-800',
  running: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  partial: 'bg-amber-100 text-amber-800',
  delayed: 'bg-yellow-100 text-yellow-800',
  cancelled: 'bg-gray-100 text-gray-600',
  retried: 'bg-orange-100 text-orange-800',
  collected: 'bg-blue-100 text-blue-800',
  chunked: 'bg-purple-100 text-purple-800',
  indexed: 'bg-green-100 text-green-800',
};

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex rounded-full px-2 py-1 text-xs font-medium',
        statusStyles[status] || 'bg-gray-100 text-gray-800'
      )}
    >
      {status}
    </span>
  );
}
