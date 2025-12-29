'use client';

import { RefreshCw } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';

export function Header() {
  const queryClient = useQueryClient();

  const handleRefresh = () => {
    queryClient.invalidateQueries();
  };

  return (
    <header className="flex h-16 items-center justify-between border-b bg-white px-6">
      <div className="flex items-center gap-4">
        <span className="text-sm text-gray-500">
          {new Date().toLocaleDateString('ko-KR', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
          })}
        </span>
      </div>
      <div className="flex items-center gap-4">
        <button
          onClick={handleRefresh}
          className="flex items-center gap-2 rounded-md bg-gray-100 px-3 py-2 text-sm text-gray-700 hover:bg-gray-200"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>
    </header>
  );
}
