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

export const DEFAULT_SEARCH_CONFIG = {
  limit: 10,
  alpha: 0.7,
  reranker: null as string | null,  // 기본값: 미사용 (백엔드에서 사용 가능한 옵션 동적 로드)
  collectionName: null as string | null,
};

export const DEFAULT_SELECTED_STRATEGIES = {
  chunker: 'semantic',
  embedder: 'openai',
  retriever: 'hybrid',
  reranker: 'none',
  classifier: 'none',  // 기본: 분류 미사용
};

export const DEFAULT_CONFIG = {
  query: '',
  limit: 10,
  alpha: 0.7,
  useReranker: false,
  reranker: '',  // 빈 문자열 (UI에서 선택 필요)
  // A/B 비교용 기본 설정
  configA: { ...DEFAULT_SEARCH_CONFIG, reranker: null },  // 기본: 미사용
  configB: { ...DEFAULT_SEARCH_CONFIG, reranker: null },  // 기본: 미사용
  // RAG 전략 선택
  selectedStrategies: { ...DEFAULT_SELECTED_STRATEGIES },
  // 데이터 소스 (기본: 프로덕션)
  dataSource: 'production' as const,
  collectionName: null as string | null,
};
