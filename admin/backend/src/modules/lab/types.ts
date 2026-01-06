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
