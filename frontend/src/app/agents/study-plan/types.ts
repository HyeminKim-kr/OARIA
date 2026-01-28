/**
 * Study Plan Agent 타입 정의
 */

import { ReactNode } from "react";

// ─────────────────────────────────────────────────────────────
// Token Usage Types (LangGraph 토큰 추적)
// ─────────────────────────────────────────────────────────────

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  model?: string;
  estimated_cost?: number;
}

// ─────────────────────────────────────────────────────────────
// Recovery Types (실패 복구)
// ─────────────────────────────────────────────────────────────

export type RiskLevel = "low" | "medium" | "high";

export interface RecoveryOption {
  id: string;
  label: string;
  description: string;
  risk_level: RiskLevel;
  estimated_time?: string;
}

export interface RecoveryEvent {
  error: string;
  strategy?: string;
  options?: RecoveryOption[];
  auto_select_after?: number; // seconds
}

// ─────────────────────────────────────────────────────────────
// Session Persistence Types (사고 과정 저장/재생)
// ─────────────────────────────────────────────────────────────

export type SessionStatus = "completed" | "interrupted" | "error";

export interface SavedSession {
  id: string;
  hypothesis: string;
  timestamp: Date;
  stepCount: number;
  status: SessionStatus;
  cumulativeTokens?: number;
  qualityScore?: number;
}

export interface SessionSnapshot {
  session: SavedSession;
  steps: ThinkingStep[];
  tokenHistory: TokenUsage[];
  metadata: {
    research_context?: string;
    constraints?: string[];
    preferences?: string[];
    plan_a?: string;
    plan_b?: string;
  };
}

// ─────────────────────────────────────────────────────────────
// Source Types (Perplexity-style Sources Cards)
// ─────────────────────────────────────────────────────────────

export type SourceType = "paper" | "snippet" | "web";

export interface PaperSource {
  id: number;
  type: "paper";
  title: string;
  journal?: string;
  year?: number;
  authors?: string[];
  relevance?: number;
  pmid?: string;
  doi?: string;
}

export interface SnippetSource {
  id: number;
  type: "snippet";
  text: string;
  section?: string;
  paper_id?: string;
  relevance?: number;
}

export interface WebSource {
  id: number;
  type: "web";
  title: string;
  url: string;
  description?: string;
}

export type Source = PaperSource | SnippetSource | WebSource;

// ─────────────────────────────────────────────────────────────
// Thinking Step Types (사고 패널)
// ─────────────────────────────────────────────────────────────

export type ThinkingStepType =
  | "thinking"
  | "acting"
  | "observation"
  | "goal_check"
  | "recovery"
  | "started"
  | "completed";

// Detailed result from observation events
export interface ObservationDetails {
  type: string;
  // parse_hypothesis
  hypothesis?: {
    iv: string;
    dv: string;
    mechanism: string;
    mediators: string[];
    moderators: string[];
    confidence: number;
  };
  // decompose_questions
  questions?: Array<{
    id: string;
    question: string;
    category: string;
    priority: string;
  }>;
  count?: number;
  // search
  papers?: Array<{
    title: string;
    authors: string[];
    year?: number;
    journal: string;
    relevance: number;
  }>;
  total_count?: number;
  coverage?: number;
  // design_experiment
  experiment?: {
    name: string;
    type: string;
    objective: string;
    methods: string[];
    duration: string;
    sample_size: string;
  };
  // design_controls
  controls?: Array<{
    type: string;
    name: string;
    purpose: string;
  }>;
  // suggest_measurements
  measurements?: Array<{
    name: string;
    type: string;
    method: string;
    unit: string;
  }>;
  // critique_design
  critique?: {
    score: number;
    issues: string[];
    suggestions: string[];
    strengths: string[];
  };
  // synthesize_plan / generate_plan_b
  plan?: {
    has_plan: boolean;
    sections: string[];
    experiment_count: number;
  };
  plan_b?: {
    has_plan: boolean;
    approach: string;
    cost_reduction: string;
  };
}

