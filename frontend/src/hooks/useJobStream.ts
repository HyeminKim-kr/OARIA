"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { agentJobsApi, AgentJobResponse, fetchWithAuth } from "@/lib/api";

export type JobStreamStatus =
  | "idle"
  | "connecting"
  | "running"
  | "waiting_approval"
  | "completed"
  | "failed"
  | "cancelled";

// Token usage info from v4 agent
export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost?: number;
}

// Recovery option from v4 agent
export interface RecoveryOption {
  id: string;
  label: string;
  description: string;
  risk_level: "low" | "medium" | "high";
  estimated_time?: string;
}

export interface JobStreamEvent {
  event: string;
  node?: string;
  detail?: string;
  progress_percent?: number;
  current_step?: string;
  // Approval related
  approval_required?: boolean;
  approval_gate_id?: string;
  approval_choices?: Array<{
    choice_id: string;
    label: string;
    description: string;
    estimated_cost?: string;
    estimated_timeline?: string;
  }>;
  // Result related
  success?: boolean;
  final_plan?: string;
  executive_summary?: string;
  experiment_count?: number;
  plan_a?: string;
  plan_b?: string;
  dp3_decision?: string;
  total_duration_ms?: number;
  // Error related
  error?: string;
  message?: string;
  // v4/LangGraph specific
  iteration?: number;
  timestamp?: string;
  thought?: string;
  action?: string;
  parameters?: Record<string, unknown>;
  confidence?: number;
  duration_ms?: number;
  token_usage?: TokenUsage;
  cumulative_tokens?: TokenUsage;
  quality_score?: number;
  goal_achieved?: boolean;
  goals_missing?: string[];
  recovery_options?: RecoveryOption[];
  is_terminal?: boolean;
  // Node-specific data
  [key: string]: unknown;
}

interface UseJobStreamOptions {
  onEvent?: (event: JobStreamEvent) => void;
  onApprovalRequired?: (event: JobStreamEvent) => void;
  onCompleted?: (event: JobStreamEvent) => void;
  onError?: (error: string) => void;
  // v4/LangGraph specific callbacks
  onTokenUpdate?: (current: TokenUsage | null, cumulative: TokenUsage | null) => void;
  onRecoveryRequired?: (options: RecoveryOption[], error: string, action: string) => void;
  onThinkingStep?: (event: JobStreamEvent) => void;
}

interface UseJobStreamReturn {
  jobId: string | null;
  status: JobStreamStatus;
  progress: number;
  currentStep: string | null;
  error: string | null;
  result: JobStreamEvent | null;
  approvalData: JobStreamEvent | null;
  // v4/LangGraph specific
  currentTokenUsage: TokenUsage | null;
  cumulativeTokenUsage: TokenUsage | null;
  tokenHistory: TokenUsage[];
  recoveryOptions: RecoveryOption[] | null;
  iteration: number;
  // Actions
  startJob: (agentType: string, inputData: Record<string, unknown>, config?: Record<string, unknown>) => Promise<string>;
  approve: (decision: Record<string, unknown>) => Promise<void>;
  cancel: () => Promise<void>;
  retry: () => Promise<void>;
  reset: () => void;
  selectRecovery: (optionId: string) => Promise<void>;
}

