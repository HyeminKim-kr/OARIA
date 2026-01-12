'use client';

import { useState, useMemo, useCallback } from 'react';
import {
  Settings,
  ChevronDown,
  Plus,
  Loader2,
  AlertCircle,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { RAGSettings } from '@/lib/api';
import { RAGSettingsPanelProps, SettingFormData } from './types';
import { SettingCard } from './SettingCard';
import { NewSettingForm } from './NewSettingForm';
import {
  useStrategies,
  useRAGSettings,
  useRAGSettingsMutations,
  useStrategyOptions,
  useSettingMismatches,
} from './hooks';
import { normalizeNullableValue } from './utils';

const DEFAULT_FORM: SettingFormData = {
  name: '',
  description: '',
  chunker: '',
  embedder: '',
  retriever: '',
  reranker: 'none',
  classifier: 'none',
  parameters: { limit: 10, alpha: 0.7 },
};

export function RAGSettingsPanel({ strategies: initialStrategies }: RAGSettingsPanelProps) {
  // UI State
  const [isExpanded, setIsExpanded] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Partial<RAGSettings>>({});
  const [showNewForm, setShowNewForm] = useState(false);
  const [newForm, setNewForm] = useState<SettingFormData>(DEFAULT_FORM);

  // Data Hooks
  const {
    data: strategies,
    isLoading: isLoadingStrategies,
    refetch: refetchStrategies,
    isRefetching: isRefetchingStrategies,
  } = useStrategies(initialStrategies);
  const { data: settings, isLoading } = useRAGSettings();
  const mutations = useRAGSettingsMutations();

  // Derived State
  const options = useStrategyOptions(strategies);
  const getSettingMismatches = useSettingMismatches(options);
  const activeSettings = settings?.find((s) => s.isActive);

  // 새 폼 초기값 설정 (strategies 로드 후)
  useMemo(() => {
    if (strategies && newForm.chunker === '') {
      setNewForm((prev) => ({
        ...prev,
        chunker: strategies.chunkers[0] ?? '',
        embedder: strategies.embedders[0] ?? '',
        retriever: strategies.retrievers[0] ?? '',
        reranker: strategies.rerankers?.find((r) => r !== 'none') ?? 'none',
        classifier: strategies.classifiers?.find((c) => c !== 'none') ?? 'none',
      }));
    }
  }, [strategies, newForm.chunker]);

  // 전체 설정에 불일치가 있는지
  const hasAnyMismatch = useMemo(() => {
    if (!settings || !strategies) return false;
    return settings.some((s) => getSettingMismatches(s).length > 0);
  }, [settings, strategies, getSettingMismatches]);

  // Handlers
  const handleStartEdit = useCallback((setting: RAGSettings) => {
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
  }, []);

  const handleSaveEdit = useCallback(() => {
    if (!editingId) return;
    mutations.updateMutation.mutate(
      {
        id: editingId,
        data: {
          name: editForm.name,
          description: editForm.description ?? undefined,
          chunker: editForm.chunker,
          embedder: editForm.embedder,
          retriever: editForm.retriever,
          reranker: normalizeNullableValue(editForm.reranker ?? null),
          classifier: normalizeNullableValue(editForm.classifier ?? null),
        },
      },
      {
        onSuccess: () => setEditingId(null),
      }
    );
  }, [editingId, editForm, mutations.updateMutation]);

  const handleCreate = useCallback(() => {
    mutations.createMutation.mutate(
      {
        ...newForm,
        reranker: normalizeNullableValue(newForm.reranker),
        classifier: normalizeNullableValue(newForm.classifier),
      },
      {
        onSuccess: () => {
          setShowNewForm(false);
          setNewForm({
            ...DEFAULT_FORM,
            chunker: strategies?.chunkers[0] ?? '',
            embedder: strategies?.embedders[0] ?? '',
            retriever: strategies?.retrievers[0] ?? '',
            reranker: strategies?.rerankers?.find((r) => r !== 'none') ?? 'none',
            classifier: strategies?.classifiers?.find((c) => c !== 'none') ?? 'none',
          });
        },
      }
    );
  }, [newForm, strategies, mutations.createMutation]);

  const handleSync = useCallback(() => {
    refetchStrategies();
  }, [refetchStrategies]);

  return (
    <div className="rounded-lg border border-amber-200 bg-gradient-to-r from-amber-50 to-orange-50">
      {/* Header */}
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
              {/* Info Banner & Sync Button */}
              <div className="flex items-center justify-between">
                <div className="flex flex-1 items-start gap-2 rounded-lg bg-amber-100 p-3 text-sm text-amber-800">
                  <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                  <p>
                    여기서 설정을 변경하고 <strong>&quot;적용&quot;</strong> 버튼을 클릭하면 DB에
                    저장됩니다. 실제 서비스에 반영되려면 <strong>User Backend 재시작</strong>이
                    필요합니다.
                  </p>
                </div>
                <button
                  onClick={handleSync}
                  disabled={isRefetchingStrategies || isLoadingStrategies}
                  className="ml-3 flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-blue-400"
                  title="백엔드에서 최신 전략 목록 가져오기"
                >
                  <RefreshCw
                    className={cn(
                      'h-4 w-4',
                      (isRefetchingStrategies || isLoadingStrategies) && 'animate-spin'
                    )}
                  />
                  Sync
                </button>
              </div>

              {/* Mismatch Warning */}
              {hasAnyMismatch && (
                <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
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
                  <SettingCard
                    key={setting.id}
                    setting={setting}
                    isEditing={editingId === setting.id}
                    editForm={editForm}
                    options={options}
                    mismatches={getSettingMismatches(setting)}
                    onStartEdit={() => handleStartEdit(setting)}
                    onCancelEdit={() => setEditingId(null)}
                    onSaveEdit={handleSaveEdit}
                    onActivate={() => mutations.activateMutation.mutate(setting.id)}
                    onDelete={() => mutations.deleteMutation.mutate(setting.id)}
                    onEditFormChange={(updates) => setEditForm((prev) => ({ ...prev, ...updates }))}
                    isUpdatePending={mutations.updateMutation.isPending}
                    isActivatePending={mutations.activateMutation.isPending}
                    isDeletePending={mutations.deleteMutation.isPending}
                  />
                ))}
              </div>

              {/* New Setting Form */}
              {showNewForm ? (
                <NewSettingForm
                  form={newForm}
                  options={options}
                  onChange={(updates) => setNewForm((prev) => ({ ...prev, ...updates }))}
                  onSubmit={handleCreate}
                  onCancel={() => setShowNewForm(false)}
                  isPending={mutations.createMutation.isPending}
                />
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
