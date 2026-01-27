/**
 * Study Plan Agent 상수
 */

import {
  Brain,
  Target,
  Search,
  BookOpen,
  Microscope,
  FlaskConical,
  ClipboardCheck,
  Gauge,
  ShieldCheck,
  FileCheck,
  Beaker,
  Clock,
  Shield,
} from "lucide-react";
import type { NodeProgress, Feature, FAQ } from "./types";

// ─────────────────────────────────────────────────────────────
// Initial Nodes
// ─────────────────────────────────────────────────────────────

export const createInitialNodes = (): NodeProgress[] => [
  {
    id: "parse_hypothesis",
    label: "가설 파싱",
    status: "pending",
    icon: <Brain size={16} />,
    description: "입력된 가설을 구조화하고 핵심 변수를 추출합니다",
  },
  {
    id: "decompose_tests",
    label: "검증 질문 분해",
    status: "pending",
    icon: <Target size={16} />,
    description: "가설 검증을 위한 NSPE 질문을 생성합니다",
  },
  {
    id: "search_studies",
    label: "관련 연구 검색",
    status: "pending",
    icon: <Search size={16} />,
    description: "관련 논문을 RAG로 검색합니다",
  },
  {
    id: "build_evidence",
    label: "Evidence Pack 구축",
    status: "pending",
    icon: <BookOpen size={16} />,
    description: "검색된 논문에서 근거를 추출합니다",
  },
  {
    id: "analyze_methodologies",
    label: "방법론 분석",
    status: "pending",
    icon: <Microscope size={16} />,
    description: "기존 연구의 방법론 패턴을 분석합니다",
  },
  {
    id: "design_experiments",
    label: "실험 설계",
    status: "pending",
    icon: <FlaskConical size={16} />,
    description: "검증 질문에 맞는 실험을 설계합니다",
  },
  {
    id: "critique_refine",
    label: "설계 검증",
    status: "pending",
    icon: <ClipboardCheck size={16} />,
    description: "설계의 품질을 평가하고 개선합니다",
  },
  {
    id: "identify_measurements",
    label: "측정 항목 도출",
    status: "pending",
    icon: <Gauge size={16} />,
    description: "실험에 필요한 측정 항목을 식별합니다",
  },
  {
    id: "validate_feasibility",
    label: "실현가능성 평가",
    status: "pending",
    icon: <ShieldCheck size={16} />,
    description: "기술/자원/일정 측면의 실현가능성을 평가합니다",
  },
  {
    id: "approval_gate",
    label: "승인 게이트",
    status: "pending",
    icon: <FileCheck size={16} />,
    description: "고비용/윤리 심의 필요 항목을 검토합니다",
  },
  {
    id: "synthesize_plan",
    label: "최종 계획 합성",
    status: "pending",
    icon: <Beaker size={16} />,
    description: "모든 정보를 종합하여 최종 계획서를 생성합니다",
  },
];

// ─────────────────────────────────────────────────────────────
// Features (Landing Page)
// ─────────────────────────────────────────────────────────────

export const features: Feature[] = [
  {
    icon: <FlaskConical size={28} className="text-[var(--oaria-teal)]" />,
    title: "AI 기반 실험 설계",
    description:
      "가설을 입력하면 검증 가능한 실험 설계안을 자동으로 생성합니다. In vitro, In vivo, 임상 실험까지 포괄적으로 제안합니다.",
  },
  {
    icon: <BookOpen size={28} className="text-[var(--oaria-teal)]" />,
    title: "Evidence Pack 자동 구축",
    description:
      "관련 선행 연구를 자동으로 검색하고, 방법론과 결과를 분석하여 실험 설계의 근거 자료를 구축합니다.",
  },
  {
    icon: <Shield size={28} className="text-[var(--oaria-teal)]" />,
    title: "자기검증 시스템",
    description:
      "내장된 Critic 시스템이 생성된 실험 설계의 품질을 평가하고, 개선점을 자동으로 반영합니다.",
  },
  {
    icon: <Clock size={28} className="text-[var(--oaria-teal)]" />,
    title: "비용 & 윤리 승인 게이트",
    description:
      "실험의 예상 비용과 윤리적 고려사항을 분석하여, 연구자가 의사결정하기 전에 주요 사항을 확인할 수 있습니다.",
  },
];

// ─────────────────────────────────────────────────────────────
// FAQs (Landing Page)
// ─────────────────────────────────────────────────────────────

export const faqs: FAQ[] = [
  {
    question: "Study Plan Agent란 무엇인가요?",
    answer:
      "Study Plan Agent는 연구 가설을 입력받아 체계적인 실험 설계 계획서를 자동으로 생성하는 AI 에이전트입니다. 가설 파싱, 검증 질문 분해, 선행 연구 검색, Evidence Pack 구축, 실험 설계, 자기검증까지 전체 과정을 자동화합니다.",
  },
  {
    question: "어떤 종류의 가설을 입력할 수 있나요?",
    answer:
      "생명과학, 의학, 약학 분야의 가설을 지원합니다. 예를 들어 'EGFR T790M 돌연변이 환자에서 osimertinib 내성 기전으로 MET amplification이 관여한다'와 같은 분자생물학적 가설부터 임상적 가설까지 다양하게 처리할 수 있습니다.",
  },
  {
    question: "생성된 계획서는 저장되나요?",
    answer:
      "네, 생성된 모든 실험 설계 계획서는 자동으로 저장됩니다. '내 기록 보기' 버튼을 통해 과거에 생성한 계획서들을 언제든지 다시 확인하고 활용할 수 있습니다.",
  },
  {
    question: "생성에 얼마나 시간이 걸리나요?",
    answer:
      "가설의 복잡도와 선행 연구 검색 범위에 따라 다르지만, 일반적으로 2-5분 내에 완료됩니다. 진행 상황은 실시간으로 화면에 표시되므로 각 단계의 완료 여부를 확인할 수 있습니다.",
  },
];

// ─────────────────────────────────────────────────────────────
// v4 LangGraph Event Mapping
// ─────────────────────────────────────────────────────────────

export const v4EventNodeMap: Record<string, string> = {
  started: "parse_hypothesis",
  thinking: "parse_hypothesis",
  acting: "design_experiments",
  observation: "build_evidence",
  recovery: "critique_refine",
  goal_check: "validate_feasibility",
  completed: "synthesize_plan",
};

export const v4EventTitles: Record<string, string> = {
  started: "에이전트 시작",
  thinking: "다음 행동 결정 중",
  acting: "도구 실행 중",
  observation: "실행 결과 관찰",
  recovery: "실패 복구 시도",
  goal_check: "목표 달성 확인",
  completed: "계획 생성 완료",
};
