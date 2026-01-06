import { RelevanceLevel, RelevanceStyle } from './types';

export const SCORE_THRESHOLDS = {
  HIGH: 0.7,
  MEDIUM: 0.5,
  LOW: 0.3,
  IRRELEVANT: 0.1,
} as const;

export const RELEVANCE_STYLES: Record<RelevanceLevel, RelevanceStyle> = {
  high: { bg: 'bg-green-100', text: 'text-green-700', label: '높음' },
  medium: { bg: 'bg-yellow-100', text: 'text-yellow-700', label: '중간' },
  low: { bg: 'bg-orange-100', text: 'text-orange-700', label: '낮음' },
  irrelevant: { bg: 'bg-red-100', text: 'text-red-700', label: '관련없음' },
};

export const DEFAULT_CONFIG = {
  query: '',
  limit: 10,
  alpha: 0.7,
  useReranker: false,
} as const;