export function useJobStream(options: UseJobStreamOptions = {}): UseJobStreamReturn {
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStreamStatus>("idle");
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<JobStreamEvent | null>(null);
  const [approvalData, setApprovalData] = useState<JobStreamEvent | null>(null);

  // v4/LangGraph specific state
  const [currentTokenUsage, setCurrentTokenUsage] = useState<TokenUsage | null>(null);
  const [cumulativeTokenUsage, setCumulativeTokenUsage] = useState<TokenUsage | null>(null);
  const [tokenHistory, setTokenHistory] = useState<TokenUsage[]>([]);
  const [recoveryOptions, setRecoveryOptions] = useState<RecoveryOption[] | null>(null);
  const [iteration, setIteration] = useState(0);

  const eventSourceRef = useRef<EventSource | null>(null);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  // Connect to SSE stream
  const connectToStream = useCallback(async (id: string) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setStatus("connecting");

    // Get auth token for SSE
    const token = localStorage.getItem("access_token");
    const streamUrl = `${agentJobsApi.streamUrl(id)}${token ? `?token=${token}` : ""}`;

    const eventSource = new EventSource(streamUrl);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      console.log("[useJobStream] SSE connected");
      setStatus("running");
    };

    // 공통 이벤트 핸들러
    const handleEvent = (event: MessageEvent) => {
      try {
        // Skip if event.data is undefined or empty
        if (!event.data || event.data === "undefined") {
          console.warn("[useJobStream] Received empty event data, skipping");
          return;
        }

        // SSE event.type을 data.event에 주입 (SSE event: 라인의 값)
        const parsedData = JSON.parse(event.data);
        const data: JobStreamEvent = {
          ...parsedData,
          event: event.type || parsedData.event || "message",
        };
        console.log("[useJobStream] Event received:", data.event, data);

        // Update progress
        if (data.progress_percent !== undefined) {
          setProgress(data.progress_percent);
        }
        if (data.current_step) {
          setCurrentStep(data.current_step);
        }

        // Update iteration
        if (data.iteration !== undefined) {
          setIteration(data.iteration);
        }

        // Handle token usage updates (v4/LangGraph)
        if (data.token_usage) {
          setCurrentTokenUsage(data.token_usage);
          setTokenHistory((prev) => [...prev, data.token_usage!]);
          optionsRef.current.onTokenUpdate?.(data.token_usage, cumulativeTokenUsage);
        }
        if (data.cumulative_tokens) {
          setCumulativeTokenUsage(data.cumulative_tokens);
          optionsRef.current.onTokenUpdate?.(currentTokenUsage, data.cumulative_tokens);
        }

        // Handle recovery events (v4/LangGraph)
        if (data.event === "recovery" && data.recovery_options) {
          setRecoveryOptions(data.recovery_options);
          optionsRef.current.onRecoveryRequired?.(
            data.recovery_options,
            data.error || "Action failed",
            data.action || ""
          );
        }

        // Handle thinking step events (v4/LangGraph)
        const thinkingEvents = ["reasoning", "acting", "observation", "goal_check", "initialization"];
        if (thinkingEvents.includes(data.event)) {
          optionsRef.current.onThinkingStep?.(data);
        }

        // Handle different event types
        if (data.event === "waiting_approval" || data.approval_required) {
          setStatus("waiting_approval");
          setApprovalData(data);
          optionsRef.current.onApprovalRequired?.(data);
        } else if (data.event === "completed" || data.event === "completion") {
          // Only treat as completion when event type is explicitly "completed" or "completion"
          // Do NOT use data.success alone - observation events also have success field
          setStatus("completed");
          setResult(data);
          eventSource.close();
          optionsRef.current.onCompleted?.(data);
        } else if (data.event === "failed" || data.event === "error" || data.error) {
          setStatus("failed");
          setError(data.error || data.message || "Job failed");
          eventSource.close();
          optionsRef.current.onError?.(data.error || data.message || "Job failed");
        } else if (data.event === "cancelled") {
          setStatus("cancelled");
          eventSource.close();
        }

        // Call generic event handler
        optionsRef.current.onEvent?.(data);
      } catch (e) {
        console.error("[useJobStream] Parse error:", e, event.data);
      }
    };

    // 모든 named events 리스너 등록 (SSE는 event type별로 리스너 필요)
    const eventTypes = [
      "status",
      "progress",
      "step_complete",
      "hypothesis",
      "tests",
      "studies",
      "search_expanding",
      "evidence",
      "methodologies",
      "experiments",
      "critique",
      "revision",
      "measurements",
      "feasibility",
      "waiting_approval",
      "approval_required",
      "completed",
      "failed",
      "cancelled",
      "heartbeat",
      // v4/LangGraph events
      "thinking",
      "acting",
      "observation",
      "recovery",
      "goal_check",
      "reasoning",
      "initialization",
      "completion",
      "result",
      "error",
    ];

    eventTypes.forEach((eventType) => {
      eventSource.addEventListener(eventType, handleEvent);
    });

    // 기본 message 핸들러 (event type 없는 경우)
    eventSource.onmessage = handleEvent;

    eventSource.onerror = (e) => {
      console.error("[useJobStream] SSE error:", e);
      setStatus("failed");
      setError("Connection lost");
      eventSource.close();
    };
  }, []);

  // Start a new job
  const startJob = useCallback(async (
    agentType: string,
    inputData: Record<string, unknown>,
    config?: Record<string, unknown>
  ): Promise<string> => {
    setError(null);
    setResult(null);
    setApprovalData(null);
    setProgress(0);
    setCurrentStep(null);

    try {
      const response = await agentJobsApi.create({
        agent_type: agentType,
        input_data: inputData,
        config,
        job_name: (inputData.hypothesis as string)?.substring(0, 100),
      });

      const job: AgentJobResponse = response.data;
      setJobId(job.id);

      // Connect to stream
      await connectToStream(job.id);

      return job.id;
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : "Failed to start job";
      setError(errorMessage);
      setStatus("failed");
      throw e;
    }
  }, [connectToStream]);

  // Approve the job
  const approve = useCallback(async (decision: Record<string, unknown>) => {
    if (!jobId) throw new Error("No job to approve");

    try {
      await agentJobsApi.approve(jobId, decision);
      setApprovalData(null);
      setStatus("running");
      // Reconnect to stream to continue receiving updates
      await connectToStream(jobId);
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : "Approval failed";
      setError(errorMessage);
      throw e;
    }
  }, [jobId, connectToStream]);

  // Cancel the job
  const cancel = useCallback(async () => {
    if (!jobId) throw new Error("No job to cancel");

    try {
      await agentJobsApi.cancel(jobId);
      setStatus("cancelled");
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : "Cancel failed";
      setError(errorMessage);
      throw e;
    }
  }, [jobId]);

  // Retry the job
  const retry = useCallback(async () => {
    if (!jobId) throw new Error("No job to retry");

    try {
      setError(null);
      setProgress(0);
      await agentJobsApi.retry(jobId);
      await connectToStream(jobId);
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : "Retry failed";
      setError(errorMessage);
      throw e;
    }
  }, [jobId, connectToStream]);

  // Select recovery option (v4/LangGraph)
  const selectRecovery = useCallback(async (optionId: string) => {
    if (!jobId) throw new Error("No job to recover");

    try {
      // Send recovery selection via approve endpoint with recovery flag
      await agentJobsApi.approve(jobId, {
        recovery_option: optionId,
        is_recovery: true,
      });
      setRecoveryOptions(null);
      setStatus("running");
      // Reconnect to stream to continue receiving updates
      await connectToStream(jobId);
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : "Recovery selection failed";
      setError(errorMessage);
      throw e;
    }
  }, [jobId, connectToStream]);

  // Reset state
  const reset = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    setJobId(null);
    setStatus("idle");
    setProgress(0);
    setCurrentStep(null);
    setError(null);
    setResult(null);
    setApprovalData(null);
    // Reset v4/LangGraph state
    setCurrentTokenUsage(null);
    setCumulativeTokenUsage(null);
    setTokenHistory([]);
    setRecoveryOptions(null);
    setIteration(0);
  }, []);

  return {
    jobId,
    status,
    progress,
    currentStep,
    error,
    result,
    approvalData,
    // v4/LangGraph specific
    currentTokenUsage,
    cumulativeTokenUsage,
    tokenHistory,
    recoveryOptions,
    iteration,
    // Actions
    startJob,
    approve,
    cancel,
    retry,
    reset,
    selectRecovery,
  };
}
