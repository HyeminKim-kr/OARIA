'use client';

import { useState, useMemo, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Settings,
  ChevronDown,
  Check,
  Save,
  Plus,
  Trash2,
  Loader2,
  AlertCircle,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';
import { ragSettingsApi, labApi, RAGSettings, StrategiesResponse } from '@/lib/api';
import { cn } from '@/lib/utils';

interface RAGSettingsPanelProps {
  strategies?: StrategiesResponse;
}

// 전략 타입
type StrategyType = 'chunker' | 'embedder' | 'retriever' | 'reranker' | 'classifier';

// 전략 값이 유효한지 확인하는 헬퍼 함수
function isValidStrategy(
  value: string | null,
  availableStrategies: string[],
  type: StrategyType
): boolean {
  // reranker와 classifier는 null 또는 'none'이 허용됨
  if ((type === 'reranker' || type === 'classifier') && (value === null || value === 'none')) {
    return true;
  }
  return value !== null && availableStrategies.includes(value);
}

export function RAGSettingsPanel({ strategies: initialStrategies }: RAGSettingsPanelProps) {
  const queryClient = useQueryClient();
  const [isExpanded, setIsExpanded] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Partial<RAGSettings>>({});
  const [showNewForm, setShowNewForm] = useState(false);
  const [newForm, setNewForm] = useState({
    name: '',
    description: '',
    chunker: '',
    embedder: '',
    retriever: '',
    reranker: 'none' as string | null,
    classifier: 'none' as string | null,
    parameters: { limit: 10, alpha: 0.7 },
  });

  // 백엔드에서 최신 전략 목록 가져오기
  const {
    data: strategies,
    isLoading: isLoadingStrategies,
    refetch: refetchStrategies,
    isRefetching: isRefetchingStrategies
  } = useQuery({
    queryKey: ['lab-strategies'],
    queryFn: labApi.getStrategies,
    initialData: initialStrategies,
    staleTime: 1000 * 60 * 5, // 5분간 캐시
  });

  // Fetch all settings
  const { data: settings, isLoading } = useQuery({
    queryKey: ['rag-settings'],
    queryFn: ragSettingsApi.getAll,
  });

  // Mutations
  const activateMutation = useMutation({
    mutationFn: ragSettingsApi.activate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rag-settings'] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: {
      name?: string;
      description?: string;
      chunker?: string;
      embedder?: string;
      retriever?: string;
      reranker?: string | null;
      classifier?: string | null;
    } }) => ragSettingsApi.update(id, {
      ...data,
      description: data.description ?? undefined,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rag-settings'] });
      setEditingId(null);
    },
  });

  const createMutation = useMutation({
    mutationFn: ragSettingsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rag-settings'] });
      setShowNewForm(false);
      setNewForm({
        name: '',
        description: '',
        chunker: 'semantic',
        embedder: 'openai',
        retriever: 'hybrid',
        reranker: 'bge',
        classifier: 'pubmedbert_domain_v1',
        parameters: { limit: 10, alpha: 0.7 },
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: ragSettingsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rag-settings'] });
    },
  });

  const activeSettings = settings?.find((s) => s.isActive);

  // 전략 옵션 (fallback 없이 순수하게 API에서 가져옴)
  const chunkerOptions = useMemo(() => strategies?.chunkers ?? [], [strategies?.chunkers]);
  const embedderOptions = useMemo(() => strategies?.embedders ?? [], [strategies?.embedders]);
  const retrieverOptions = useMemo(() => strategies?.retrievers ?? [], [strategies?.retrievers]);
  const rerankerOptions = useMemo(() => {
    const rerankers = strategies?.rerankers?.filter((r) => r !== 'none') ?? [];
    return ['none', ...rerankers];
  }, [strategies?.rerankers]);
  const classifierOptions = useMemo(() => {
    const classifiers = strategies?.classifiers?.filter((c) => c !== 'none') ?? [];
    return ['none', ...classifiers];
  }, [strategies?.classifiers]);

  // 새 폼 초기값 설정 (strategies 로드 후)
  useMemo(() => {
    if (strategies && newForm.chunker === '') {
      setNewForm((prev) => ({
        ...prev,
        chunker: strategies.chunkers[0] ?? '',
        embedder: strategies.embedders[0] ?? '',
        retriever: strategies.retrievers[0] ?? '',
        reranker: strategies.rerankers?.find(r => r !== 'none') ?? 'none',
        classifier: strategies.classifiers?.find(c => c !== 'none') ?? 'none',
      }));
    }
  }, [strategies, newForm.chunker]);

  // 설정에 불일치가 있는지 확인
  const getSettingMismatches = useCallback(
    (setting: RAGSettings): { type: StrategyType; value: string | null; valid: boolean }[] => {
      const mismatches: { type: StrategyType; value: string | null; valid: boolean }[] = [];

      const checks: { type: StrategyType; value: string | null; options: string[] }[] = [
        { type: 'chunker', value: setting.chunker, options: chunkerOptions },
        { type: 'embedder', value: setting.embedder, options: embedderOptions },
        { type: 'retriever', value: setting.retriever, options: retrieverOptions },
        { type: 'reranker', value: setting.reranker, options: rerankerOptions },
        { type: 'classifier', value: setting.classifier, options: classifierOptions },
      ];

      for (const check of checks) {
        const valid = isValidStrategy(check.value, check.options, check.type);
        if (!valid) {
          mismatches.push({ type: check.type, value: check.value, valid: false });
        }
      }

      return mismatches;
    },
    [chunkerOptions, embedderOptions, retrieverOptions, rerankerOptions, classifierOptions]
  );

  // 전체 설정에 불일치가 있는지
  const hasAnyMismatch = useMemo(() => {
    if (!settings || !strategies) return false;
    return settings.some((s) => getSettingMismatches(s).length > 0);
  }, [settings, strategies, getSettingMismatches]);

  const handleStartEdit = (setting: RAGSettings) => {
    setEditingId(setting.id);
    setEditForm({
      name: setting.name,
      description: setting.description,
      chunker: setting.chunker,
      embedder: setting.embedder,
      retriever: setting.retriever,
      reranker: setting.reranker,
      classifier: setting.classifier,
      parameters: setting.parameters,
    });
  };

  const handleSaveEdit = () => {
    if (!editingId) return;
    updateMutation.mutate({
      id: editingId,
      data: {
        name: editForm.name,
        description: editForm.description ?? undefined,
        chunker: editForm.chunker,
        embedder: editForm.embedder,
        retriever: editForm.retriever,
        reranker: editForm.reranker === 'none' ? null : editForm.reranker,
        classifier: editForm.classifier === 'none' ? null : editForm.classifier,
      },
    });
  };

  const handleCreate = () => {
    createMutation.mutate({
      ...newForm,
      reranker: newForm.reranker === 'none' ? null : newForm.reranker,
      classifier: newForm.classifier === 'none' ? null : newForm.classifier,
    });
  };

  // Sync 핸들러 - 최신 전략 목록 가져오기
  const handleSync = useCallback(() => {
    refetchStrategies();
  }, [refetchStrategies]);

  return (
    <div className="rounded-lg border border-amber-200 bg-gradient-to-r from-amber-50 to-orange-50">
      {/* Header - Always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex w-full items-center justify-between p-4"
      >
        <div className="flex items-center gap-2">
          <Settings className="h-4 w-4 text-amber-600" />
          <h3 className="text-sm font-semibold text-amber-900">프로덕션 RAG 설정</h3>
          {activeSettings && (
            <span className="rounded-full bg-amber-200 px-2 py-0.5 text-xs font-medium text-amber-800">
              활성: {activeSettings.name}
            </span>
          )}
          {hasAnyMismatch && (
            <span className="flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
              <AlertTriangle className="h-3 w-3" />
              전략 불일치
            </span>
          )}
        </div>
        <ChevronDown
          className={cn(
            'h-4 w-4 text-amber-600 transition-transform',
            isExpanded && 'rotate-180'
          )}
        />
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t border-amber-200 p-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-amber-500" />
            </div>
          ) : (
            <div className="space-y-4">
              {/* Sync Button & Info Banner */}
              <div className="flex items-center justify-between">
                <div className="flex items-start gap-2 rounded-lg bg-amber-100 p-3 text-sm text-amber-800 flex-1">
                  <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                  <p>
                    여기서 설정을 변경하고 <strong>&quot;적용&quot;</strong> 버튼을 클릭하면 DB에
                    저장됩니다. 실제 서비스에 반영되려면 <strong>User Backend 재시작</strong>이
                    필요합니다.
                  </p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleSync();
                  }}
                  disabled={isRefetchingStrategies || isLoadingStrategies}
                  className="ml-3 flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-blue-400"
                  title="백엔드에서 최신 전략 목록 가져오기"
                >
                  <RefreshCw className={cn('h-4 w-4', (isRefetchingStrategies || isLoadingStrategies) && 'animate-spin')} />
                  Sync
                </button>
              </div>

              {/* Mismatch Warning */}
              {hasAnyMismatch && (
                <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-800">
                  <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-600" />
                  <div>
                    <p className="font-medium">전략 불일치 감지</p>
                    <p className="mt-1 text-red-700">
                      DB에 저장된 일부 전략 값이 현재 코드에 등록된 전략과 일치하지 않습니다.
                      해당 설정을 수정하여 유효한 전략으로 변경해주세요.
                    </p>
                  </div>
                </div>
              )}

              {/* Settings List */}
              <div className="space-y-3">
                {settings?.map((setting) => (
                  <div
                    key={setting.id}
                    className={cn(
                      'rounded-lg border p-4',
                      setting.isActive
                        ? 'border-green-300 bg-green-50'
                        : 'border-gray-200 bg-white'
                    )}
                  >
                    {editingId === setting.id ? (
                      // Edit Mode
                      <div className="space-y-3">
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="text-xs font-medium text-gray-600">이름</label>
                            <input
                              type="text"
                              value={editForm.name || ''}
                              onChange={(e) =>
                                setEditForm({ ...editForm, name: e.target.value })
                              }
                              className="mt-1 w-full rounded border px-2 py-1 text-sm"
                            />
                          </div>
                          <div>
                            <label className="text-xs font-medium text-gray-600">설명</label>
                            <input
                              type="text"
                              value={editForm.description || ''}
                              onChange={(e) =>
                                setEditForm({ ...editForm, description: e.target.value })
                              }
                              className="mt-1 w-full rounded border px-2 py-1 text-sm"
                            />
                          </div>
                        </div>
                        <div className="grid grid-cols-5 gap-3">
                          <div>
                            <label className={cn(
                              'text-xs font-medium',
                              !isValidStrategy(editForm.chunker ?? null, chunkerOptions, 'chunker')
                                ? 'text-red-600'
                                : 'text-gray-600'
                            )}>
                              Chunker {!isValidStrategy(editForm.chunker ?? null, chunkerOptions, 'chunker') && '⚠️'}
                            </label>
                            <select
                              value={editForm.chunker}
                              onChange={(e) =>
                                setEditForm({ ...editForm, chunker: e.target.value })
                              }
                              className={cn(
                                'mt-1 w-full rounded border px-2 py-1 text-sm',
                                !isValidStrategy(editForm.chunker ?? null, chunkerOptions, 'chunker')
                                  ? 'border-red-300 bg-red-50'
                                  : ''
                              )}
                            >
                              {/* 현재 값이 유효하지 않으면 disabled 옵션으로 표시 */}
                              {editForm.chunker && !chunkerOptions.includes(editForm.chunker) && (
                                <option value={editForm.chunker} disabled className="text-red-600">
                                  ⚠️ {editForm.chunker} (존재하지 않음)
                                </option>
                              )}
                              {chunkerOptions.map((opt) => (
                                <option key={opt} value={opt}>
                                  {opt}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label className={cn(
                              'text-xs font-medium',
                              !isValidStrategy(editForm.embedder ?? null, embedderOptions, 'embedder')
                                ? 'text-red-600'
                                : 'text-gray-600'
                            )}>
                              Embedder {!isValidStrategy(editForm.embedder ?? null, embedderOptions, 'embedder') && '⚠️'}
                            </label>
                            <select
                              value={editForm.embedder}
                              onChange={(e) =>
                                setEditForm({ ...editForm, embedder: e.target.value })
                              }
                              className={cn(
                                'mt-1 w-full rounded border px-2 py-1 text-sm',
                                !isValidStrategy(editForm.embedder ?? null, embedderOptions, 'embedder')
                                  ? 'border-red-300 bg-red-50'
                                  : ''
                              )}
                            >
                              {editForm.embedder && !embedderOptions.includes(editForm.embedder) && (
                                <option value={editForm.embedder} disabled className="text-red-600">
                                  ⚠️ {editForm.embedder} (존재하지 않음)
                                </option>
                              )}
                              {embedderOptions.map((opt) => (
                                <option key={opt} value={opt}>
                                  {opt}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label className={cn(
                              'text-xs font-medium',
                              !isValidStrategy(editForm.retriever ?? null, retrieverOptions, 'retriever')
                                ? 'text-red-600'
                                : 'text-gray-600'
                            )}>
                              Retriever {!isValidStrategy(editForm.retriever ?? null, retrieverOptions, 'retriever') && '⚠️'}
                            </label>
                            <select
                              value={editForm.retriever}
                              onChange={(e) =>
                                setEditForm({ ...editForm, retriever: e.target.value })
                              }
                              className={cn(
                                'mt-1 w-full rounded border px-2 py-1 text-sm',
                                !isValidStrategy(editForm.retriever ?? null, retrieverOptions, 'retriever')
                                  ? 'border-red-300 bg-red-50'
                                  : ''
                              )}
                            >
                              {editForm.retriever && !retrieverOptions.includes(editForm.retriever) && (
                                <option value={editForm.retriever} disabled className="text-red-600">
                                  ⚠️ {editForm.retriever} (존재하지 않음)
                                </option>
                              )}
                              {retrieverOptions.map((opt) => (
                                <option key={opt} value={opt}>
                                  {opt}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label className={cn(
                              'text-xs font-medium',
                              !isValidStrategy(editForm.reranker ?? null, rerankerOptions, 'reranker')
                                ? 'text-red-600'
                                : 'text-gray-600'
                            )}>
                              Reranker {!isValidStrategy(editForm.reranker ?? null, rerankerOptions, 'reranker') && '⚠️'}
                            </label>
                            <select
                              value={editForm.reranker || 'none'}
                              onChange={(e) =>
                                setEditForm({
                                  ...editForm,
                                  reranker: e.target.value === 'none' ? null : e.target.value,
                                })
                              }
                              className={cn(
                                'mt-1 w-full rounded border px-2 py-1 text-sm',
                                !isValidStrategy(editForm.reranker ?? null, rerankerOptions, 'reranker')
                                  ? 'border-red-300 bg-red-50'
                                  : ''
                              )}
                            >
                              {editForm.reranker && !rerankerOptions.includes(editForm.reranker) && (
                                <option value={editForm.reranker} disabled className="text-red-600">
                                  ⚠️ {editForm.reranker} (존재하지 않음)
                                </option>
                              )}
                              {rerankerOptions.map((opt) => (
                                <option key={opt} value={opt}>
                                  {opt}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label className={cn(
                              'text-xs font-medium',
                              !isValidStrategy(editForm.classifier ?? null, classifierOptions, 'classifier')
                                ? 'text-red-600'
                                : 'text-gray-600'
                            )}>
                              Classifier {!isValidStrategy(editForm.classifier ?? null, classifierOptions, 'classifier') && '⚠️'}
                            </label>
                            <select
                              value={editForm.classifier || 'none'}
                              onChange={(e) =>
                                setEditForm({
                                  ...editForm,
                                  classifier: e.target.value === 'none' ? null : e.target.value,
                                })
                              }
                              className={cn(
                                'mt-1 w-full rounded border px-2 py-1 text-sm',
                                !isValidStrategy(editForm.classifier ?? null, classifierOptions, 'classifier')
                                  ? 'border-red-300 bg-red-50'
                                  : ''
                              )}
                            >
                              {editForm.classifier && !classifierOptions.includes(editForm.classifier) && (
                                <option value={editForm.classifier} disabled className="text-red-600">
                                  ⚠️ {editForm.classifier} (존재하지 않음)
                                </option>
                              )}
                              {classifierOptions.map((opt) => (
                                <option key={opt} value={opt}>
                                  {opt}
                                </option>
                              ))}
                            </select>
                          </div>
                        </div>
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => setEditingId(null)}
                            className="rounded px-3 py-1 text-sm text-gray-600 hover:bg-gray-100"
                          >
                            취소
                          </button>
                          <button
                            onClick={handleSaveEdit}
                            disabled={updateMutation.isPending}
                            className="flex items-center gap-1 rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700"
                          >
                            {updateMutation.isPending ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <Save className="h-3 w-3" />
                            )}
                            저장
                          </button>
                        </div>
                      </div>
                    ) : (
                      // View Mode
                      (() => {
                        const mismatches = getSettingMismatches(setting);
                        const hasMismatch = mismatches.length > 0;
                        const mismatchTypes = new Set(mismatches.map(m => m.type));

                        return (
                          <div className="flex items-center justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-gray-900">{setting.name}</span>
                                {setting.isActive && (
                                  <span className="flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-700">
                                    <Check className="h-3 w-3" />
                                    활성
                                  </span>
                                )}
                                {hasMismatch && (
                                  <span className="flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-700">
                                    <AlertTriangle className="h-3 w-3" />
                                    불일치
                                  </span>
                                )}
                              </div>
                              {setting.description && (
                                <p className="mt-1 text-xs text-gray-500">{setting.description}</p>
                              )}
                              <div className="mt-2 flex flex-wrap gap-2 text-xs text-gray-600">
                                <span className={cn(
                                  'rounded px-1.5 py-0.5',
                                  mismatchTypes.has('chunker')
                                    ? 'bg-red-100 text-red-700 border border-red-300'
                                    : 'bg-gray-100'
                                )}>
                                  chunker: {setting.chunker}
                                  {mismatchTypes.has('chunker') && ' ⚠️'}
                                </span>
                                <span className={cn(
                                  'rounded px-1.5 py-0.5',
                                  mismatchTypes.has('embedder')
                                    ? 'bg-red-100 text-red-700 border border-red-300'
                                    : 'bg-gray-100'
                                )}>
                                  embedder: {setting.embedder}
                                  {mismatchTypes.has('embedder') && ' ⚠️'}
                                </span>
                                <span className={cn(
                                  'rounded px-1.5 py-0.5',
                                  mismatchTypes.has('retriever')
                                    ? 'bg-red-100 text-red-700 border border-red-300'
                                    : 'bg-gray-100'
                                )}>
                                  retriever: {setting.retriever}
                                  {mismatchTypes.has('retriever') && ' ⚠️'}
                                </span>
                                <span className={cn(
                                  'rounded px-1.5 py-0.5',
                                  mismatchTypes.has('reranker')
                                    ? 'bg-red-100 text-red-700 border border-red-300'
                                    : 'bg-gray-100'
                                )}>
                                  reranker: {setting.reranker || 'none'}
                                  {mismatchTypes.has('reranker') && ' ⚠️'}
                                </span>
                                <span className={cn(
                                  'rounded px-1.5 py-0.5',
                                  mismatchTypes.has('classifier')
                                    ? 'bg-red-100 text-red-700 border border-red-300'
                                    : 'bg-gray-100'
                                )}>
                                  classifier: {setting.classifier || 'none'}
                                  {mismatchTypes.has('classifier') && ' ⚠️'}
                                </span>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => handleStartEdit(setting)}
                                className={cn(
                                  'rounded px-2 py-1 text-xs',
                                  hasMismatch
                                    ? 'bg-red-100 text-red-700 hover:bg-red-200 font-medium'
                                    : 'text-gray-600 hover:bg-gray-100'
                                )}
                              >
                                {hasMismatch ? '수정 필요' : '수정'}
                              </button>
                              {!setting.isActive && (
                                <>
                                  <button
                                    onClick={() => activateMutation.mutate(setting.id)}
                                    disabled={activateMutation.isPending}
                                    className="flex items-center gap-1 rounded bg-green-600 px-2 py-1 text-xs text-white hover:bg-green-700"
                                  >
                                    {activateMutation.isPending ? (
                                      <Loader2 className="h-3 w-3 animate-spin" />
                                    ) : (
                                      <Check className="h-3 w-3" />
                                    )}
                                    적용
                                  </button>
                                  <button
                                    onClick={() => {
                                      if (confirm('정말 삭제하시겠습니까?')) {
                                        deleteMutation.mutate(setting.id);
                                      }
                                    }}
                                    disabled={deleteMutation.isPending}
                                    className="rounded p-1 text-red-600 hover:bg-red-50"
                                  >
                                    <Trash2 className="h-4 w-4" />
                                  </button>
                                </>
                              )}
                            </div>
                          </div>
                        );
                      })()
                    )}
                  </div>
                ))}
              </div>

              {/* New Setting Form */}
              {showNewForm ? (
                <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
                  <h4 className="mb-3 font-medium text-blue-900">새 설정 추가</h4>
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs font-medium text-gray-600">이름 *</label>
                        <input
                          type="text"
                          value={newForm.name}
                          onChange={(e) => setNewForm({ ...newForm, name: e.target.value })}
                          placeholder="high-precision"
                          className="mt-1 w-full rounded border px-2 py-1 text-sm"
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-gray-600">설명</label>
                        <input
                          type="text"
                          value={newForm.description}
                          onChange={(e) => setNewForm({ ...newForm, description: e.target.value })}
                          placeholder="고정밀 설정"
                          className="mt-1 w-full rounded border px-2 py-1 text-sm"
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-5 gap-3">
                      <div>
                        <label className="text-xs font-medium text-gray-600">Chunker</label>
                        <select
                          value={newForm.chunker}
                          onChange={(e) => setNewForm({ ...newForm, chunker: e.target.value })}
                          className="mt-1 w-full rounded border px-2 py-1 text-sm"
                        >
                          {chunkerOptions.map((opt) => (
                            <option key={opt} value={opt}>
                              {opt}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-xs font-medium text-gray-600">Embedder</label>
                        <select
                          value={newForm.embedder}
                          onChange={(e) => setNewForm({ ...newForm, embedder: e.target.value })}
                          className="mt-1 w-full rounded border px-2 py-1 text-sm"
                        >
                          {embedderOptions.map((opt) => (
                            <option key={opt} value={opt}>
                              {opt}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-xs font-medium text-gray-600">Retriever</label>
                        <select
                          value={newForm.retriever}
                          onChange={(e) => setNewForm({ ...newForm, retriever: e.target.value })}
                          className="mt-1 w-full rounded border px-2 py-1 text-sm"
                        >
                          {retrieverOptions.map((opt) => (
                            <option key={opt} value={opt}>
                              {opt}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-xs font-medium text-gray-600">Reranker</label>
                        <select
                          value={newForm.reranker || 'none'}
                          onChange={(e) =>
                            setNewForm({
                              ...newForm,
                              reranker: e.target.value === 'none' ? null : e.target.value,
                            })
                          }
                          className="mt-1 w-full rounded border px-2 py-1 text-sm"
                        >
                          {rerankerOptions.map((opt) => (
                            <option key={opt} value={opt}>
                              {opt}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-xs font-medium text-gray-600">Classifier</label>
                        <select
                          value={newForm.classifier || 'none'}
                          onChange={(e) =>
                            setNewForm({
                              ...newForm,
                              classifier: e.target.value === 'none' ? null : e.target.value,
                            })
                          }
                          className="mt-1 w-full rounded border px-2 py-1 text-sm"
                        >
                          {classifierOptions.map((opt) => (
                            <option key={opt} value={opt}>
                              {opt}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => setShowNewForm(false)}
                        className="rounded px-3 py-1 text-sm text-gray-600 hover:bg-gray-100"
                      >
                        취소
                      </button>
                      <button
                        onClick={handleCreate}
                        disabled={!newForm.name || createMutation.isPending}
                        className="flex items-center gap-1 rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700 disabled:bg-blue-300"
                      >
                        {createMutation.isPending ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <Plus className="h-3 w-3" />
                        )}
                        생성
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => setShowNewForm(true)}
                  className="flex w-full items-center justify-center gap-2 rounded-lg border-2 border-dashed border-gray-300 py-3 text-sm text-gray-500 hover:border-gray-400 hover:text-gray-600"
                >
                  <Plus className="h-4 w-4" />새 설정 추가
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
