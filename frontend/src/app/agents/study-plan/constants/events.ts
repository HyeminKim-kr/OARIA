/**
 * Centralized event types for Study Plan Agent.
 *
 * This is the single source of truth for all event type constants.
 * Must match backend Python definitions in:
 * backend/app/services/agent/study_plan/v4/constants/events.py
 */

/**
 * Agent SSE event types.
 */
export const AgentEventType = {
  // Lifecycle events
  INITIALIZATION: "initialization",
  STARTED: "started",
  COMPLETED: "completed",
  ERROR: "error",

  // Reasoning/Action events
  THINKING: "thinking", // LLM reasoning
  REASONING: "reasoning", // Alias for thinking
  ACTING: "acting", // Action being executed
  OBSERVATION: "observation", // Action result

  // Goal/Recovery events
  GOAL_CHECK: "goal_check",
  RECOVERY: "recovery",
  USER_INPUT_REQUEST: "user_input_request",

  // Result events
  RESULT: "result",
} as const;

export type AgentEventTypeValue =
  (typeof AgentEventType)[keyof typeof AgentEventType];

/**
 * Node/step status values.
 */
export const NodeStatus = {
  PENDING: "pending",
  ACTIVE: "active",
  IN_PROGRESS: "in_progress",
  COMPLETED: "completed",
  ERROR: "error",
} as const;

export type NodeStatusValue = (typeof NodeStatus)[keyof typeof NodeStatus];

/**
 * Agent job status values.
 */
export const JobStatus = {
  PENDING: "pending",
  RUNNING: "running",
  COMPLETED: "completed",
  FAILED: "failed",
  CANCELLED: "cancelled",
} as const;

export type JobStatusValue = (typeof JobStatus)[keyof typeof JobStatus];

/**
 * Helper to check if a string is a valid event type
 */
export function isValidEventType(type: string): type is AgentEventTypeValue {
  return Object.values(AgentEventType).includes(type as AgentEventTypeValue);
}

/**
 * Event types that should be displayed in the thinking panel
 */
export const THINKING_PANEL_EVENTS: AgentEventTypeValue[] = [
  AgentEventType.THINKING,
  AgentEventType.REASONING,
  AgentEventType.ACTING,
  AgentEventType.OBSERVATION,
  AgentEventType.GOAL_CHECK,
  AgentEventType.RECOVERY,
];
