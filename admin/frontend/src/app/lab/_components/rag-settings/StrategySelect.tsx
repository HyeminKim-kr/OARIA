'use client';

import { cn } from '@/lib/utils';
import { StrategySelectProps } from './types';
import { isValidStrategy, displayNullableValue, normalizeNullableValue } from './utils';

export function StrategySelect({
  label,
  value,
  options,
  type,
  onChange,
  isValid = true,
  showMismatchWarning = false,
}: StrategySelectProps) {
  const displayValue = displayNullableValue(value);
  const isNullableType = type === 'reranker' || type === 'classifier';
  const hasInvalidValue = value && !options.includes(value) && !(isNullableType && value === 'none');

  return (
    <div>
      <label
        className={cn(
          'text-xs font-medium',
          !isValid ? 'text-red-600' : 'text-gray-600'
        )}
      >
        {label} {!isValid && showMismatchWarning && '⚠️'}
      </label>
      <select
        value={displayValue}
        onChange={(e) => {
          const newValue = normalizeNullableValue(e.target.value);
          onChange(newValue);
        }}
        className={cn(
          'mt-1 w-full rounded border px-2 py-1 text-sm',
          !isValid ? 'border-red-300 bg-red-50' : ''
        )}
      >
        {/* 현재 값이 유효하지 않으면 disabled 옵션으로 표시 */}
        {hasInvalidValue && (
          <option value={value!} disabled className="text-red-600">
            ⚠️ {value} (존재하지 않음)
          </option>
        )}
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    </div>
  );
}
