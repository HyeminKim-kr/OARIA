"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Search,
  Bot,
  MessageSquare,
  Beaker,
  BarChart3,
  Loader2,
  CheckCircle2,
  Circle,
  ChevronDown,
  ChevronUp,
  FileText,
  FlaskConical,
  Target,
  AlertTriangle,
  Clock,
  DollarSign,
  X,
  Brain,
  BookOpen,
  Microscope,
  ClipboardCheck,
  Gauge,
  ShieldCheck,
  FileCheck,
  Lightbulb,
  ArrowLeft,
  History,
  Sparkles,
  Shield,
} from "lucide-react";
import { studyPlanApi, StudyPlanV3Response, StudyPlanV3SaveRequest, StudyPlanSSEEvent, fetchWithAuth, agentJobsApi } from "@/lib/api";
import { useJobStream, JobStreamEvent } from "@/hooks";
import { ApprovalModal } from "@/components/jobs";
import { useNotifications } from "@/contexts/NotificationContext";

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

interface HypothesisData {
  independent_variable: string;
  dependent_variable: string;
  population: string;
}

interface TestQuestion {
  category: string;
  question: string;
  decision_rule: string;
}

interface Experiment {
  id: string;
  type: string;
  title: string;
  test_category: string;
}

interface ApprovalChoice {
  choice_id: string;
  label: string;
  description: string;
  estimated_cost: string;
  estimated_timeline: string;
}

interface CritiqueData {
  quality_score: number;
  passed: boolean;
  suggestions: string[];
}

interface FeasibilityData {
  overall_score: number;
  concerns: string[];
}

interface NodeDetailData {
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

interface StudyPlanState {
  status: string;
  nodeDetails: NodeDetailData;
  error?: string;
}

type NodeStatus = "pending" | "active" | "completed" | "error";

interface NodeProgress {
  id: string;
  label: string;
  status: NodeStatus;
  icon: React.ReactNode;
  description: string;
}

interface Feature {
  icon: React.ReactNode;
  title: string;
  description: string;
}

interface FAQ {
  question: string;
  answer: string;
}

// 활동 로그 타입
interface ActivityLog {
  id: string;
  timestamp: Date;
  type: "thinking" | "action" | "result" | "error";
  title: string;
  description?: string;
  nodeId?: string;
}

// ─────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const createInitialNodes = (): NodeProgress[] => [
  { id: "parse_hypothesis", label: "가설 파싱", status: "pending", icon: <Brain size={16} />, description: "입력된 가설을 구조화하고 핵심 변수를 추출합니다" },
  { id: "decompose_tests", label: "검증 질문 분해", status: "pending", icon: <Target size={16} />, description: "가설 검증을 위한 NSPE 질문을 생성합니다" },
  { id: "search_studies", label: "관련 연구 검색", status: "pending", icon: <Search size={16} />, description: "관련 논문을 RAG로 검색합니다" },
  { id: "build_evidence", label: "Evidence Pack 구축", status: "pending", icon: <BookOpen size={16} />, description: "검색된 논문에서 근거를 추출합니다" },
  { id: "analyze_methodologies", label: "방법론 분석", status: "pending", icon: <Microscope size={16} />, description: "기존 연구의 방법론 패턴을 분석합니다" },
  { id: "design_experiments", label: "실험 설계", status: "pending", icon: <FlaskConical size={16} />, description: "검증 질문에 맞는 실험을 설계합니다" },
  { id: "critique_refine", label: "설계 검증", status: "pending", icon: <ClipboardCheck size={16} />, description: "설계의 품질을 평가하고 개선합니다" },
  { id: "identify_measurements", label: "측정 항목 도출", status: "pending", icon: <Gauge size={16} />, description: "실험에 필요한 측정 항목을 식별합니다" },
  { id: "validate_feasibility", label: "실현가능성 평가", status: "pending", icon: <ShieldCheck size={16} />, description: "기술/자원/일정 측면의 실현가능성을 평가합니다" },
  { id: "approval_gate", label: "승인 게이트", status: "pending", icon: <FileCheck size={16} />, description: "고비용/윤리 심의 필요 항목을 검토합니다" },
  { id: "synthesize_plan", label: "최종 계획 합성", status: "pending", icon: <Beaker size={16} />, description: "모든 정보를 종합하여 최종 계획서를 생성합니다" },
];

const features: Feature[] = [
  {
    icon: <FlaskConical size={28} className="text-[var(--oaria-teal)]" />,
    title: "AI 기반 실험 설계",
    description: "가설을 입력하면 검증 가능한 실험 설계안을 자동으로 생성합니다. In vitro, In vivo, 임상 실험까지 포괄적으로 제안합니다.",
  },
  {
    icon: <BookOpen size={28} className="text-[var(--oaria-teal)]" />,
    title: "Evidence Pack 자동 구축",
    description: "관련 선행 연구를 자동으로 검색하고, 방법론과 결과를 분석하여 실험 설계의 근거 자료를 구축합니다.",
  },
  {
    icon: <Shield size={28} className="text-[var(--oaria-teal)]" />,
    title: "자기검증 시스템",
    description: "내장된 Critic 시스템이 생성된 실험 설계의 품질을 평가하고, 개선점을 자동으로 반영합니다.",
  },
  {
    icon: <Clock size={28} className="text-[var(--oaria-teal)]" />,
    title: "비용 & 윤리 승인 게이트",
    description: "실험의 예상 비용과 윤리적 고려사항을 분석하여, 연구자가 의사결정하기 전에 주요 사항을 확인할 수 있습니다.",
  },
];

const faqs: FAQ[] = [
  {
    question: "Study Plan Agent란 무엇인가요?",
    answer: "Study Plan Agent는 연구 가설을 입력받아 체계적인 실험 설계 계획서를 자동으로 생성하는 AI 에이전트입니다. 가설 파싱, 검증 질문 분해, 선행 연구 검색, Evidence Pack 구축, 실험 설계, 자기검증까지 전체 과정을 자동화합니다.",
  },
  {
    question: "어떤 종류의 가설을 입력할 수 있나요?",
    answer: "생명과학, 의학, 약학 분야의 가설을 지원합니다. 예를 들어 'EGFR T790M 돌연변이 환자에서 osimertinib 내성 기전으로 MET amplification이 관여한다'와 같은 분자생물학적 가설부터 임상적 가설까지 다양하게 처리할 수 있습니다.",
  },
  {
    question: "생성된 계획서는 저장되나요?",
    answer: "네, 생성된 모든 실험 설계 계획서는 자동으로 저장됩니다. '내 기록 보기' 버튼을 통해 과거에 생성한 계획서들을 언제든지 다시 확인하고 활용할 수 있습니다.",
  },
  {
    question: "생성에 얼마나 시간이 걸리나요?",
    answer: "가설의 복잡도와 선행 연구 검색 범위에 따라 다르지만, 일반적으로 2-5분 내에 완료됩니다. 진행 상황은 실시간으로 화면에 표시되므로 각 단계의 완료 여부를 확인할 수 있습니다.",
  },
];

// ─────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────

