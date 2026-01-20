'use client';

import { useEffect, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { X, Search, Loader2 } from 'lucide-react';
import { searchQueriesApi, SearchQuery, QueryType } from '@/lib/api';

interface QueryModalProps {
  isOpen: boolean;
  onClose: () => void;
  query: SearchQuery | null;
}

export function QueryModal({ isOpen, onClose, query }: QueryModalProps) {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({
    name: '',
    query: '',
    description: '',
    queryType: 'production' as QueryType,
    isActive: true,
    priority: 10,
    maxResults: '',
    yearFrom: '',
    yearTo: '',
    openAccessOnly: true,
    maxConcurrent: 35,
    autoBackfill: false,
  });
  const [preview, setPreview] = useState<{ hitCount: number; fullQuery: string } | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  useEffect(() => {
    if (query) {
      setFormData({
        name: query.name,
        query: query.query,
        description: query.description || '',
        queryType: query.queryType || 'production',
        isActive: query.isActive,
        priority: query.priority,
        maxResults: query.maxResults?.toString() || '',
        yearFrom: query.yearFrom?.toString() || '',
        yearTo: query.yearTo?.toString() || '',
        openAccessOnly: query.openAccessOnly,
        maxConcurrent: query.maxConcurrent || 35,
        autoBackfill: query.autoBackfill || false,
      });
    } else {
      setFormData({
        name: '',
        query: '',
        description: '',
        queryType: 'production',
        isActive: true,
        priority: 10,
        maxResults: '',
        yearFrom: '',
        yearTo: '',
        openAccessOnly: true,
        maxConcurrent: 35,
        autoBackfill: false,
      });
    }
    // 모달 열릴 때마다 preview 초기화
    setPreview(null);
    setPreviewError(null);
  }, [query, isOpen]);

  const handlePreview = async () => {
    if (!formData.query.trim()) return;

    setPreviewLoading(true);
    setPreviewError(null);
    setPreview(null);

    try {
      const result = await searchQueriesApi.preview({
        query: formData.query,
        yearFrom: formData.yearFrom ? parseInt(formData.yearFrom) : undefined,
        yearTo: formData.yearTo ? parseInt(formData.yearTo) : undefined,
        openAccessOnly: formData.openAccessOnly,
      });
      setPreview(result);
    } catch (err) {
      setPreviewError('검색 결과를 가져올 수 없습니다');
    } finally {
      setPreviewLoading(false);
    }
  };

  const createMutation = useMutation({
    mutationFn: searchQueriesApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['search-queries'] });
      onClose();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<SearchQuery> }) =>
      searchQueriesApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['search-queries'] });
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const data = {
      name: formData.name,
      query: formData.query,
      description: formData.description || null,
      queryType: formData.queryType,
      isActive: formData.isActive,
      priority: formData.priority,
      maxResults: formData.maxResults ? parseInt(formData.maxResults) : null,
      yearFrom: formData.yearFrom ? parseInt(formData.yearFrom) : null,
      yearTo: formData.yearTo ? parseInt(formData.yearTo) : null,
      openAccessOnly: formData.openAccessOnly,
      maxConcurrent: formData.maxConcurrent,
      autoBackfill: formData.autoBackfill,
    };

    if (query) {
      updateMutation.mutate({ id: query.id, data });
    } else {
      createMutation.mutate(data);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">
            {query ? 'Edit Query' : 'New Query'}
          </h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Name *
              </label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Type *
              </label>
              <select
                value={formData.queryType}
                onChange={(e) =>
                  setFormData({ ...formData, queryType: e.target.value as QueryType })
                }
                disabled={!!query} // 수정 시에는 타입 변경 불가
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              >
                <option value="production">Production</option>
                <option value="sample">Sample (Lab 테스트용)</option>
              </select>
              {formData.queryType === 'sample' && !query && (
                <p className="mt-1 text-xs text-amber-600">
                  샘플 쿼리는 임베딩 관리에서 다양한 청킹/임베딩 전략 테스트용으로 사용됩니다.
                </p>
              )}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Query *
            </label>
            <div className="mt-1 flex gap-2">
              <input
                type="text"
                required
                value={formData.query}
                onChange={(e) => {
                  setFormData({ ...formData, query: e.target.value });
                  setPreview(null); // 쿼리 변경 시 미리보기 초기화
                }}
                placeholder="e.g., lung cancer immunotherapy"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <button
                type="button"
                onClick={handlePreview}
                disabled={!formData.query.trim() || previewLoading}
                className="flex items-center gap-1 rounded-md bg-gray-100 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 disabled:opacity-50"
              >
                {previewLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Search className="h-4 w-4" />
                )}
                미리보기
              </button>
            </div>
            {preview && (
              <div className="mt-2 rounded-md bg-blue-50 p-2 text-sm">
                <span className="font-semibold text-blue-800">
                  {preview.hitCount.toLocaleString()}건
                </span>
                <span className="text-blue-600"> 검색됨</span>
              </div>
            )}
            {previewError && (
              <p className="mt-2 text-sm text-red-600">{previewError}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Description
            </label>
            <textarea
              value={formData.description}
              onChange={(e) =>
                setFormData({ ...formData, description: e.target.value })
              }
              rows={2}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Year From
              </label>
              <input
                type="number"
                value={formData.yearFrom}
                onChange={(e) =>
                  setFormData({ ...formData, yearFrom: e.target.value })
                }
                placeholder="2020"
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Year To
              </label>
              <input
                type="number"
                value={formData.yearTo}
                onChange={(e) =>
                  setFormData({ ...formData, yearTo: e.target.value })
                }
                placeholder="2024"
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Priority
              </label>
              <input
                type="number"
                value={formData.priority}
                onChange={(e) =>
                  setFormData({ ...formData, priority: parseInt(e.target.value) || 10 })
                }
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Max Results
              </label>
              <input
                type="number"
                value={formData.maxResults}
                onChange={(e) =>
                  setFormData({ ...formData, maxResults: e.target.value })
                }
                placeholder="Unlimited"
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Concurrency
              </label>
              <input
                type="number"
                min={1}
                max={100}
                value={formData.maxConcurrent}
                onChange={(e) =>
                  setFormData({ ...formData, maxConcurrent: parseInt(e.target.value) || 35 })
                }
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <p className="mt-1 text-xs text-gray-500">API 동시 요청 수</p>
            </div>
          </div>

          <div className="flex items-center gap-6 flex-wrap">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={formData.isActive}
                onChange={(e) =>
                  setFormData({ ...formData, isActive: e.target.checked })
                }
                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">Active</span>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={formData.openAccessOnly}
                onChange={(e) =>
                  setFormData({ ...formData, openAccessOnly: e.target.checked })
                }
                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">Open Access Only</span>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={formData.autoBackfill}
                onChange={(e) =>
                  setFormData({ ...formData, autoBackfill: e.target.checked })
                }
                className="h-4 w-4 rounded border-gray-300 text-green-600 focus:ring-green-500"
              />
              <span className="text-sm text-gray-700">Auto Backfill</span>
            </label>
          </div>

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
              disabled={createMutation.isPending || updateMutation.isPending}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {query ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
