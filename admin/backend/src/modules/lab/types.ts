/**
 * RAG Lab Types
 */

// 검색 테스트 요청
export interface SearchTestRequest {
  query: string;
  limit?: number;
  alpha?: number; // 하이브리드 검색 가중치 (0: 키워드, 1: 벡터)
  useReranker?: boolean; // Reranker 사용 여부
  minRerankScore?: number; // Reranker 최소 점수 임계값
}

// 검색된 청크 정보
export interface SearchedChunk {
  paperId: string;
  paperTitle: string;
  sectionName: string;
  chunkIndex: number;
  content: string;
  score: number;
  rerankScore?: number; // Reranker 점수
  originalScore?: number; // 원본 벡터 검색 점수
  metadata?: Record<string, unknown>;
}

// 분류 결과
export interface ClassificationResult {
  category: string;
  confidence: number;
  isOncology: boolean;
  warning?: string;
  classifierLatencyMs: number;
}

// 검색 테스트 결과
export interface SearchTestResult {
  query: string;
  chunks: SearchedChunk[];
  searchLatencyMs: number;
  rerankLatencyMs?: number; // Reranker 소요 시간
  totalChunks: number;
  parameters: {
    limit: number;
    alpha: number;
    useReranker?: boolean;
    minRerankScore?: number;
    rerankerModel?: string;
  };
  classification?: ClassificationResult; // 분류 결과
}

// 답변 생성 요청
export interface GenerateTestRequest {
  query: string;
  context?: string; // 선택적 컨텍스트 (검색 결과에서 가져온)
  limit?: number;
  alpha?: number;
  useReranker?: boolean; // Reranker 사용 여부
}

// Reference 정보
export interface Reference {
  paperId: string;
  title: string;
  section: string;
  content: string;
  score: number;
}

// 답변 생성 결과
export interface GenerateTestResult {
  query: string;
  answer: string;
  references: Reference[];
  searchLatencyMs: number;
  rerankLatencyMs?: number; // Reranker 소요 시간
  llmLatencyMs: number;
  totalLatencyMs: number;
  model: string;
  tokensUsed?: {
    prompt: number;
    completion: number;
  };
  useReranker?: boolean;
  classification?: ClassificationResult; // 분류 결과
}

// 피드백 요청
export interface FeedbackRequest {
  testId: string;
  type: 'search' | 'answer';
  rating: 'good' | 'bad';
  comment?: string;
}

// 피드백 결과
export interface FeedbackResult {
  success: boolean;
  feedbackId?: string;
  message: string;
}

// User Backend 상태
export interface UserBackendStatus {
  available: boolean;
  url: string;
  latencyMs?: number;
  error?: string;
}

// 테스트 로그 파라미터
export interface TestLogParametersType {
  limit: number;
  alpha: number;
  useReranker?: boolean;
  minRerankScore?: number;
  rerankerModel?: string;
}

// 테스트 로그 목록 아이템
export interface TestLogItem {
  id: string;
  testType: string;
  query: string;
  parameters: TestLogParametersType;
  searchLatencyMs: number | null;
  rerankLatencyMs: number | null;
  llmLatencyMs: number | null;
  totalLatencyMs: number | null;
  createdAt: string;
  resultSummary: Record<string, unknown>;
}

// 테스트 로그 목록 응답
export interface TestLogListResult {
  items: TestLogItem[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

// RAG 전략 목록
export interface StrategiesResponse {
  chunkers: string[];
  embedders: string[];
  retrievers: string[];
  rerankers: string[];
  classifiers: string[];
  evaluators: string[];
}

// RAG 전략 상세 정보
export interface StrategyInfo {
  name: string;
  class_name: string;
  module: string;
  description: string;
  config?: Record<string, unknown>;
}

// RAG 전략 상세 응답
export interface StrategiesDetailResponse {
  chunkers: StrategyInfo[];
  embedders: StrategyInfo[];
  retrievers: StrategyInfo[];
  rerankers: StrategyInfo[];
}

// DB 저장 RAG 전략 정보
export interface DBStrategyInfo {
  id: string;
  category: string;
  name: string;
  description: string | null;
  config: Record<string, unknown> | null;
  location: 'backend' | 'batch';
  is_active: boolean;
}

// DB 기반 RAG 전략 응답
export interface DBStrategiesResponse {
  chunkers: DBStrategyInfo[];
  embedders: DBStrategyInfo[];
  retrievers: DBStrategyInfo[];
  rerankers: DBStrategyInfo[];
}
