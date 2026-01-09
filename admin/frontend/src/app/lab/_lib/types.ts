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

// 검색 파라미터 설정 (A/B 비교에서 독립적으로 사용)
export interface SearchConfig {
  limit: number;
  alpha: number;
  reranker: string | null;  // null이면 리랭킹 안함
  collectionName: string | null;  // null이면 프로덕션, 값이 있으면 샘플 임베딩
}

// RAG 전략 선택 상태
export interface SelectedStrategies {
  chunker: string;
  embedder: string;
  retriever: string;
  reranker: string;
}

// 데이터 소스 타입
export type DataSource = 'production' | 'sample';

export interface LabConfig {
  query: string;
  // 단일 테스트용 설정
  limit: number;
  alpha: number;
  useReranker: boolean;
  reranker: string;
  // A/B 비교용 설정
  configA: SearchConfig;
  configB: SearchConfig;
  // RAG 전략 선택
  selectedStrategies: SelectedStrategies;
  // 데이터 소스 선택
  dataSource: DataSource;
  collectionName: string | null;  // sample 선택 시 사용할 컬렉션
}
