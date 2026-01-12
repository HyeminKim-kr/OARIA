'use client';

import { Check, Save, Trash2, Loader2, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SettingCardProps, StrategyType } from './types';
import { StrategySelect } from './StrategySelect';
import { isValidStrategy, displayNullableValue, normalizeNullableValue } from './utils';

export function SettingCard({
  setting,
  isEditing,
  editForm,
  options,
  mismatches,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
  onActivate,
  onDelete,
  onEditFormChange,
  isUpdatePending,
  isActivatePending,
  isDeletePending,
}: SettingCardProps) {
  const hasMismatch = mismatches.length > 0;
  const mismatchTypes = new Set(mismatches.map((m) => m.type));

  if (isEditing) {
    return (
      <div
        className={cn(
          'rounded-lg border p-4',
          setting.isActive ? 'border-green-300 bg-green-50' : 'border-gray-200 bg-white'
        )}
      >
        <div className="space-y-3">
          {/* Name & Description */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-600">이름</label>
              <input
                type="text"
                value={editForm.name || ''}
                onChange={(e) => onEditFormChange({ name: e.target.value })}
                className="mt-1 w-full rounded border px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600">설명</label>
              <input
                type="text"
                value={editForm.description || ''}
                onChange={(e) => onEditFormChange({ description: e.target.value })}
                className="mt-1 w-full rounded border px-2 py-1 text-sm"
              />
            </div>
          </div>

          {/* Strategy Selects */}
          <div className="grid grid-cols-5 gap-3">
            <StrategySelect
              label="Chunker"
              value={editForm.chunker ?? null}
              options={options.chunkers}
              type="chunker"
              onChange={(v) => onEditFormChange({ chunker: v || '' })}
              isValid={isValidStrategy(editForm.chunker ?? null, options.chunkers, 'chunker')}
              showMismatchWarning
            />
            <StrategySelect
              label="Embedder"
              value={editForm.embedder ?? null}
              options={options.embedders}
              type="embedder"
              onChange={(v) => onEditFormChange({ embedder: v || '' })}
              isValid={isValidStrategy(editForm.embedder ?? null, options.embedders, 'embedder')}
              showMismatchWarning
            />
            <StrategySelect
              label="Retriever"
              value={editForm.retriever ?? null}
              options={options.retrievers}
              type="retriever"
              onChange={(v) => onEditFormChange({ retriever: v || '' })}
              isValid={isValidStrategy(editForm.retriever ?? null, options.retrievers, 'retriever')}
              showMismatchWarning
            />
            <StrategySelect
              label="Reranker"
              value={editForm.reranker ?? null}
              options={options.rerankers}
              type="reranker"
              onChange={(v) => onEditFormChange({ reranker: v })}
              isValid={isValidStrategy(editForm.reranker ?? null, options.rerankers, 'reranker')}
              showMismatchWarning
            />
            <StrategySelect
              label="Classifier"
              value={editForm.classifier ?? null}
              options={options.classifiers}
              type="classifier"
              onChange={(v) => onEditFormChange({ classifier: v })}
              isValid={isValidStrategy(editForm.classifier ?? null, options.classifiers, 'classifier')}
              showMismatchWarning
            />
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-2">
            <button
              onClick={onCancelEdit}
              className="rounded px-3 py-1 text-sm text-gray-600 hover:bg-gray-100"
            >
              취소
            </button>
            <button
              onClick={onSaveEdit}
              disabled={isUpdatePending}
              className="flex items-center gap-1 rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700"
            >
              {isUpdatePending ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Save className="h-3 w-3" />
              )}
              저장
            </button>
          </div>
        </div>
      </div>
    );
  }

  // View Mode
  return (
    <div
      className={cn(
        'rounded-lg border p-4',
        setting.isActive ? 'border-green-300 bg-green-50' : 'border-gray-200 bg-white'
      )}
    >
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
            <StrategyBadge type="chunker" value={setting.chunker} hasMismatch={mismatchTypes.has('chunker')} />
            <StrategyBadge type="embedder" value={setting.embedder} hasMismatch={mismatchTypes.has('embedder')} />
            <StrategyBadge type="retriever" value={setting.retriever} hasMismatch={mismatchTypes.has('retriever')} />
            <StrategyBadge type="reranker" value={setting.reranker} hasMismatch={mismatchTypes.has('reranker')} />
            <StrategyBadge type="classifier" value={setting.classifier} hasMismatch={mismatchTypes.has('classifier')} />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onStartEdit}
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
                onClick={onActivate}
                disabled={isActivatePending}
                className="flex items-center gap-1 rounded bg-green-600 px-2 py-1 text-xs text-white hover:bg-green-700"
              >
                {isActivatePending ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Check className="h-3 w-3" />
                )}
                적용
              </button>
              <button
                onClick={() => {
                  if (confirm('정말 삭제하시겠습니까?')) {
                    onDelete();
                  }
                }}
                disabled={isDeletePending}
                className="rounded p-1 text-red-600 hover:bg-red-50"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// 전략 배지 컴포넌트
function StrategyBadge({
  type,
  value,
  hasMismatch,
}: {
  type: StrategyType;
  value: string | null;
  hasMismatch: boolean;
}) {
  return (
    <span
      className={cn(
        'rounded px-1.5 py-0.5',
        hasMismatch ? 'bg-red-100 text-red-700 border border-red-300' : 'bg-gray-100'
      )}
    >
      {type}: {displayNullableValue(value)}
      {hasMismatch && ' ⚠️'}
    </span>
  );
}
