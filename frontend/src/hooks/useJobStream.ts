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
  // Node-specific data
  [key: string]: unknown;
}

interface UseJobStreamOptions {
  onEvent?: (event: JobStreamEvent) => void;
  onApprovalRequired?: (event: JobStreamEvent) => void;
  onCompleted?: (event: JobStreamEvent) => void;
  onError?: (error: string) => void;
}

interface UseJobStreamReturn {
  jobId: string | null;
  status: JobStreamStatus;
  progress: number;
  currentStep: string | null;
  error: string | null;
  result: JobStreamEvent | null;
  approvalData: JobStreamEvent | null;
  startJob: (agentType: string, inputData: Record<string, unknown>, config?: Record<string, unknown>) => Promise<string>;
  approve: (decision: Record<string, unknown>) => Promise<void>;
  cancel: () => Promise<void>;
  retry: () => Promise<void>;
  reset: () => void;
}

export function useJobStream(options: UseJobStreamOptions = {}): UseJobStreamReturn {
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStreamStatus>("idle");
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<JobStreamEvent | null>(null);
  const [approvalData, setApprovalData] = useState<JobStreamEvent | null>(null);

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
      setStatus("running");
    };

    eventSource.onmessage = (event) => {
      try {
        const data: JobStreamEvent = JSON.parse(event.data);

        // Update progress
        if (data.progress_percent !== undefined) {
          setProgress(data.progress_percent);
        }
        if (data.current_step) {
          setCurrentStep(data.current_step);
        }

        // Handle different event types
        if (data.event === "waiting_approval" || data.approval_required) {
          setStatus("waiting_approval");
          setApprovalData(data);
          optionsRef.current.onApprovalRequired?.(data);
        } else if (data.event === "completed" || data.success) {
          setStatus("completed");
          setResult(data);
          eventSource.close();
          optionsRef.current.onCompleted?.(data);
        } else if (data.event === "failed" || data.error) {
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
        console.error("[useJobStream] Parse error:", e);
      }
    };

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
  }, []);

  return {
    jobId,
    status,
    progress,
    currentStep,
    error,
    result,
    approvalData,
    startJob,
    approve,
    cancel,
    retry,
    reset,
  };
}