export interface ThinkingStep {
  id: string;
  type: ThinkingStepType;
  timestamp: Date;
  iteration?: number;
  // thinking - Extended Thinking format (Claude-style)
  title?: string; // 사고 단계 제목 (예: "가설 분석 및 구조화")
  bullets?: string[]; // 세부 사고 포인트들
  message?: string; // Raw thought message
  status?: "in_progress" | "completed"; // 이 사고 단계의 상태
  // acting
  action?: string;
  confidence?: number;
  parameters?: Record<string, unknown>;
  thought?: string; // Acting 시 LLM의 사고 과정
  // observation
  success?: boolean;
  result?: string;
  duration_ms?: number;
  // observation - Detailed result for UI display
  observationDetails?: ObservationDetails;
  // goal_check
  achieved?: boolean;
  missing?: string[];
  details?: Record<string, boolean>;
  // recovery
  error?: string;
  strategy?: string;
  // started
  hypothesis?: string;
  // Token tracking (신규)
  token_usage?: TokenUsage;
  // Recovery options (신규)
  recovery_options?: RecoveryOption[];
  // Sources (Perplexity-style cards) - 신규
  sources?: Source[];
  summary?: string; // Friendly summary message
}

// ─────────────────────────────────────────────────────────────
// Node & Progress Types
// ─────────────────────────────────────────────────────────────

export type NodeStatus = "pending" | "active" | "completed" | "error";

export interface NodeProgress {
  id: string;
  label: string;
  status: NodeStatus;
  icon: ReactNode;
  description: string;
}

// ─────────────────────────────────────────────────────────────
// Data Types
// ─────────────────────────────────────────────────────────────

export interface HypothesisData {
  independent_variable: string;
  dependent_variable: string;
  population: string;
}

export interface TestQuestion {
  category: string;
  question: string;
  decision_rule: string;
}

export interface Experiment {
  id: string;
  type: string;
  title: string;
  test_category: string;
}

export interface ApprovalChoice {
  choice_id: string;
  label: string;
  description: string;
  estimated_cost: string;
  estimated_timeline: string;
}

export interface CritiqueData {
  quality_score: number;
  passed: boolean;
  suggestions: string[];
}

export interface FeasibilityData {
  overall_score: number;
  concerns: string[];
}

// ─────────────────────────────────────────────────────────────
// Node Detail Types
// ─────────────────────────────────────────────────────────────

export interface NodeDetailData {
  parse_hypothesis?: {
    hypothesis?: HypothesisData;
    confidence?: number;
  };
  clarify_hypothesis?: {
    questions?: string[];
  };
  decompose_tests?: {
    test_questions?: TestQuestion[];
  };
  search_studies?: {
    study_count?: number;
    coverage?: number;
    gaps?: string[];
  };
  expand_search?: {
    expanded_queries?: string[];
    expand_count?: number;
  };
  build_evidence?: {
    snippet_count?: number;
    pack_count?: number;
  };
  analyze_methodologies?: {
    pattern_count?: number;
  };
  design_experiments?: {
    experiments?: Experiment[];
  };
  critique_refine?: {
    quality_score?: number;
    passed?: boolean;
    suggestions?: string[];
    revision_count?: number;
  };
  identify_measurements?: {
    measurement_count?: number;
    priority?: string[];
  };
  validate_feasibility?: {
    overall_score?: number;
    concerns?: string[];
  };
  approval_gate?: {
    approval_required?: boolean;
    item_count?: number;
    choices?: ApprovalChoice[];
  };
  synthesize_plan?: {
    final_plan?: string;
    executive_summary?: string;
  };
}

// ─────────────────────────────────────────────────────────────
// State Types
// ─────────────────────────────────────────────────────────────

