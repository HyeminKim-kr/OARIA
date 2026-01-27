"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Search,
  Bot,
  MessageSquare,
  Beaker,
  BarChart3,
  ArrowLeft,
  AlertTriangle,
  X,
  History,
} from "lucide-react";
import { useJobStream } from "@/hooks";
// ApprovalModal 제거됨 - 승인 게이트가 더 이상 작업을 멈추지 않음
import { useNotifications } from "@/contexts/NotificationContext";
import { agentJobsApi, ThinkingHistoryEntry } from "@/lib/api";

// Local imports
import { createInitialNodes, v4EventNodeMap, v4EventTitles } from "./constants";
import type {
  NodeProgress,
  NodeStatus,
  StudyPlanState,
  StudyPlanSSEEvent,
} from "./types";
import {
  LandingSection,
  HypothesisForm,
  NodeDetailModal,
  ResultsPanel,
  ExtendedThinkingPanel,
} from "./components";
import type { ThinkingStep } from "./components";

// ─────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────

const STORAGE_KEY = "study-plan-view-mode";
const STORAGE_JOB_KEY = "study-plan-job-id";

// ─────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────

export default function StudyPlanPage() {
  // View mode: "landing" or "generate" - 초기값은 sessionStorage에서 복원
  const [viewMode, setViewMode] = useState<"landing" | "generate">("landing");
  const [isHydrated, setIsHydrated] = useState(false);

  // Form state
  const [hypothesis, setHypothesis] = useState("");
  const [researchContext, setResearchContext] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [nodes, setNodes] = useState<NodeProgress[]>(createInitialNodes());
  const [state, setState] = useState<StudyPlanState>({
    status: "idle",
    nodeDetails: {},
  });
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const [elapsedTime, setElapsedTime] = useState(0);

  // 결과 저장 state
  const [resultData, setResultData] = useState<{
    planA?: string;
    planB?: string;
    experimentCount?: number;
    totalDuration?: number;
  }>({});

  // v4 사고 과정 state
  const [thinkingSteps, setThinkingSteps] = useState<ThinkingStep[]>([]);
  const [currentThinkingStep, setCurrentThinkingStep] = useState<ThinkingStep | null>(null);
  const [currentIteration, setCurrentIteration] = useState(0);

  // 승인 모달 제거됨 - 대신 알림으로 처리
  const { addToast } = useNotifications();

  // useJobStream hook for background job mode
  const {
    jobId,
    startJob,
    cancel: cancelJob,
    reset: resetJob,
    // v4/LangGraph specific state
    currentTokenUsage,
    cumulativeTokenUsage,
    tokenHistory,
    recoveryOptions,
    selectRecovery,
  } = useJobStream({
    onEvent: (event) => {
      // v4 ReAct 이벤트 처리
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const v4Data = event as any;
      const eventType = v4Data.event;

      if (eventType && v4EventTitles[eventType]) {
        const nodeId = v4EventNodeMap[eventType];
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

        // ThinkingStep 생성 및 업데이트
        const thinkingStep: ThinkingStep = {
          id: `step-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
          type: eventType as ThinkingStep["type"],
          timestamp: new Date(),
          iteration: v4Data.iteration,
          // thinking - Extended Thinking format
          title: v4Data.title,
          bullets: v4Data.bullets,
          message: v4Data.message || v4Data.thought,
          status: v4Data.status,
          // acting
          action: v4Data.action,
          confidence: v4Data.confidence,
          parameters: v4Data.action_input || v4Data.parameters,
          thought: v4Data.thought,
          // observation
          success: v4Data.success,
          result: v4Data.result,
          duration_ms: v4Data.duration_ms,
          // observation - Detailed result for UI display
          observationDetails: v4Data.details,
          // observation - Sources (Perplexity-style cards)
          sources: v4Data.sources,
          summary: v4Data.summary,
          // goal_check
          achieved: v4Data.achieved,
          missing: v4Data.missing,
          // recovery
          error: v4Data.error,
          strategy: v4Data.strategy,
          // started
          hypothesis: v4Data.hypothesis,
        };

        // 현재 스텝 업데이트
        setCurrentThinkingStep(thinkingStep);

        // 반복 횟수 업데이트
        if (v4Data.iteration) {
          setCurrentIteration(v4Data.iteration);
        }

        // 히스토리에 추가 (thinking, acting, observation, goal_check, recovery)
        if (["thinking", "acting", "observation", "goal_check", "recovery"].includes(eventType)) {
          setThinkingSteps((prev) => [...prev, thinkingStep]);
        }
      }
    },
    onApprovalRequired: () => {
      // 승인 게이트 - toast로 알림
      addToast({
        type: "info",
        title: "주의사항 확인",
        message: "고비용 실험 또는 윤리 심의가 필요한 항목이 포함되어 있습니다.",
        duration: 5000,
      });
    },
    onCompleted: (event) => {
      setNodes((prev) =>
        prev.map((n) => ({ ...n, status: "completed" as NodeStatus }))
      );

      const sseEvent = event as StudyPlanSSEEvent;

      // Update state with result
      const planContent = sseEvent.final_plan || sseEvent.plan_a || "";
      setState({
        status: "completed",
        nodeDetails: {
          synthesize_plan: {
            final_plan: planContent,
            executive_summary: sseEvent.executive_summary || "",
          },
        },
      });

      // 결과 데이터 저장 (ResultsPanel용)
      setResultData({
        planA: sseEvent.plan_a,
        planB: sseEvent.plan_b,
        experimentCount: sseEvent.experiment_count || 0,
        totalDuration: sseEvent.total_duration_ms || 0,
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

  // DB에서 thinking_history 복원하는 함수
  const restoreThinkingHistory = useCallback(async (jobIdToRestore: string) => {
    try {
      console.log("[StudyPlanPage] Restoring thinking history for job:", jobIdToRestore);
      const response = await agentJobsApi.get(jobIdToRestore);
      const jobDetail = response.data;

      // thinking_history가 있으면 복원
      if (jobDetail.thinking_history && jobDetail.thinking_history.length > 0) {
        const restoredSteps: ThinkingStep[] = jobDetail.thinking_history.map(
          (entry: ThinkingHistoryEntry, index: number) => ({
            id: `restored-${index}-${entry.iteration}`,
            type: entry.action ? "acting" : "thinking",
            timestamp: entry.timestamp ? new Date(entry.timestamp) : new Date(),
            iteration: entry.iteration,
            title: entry.title,
            bullets: entry.bullets || [],
            message: entry.message,
            action: entry.action,
            parameters: entry.parameters,
            confidence: entry.confidence,
            success: entry.observation?.success,
            summary: entry.observation?.summary,
            observationDetails: entry.observation?.details,
            status: entry.status || "completed",
          })
        );

        setThinkingSteps(restoredSteps);
        setCurrentIteration(restoredSteps.length > 0
          ? restoredSteps[restoredSteps.length - 1].iteration || 0
          : 0
        );
        console.log(`[StudyPlanPage] Restored ${restoredSteps.length} thinking steps`);
      }

      // 작업이 완료되었으면 결과도 복원
      if (jobDetail.status === "completed" && jobDetail.result_data) {
        setResultData({
          planA: jobDetail.result_data.plan_a as string | undefined,
          planB: jobDetail.result_data.plan_b as string | undefined,
          experimentCount: jobDetail.experiment_count || 0,
          totalDuration: jobDetail.total_duration_ms || 0,
        });
        setState({
          status: "completed",
          nodeDetails: {
            synthesize_plan: {
              final_plan: jobDetail.result_data.plan_a || "",
              executive_summary: jobDetail.executive_summary || "",
            },
          },
        });
        setNodes((prev) =>
          prev.map((n) => ({ ...n, status: "completed" as NodeStatus }))
        );
      } else if (jobDetail.status === "running") {
        // 아직 실행 중이면 로딩 상태로
        setIsLoading(true);
        setState({ status: "generating", nodeDetails: {} });
      }
    } catch (error) {
      console.error("[StudyPlanPage] Failed to restore thinking history:", error);
      // 404 등 복원 실패 시 sessionStorage 완전 클리어 및 상태 리셋
      sessionStorage.removeItem(STORAGE_JOB_KEY);
      sessionStorage.removeItem(STORAGE_KEY);
      // 상태 초기화
      setThinkingSteps([]);
      setCurrentIteration(0);
      setResultData({});
      setState({ status: "idle", nodeDetails: {} });
      setViewMode("landing");
    }
  }, []);

  // 마운트 시 sessionStorage에서 viewMode 복원 및 thinking_history 복원
  useEffect(() => {
    const savedViewMode = sessionStorage.getItem(STORAGE_KEY);
    const savedJobId = sessionStorage.getItem(STORAGE_JOB_KEY);

    // 저장된 viewMode가 있고 generate였다면 복원
    if (savedViewMode === "generate" || savedJobId) {
      setViewMode("generate");

      // savedJobId가 있으면 DB에서 thinking_history 복원
      if (savedJobId) {
        restoreThinkingHistory(savedJobId);
      }
    }
    setIsHydrated(true);
  }, [restoreThinkingHistory]);

  // viewMode 변경 시 sessionStorage에 저장
  const updateViewMode = useCallback((mode: "landing" | "generate") => {
    setViewMode(mode);
    if (mode === "generate") {
      sessionStorage.setItem(STORAGE_KEY, mode);
    } else {
      sessionStorage.removeItem(STORAGE_KEY);
      sessionStorage.removeItem(STORAGE_JOB_KEY);
    }
  }, []);

  // jobId 변경 시 sessionStorage에 저장
  useEffect(() => {
    if (jobId) {
      sessionStorage.setItem(STORAGE_JOB_KEY, jobId);
    }
  }, [jobId]);

  const toggleFaq = (index: number) => {
    setOpenFaqIndex(openFaqIndex === index ? null : index);
  };

  // 승인 처리 핸들러 제거됨 - 승인 게이트가 더 이상 작업을 멈추지 않음

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!hypothesis.trim() || isLoading) return;

    // 이전 작업과 완전히 분리: sessionStorage 클리어
    sessionStorage.removeItem(STORAGE_JOB_KEY);

    setIsLoading(true);
    setNodes(createInitialNodes());
    setState({ status: "generating", nodeDetails: {} });
    setSelectedNode(null);
    // v4 사고 과정 및 결과 초기화
    setThinkingSteps([]);
    setCurrentThinkingStep(null);
    setCurrentIteration(0);
    setResultData({});

    try {
      const agentType =
        "study_plan_v4";
      await startJob(agentType, {
        hypothesis: hypothesis.trim(),
        research_context: researchContext.trim() || undefined,
        preferred_experiment_types: ["in_vitro", "in_vivo"],
      });
    } catch (error) {
      console.error("Failed to start job:", error);
      setState((prev) => ({
        ...prev,
        status: "error",
        error: error instanceof Error ? error.message : "작업 시작 실패",
      }));
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (state.nodeDetails.synthesize_plan?.final_plan && resultRef.current) {
      resultRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [state.nodeDetails.synthesize_plan?.final_plan]);

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
        {!isHydrated ? (
          // Hydration 완료 전 로딩 상태 표시
          <div className="flex items-center justify-center h-full">
            <div className="flex items-center gap-2 text-[var(--oaria-text-secondary)]">
              <div className="w-5 h-5 border-2 border-[var(--oaria-teal)] border-t-transparent rounded-full animate-spin" />
              <span>로딩 중...</span>
            </div>
          </div>
        ) : viewMode === "landing" ? (
          <LandingSection
            onStartGenerate={() => updateViewMode("generate")}
            openFaqIndex={openFaqIndex}
            onToggleFaq={toggleFaq}
          />
        ) : (
          // ─────────────────────────────────────────────────────────────
          // Generate View
          // ─────────────────────────────────────────────────────────────
          <div className="flex h-full">
            {/* 왼쪽: 메인 콘텐츠 */}
            <div className="flex-1 overflow-y-auto">
              <div className="max-w-5xl mx-auto px-6 py-8">
                {/* Back & Header */}
                <div className="flex items-center justify-between mb-8">
                  <div className="flex items-center gap-4">
                    <button
                      onClick={async () => {
                        if (isLoading && jobId) {
                          // 실행 중일 때: 확인 후 취소하고 돌아가기
                          if (confirm("실행 중인 작업을 중단하시겠습니까?")) {
                            try {
                              await cancelJob();
                            } catch (e) {
                              console.error("Failed to cancel job:", e);
                            }
                            setIsLoading(false);
                            updateViewMode("landing");
                            setHypothesis("");
                            setResearchContext("");
                            setNodes(createInitialNodes());
                            setState({ status: "idle", nodeDetails: {} });
                            setThinkingSteps([]);
                            setCurrentThinkingStep(null);
                            setCurrentIteration(0);
                            setResultData({});
                            resetJob();
                          }
                        } else {
                          // jobId 없거나 로딩 중 아닐 때: 그냥 돌아가기
                          if (isLoading) setIsLoading(false);
                          updateViewMode("landing");
                          setHypothesis("");
                          setResearchContext("");
                          setNodes(createInitialNodes());
                          setState({ status: "idle", nodeDetails: {} });
                          setThinkingSteps([]);
                          setCurrentThinkingStep(null);
                          setCurrentIteration(0);
                          setResultData({});
                          resetJob();
                        }
                      }}
                      className="p-2 rounded-lg hover:bg-[var(--oaria-border)] transition-colors"
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

                  {/* 오른쪽: 중단 버튼 & 히스토리 링크 */}
                  <div className="flex items-center gap-3">
                    {isLoading && jobId && (
                      <button
                        onClick={async () => {
                          if (confirm("실행 중인 작업을 중단하시겠습니까?")) {
                            try {
                              await cancelJob();
                              addToast({
                                type: "info",
                                title: "작업 중단됨",
                                message: "작업이 중단되었습니다.",
                              });
                            } catch (e) {
                              console.error("Failed to cancel job:", e);
                            }
                            setIsLoading(false);
                            setState({ status: "idle", nodeDetails: {} });
                          }
                        }}
                        className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-lg transition-colors"
                      >
                        <X size={16} />
                        중단
                      </button>
                    )}
                    <Link
                      href="/agents/study-plan/history"
                      className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-green-600 bg-green-50 hover:bg-green-100 rounded-lg transition-colors"
                    >
                      <History size={16} />
                      기록
                    </Link>
                  </div>
                </div>

                {/* Input Form */}
                <HypothesisForm
                  hypothesis={hypothesis}
                  onHypothesisChange={setHypothesis}
                  researchContext={researchContext}
                  onResearchContextChange={setResearchContext}
                  showAdvanced={showAdvanced}
                  onToggleAdvanced={() => setShowAdvanced(!showAdvanced)}
                  isLoading={isLoading}
                  onSubmit={handleSubmit}
                />

                {/* Extended Thinking Panel - Claude 스타일 사고 과정 */}
                {(isLoading || thinkingSteps.length > 0) && (
                  <div className="mb-6">
                    <ExtendedThinkingPanel
                      steps={thinkingSteps}
                      currentStep={currentThinkingStep}
                      isLoading={isLoading}
                      isCompleted={state.status === "completed"}
                      elapsedTime={elapsedTime}
                    />
                  </div>
                )}

                {/* Progress Timeline 제거됨 - ThinkingPanel로 통합 */}

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
                  <div ref={resultRef}>
                    <ResultsPanel
                      finalPlan={state.nodeDetails.synthesize_plan.final_plan}
                      executiveSummary={state.nodeDetails.synthesize_plan.executive_summary}
                      planA={resultData.planA}
                      planB={resultData.planB}
                      experimentCount={resultData.experimentCount}
                      totalDuration={resultData.totalDuration}
                      nodeDetails={state.nodeDetails as Record<string, unknown>}
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Node Detail Modal */}
      {selectedNode && (
        <NodeDetailModal
          nodeId={selectedNode}
          nodes={nodes}
          nodeDetails={state.nodeDetails}
          onClose={() => setSelectedNode(null)}
        />
      )}

      {/* 승인 모달 제거됨 - 승인 게이트가 더 이상 작업을 멈추지 않음 */}
    </div>
  );
}
