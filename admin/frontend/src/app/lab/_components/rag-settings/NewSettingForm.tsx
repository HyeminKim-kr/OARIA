'use client';

import { Plus, Loader2 } from 'lucide-react';
import { NewSettingFormProps } from './types';
import { StrategySelect } from './StrategySelect';

export function NewSettingForm({
  form,
  options,
  onChange,
  onSubmit,
  onCancel,
  isPending,
}: NewSettingFormProps) {
  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
      <h4 className="mb-3 font-medium text-blue-900">새 설정 추가</h4>
      <div className="space-y-3">
        {/* Name & Description */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium text-gray-600">이름 *</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => onChange({ name: e.target.value })}
              placeholder="high-precision"
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-600">설명</label>
            <input
              type="text"
              value={form.description}
              onChange={(e) => onChange({ description: e.target.value })}
              placeholder="고정밀 설정"
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
            />
          </div>
        </div>

        {/* Strategy Selects */}
        <div className="grid grid-cols-5 gap-3">
          <StrategySelect
            label="Chunker"
            value={form.chunker}
            options={options.chunkers}
            type="chunker"
            onChange={(v) => onChange({ chunker: v || '' })}
          />
          <StrategySelect
            label="Embedder"
            value={form.embedder}
            options={options.embedders}
            type="embedder"
            onChange={(v) => onChange({ embedder: v || '' })}
          />
          <StrategySelect
            label="Retriever"
            value={form.retriever}
            options={options.retrievers}
            type="retriever"
            onChange={(v) => onChange({ retriever: v || '' })}
          />
          <StrategySelect
            label="Reranker"
            value={form.reranker}
            options={options.rerankers}
            type="reranker"
            onChange={(v) => onChange({ reranker: v })}
          />
          <StrategySelect
            label="Classifier"
            value={form.classifier}
            options={options.classifiers}
            type="classifier"
            onChange={(v) => onChange({ classifier: v })}
          />
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="rounded px-3 py-1 text-sm text-gray-600 hover:bg-gray-100"
          >
            취소
          </button>
          <button
            onClick={onSubmit}
            disabled={!form.name || isPending}
            className="flex items-center gap-1 rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700 disabled:bg-blue-300"
          >
            {isPending ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Plus className="h-3 w-3" />
            )}
            생성
          </button>
        </div>
      </div>
    </div>
  );
}
