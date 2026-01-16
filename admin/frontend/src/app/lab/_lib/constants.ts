import { RelevanceLevel, RelevanceStyle, DataSourceConfig, SearchSettings, SearchConfig, LabConfig } from './types';

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

// 프로덕션 데이터 소스 기본값
export const DEFAULT_PRODUCTION_DATA_SOURCE: DataSourceConfig = {
  type: 'production',
  collectionName: null,
  chunker: 'semantic_section_700t',  // 프로덕션 기본 chunker
  embedder: 'openai_3small_1536d',   // 프로덕션 기본 embedder
};

// 검색 설정 기본값 (검색 시점에 변경 가능)
export const DEFAULT_SEARCH_SETTINGS: SearchSettings = {
  retriever: 'hybrid',
  reranker: 'none',      // 기본: 리랭커 미사용
  classifier: 'none',    // 기본: 분류 미사용
};

// 검색 파라미터 기본값 (A/B 비교용)
export const DEFAULT_SEARCH_CONFIG: SearchConfig = {
  limit: 10,
  alpha: 0.7,
  dataSource: { ...DEFAULT_PRODUCTION_DATA_SOURCE },
};

// 레거시 호환용 (점진적 제거 예정)
export const DEFAULT_SELECTED_STRATEGIES = {
  chunker: 'semantic',
  embedder: 'openai',
  retriever: 'hybrid',
  reranker: 'none',
  classifier: 'none',
};

// LabConfig 기본값
export const DEFAULT_CONFIG: LabConfig = {
  query: '',
  // 검색 설정 (Retriever, Reranker, Classifier)
  searchSettings: { ...DEFAULT_SEARCH_SETTINGS },
  // 검색 파라미터 (단일 테스트용)
  limit: 10,
  alpha: 0.7,
  // 데이터 소스 (단일 테스트용)
  dataSource: { ...DEFAULT_PRODUCTION_DATA_SOURCE },
  // A/B 비교용 설정 (각각 독립적인 데이터 소스 선택 가능)
  configA: { ...DEFAULT_SEARCH_CONFIG },
  configB: { ...DEFAULT_SEARCH_CONFIG },
  // 레거시 호환용 (점진적 제거 예정)
  useReranker: false,
  reranker: '',
  selectedStrategies: { ...DEFAULT_SELECTED_STRATEGIES },
  collectionName: null,
};
