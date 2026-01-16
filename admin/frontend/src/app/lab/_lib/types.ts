import { SearchTestResult } from '@/lib/api';

export type TestMode = 'search' | 'generate' | 'compare';

export type RelevanceLevel = 'high' | 'medium' | 'low' | 'irrelevant';

export interface RelevanceStyle {
  bg: string;
  text: string;
  label: string;
}

export interface CompareResults {
  configA?: SearchTestResult;
  configB?: SearchTestResult;
}

export interface FeedbackState {
  search?: 'good' | 'bad';
  generate?: 'good' | 'bad';
}

export interface ErrorInfo {
  type: 'no_data' | 'error';
  message: string;
}

// 데이터 소스 타입
export type DataSource = 'production' | 'sample';

// 데이터 소스 설정 (Chunker + Embedder 조합)
export interface DataSourceConfig {
  type: DataSource;
  collectionName: string | null;  // sample일 때만 사용
  // 표시용 정보 (읽기 전용)
  chunker: string;
  embedder: string;
  // 샘플 임베딩 추가 정보
  queryName?: string;  // 어떤 검색 쿼리 기반인지
}

// 검색 설정 (검색 시점에 변경 가능)
export interface SearchSettings {
  retriever: string;
  reranker: string;      // 'none' | 모델명
  classifier: string;    // 'none' | 분류기명
}

// 검색 파라미터 설정 (A/B 비교에서 독립적으로 사용)
export interface SearchConfig {
  limit: number;
  alpha: number;
  dataSource: DataSourceConfig;  // 데이터 소스 (프로덕션 또는 샘플)
}

// RAG 전략 선택 상태 (레거시 호환용 - 점진적 제거 예정)
export interface SelectedStrategies {
  chunker: string;
  embedder: string;
  retriever: string;
  reranker: string;
  classifier: string;
}

export interface LabConfig {
  query: string;
  // 검색 설정 (Retriever, Reranker, Classifier)
  searchSettings: SearchSettings;
  // 검색 파라미터 (단일 테스트용)
  limit: number;
  alpha: number;
  // 데이터 소스 선택 (단일 테스트용)
  dataSource: DataSourceConfig;
  // A/B 비교용 설정 (각각 독립적인 데이터 소스 선택 가능)
  configA: SearchConfig;
  configB: SearchConfig;
  // 레거시 호환용 (점진적 제거 예정)
  useReranker: boolean;
  reranker: string;
  selectedStrategies: SelectedStrategies;
  collectionName: string | null;
}
