import { SCORE_THRESHOLDS } from './constants';
import { RelevanceLevel, ErrorInfo } from './types';

export function getRelevanceLevel(score: number): RelevanceLevel {
  if (score >= SCORE_THRESHOLDS.HIGH) return 'high';
  if (score >= SCORE_THRESHOLDS.MEDIUM) return 'medium';
  if (score >= SCORE_THRESHOLDS.LOW) return 'low';
  return 'irrelevant';
}

export function extractErrorInfo(error: unknown): ErrorInfo | null {
  if (!error) return null;

  const axiosError = error as {
    response?: { data?: { detail?: { error?: string; message?: string } | string } };
  };
  const detail = axiosError.response?.data?.detail;

  if (typeof detail === 'object' && detail?.error === 'no_embedding_data') {
    return {
      type: 'no_data',
      message: detail.message || '임베딩 데이터가 없습니다.',
    };
  }

  return {
    type: 'error',
    message: typeof detail === 'string' ? detail : '알 수 없는 오류가 발생했습니다.',
  };
}