export interface StudyPlanState {
  status: "idle" | "generating" | "completed" | "error";
  nodeDetails: NodeDetailData;
  error?: string;
}

// ─────────────────────────────────────────────────────────────
// Activity Log Types
// ─────────────────────────────────────────────────────────────

export type ActivityLogType = "thinking" | "action" | "result" | "error";

export interface ActivityLog {
  id: string;
  timestamp: Date;
  type: ActivityLogType;
  title: string;
  description?: string;
  nodeId?: string;
}

// ─────────────────────────────────────────────────────────────
// Landing Page Types
// ─────────────────────────────────────────────────────────────

export interface Feature {
  icon: ReactNode;
  title: string;
  description: string;
}

export interface FAQ {
  question: string;
  answer: string;
}

// ─────────────────────────────────────────────────────────────
// SSE Event Types (from agent_jobs stream)
// ─────────────────────────────────────────────────────────────

export interface StudyPlanSSEEvent {
  node?: string;
  detail?: string;
  // 가설 파싱
  hypothesis?: {
    original_text?: string;
    independent_variable?: string;
    dependent_variable?: string;
    mediating_variables?: string[];
    moderating_variables?: string[];
    population?: string;
    mechanism_pathway?: string;
    keywords?: string[];
    expanded_keywords?: string[];
    gene_aliases?: string[];
  };
  confidence?: number;
  // 검증 질문
  test_questions?: Array<{
    category: string;
    question: string;
    decision_rule: string;
    rationale?: string;
    priority: number;
  }>;
  count?: number;
  // 검색
  study_count?: number;
  coverage?: number;
  gaps?: string[];
  current_tier?: number;
  queries?: string[];
  // Evidence
  snippet_count?: number;
  pack_count?: number;
  // 방법론
  patterns?: Array<{ name: string; frequency: number }>;
  biomarkers?: string[];
  techniques?: string[];
  // 실험 설계
  experiments?: Experiment[];
  // Critique
  quality_score?: number;
  passed?: boolean;
  suggestions?: string[];
  missing_controls?: string[];
  confounders?: string[];
  revision_count?: number;
  dp2_decision?: string;
  // 측정
  measurement_count?: number;
  priority?: string[];
  measurements?: Array<{ name: string; category: string; method: string }>;
  // 실현가능성
  overall_score?: number;
  technical_feasibility?: number;
  resource_feasibility?: number;
  timeline_feasibility?: number;
  concerns?: string[];
  // 승인
  approval_required?: boolean;
  item_count?: number;
  items?: Array<{ type: string; reason: string }>;
  // 합성
  final_plan_length?: number;
  summary_length?: number;
  plan_a_length?: number;
  plan_b_length?: number;
  // 완료
  success?: boolean;
  experiment_count?: number;
  total_duration_ms?: number;
  final_plan?: string;
  executive_summary?: string;
  plan_a?: string;
  plan_b?: string;
  dp3_decision?: string;
  highest_tier_used?: number;
  // Papers count (논문 수)
  paper_count?: number;
  // 에러
  error?: string;
  message?: string;

  // ─────────────────────────────────────────────────────────────
  // v4 ReAct/LangGraph 확장 필드
  // ─────────────────────────────────────────────────────────────

  // 현재 액션 정보
  action?: string;
  action_input?: Record<string, unknown>;
  thought?: string;

  // 토큰 사용량
  token_usage?: TokenUsage;
  cumulative_tokens?: TokenUsage;

  // 복구 옵션
  recovery_options?: RecoveryOption[];
  auto_recovery_timeout?: number;

  // 목표 체크
  achieved?: boolean;
  goal_details?: Record<string, boolean>;
  goals_achieved?: string[];
  goals_missing?: string[];

  // 반복 정보
  iteration?: number;
  iteration_count?: number;

  // Sources (Perplexity-style cards) - 신규
  sources?: Source[];
  summary?: string; // Friendly summary message
}