export default function StudyPlanPage() {
  // View mode: "landing" or "generate"
  const [viewMode, setViewMode] = useState<"landing" | "generate">("landing");

  // Form state
  const [hypothesis, setHypothesis] = useState("");
  const [researchContext, setResearchContext] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [agentVersion, setAgentVersion] = useState<"v3" | "v4">("v3");
  const [nodes, setNodes] = useState<NodeProgress[]>(createInitialNodes());
  const [state, setState] = useState<StudyPlanState>({ status: "idle", nodeDetails: {} });
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(["plan"]));
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  // 활동 로그 state
  const [activityLogs, setActivityLogs] = useState<ActivityLog[]>([]);
  const [showActivitySidebar, setShowActivitySidebar] = useState(true);
  const [elapsedTime, setElapsedTime] = useState(0);
  const activityEndRef = useRef<HTMLDivElement>(null);

  // 백그라운드 작업 모드 state
  const [useBackgroundMode, setUseBackgroundMode] = useState(false);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const { addToast } = useNotifications();

  // useJobStream hook for background job mode
  const {
    jobId,
    status: jobStatus,
    progress: jobProgress,
    currentStep: jobCurrentStep,
    error: jobError,
    result: jobResult,
    approvalData,
    startJob,
    approve,
    cancel,
    reset: resetJob,
  } = useJobStream({
    onEvent: (event) => {
      // Update activity logs based on job events
      if (event.node && event.detail) {
        const nodeLabel = nodes.find(n => n.id === event.node)?.label || event.node;
        addActivityLog({
          type: "action",
          title: nodeLabel,
          description: event.detail,
          nodeId: event.node,
        });
      }

      // Update node status
      if (event.node) {
        setNodes((prev) => {
          const nodeIndex = prev.findIndex((n) => n.id === event.node);
          return prev.map((n, i) => {
            if (i < nodeIndex && n.status !== "completed") {
              return { ...n, status: "completed" as NodeStatus };
            }
            if (i === nodeIndex) {
              return { ...n, status: "active" as NodeStatus };
            }
            return n;
          });
        });
      }
    },
    onApprovalRequired: (event) => {
      addActivityLog({
        type: "thinking",
        title: "승인 필요",
        description: "고비용 실험 또는 윤리 심의가 필요한 항목이 있습니다.",
      });
      setShowApprovalModal(true);
    },
    onCompleted: (event) => {
      setNodes((prev) => prev.map((n) => ({ ...n, status: "completed" as NodeStatus })));
      addActivityLog({
        type: "result",
        title: "실험 계획서 생성 완료",
        description: `${event.experiment_count || 0}개 실험 · 소요시간 ${((event.total_duration_ms || 0) / 1000).toFixed(1)}초`,
      });

      // Update state with result
      setState({
        status: "completed",
        nodeDetails: {
          synthesize_plan: {
            final_plan: event.final_plan || event.plan_a || "",
            executive_summary: event.executive_summary || "",
          },
        },
      });

      setIsLoading(false);

      // Show toast notification
      addToast({
        type: "success",
        title: "실험 계획서 완료",
        message: "Study Plan이 성공적으로 생성되었습니다.",
        duration: 5000,
      });
    },
    onError: (error) => {
      addActivityLog({
        type: "error",
        title: "오류 발생",
        description: error,
      });
      setState((prev) => ({
        ...prev,
        status: "error",
        error,
      }));
      setIsLoading(false);

      addToast({
        type: "error",
        title: "생성 실패",
        message: error,
        duration: 5000,
      });
    },
  });

  // 활동 로그 추가 헬퍼
  const addActivityLog = (log: Omit<ActivityLog, "id" | "timestamp">) => {
    setActivityLogs((prev) => [
      ...prev,
      {
        ...log,
        id: `log-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        timestamp: new Date(),
      },
    ]);
  };

  // 타이머 효과
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isLoading) {
      setElapsedTime(0);
      interval = setInterval(() => {
        setElapsedTime((prev) => prev + 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isLoading]);

  // 활동 로그 자동 스크롤
  useEffect(() => {
    activityEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activityLogs]);

  const toggleFaq = (index: number) => {
    setOpenFaqIndex(openFaqIndex === index ? null : index);
  };

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

  const updateNodeStatus = (nodeId: string, status: NodeStatus) => {
    setNodes((prev) =>
      prev.map((n) =>
        n.id === nodeId ? { ...n, status } : n
      )
    );
  };

  const updateNodeDetails = (nodeId: string, data: Record<string, unknown>) => {
    setState((prev) => ({
      ...prev,
      nodeDetails: {
        ...prev.nodeDetails,
        [nodeId]: { ...((prev.nodeDetails as Record<string, unknown>)[nodeId] || {}), ...data },
      },
    }));
  };

  // 백그라운드 모드 제출 핸들러
  const handleSubmitBackground = async () => {
    setIsLoading(true);
    setNodes(createInitialNodes());
    setState({ status: "generating", nodeDetails: {} });
    setSelectedNode(null);
    setActivityLogs([]);
    setShowActivitySidebar(true);

    addActivityLog({
      type: "thinking",
      title: `가설 분석 시작 (${agentVersion.toUpperCase()} 백그라운드)`,
      description: hypothesis.trim().substring(0, 100) + (hypothesis.length > 100 ? "..." : ""),
    });

    try {
      const agentType = agentVersion === "v4" ? "study_plan_v4" : "study_plan_v3";
      await startJob(agentType, {
        hypothesis: hypothesis.trim(),
        research_context: researchContext.trim() || undefined,
        preferred_experiment_types: ["in_vitro", "in_vivo"],
      });
    } catch (error) {
      console.error("Failed to start background job:", error);
      setIsLoading(false);
    }
  };

  // 승인 처리 핸들러
  const handleApprove = async (decision: Record<string, unknown>) => {
    try {
      await approve(decision);
      setShowApprovalModal(false);
      addActivityLog({
        type: "result",
        title: "승인 완료",
        description: "작업이 계속 진행됩니다.",
      });
    } catch (error) {
      console.error("Approval failed:", error);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!hypothesis.trim() || isLoading) return;

    // 백그라운드 모드 사용 시
    if (useBackgroundMode) {
      handleSubmitBackground();
      return;
    }

    setIsLoading(true);
    setNodes(createInitialNodes());
    setState({ status: "generating", nodeDetails: {} });
    setSelectedNode(null);
    setActivityLogs([]); // 활동 로그 초기화
    setShowActivitySidebar(true); // 사이드바 열기

    // 초기 활동 로그
    addActivityLog({
      type: "thinking",
      title: `가설 분석 시작 (${agentVersion.toUpperCase()})`,
      description: hypothesis.trim().substring(0, 100) + (hypothesis.length > 100 ? "..." : ""),
    });

    // 버전에 따른 API URL 선택
    const streamUrl = agentVersion === "v4"
      ? studyPlanApi.generateV4StreamUrl()
      : studyPlanApi.generateV3StreamUrl();

    // SSE 스트리밍 API 사용 - 실제 중간 단계 데이터 수신
    try {
      const response = await fetchWithAuth(streamUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          hypothesis: hypothesis.trim(),
          research_context: researchContext.trim() || undefined,
          preferred_experiment_types: ["in_vitro", "in_vivo"],
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("Response body is null");

      const decoder = new TextDecoder();
      let buffer = "";
      let finalResult: StudyPlanV3Response | null = null;
      let currentEventType = "";

      // v4 전용 노드 매핑 (ReAct 이벤트)
      const v4EventNodeMap: Record<string, string> = {
        started: "parse_hypothesis",
        thinking: "parse_hypothesis",
        acting: "design_experiments",
        observation: "build_evidence",
        recovery: "critique_refine",
        goal_check: "validate_feasibility",
        completed: "synthesize_plan",
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;

          // SSE 이벤트 파싱 - event type 저장
          if (line.startsWith("event:")) {
            currentEventType = line.substring(6).trim();
            continue;
          }

          if (line.startsWith("data:")) {
            const dataStr = line.substring(5).trim();
            if (!dataStr) continue;

            try {
              const data: StudyPlanSSEEvent = JSON.parse(dataStr);
              const nodeId = data.node;

              console.log("[SSE v3] Event:", currentEventType, nodeId, data);

              // v4 completed 이벤트 처리 (ReAct 에이전트)
              if (agentVersion === "v4" && currentEventType === "completed") {
                finalResult = {
                  success: data.success || false,
                  final_plan: data.plan_a || "",
                  executive_summary: data.executive_summary || "",
                  experiment_count: data.experiment_count || 0,
                  approval_required: false,
                  approval_status: "approved",
                  total_duration_ms: data.total_duration_ms || 0,
                  plan_a: data.plan_a,
                  plan_b: data.plan_b,
                };
                currentEventType = "";
                continue;
              }

              // v4 이벤트 처리 (ReAct 에이전트)
              if (agentVersion === "v4") {
                const v4Titles: Record<string, string> = {
                  started: "v4 에이전트 시작",
                  thinking: "다음 행동 결정 중",
                  acting: "도구 실행 중",
                  observation: "실행 결과 관찰",
                  recovery: "실패 복구 시도",
                  goal_check: "목표 달성 확인",
                };

                if (v4Titles[currentEventType]) {
                  // v4 이벤트 데이터 (다른 구조)
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  const v4Data = data as any;

                  // 노드 상태 업데이트 (v4 매핑)
                  const nodeId = v4EventNodeMap[currentEventType];
                  if (nodeId) {
                    setNodes((prev) => {
                      const nodeIndex = prev.findIndex((n) => n.id === nodeId);
                      return prev.map((n, i) => {
                        if (i < nodeIndex && n.status !== "completed") {
                          return { ...n, status: "completed" as NodeStatus };
                        }
                        if (i === nodeIndex) {
                          return { ...n, status: "active" as NodeStatus };
                        }
                        return n;
                      });
                    });
                  }

                  // 활동 로그
                  let description = "";
                  if (currentEventType === "started") {
                    description = `가설: ${v4Data.hypothesis}`;
                  } else if (currentEventType === "thinking") {
                    description = `반복 ${v4Data.iteration}: ${v4Data.message}`;
                  } else if (currentEventType === "acting") {
                    description = `반복 ${v4Data.iteration}: ${v4Data.action} 실행 (신뢰도: ${((v4Data.confidence || 0) * 100).toFixed(0)}%)`;
                  } else if (currentEventType === "observation") {
                    description = `${v4Data.action}: ${v4Data.success ? "성공" : "실패"} (${v4Data.duration_ms}ms)`;
                  } else if (currentEventType === "recovery") {
                    description = `오류: ${v4Data.error}`;
                  } else if (currentEventType === "goal_check") {
                    description = v4Data.achieved
                      ? "목표 달성!"
                      : `미완료 항목: ${v4Data.missing?.slice(0, 3).join(", ")}`;
                  }

                  addActivityLog({
                    type: currentEventType === "recovery" ? "error" :
                          currentEventType === "observation" ? "result" :
                          "action",
                    title: v4Titles[currentEventType],
                    description,
                    nodeId,
                  });

                  currentEventType = "";
                  continue;
                }
              }

              // v3 done 이벤트 처리 - 최종 결과
              if (currentEventType === "done" && data.success && data.final_plan) {
                finalResult = {
                  success: data.success,
                  final_plan: data.final_plan,
                  executive_summary: data.executive_summary || "",
                  experiment_count: data.experiment_count || 0,
                  approval_required: data.approval_required || false,
                  approval_status: "approved",
                  total_duration_ms: data.total_duration_ms || 0,
                  plan_a: data.plan_a,
                  plan_b: data.plan_b,
                  dp3_decision: data.dp3_decision,
                  highest_tier_used: data.highest_tier_used,
                };
                currentEventType = "";
                continue;
              }

              // error 이벤트 처리
              if (currentEventType === "error") {
                addActivityLog({
                  type: "error",
                  title: "오류 발생",
                  description: data.message || data.error || "알 수 없는 오류",
                });
                setState((prev) => ({
                  ...prev,
                  status: "error",
                  error: data.message || data.error || "알 수 없는 오류",
                }));
                currentEventType = "";
                continue;
              }

              // 노드 상태 업데이트
              if (nodeId) {
                setNodes((prev) => {
                  const nodeIndex = prev.findIndex((n) => n.id === nodeId);
                  return prev.map((n, i) => {
                    if (i < nodeIndex && n.status !== "completed") {
                      return { ...n, status: "completed" as NodeStatus };
                    }
                    if (i === nodeIndex) {
                      return { ...n, status: "active" as NodeStatus };
                    }
                    return n;
                  });
                });

                // 노드별 상세 데이터 저장
                updateNodeDetails(nodeId, data as unknown as Record<string, unknown>);

                // 활동 로그에 실제 데이터 추가
                if (data.detail) {
                  const nodeLabel = nodes.find(n => n.id === nodeId)?.label || nodeId;
                  addActivityLog({
                    type: "action",
                    title: nodeLabel,
                    description: data.detail,
                    nodeId,
                  });
                }

                // 추가 상세 정보 로그
                if (nodeId === "parse_hypothesis" && data.hypothesis) {
                  addActivityLog({
                    type: "thinking",
                    title: "가설 구조 분석",
                    description: `독립변수: ${data.hypothesis.independent_variable}\n종속변수: ${data.hypothesis.dependent_variable}`,
                    nodeId,
                  });
                  if (data.hypothesis.keywords && data.hypothesis.keywords.length > 0) {
                    addActivityLog({
                      type: "thinking",
                      title: "핵심 키워드 추출",
                      description: data.hypothesis.keywords.slice(0, 5).join(", "),
                      nodeId,
                    });
                  }
                }

                if (nodeId === "decompose_tests" && data.test_questions) {
                  addActivityLog({
                    type: "result",
                    title: "검증 질문 생성 완료",
                    description: `${data.test_questions.length}개 질문 (${data.test_questions.map(q => q.category.toUpperCase()).join(", ")})`,
                    nodeId,
                  });
                }

                if ((nodeId === "search_studies" || nodeId === "search_v3") && data.study_count !== undefined) {
                  const tierNames = ["", "RAG", "Europe PMC", "Web"];
                  const tier = data.current_tier || 1;
                  addActivityLog({
                    type: "result",
                    title: `${tierNames[tier]} 검색 완료`,
                    description: `${data.study_count}편 논문 발견 (커버리지: ${((data.coverage || 0) * 100).toFixed(0)}%)`,
                    nodeId,
                  });
                  if (data.gaps && data.gaps.length > 0) {
                    addActivityLog({
                      type: "thinking",
                      title: "커버리지 부족 영역",
                      description: data.gaps.slice(0, 2).join(", "),
                      nodeId,
                    });
                  }
                }

                if (nodeId === "build_evidence" && data.snippet_count !== undefined) {
                  addActivityLog({
                    type: "result",
                    title: "Evidence Pack 구축",
                    description: `${data.pack_count}개 논문에서 ${data.snippet_count}개 스니펫 추출`,
                    nodeId,
                  });
                }

                if (nodeId === "design_experiments" && data.experiments) {
                  const expTypes = [...new Set(data.experiments.map(e => e.type))];
                  addActivityLog({
                    type: "result",
                    title: "실험 설계 완료",
                    description: `${data.experiments.length}개 실험 (${expTypes.join(", ")})`,
                    nodeId,
                  });
                  // 각 실험 제목 표시
                  data.experiments.slice(0, 3).forEach(exp => {
                    addActivityLog({
                      type: "thinking",
                      title: `실험: ${exp.type.toUpperCase()}`,
                      description: exp.title,
                      nodeId,
                    });
                  });
                }

                if ((nodeId === "critique_refine" || nodeId === "critique_v3") && data.quality_score !== undefined) {
                  addActivityLog({
                    type: data.passed ? "result" : "thinking",
                    title: data.passed ? "품질 검증 통과" : "설계 개선 필요",
                    description: `품질 점수: ${(data.quality_score * 100).toFixed(0)}%`,
                    nodeId,
                  });
                  if (data.suggestions && data.suggestions.length > 0) {
                    addActivityLog({
                      type: "thinking",
                      title: "개선 제안",
                      description: data.suggestions[0],
                      nodeId,
                    });
                  }
                }

                if (nodeId === "validate_feasibility" && data.overall_score !== undefined) {
                  addActivityLog({
                    type: "result",
                    title: "실현가능성 평가",
                    description: `종합 점수: ${(data.overall_score * 100).toFixed(0)}%`,
                    nodeId,
                  });
                }

                // 노드 완료 처리
                if (data.detail) {
                  setTimeout(() => {
                    updateNodeStatus(nodeId, "completed");
                  }, 500);
                }
              }

            } catch (parseError) {
              console.warn("[SSE v3] Parse error:", parseError, dataStr);
            }
          }
        }
      }

      // 최종 결과 처리 - success가 false여도 plan이 있으면 결과 표시
      const hasPlan = finalResult && (finalResult.final_plan || finalResult.plan_a);
      if (hasPlan) {
        // 모든 노드 완료 처리
        setNodes((prev) => prev.map((n) => ({ ...n, status: "completed" as NodeStatus })));

        // 완료 활동 로그
        addActivityLog({
          type: "result",
          title: `실험 계획서 생성 완료 (${agentVersion.toUpperCase()})`,
          description: `${finalResult.experiment_count || 0}개 실험 · 소요시간 ${((finalResult.total_duration_ms || 0) / 1000).toFixed(1)}초`,
        });

        // Plan A/B 로그
        if (finalResult.plan_a && finalResult.plan_b) {
          addActivityLog({
            type: "result",
            title: "Plan A/B 생성",
            description: "이상적 설계(Plan A)와 현실적 대안(Plan B) 모두 준비됨",
          });
        } else if (finalResult.plan_a && !finalResult.plan_b) {
          addActivityLog({
            type: "thinking",
            title: "Plan A 생성됨",
            description: "Plan B는 생성되지 않았습니다",
          });
        }

        // 결과 데이터 저장
        const planContent = finalResult.final_plan || finalResult.plan_a || "";
        setState({
          status: "completed",
          nodeDetails: {
            synthesize_plan: {
              final_plan: planContent,
              executive_summary: finalResult.executive_summary || "",
            },
          },
        });

        // 자동 저장 - DB에 저장
        try {
          const saveData: StudyPlanV3SaveRequest = {
            hypothesis_input: hypothesis.trim(),
            research_context: researchContext.trim() || undefined,
            preferred_experiment_types: ["in_vitro", "in_vivo"],
            final_plan: planContent,
            executive_summary: finalResult.executive_summary || "",
            experiment_count: finalResult.experiment_count || 0,
            approval_required: finalResult.approval_required || false,
            approval_status: finalResult.approval_status || "approved",
            total_duration_ms: finalResult.total_duration_ms || 0,
            status: "completed",
            // v3 필드
            plan_a: finalResult.plan_a,
            plan_b: finalResult.plan_b,
            dp3_decision: finalResult.dp3_decision,
            highest_tier_used: finalResult.highest_tier_used,
          };
          await studyPlanApi.save(saveData);
          console.log("[StudyPlan] 자동 저장 완료");
          addActivityLog({
            type: "result",
            title: "히스토리에 저장됨",
            description: "나중에 '내 기록 보기'에서 확인 가능",
          });
        } catch (saveError) {
          console.error("[StudyPlan] 자동 저장 실패:", saveError);
        }
      } else if (!finalResult) {
        throw new Error("스트리밍이 완료되었으나 결과가 없습니다");
      } else {
        // finalResult는 있지만 plan이 없는 경우
        const experimentCount = finalResult.experiment_count || 0;
        if (experimentCount > 0) {
          throw new Error(
            `${experimentCount}개의 실험이 설계되었으나 최종 계획서 생성에 실패했습니다. 다시 시도해주세요.`
          );
        } else {
          throw new Error(
            "실험 계획서 생성에 실패했습니다. 가설을 수정하거나 다시 시도해주세요."
          );
        }
      }

    } catch (error) {
      console.error("Study Plan generation error:", error);
      addActivityLog({
        type: "error",
        title: "오류 발생",
        description: error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다",
      });
      setState((prev) => ({
        ...prev,
        status: "error",
        error: error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다",
      }));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (state.nodeDetails.synthesize_plan?.final_plan && resultRef.current) {
      resultRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [state.nodeDetails.synthesize_plan?.final_plan]);

  const renderNodeDetail = (nodeId: string) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const details = state.nodeDetails as Record<string, any>;
    const nodeData = details[nodeId];
    const node = nodes.find((n) => n.id === nodeId);

    if (!node) return null;

    return (
      <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setSelectedNode(null)}>
        <div
          className="bg-[var(--background)] rounded-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden shadow-xl"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="px-6 py-4 border-b border-[var(--oaria-border)] flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${
                node.status === "completed" ? "bg-green-100 text-green-600" :
                node.status === "active" ? "bg-[var(--oaria-teal)]/20 text-[var(--oaria-teal)]" :
                "bg-[var(--oaria-border)] text-[var(--oaria-text-secondary)]"
              }`}>
                {node.icon}
              </div>
              <div>
                <h3 className="font-[family-name:var(--font-outfit)] font-semibold">{node.label}</h3>
                <p className="text-xs text-[var(--oaria-text-secondary)]">{node.description}</p>
              </div>
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              className="p-2 hover:bg-[var(--oaria-border)] rounded-lg transition-colors"
            >
              <X size={20} />
            </button>
          </div>

          {/* Content */}
          <div className="px-6 py-4 overflow-y-auto max-h-[60vh]">
            {!nodeData ? (
              <div className="text-center py-8 text-[var(--oaria-text-secondary)]">
                {node.status === "completed" ? (
                  <>
                    <CheckCircle2 size={32} className="mx-auto mb-2 text-green-500" />
                    <p>이 단계가 완료되었습니다</p>
                    <p className="text-xs mt-1 opacity-70">상세 정보는 최종 계획서에서 확인하세요</p>
                  </>
                ) : (
                  <>
                    <Lightbulb size={32} className="mx-auto mb-2 opacity-50" />
                    <p>아직 이 단계가 실행되지 않았습니다</p>
                  </>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                {/* 가설 파싱 */}
                {nodeId === "parse_hypothesis" && nodeData.hypothesis && (
                  <>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-xs font-medium px-2 py-1 rounded bg-[var(--oaria-teal)]/20 text-[var(--oaria-teal)]">
                        신뢰도: {((nodeData.confidence as number) * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
                        <span className="text-xs text-blue-600 font-medium">독립 변수</span>
                        <p className="font-[family-name:var(--font-dm-sans)] text-blue-900">
                          {(nodeData.hypothesis as HypothesisData).independent_variable}
                        </p>
                      </div>
                      <div className="p-3 rounded-lg bg-orange-50 border border-orange-200">
                        <span className="text-xs text-orange-600 font-medium">종속 변수</span>
                        <p className="font-[family-name:var(--font-dm-sans)] text-orange-900">
                          {(nodeData.hypothesis as HypothesisData).dependent_variable}
                        </p>
                      </div>
                    </div>
                    {(nodeData.hypothesis as HypothesisData).population && (
                      <div className="p-3 rounded-lg bg-[var(--oaria-border)]/30">
                        <span className="text-xs text-[var(--oaria-text-secondary)]">대상 집단</span>
                        <p className="font-[family-name:var(--font-dm-sans)]">
                          {(nodeData.hypothesis as HypothesisData).population}
                        </p>
                      </div>
                    )}
                  </>
                )}

                {/* 검증 질문 */}
                {nodeId === "decompose_tests" && nodeData.test_questions && (
                  <div className="space-y-3">
                    {(nodeData.test_questions as TestQuestion[]).map((tq, i) => (
                      <div key={i} className="p-3 rounded-lg bg-[var(--oaria-border)]/30">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                            tq.category === "necessity" ? "bg-blue-100 text-blue-700" :
                            tq.category === "sufficiency" ? "bg-green-100 text-green-700" :
                            tq.category === "epistasis" ? "bg-orange-100 text-orange-700" :
                            "bg-purple-100 text-purple-700"
                          }`}>
                            {tq.category.toUpperCase()}
                          </span>
                        </div>
                        <p className="font-[family-name:var(--font-dm-sans)] text-sm mb-2">{tq.question}</p>
                        <p className="text-xs text-[var(--oaria-text-secondary)] italic">
                          판정 기준: {tq.decision_rule}
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                {/* 검색 결과 */}
                {nodeId === "search_studies" && (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-4 rounded-lg bg-[var(--oaria-teal)]/10 text-center">
                        <p className="text-3xl font-bold text-[var(--oaria-teal)]">{nodeData.study_count || 0}</p>
                        <p className="text-xs text-[var(--oaria-text-secondary)]">관련 논문</p>
                      </div>
                      <div className="p-4 rounded-lg bg-green-50 text-center">
                        <p className="text-3xl font-bold text-green-600">{((nodeData.coverage as number || 0) * 100).toFixed(0)}%</p>
                        <p className="text-xs text-[var(--oaria-text-secondary)]">커버리지</p>
                      </div>
                    </div>
                    {nodeData.gaps && (nodeData.gaps as string[]).length > 0 && (
                      <div>
                        <p className="text-xs text-[var(--oaria-text-secondary)] mb-2">커버리지 부족 영역</p>
                        <ul className="space-y-1">
                          {(nodeData.gaps as string[]).map((gap, i) => (
                            <li key={i} className="text-sm text-orange-600 flex items-start gap-2">
                              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                              {gap}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* Evidence Pack */}
                {nodeId === "build_evidence" && (
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 rounded-lg bg-purple-50 text-center">
                      <p className="text-3xl font-bold text-purple-600">{nodeData.snippet_count || 0}</p>
                      <p className="text-xs text-[var(--oaria-text-secondary)]">스니펫</p>
                    </div>
                    <div className="p-4 rounded-lg bg-indigo-50 text-center">
                      <p className="text-3xl font-bold text-indigo-600">{nodeData.pack_count || 0}</p>
                      <p className="text-xs text-[var(--oaria-text-secondary)]">Evidence Pack</p>
                    </div>
                  </div>
                )}

                {/* 실험 설계 */}
                {nodeId === "design_experiments" && nodeData.experiments && (
                  <div className="space-y-3">
                    {(nodeData.experiments as Experiment[]).map((exp) => (
                      <div key={exp.id} className="p-3 rounded-lg border border-[var(--oaria-border)]">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                            exp.type === "in_vitro" ? "bg-blue-100 text-blue-700" :
                            exp.type === "in_vivo" ? "bg-green-100 text-green-700" :
                            exp.type === "clinical" ? "bg-red-100 text-red-700" :
                            "bg-gray-100 text-gray-700"
                          }`}>
                            {exp.type.replace("_", " ").toUpperCase()}
                          </span>
                          <span className="text-xs text-[var(--oaria-text-secondary)]">
                            {exp.test_category}
                          </span>
                        </div>
                        <p className="font-[family-name:var(--font-dm-sans)] font-medium">{exp.title}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Critique */}
                {nodeId === "critique_refine" && (
                  <div className="space-y-4">
                    <div className="flex items-center gap-4">
                      <div className={`p-4 rounded-lg flex-1 text-center ${
                        (nodeData.quality_score as number) >= 0.8 ? "bg-green-50" : "bg-yellow-50"
                      }`}>
                        <p className={`text-3xl font-bold ${
                          (nodeData.quality_score as number) >= 0.8 ? "text-green-600" : "text-yellow-600"
                        }`}>
                          {((nodeData.quality_score as number || 0) * 100).toFixed(0)}%
                        </p>
                        <p className="text-xs text-[var(--oaria-text-secondary)]">품질 점수</p>
                      </div>
                      <div className={`p-4 rounded-lg flex-1 text-center ${
                        nodeData.passed ? "bg-green-50" : "bg-orange-50"
                      }`}>
                        <p className={`text-lg font-bold ${
                          nodeData.passed ? "text-green-600" : "text-orange-600"
                        }`}>
                          {nodeData.passed ? "통과" : `수정 ${nodeData.revision_count || 0}회`}
                        </p>
                        <p className="text-xs text-[var(--oaria-text-secondary)]">상태</p>
                      </div>
                    </div>
                    {nodeData.suggestions && (nodeData.suggestions as string[]).length > 0 && (
                      <div>
                        <p className="text-xs text-[var(--oaria-text-secondary)] mb-2">개선 제안</p>
                        <ul className="space-y-1">
                          {(nodeData.suggestions as string[]).slice(0, 3).map((s, i) => (
                            <li key={i} className="text-sm flex items-start gap-2">
                              <Lightbulb size={14} className="mt-0.5 shrink-0 text-yellow-500" />
                              {s}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* 측정 항목 */}
                {nodeId === "identify_measurements" && (
                  <div className="space-y-4">
                    <div className="p-4 rounded-lg bg-[var(--oaria-teal)]/10 text-center">
                      <p className="text-3xl font-bold text-[var(--oaria-teal)]">{nodeData.measurement_count || 0}</p>
                      <p className="text-xs text-[var(--oaria-text-secondary)]">측정 항목</p>
                    </div>
                    {nodeData.priority && (nodeData.priority as string[]).length > 0 && (
                      <div>
                        <p className="text-xs text-[var(--oaria-text-secondary)] mb-2">우선순위</p>
                        <ol className="list-decimal list-inside space-y-1">
                          {(nodeData.priority as string[]).map((p, i) => (
                            <li key={i} className="text-sm">{p}</li>
                          ))}
                        </ol>
                      </div>
                    )}
                  </div>
                )}

                {/* 실현가능성 */}
                {nodeId === "validate_feasibility" && (
                  <div className="space-y-4">
                    <div className="p-4 rounded-lg bg-[var(--oaria-teal)]/10 text-center">
                      <p className="text-3xl font-bold text-[var(--oaria-teal)]">
                        {((nodeData.overall_score as number || 0) * 100).toFixed(0)}%
                      </p>
                      <p className="text-xs text-[var(--oaria-text-secondary)]">실현가능성 점수</p>
                    </div>
                    {nodeData.concerns && (nodeData.concerns as string[]).length > 0 && (
                      <div>
                        <p className="text-xs text-[var(--oaria-text-secondary)] mb-2">우려 사항</p>
                        <ul className="space-y-1">
                          {(nodeData.concerns as string[]).map((c, i) => (
                            <li key={i} className="text-sm text-orange-600 flex items-start gap-2">
                              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                              {c}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* 승인 게이트 */}
                {nodeId === "approval_gate" && (
                  <div className="space-y-4">
                    <div className={`p-4 rounded-lg text-center ${
                      nodeData.approval_required ? "bg-orange-50" : "bg-green-50"
                    }`}>
                      <p className={`text-lg font-bold ${
                        nodeData.approval_required ? "text-orange-600" : "text-green-600"
                      }`}>
                        {nodeData.approval_required ? "승인 필요" : "승인 불필요"}
                      </p>
                      {nodeData.item_count && (
                        <p className="text-xs text-[var(--oaria-text-secondary)]">
                          {nodeData.item_count}개 항목 검토 필요
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {/* 최종 계획 */}
                {nodeId === "synthesize_plan" && nodeData.final_plan && (
                  <div className="space-y-4">
                    {nodeData.executive_summary && (
                      <div className="p-4 rounded-lg bg-[var(--oaria-teal)]/10 border border-[var(--oaria-teal)]/20">
                        <h4 className="font-[family-name:var(--font-outfit)] font-medium text-[var(--oaria-teal)] mb-2">
                          Executive Summary
                        </h4>
                        <p className="text-sm">{nodeData.executive_summary as string}</p>
                      </div>
                    )}
                    <div className="text-sm leading-relaxed max-h-[300px] overflow-y-auto prose prose-sm max-w-none prose-headings:font-semibold prose-headings:text-[var(--foreground)] prose-p:text-[var(--foreground)] prose-strong:text-[var(--foreground)] prose-li:text-[var(--foreground)] prose-table:text-sm prose-th:bg-[var(--oaria-border)]/50 prose-th:px-2 prose-th:py-1 prose-td:px-2 prose-td:py-1 prose-td:border prose-td:border-[var(--oaria-border)] prose-th:border prose-th:border-[var(--oaria-border)]">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {nodeData.final_plan as string}
                      </ReactMarkdown>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  // ─────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header with Tabs */}
      <div className="bg-[var(--background)]">
        <div className="flex items-center justify-center">
          <div className="flex items-center gap-6">
            <Link
              href="/ask"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
            >
              <MessageSquare size={20} />
              Ask AI
            </Link>
            <Link
              href="/main"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
            >
              <Search size={20} />
              Search Papers
            </Link>
            <Link
              href="/agents"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-[var(--oaria-teal)] text-[var(--oaria-teal)]"
            >
              <Bot size={20} />
              Agents
            </Link>
            <Link
              href="/dashboard"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
            >
              <BarChart3 size={20} />
              Dashboard
            </Link>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto">
        {viewMode === "landing" ? (
          // ─────────────────────────────────────────────────────────────
          // Landing View
          // ─────────────────────────────────────────────────────────────
          <>
            {/* Hero Section */}
            <section className="relative overflow-hidden bg-gradient-to-b from-[var(--oaria-teal)]/5 to-transparent">
              <div className="max-w-5xl mx-auto px-6 py-16 text-center">
                {/* Back to Agents */}
                <div className="mb-6">
                  <Link
                    href="/agents"
                    className="inline-flex items-center gap-1 text-sm text-[var(--oaria-text-secondary)] hover:text-[var(--oaria-teal)] transition-colors"
                  >
                    <ArrowLeft size={16} />
                    AI Agents
                  </Link>
                </div>

                {/* Icon Badge */}
                <div className="mb-6">
                  <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[var(--oaria-teal)]/10 border border-[var(--oaria-teal)]/20">
                    <Sparkles size={16} className="text-[var(--oaria-teal)]" />
                    <span className="font-[family-name:var(--font-dm-sans)] text-sm font-medium text-[var(--oaria-teal)]">
                      AI-Powered Research
                    </span>
                  </div>
                </div>

                {/* Main Title */}
                <h1 className="font-[family-name:var(--font-outfit)] text-4xl md:text-5xl font-bold mb-4 leading-tight">
                  <span className="text-[var(--foreground)]">Study Plan Agent</span>
                </h1>

                {/* Subtitle */}
                <p className="font-[family-name:var(--font-dm-sans)] text-lg text-[var(--oaria-text-secondary)] max-w-2xl mx-auto mb-8 leading-relaxed">
                  가설을 입력하면 AI가 체계적인 실험 설계 계획서를 자동으로 생성합니다.
                  <br />
                  선행 연구 검색부터 실험 설계까지, 연구 계획의 전 과정을 지원합니다.
                </p>

                {/* CTA Buttons */}
                <div className="flex items-center justify-center gap-4">
                  <button
                    onClick={() => setViewMode("generate")}
                    className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-[var(--oaria-teal)] text-white font-[family-name:var(--font-dm-sans)] font-medium hover:bg-[#0B7A70] transition-colors shadow-lg shadow-[var(--oaria-teal)]/20"
                  >
                    <Beaker size={20} />
                    실험 계획 시작하기
                  </button>
                  <Link
                    href="/agents/study-plan/history"
                    className="inline-flex items-center gap-2 px-6 py-3 rounded-xl border-2 border-[var(--oaria-border-strong)] bg-[var(--background)] text-[var(--foreground)] font-[family-name:var(--font-dm-sans)] font-medium hover:border-[var(--oaria-teal)] hover:text-[var(--oaria-teal)] transition-colors"
                  >
                    <History size={20} />
                    내 기록 보기
                  </Link>
                </div>
              </div>
            </section>

            {/* Features Section */}
            <section className="max-w-5xl mx-auto px-6 py-12">
              <div className="text-center mb-10">
                <h2 className="font-[family-name:var(--font-outfit)] text-2xl font-semibold mb-2">
                  주요 기능
                </h2>
                <p className="font-[family-name:var(--font-dm-sans)] text-[var(--oaria-text-secondary)]">
                  연구자의 실험 설계 과정을 AI가 체계적으로 지원합니다
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {features.map((feature, index) => (
                  <div
                    key={index}
                    className="p-6 rounded-xl border-2 border-[var(--oaria-border)] bg-[var(--background)] hover:border-[var(--oaria-teal)]/30 transition-colors"
                  >
                    <div className="w-12 h-12 rounded-xl bg-[var(--oaria-teal)]/10 flex items-center justify-center mb-4">
                      {feature.icon}
                    </div>
                    <h3 className="font-[family-name:var(--font-outfit)] text-lg font-semibold mb-2">
                      {feature.title}
                    </h3>
                    <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] leading-relaxed">
                      {feature.description}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            {/* FAQ Section */}
            <section className="max-w-3xl mx-auto px-6 py-12 pb-16">
              <div className="text-center mb-10">
                <h2 className="font-[family-name:var(--font-outfit)] text-2xl font-semibold mb-2">
                  자주 묻는 질문
                </h2>
                <p className="font-[family-name:var(--font-dm-sans)] text-[var(--oaria-text-secondary)]">
                  Study Plan Agent에 대해 궁금한 점을 확인하세요
                </p>
              </div>

              <div className="space-y-3">
                {faqs.map((faq, index) => (
                  <div
                    key={index}
                    className="border-2 border-[var(--oaria-border)] rounded-xl overflow-hidden"
                  >
                    <button
                      type="button"
                      onClick={() => toggleFaq(index)}
                      className="w-full flex items-center justify-between p-4 text-left bg-[var(--background)] hover:bg-[var(--oaria-teal)]/5 transition-colors"
                    >
                      <span className="font-[family-name:var(--font-dm-sans)] font-medium pr-4">
                        {faq.question}
                      </span>
                      {openFaqIndex === index ? (
                        <ChevronUp size={20} className="text-[var(--oaria-teal)] flex-shrink-0" />
                      ) : (
                        <ChevronDown size={20} className="text-[var(--oaria-text-secondary)] flex-shrink-0" />
                      )}
                    </button>
                    {openFaqIndex === index && (
                      <div className="px-4 pb-4 bg-[var(--background)]">
                        <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] leading-relaxed">
                          {faq.answer}
                        </p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </section>
          </>
        ) : (
          // ─────────────────────────────────────────────────────────────
          // Generate View
          // ─────────────────────────────────────────────────────────────
          <div className="flex h-full">
            {/* 왼쪽: 메인 콘텐츠 */}
            <div className={`flex-1 overflow-y-auto transition-all ${showActivitySidebar && (isLoading || state.status !== "idle") ? "" : ""}`}>
              <div className="max-w-3xl mx-auto px-6 py-8">
                {/* Back & Header */}
                <div className="flex items-center gap-4 mb-8">
                  <button
                    onClick={() => {
                      if (!isLoading) {
                        setViewMode("landing");
                        setHypothesis("");
                        setResearchContext("");
                        setNodes(createInitialNodes());
                        setState({ status: "idle", nodeDetails: {} });
                        setActivityLogs([]);
                      }
                    }}
                    className="p-2 rounded-lg hover:bg-[var(--oaria-border)] transition-colors"
                    disabled={isLoading}
                  >
                    <ArrowLeft size={20} />
                  </button>
                  <div className="w-12 h-12 rounded-xl bg-green-500 flex items-center justify-center text-white">
                    <Beaker size={24} />
                  </div>
                  <div>
                    <h1 className="font-[family-name:var(--font-outfit)] text-xl font-semibold">
                      Study Plan Agent
                    </h1>
                    <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)]">
                      가설 기반 후속 실험 설계 자동화
                    </p>
                  </div>
                </div>

            {/* Input Form */}
            <div className="bg-[var(--background)] border-2 border-[var(--oaria-border-strong)] rounded-2xl p-6 mb-8">
              <form onSubmit={handleSubmit}>
                {/* 에이전트 버전 선택 */}
                <div className="mb-6">
                  <label className="block font-[family-name:var(--font-outfit)] text-sm font-medium mb-2">
                    에이전트 버전
                  </label>
                  <div className="flex gap-3">
                    <button
                      type="button"
                      onClick={() => setAgentVersion("v3")}
                      disabled={isLoading}
                      className={`flex-1 px-4 py-3 rounded-xl border-2 transition-all ${
                        agentVersion === "v3"
                          ? "border-[var(--oaria-teal)] bg-[var(--oaria-teal)]/10 text-[var(--oaria-teal)]"
                          : "border-[var(--oaria-border)] hover:border-[var(--oaria-teal)]/50"
                      } disabled:opacity-50`}
                    >
                      <div className="font-semibold mb-1">v3 Workflow</div>
                      <div className="text-xs text-[var(--oaria-text-secondary)]">
                        고정 파이프라인 + Decision Points
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => setAgentVersion("v4")}
                      disabled={isLoading}
                      className={`flex-1 px-4 py-3 rounded-xl border-2 transition-all ${
                        agentVersion === "v4"
                          ? "border-[var(--oaria-teal)] bg-[var(--oaria-teal)]/10 text-[var(--oaria-teal)]"
                          : "border-[var(--oaria-border)] hover:border-[var(--oaria-teal)]/50"
                      } disabled:opacity-50`}
                    >
                      <div className="font-semibold mb-1">v4 ReAct</div>
                      <div className="text-xs text-[var(--oaria-text-secondary)]">
                        LLM 자율 판단 에이전트
                      </div>
                    </button>
                  </div>
                </div>

                {/* 가설 입력 */}
                <div className="mb-4">
                  <label className="block font-[family-name:var(--font-outfit)] text-sm font-medium mb-2">
                    검증하고자 하는 가설 *
                  </label>
                  <textarea
                    value={hypothesis}
                    onChange={(e) => setHypothesis(e.target.value)}
                    placeholder="예: EGFR T790M 돌연변이 환자에서 osimertinib 내성 기전으로 MET amplification이 관여한다"
                    rows={3}
                    disabled={isLoading}
                    className="w-full px-4 py-3 rounded-xl border-2 border-[var(--oaria-border)] bg-[var(--background)] font-[family-name:var(--font-dm-sans)] text-base focus:border-[var(--oaria-teal)] focus:ring-2 focus:ring-[var(--oaria-teal)]/20 outline-none transition-all resize-none placeholder:text-[var(--oaria-tagline)] disabled:opacity-50"
                  />
                </div>

                {/* 고급 옵션 토글 */}
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="flex items-center gap-2 text-sm text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] mb-4"
                >
                  {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  고급 옵션
                </button>

                {/* 고급 옵션 */}
                {showAdvanced && (
                  <div className="mb-4 p-4 rounded-xl bg-[var(--oaria-border)]/20 space-y-4">
                    <div>
                      <label className="block font-[family-name:var(--font-outfit)] text-sm font-medium mb-2">
                        연구 맥락 (선택)
                      </label>
                      <input
                        type="text"
                        value={researchContext}
                        onChange={(e) => setResearchContext(e.target.value)}
                        placeholder="예: NSCLC targeted therapy resistance research"
                        disabled={isLoading}
                        className="w-full px-4 py-2 rounded-lg border border-[var(--oaria-border)] bg-[var(--background)] font-[family-name:var(--font-dm-sans)] text-sm focus:border-[var(--oaria-teal)] outline-none transition-all placeholder:text-[var(--oaria-tagline)] disabled:opacity-50"
                      />
                    </div>

                    {/* 백그라운드 모드 토글 */}
                    <div className="flex items-center justify-between">
                      <div>
                        <label className="font-[family-name:var(--font-outfit)] text-sm font-medium">
                          백그라운드 모드
                        </label>
                        <p className="text-xs text-[var(--oaria-text-secondary)]">
                          페이지를 나가도 작업이 계속됩니다
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setUseBackgroundMode(!useBackgroundMode)}
                        disabled={isLoading}
                        className={`relative w-12 h-6 rounded-full transition-colors ${
                          useBackgroundMode
                            ? "bg-[var(--oaria-teal)]"
                            : "bg-[var(--oaria-border)]"
                        } disabled:opacity-50`}
                      >
                        <span
                          className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                            useBackgroundMode ? "translate-x-7" : "translate-x-1"
                          }`}
                        />
                      </button>
                    </div>
                  </div>
                )}

                {/* 제출 버튼 */}
                <button
                  type="submit"
                  disabled={!hypothesis.trim() || isLoading}
                  className="w-full py-3 rounded-xl bg-[var(--oaria-teal)] text-white font-[family-name:var(--font-dm-sans)] font-medium hover:bg-[var(--oaria-light-teal)] disabled:bg-[var(--oaria-border)] disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                >
                  {isLoading ? (
                    <>
                      <Loader2 size={20} className="animate-spin" />
                      실험 계획 생성 중...
                    </>
                  ) : (
                    <>
                      <FlaskConical size={20} />
                      실험 계획 생성
                    </>
                  )}
                </button>
              </form>
            </div>

            {/* Progress Indicator */}
            {(isLoading || state.status === "completed" || state.status === "error") && (
              <div className="mb-8">
                <h3 className="font-[family-name:var(--font-outfit)] text-lg font-semibold mb-4">
                  진행 상태
                </h3>
                <p className="text-xs text-[var(--oaria-text-secondary)] mb-4">
                  각 카드를 클릭하면 상세 내용을 볼 수 있습니다
                </p>
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
                  {nodes.map((node) => (
                    <button
                      key={node.id}
                      onClick={() => node.status !== "pending" && setSelectedNode(node.id)}
                      disabled={node.status === "pending"}
                      className={`p-3 rounded-lg border-2 transition-all text-left ${
                        node.status === "completed"
                          ? "border-green-500 bg-green-50 hover:bg-green-100 cursor-pointer"
                          : node.status === "active"
                          ? "border-[var(--oaria-teal)] bg-[var(--oaria-teal)]/10 animate-pulse cursor-wait"
                          : "border-[var(--oaria-border)] bg-[var(--background)] cursor-not-allowed opacity-50"
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        {node.status === "completed" ? (
                          <CheckCircle2 size={16} className="text-green-500" />
                        ) : node.status === "active" ? (
                          <Loader2 size={16} className="text-[var(--oaria-teal)] animate-spin" />
                        ) : (
                          <Circle size={16} className="text-[var(--oaria-border)]" />
                        )}
                      </div>
                      <span className="font-[family-name:var(--font-dm-sans)] text-xs text-[var(--oaria-text-secondary)]">
                        {node.label}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Error Display */}
            {state.error && (
              <div className="mb-8 p-4 rounded-xl bg-red-50 border border-red-200">
                <div className="flex items-center gap-2 text-red-600">
                  <AlertTriangle size={20} />
                  <span className="font-medium">오류 발생</span>
                </div>
                <p className="mt-2 text-sm text-red-700">{state.error}</p>
              </div>
            )}

            {/* Final Plan Result */}
            {state.nodeDetails.synthesize_plan?.final_plan && (
              <div ref={resultRef} className="space-y-6">
                <div className="bg-[var(--background)] border-2 border-[var(--oaria-border-strong)] rounded-2xl overflow-hidden">
                  <button
                    onClick={() => toggleSection("plan")}
                    className="w-full px-6 py-4 flex items-center justify-between bg-[var(--oaria-teal)]/10 hover:bg-[var(--oaria-teal)]/20 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <Beaker size={20} className="text-[var(--oaria-teal)]" />
                      <span className="font-[family-name:var(--font-outfit)] font-semibold text-[var(--oaria-teal)]">
                        최종 실험 계획서
                      </span>
                    </div>
                    {expandedSections.has("plan") ? (
                      <ChevronUp size={20} className="text-[var(--oaria-teal)]" />
                    ) : (
                      <ChevronDown size={20} className="text-[var(--oaria-teal)]" />
                    )}
                  </button>
                  {expandedSections.has("plan") && (
                    <div className="px-6 py-4">
                      {state.nodeDetails.synthesize_plan?.executive_summary && (
                        <div className="mb-4 p-4 rounded-lg bg-[var(--oaria-teal)]/5 border border-[var(--oaria-teal)]/20">
                          <h4 className="font-[family-name:var(--font-outfit)] font-medium text-[var(--oaria-teal)] mb-2">
                            Executive Summary
                          </h4>
                          <p className="font-[family-name:var(--font-dm-sans)] text-sm">
                            {state.nodeDetails.synthesize_plan.executive_summary}
                          </p>
                        </div>
                      )}
                      <div className="font-[family-name:var(--font-dm-sans)] text-sm leading-relaxed prose prose-sm max-w-none prose-headings:font-semibold prose-headings:text-[var(--foreground)] prose-p:text-[var(--foreground)] prose-strong:text-[var(--foreground)] prose-li:text-[var(--foreground)] prose-table:text-sm prose-th:bg-[var(--oaria-border)]/50 prose-th:px-3 prose-th:py-2 prose-td:px-3 prose-td:py-2 prose-td:border prose-td:border-[var(--oaria-border)] prose-th:border prose-th:border-[var(--oaria-border)]">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {state.nodeDetails.synthesize_plan.final_plan}
                        </ReactMarkdown>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
              </div>
            </div>

            {/* 오른쪽: 활동 사이드바 */}
            {showActivitySidebar && (isLoading || state.status !== "idle") && (
              <div className="w-80 border-l border-[var(--oaria-border)] bg-[var(--background)] flex flex-col">
                {/* 사이드바 헤더 */}
                <div className="px-4 py-3 border-b border-[var(--oaria-border)] flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-[family-name:var(--font-outfit)] font-semibold text-sm">활동</span>
                    {isLoading && (
                      <span className="text-xs text-[var(--oaria-text-secondary)]">· {elapsedTime}s</span>
                    )}
                  </div>
                  <button
                    onClick={() => setShowActivitySidebar(false)}
                    className="p-1 hover:bg-[var(--oaria-border)] rounded transition-colors"
                  >
                    <X size={16} />
                  </button>
                </div>

                {/* 활동 로그 목록 */}
                <div className="flex-1 overflow-y-auto p-4 space-y-3">
                  {activityLogs.map((log) => (
                    <div key={log.id} className="flex gap-3">
                      {/* 아이콘 */}
                      <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 ${
                        log.type === "thinking" ? "bg-purple-100 text-purple-600" :
                        log.type === "action" ? "bg-blue-100 text-blue-600" :
                        log.type === "result" ? "bg-green-100 text-green-600" :
                        "bg-red-100 text-red-600"
                      }`}>
                        {log.type === "thinking" && <Brain size={12} />}
                        {log.type === "action" && <Loader2 size={12} className={isLoading && log === activityLogs[activityLogs.length - 1] ? "animate-spin" : ""} />}
                        {log.type === "result" && <CheckCircle2 size={12} />}
                        {log.type === "error" && <AlertTriangle size={12} />}
                      </div>

                      {/* 내용 */}
                      <div className="flex-1 min-w-0">
                        <p className="font-[family-name:var(--font-dm-sans)] text-sm font-medium leading-tight">
                          {log.title}
                        </p>
                        {log.description && (
                          <p className="font-[family-name:var(--font-dm-sans)] text-xs text-[var(--oaria-text-secondary)] mt-0.5 leading-relaxed">
                            {log.description}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}

                  {/* 로딩 중일 때 현재 진행 표시 */}
                  {isLoading && (
                    <div className="flex gap-3 animate-pulse">
                      <div className="w-6 h-6 rounded-full bg-[var(--oaria-teal)]/20 flex items-center justify-center flex-shrink-0">
                        <Loader2 size={12} className="text-[var(--oaria-teal)] animate-spin" />
                      </div>
                      <div className="flex-1">
                        <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-teal)]">
                          처리 중...
                        </p>
                      </div>
                    </div>
                  )}

                  <div ref={activityEndRef} />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Node Detail Modal */}
      {selectedNode && renderNodeDetail(selectedNode)}

      {/* Approval Modal */}
      <ApprovalModal
        isOpen={showApprovalModal}
        onClose={() => setShowApprovalModal(false)}
        onApprove={handleApprove}
        jobName={hypothesis.trim().substring(0, 100)}
        gateId={approvalData?.approval_gate_id as string | undefined}
        choices={approvalData?.approval_choices as Array<{
          choice_id: string;
          label: string;
          description: string;
          estimated_cost?: string;
          estimated_timeline?: string;
        }> | undefined}
        isLoading={jobStatus === "running"}
      />
    </div>
  );
}
