'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Play, Edit, Trash2 } from 'lucide-react';
import { searchQueriesApi, SearchQuery } from '@/lib/api';
import { formatDate, formatNumber } from '@/lib/utils';
import { useState } from 'react';
import { QueryModal } from '@/components/queries/QueryModal';

export default function QueriesPage() {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingQuery, setEditingQuery] = useState<SearchQuery | null>(null);

  const { data: queries, isLoading } = useQuery({
    queryKey: ['search-queries'],
    queryFn: () => searchQueriesApi.getAll(),
  });

  const deleteMutation = useMutation({
    mutationFn: searchQueriesApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['search-queries'] });
    },
  });

  const backfillMutation = useMutation({
    mutationFn: searchQueriesApi.triggerBackfill,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['search-queries'] });
      queryClient.invalidateQueries({ queryKey: ['recent-jobs'] });
    },
  });

  const handleEdit = (query: SearchQuery) => {
    setEditingQuery(query);
    setIsModalOpen(true);
  };

  const handleCreate = () => {
    setEditingQuery(null);
    setIsModalOpen(true);
  };

  const handleDelete = (id: string) => {
    if (confirm('Are you sure you want to delete this query?')) {
      deleteMutation.mutate(id);
    }
  };

  const handleBackfill = (id: string) => {
    if (confirm('Start backfill job for this query?')) {
      backfillMutation.mutate(id);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Search Queries</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage search queries for paper collection
          </p>
        </div>
        <button
          onClick={handleCreate}
          className="flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          New Query
        </button>
      </div>

      {isLoading ? (
        <div className="animate-pulse space-y-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-24 rounded-lg bg-gray-200" />
          ))}
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg bg-white shadow">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Query
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Collected
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Last Backfill
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {queries?.map((query) => (
                <tr key={query.id} className="hover:bg-gray-50">
                  <td className="whitespace-nowrap px-6 py-4">
                    <div className="font-medium text-gray-900">{query.name}</div>
                    {query.description && (
                      <div className="text-sm text-gray-500">
                        {query.description}
                      </div>
                    )}
                  </td>
                  <td className="max-w-xs truncate px-6 py-4 text-sm text-gray-500">
                    {query.query}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4">
                    <span
                      className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${
                        query.queryType === 'sample'
                          ? 'bg-purple-100 text-purple-800'
                          : 'bg-blue-100 text-blue-800'
                      }`}
                    >
                      {query.queryType === 'sample' ? 'Sample' : 'Production'}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4">
                    <span
                      className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${
                        query.isActive
                          ? 'bg-green-100 text-green-800'
                          : 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {query.isActive ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                    {formatNumber(query.totalCollected)}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                    {formatDate(query.lastBackfillAt)}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-right text-sm">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => handleBackfill(query.id)}
                        className="rounded p-1 text-green-600 hover:bg-green-50"
                        title="Start Backfill"
                      >
                        <Play className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleEdit(query)}
                        className="rounded p-1 text-blue-600 hover:bg-blue-50"
                        title="Edit"
                      >
                        <Edit className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(query.id)}
                        className="rounded p-1 text-red-600 hover:bg-red-50"
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <QueryModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        query={editingQuery}
      />
    </div>
  );
}
