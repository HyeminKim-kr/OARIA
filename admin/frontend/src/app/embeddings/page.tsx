'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, Play, RefreshCw, Database, FlaskConical, CheckCircle2, XCircle, Clock, Loader2, RotateCcw, Ban } from 'lucide-react';
import {
  searchQueriesApi,
  sampleEmbeddingsApi,
  labApi,
  SearchQuery,
  SampleEmbedding,
  DBStrategiesResponse,
} from '@/lib/api';
import { formatDate, formatNumber } from '@/lib/utils';
import { useState } from 'react';

type StatusFilter = 'all' | 'pending' | 'processing' | 'completed' | 'failed';

function StatusBadge({ status }: { status: SampleEmbedding['status'] }) {
  const config = {
    pending: { icon: Clock, className: 'bg-yellow-100 text-yellow-800' },
    processing: { icon: Loader2, className: 'bg-blue-100 text-blue-800' },
    completed: { icon: CheckCircle2, className: 'bg-green-100 text-green-800' },
    failed: { icon: XCircle, className: 'bg-red-100 text-red-800' },
  };

  const { icon: Icon, className } = config[status];

  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium ${className}`}>
      <Icon className={`h-3 w-3 ${status === 'processing' ? 'animate-spin' : ''}`} />
      {status}
    </span>
  );
}

export default function EmbeddingsPage() {
  const queryClient = useQueryClient();
  const [selectedQueryId, setSelectedQueryId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  // Fetch sample queries
  const { data: sampleQueries, isLoading: isLoadingQueries } = useQuery({
    queryKey: ['search-queries', 'sample'],
    queryFn: () => searchQueriesApi.getAll({ queryType: 'sample' }),
  });

  // Fetch sample embeddings
  const { data: embeddings, isLoading: isLoadingEmbeddings } = useQuery({
    queryKey: ['sample-embeddings', selectedQueryId, statusFilter],
    queryFn: () =>
      sampleEmbeddingsApi.getAll({
        queryId: selectedQueryId || undefined,
        status: statusFilter === 'all' ? undefined : statusFilter,
      }),
  });

  // Fetch strategies for the create modal (DB 기반)
  const { data: strategies } = useQuery({
    queryKey: ['strategies-db'],
    queryFn: () => labApi.getStrategiesFromDB(true),
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: sampleEmbeddingsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sample-embeddings'] });
    },
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: sampleEmbeddingsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sample-embeddings'] });
      setIsCreateModalOpen(false);
    },
  });

  // Retry mutation
  const retryMutation = useMutation({
    mutationFn: sampleEmbeddingsApi.retry,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sample-embeddings'] });
    },
  });

  // Cancel mutation
  const cancelMutation = useMutation({
    mutationFn: sampleEmbeddingsApi.cancel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sample-embeddings'] });
    },
  });

  const handleDelete = (id: string, collectionName: string) => {
    if (confirm(`Delete embedding "${collectionName}"? This will also remove the Weaviate collection.`)) {
      deleteMutation.mutate(id);
    }
  };

  const handleRetry = (id: string) => {
    if (confirm('Retry this embedding job?')) {
      retryMutation.mutate(id);
    }
  };

  const handleCancel = (id: string) => {
    if (confirm('Cancel this embedding job?')) {
      cancelMutation.mutate(id);
    }
  };

  const selectedQuery = sampleQueries?.find((q) => q.id === selectedQueryId);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Embedding Management</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage sample embeddings for RAG experiments
          </p>
        </div>
        <button
          onClick={() => setIsCreateModalOpen(true)}
          disabled={!selectedQueryId}
          className="flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus className="h-4 w-4" />
          New Embedding
        </button>
      </div>

      {/* Sample Query Selector */}
      <div className="rounded-lg bg-white p-4 shadow">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <FlaskConical className="h-4 w-4" />
            Sample Query:
          </div>
          <select
            value={selectedQueryId || ''}
            onChange={(e) => setSelectedQueryId(e.target.value || null)}
            className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">All Sample Queries</option>
            {sampleQueries?.map((query) => (
              <option key={query.id} value={query.id}>
                {query.name} ({formatNumber(query.totalCollected)} papers)
              </option>
            ))}
          </select>

          {/* Status Filter */}
          <div className="flex items-center gap-2 text-sm text-gray-600">
            Status:
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="all">All</option>
            <option value="pending">Pending</option>
            <option value="processing">Processing</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>

          <button
            onClick={() => queryClient.invalidateQueries({ queryKey: ['sample-embeddings'] })}
            className="ml-auto flex items-center gap-1 rounded-md px-3 py-2 text-sm text-gray-600 hover:bg-gray-100"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
        </div>

        {selectedQuery && (
          <div className="mt-3 rounded-md bg-gray-50 p-3 text-sm">
            <div className="font-medium text-gray-700">{selectedQuery.name}</div>
            <div className="mt-1 text-gray-500">
              Query: {selectedQuery.query} | Papers: {formatNumber(selectedQuery.totalCollected)}
            </div>
          </div>
        )}
      </div>

      {/* No Sample Queries Warning */}
      {!isLoadingQueries && (!sampleQueries || sampleQueries.length === 0) && (
        <div className="rounded-lg border-2 border-dashed border-gray-300 p-8 text-center">
          <FlaskConical className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No Sample Queries</h3>
          <p className="mt-1 text-sm text-gray-500">
            Create a sample query in the Search Queries page first.
          </p>
        </div>
      )}

      {/* Embeddings List */}
      {isLoadingEmbeddings ? (
        <div className="animate-pulse space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-24 rounded-lg bg-gray-200" />
          ))}
        </div>
      ) : embeddings && embeddings.length > 0 ? (
        <div className="space-y-4">
          {embeddings.map((embedding) => (
            <div
              key={embedding.id}
              className="rounded-lg bg-white p-4 shadow hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <Database className="h-5 w-5 text-gray-400" />
                    <div className="font-medium text-gray-900">
                      {embedding.chunker} + {embedding.embedder}
                    </div>
                    <StatusBadge status={embedding.status} />
                  </div>

                  <div className="mt-2 grid grid-cols-4 gap-4 text-sm text-gray-500">
                    <div>
                      <span className="text-gray-400">Collection:</span>{' '}
                      <span className="font-mono text-xs">{embedding.collectionName}</span>
                    </div>
                    <div>
                      <span className="text-gray-400">Papers:</span>{' '}
                      {formatNumber(embedding.paperCount)}
                    </div>
                    <div>
                      <span className="text-gray-400">Chunks:</span>{' '}
                      {formatNumber(embedding.chunkCount)}
                    </div>
                    <div>
                      <span className="text-gray-400">Created:</span>{' '}
                      {formatDate(embedding.createdAt)}
                    </div>
                  </div>

                  {embedding.errorMessage && (
                    <div className="mt-2 rounded-md bg-red-50 p-2 text-sm text-red-700">
                      {embedding.errorMessage}
                    </div>
                  )}

                  {embedding.searchQuery && (
                    <div className="mt-2 text-xs text-gray-400">
                      Query: {embedding.searchQuery.name}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  {embedding.status === 'completed' && (
                    <button
                      className="flex items-center gap-1 rounded-md bg-green-50 px-3 py-1.5 text-sm text-green-700 hover:bg-green-100"
                      onClick={() => {
                        // Navigate to Lab with this collection selected
                        window.location.href = `/lab?collection=${embedding.collectionName}`;
                      }}
                    >
                      <Play className="h-4 w-4" />
                      Test in Lab
                    </button>
                  )}
                  {(embedding.status === 'failed' || embedding.status === 'processing') && (
                    <button
                      onClick={() => handleRetry(embedding.id)}
                      disabled={retryMutation.isPending}
                      className="flex items-center gap-1 rounded-md bg-blue-50 px-3 py-1.5 text-sm text-blue-700 hover:bg-blue-100 disabled:opacity-50"
                      title="Retry"
                    >
                      <RotateCcw className={`h-4 w-4 ${retryMutation.isPending ? 'animate-spin' : ''}`} />
                      Retry
                    </button>
                  )}
                  {(embedding.status === 'pending' || embedding.status === 'processing') && (
                    <button
                      onClick={() => handleCancel(embedding.id)}
                      disabled={cancelMutation.isPending}
                      className="flex items-center gap-1 rounded-md bg-orange-50 px-3 py-1.5 text-sm text-orange-700 hover:bg-orange-100 disabled:opacity-50"
                      title="Cancel"
                    >
                      <Ban className="h-4 w-4" />
                      Cancel
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(embedding.id, embedding.collectionName)}
                    disabled={embedding.status === 'processing'}
                    className="rounded p-2 text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        sampleQueries && sampleQueries.length > 0 && (
          <div className="rounded-lg border-2 border-dashed border-gray-300 p-8 text-center">
            <Database className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">No Embeddings</h3>
            <p className="mt-1 text-sm text-gray-500">
              {selectedQueryId
                ? 'Create an embedding for this sample query.'
                : 'Select a sample query and create embeddings.'}
            </p>
          </div>
        )
      )}

      {/* Create Modal */}
      {isCreateModalOpen && (
        <CreateEmbeddingModal
          queryId={selectedQueryId!}
          queries={sampleQueries || []}
          strategies={strategies}
          onClose={() => setIsCreateModalOpen(false)}
          onCreate={(data) => createMutation.mutate(data)}
          isCreating={createMutation.isPending}
        />
      )}
    </div>
  );
}

// Create Embedding Modal Component
function CreateEmbeddingModal({
  queryId,
  queries,
  strategies,
  onClose,
  onCreate,
  isCreating,
}: {
  queryId: string;
  queries: SearchQuery[];
  strategies?: DBStrategiesResponse;
  onClose: () => void;
  onCreate: (data: { queryId: string; chunker: string; embedder: string }) => void;
  isCreating: boolean;
}) {
  const [selectedQueryId, setSelectedQueryId] = useState(queryId);
  const [chunker, setChunker] = useState('');
  const [embedder, setEmbedder] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedQueryId && chunker && embedder) {
      onCreate({ queryId: selectedQueryId, chunker, embedder });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-gray-900">Create New Embedding</h2>
        <p className="mt-1 text-sm text-gray-500">
          Select a chunking strategy and embedding model for the sample query.
        </p>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          {/* Query Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Sample Query
            </label>
            <select
              value={selectedQueryId}
              onChange={(e) => setSelectedQueryId(e.target.value)}
              required
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">Select a query</option>
              {queries.map((q) => (
                <option key={q.id} value={q.id}>
                  {q.name} ({formatNumber(q.totalCollected)} papers)
                </option>
              ))}
            </select>
          </div>

          {/* Chunker Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Chunking Strategy
            </label>
            <select
              value={chunker}
              onChange={(e) => setChunker(e.target.value)}
              required
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">Select chunker</option>
              {strategies?.chunkers.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}{c.description ? ` - ${c.description.split('\n')[0]}` : ''}
                </option>
              ))}
            </select>
          </div>

          {/* Embedder Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Embedding Model
            </label>
            <select
              value={embedder}
              onChange={(e) => setEmbedder(e.target.value)}
              required
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">Select embedder</option>
              {strategies?.embedders.map((e) => (
                <option key={e.name} value={e.name}>
                  {e.name}{e.description ? ` - ${e.description.split('\n')[0]}` : ''}
                </option>
              ))}
            </select>
          </div>

          {/* Preview */}
          {chunker && embedder && (
            <div className="rounded-md bg-gray-50 p-3 text-sm">
              <div className="text-gray-600">Pipeline Key:</div>
              <div className="font-mono text-xs text-gray-800">
                {chunker}__{embedder}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!selectedQueryId || !chunker || !embedder || isCreating}
              className="flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isCreating && <Loader2 className="h-4 w-4 animate-spin" />}
              Create Embedding
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
