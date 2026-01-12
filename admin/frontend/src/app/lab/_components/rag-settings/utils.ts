import { StrategyType } from './types';

/**
 * 전략 값이 유효한지 확인
 * reranker와 classifier는 null 또는 'none'이 허용됨
 */
export function isValidStrategy(
  value: string | null,
  availableStrategies: string[],
  type: StrategyType
): boolean {
  if ((type === 'reranker' || type === 'classifier') && (value === null || value === 'none')) {
    return true;
  }
  return value !== null && availableStrategies.includes(value);
}

/**
 * 'none' 값을 null로 변환 (저장 시 사용)
 */
export function normalizeNullableValue(value: string | null): string | null {
  return value === 'none' ? null : value;
}

/**
 * null 값을 'none'으로 변환 (표시 시 사용)
 */
export function displayNullableValue(value: string | null): string {
  return value || 'none';
}
