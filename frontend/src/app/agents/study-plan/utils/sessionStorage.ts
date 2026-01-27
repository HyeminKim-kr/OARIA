/**
 * Session Storage Utility for Study Plan Agent
 *
 * Manages saving and loading of thinking sessions to LocalStorage.
 * Allows users to replay past sessions and export them.
 */

import { SavedSession, SessionSnapshot, ThinkingStep, TokenUsage } from "../types";

// ─────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────

const SESSION_STORAGE_KEY = "oaria_study_plan_sessions";
const MAX_SAVED_SESSIONS = 10;

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

interface SerializedSession {
  session: {
    id: string;
    hypothesis: string;
    timestamp: string; // ISO string
    stepCount: number;
    status: "completed" | "interrupted" | "error";
    cumulativeTokens?: number;
    qualityScore?: number;
  };
  steps: Array<{
    id: string;
    type: string;
    timestamp: string; // ISO string
    iteration?: number;
    message?: string;
    action?: string;
    confidence?: number;
    parameters?: Record<string, unknown>;
    success?: boolean;
    result?: string;
    duration_ms?: number;
    achieved?: boolean;
    missing?: string[];
    error?: string;
    strategy?: string;
    hypothesis?: string;
    token_usage?: TokenUsage;
  }>;
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
// Serialization Helpers
// ─────────────────────────────────────────────────────────────

function serializeSnapshot(snapshot: SessionSnapshot): SerializedSession {
  return {
    session: {
      ...snapshot.session,
      timestamp: snapshot.session.timestamp.toISOString(),
    },
    steps: snapshot.steps.map((step) => ({
      ...step,
      timestamp: step.timestamp.toISOString(),
    })),
    tokenHistory: snapshot.tokenHistory,
    metadata: snapshot.metadata,
  };
}

function deserializeSnapshot(data: SerializedSession): SessionSnapshot {
  return {
    session: {
      ...data.session,
      timestamp: new Date(data.session.timestamp),
    },
    steps: data.steps.map((step) => ({
      ...step,
      type: step.type as ThinkingStep["type"],
      timestamp: new Date(step.timestamp),
    })),
    tokenHistory: data.tokenHistory,
    metadata: data.metadata,
  };
}

// ─────────────────────────────────────────────────────────────
// Storage Functions
// ─────────────────────────────────────────────────────────────

/**
 * Save a session snapshot to LocalStorage
 */
export function saveSession(snapshot: SessionSnapshot): void {
  try {
    const sessions = getAllSessions();

    // Add new session at the beginning
    sessions.unshift(snapshot);

    // Limit to max sessions
    if (sessions.length > MAX_SAVED_SESSIONS) {
      sessions.splice(MAX_SAVED_SESSIONS);
    }

    // Serialize and save
    const serialized = sessions.map(serializeSnapshot);
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(serialized));
  } catch (error) {
    console.error("[sessionStorage] Failed to save session:", error);
  }
}

/**
 * Get all saved sessions
 */
export function getAllSessions(): SessionSnapshot[] {
  try {
    const data = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!data) return [];

    const parsed: SerializedSession[] = JSON.parse(data);
    return parsed.map(deserializeSnapshot);
  } catch (error) {
    console.error("[sessionStorage] Failed to load sessions:", error);
    return [];
  }
}

/**
 * Get session summaries (without full step data) for display
 */
export function getSessionSummaries(): SavedSession[] {
  try {
    const sessions = getAllSessions();
    return sessions.map((s) => s.session);
  } catch (error) {
    console.error("[sessionStorage] Failed to get summaries:", error);
    return [];
  }
}

/**
 * Get a specific session by ID
 */
export function getSession(id: string): SessionSnapshot | null {
  try {
    const sessions = getAllSessions();
    return sessions.find((s) => s.session.id === id) || null;
  } catch (error) {
    console.error("[sessionStorage] Failed to get session:", error);
    return null;
  }
}

/**
 * Delete a session by ID
 */
export function deleteSession(id: string): void {
  try {
    const sessions = getAllSessions();
    const filtered = sessions.filter((s) => s.session.id !== id);
    const serialized = filtered.map(serializeSnapshot);
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(serialized));
  } catch (error) {
    console.error("[sessionStorage] Failed to delete session:", error);
  }
}

/**
 * Clear all saved sessions
 */
export function clearAllSessions(): void {
  try {
    localStorage.removeItem(SESSION_STORAGE_KEY);
  } catch (error) {
    console.error("[sessionStorage] Failed to clear sessions:", error);
  }
}

/**
 * Check if storage is available
 */
export function isStorageAvailable(): boolean {
  try {
    const testKey = "__storage_test__";
    localStorage.setItem(testKey, testKey);
    localStorage.removeItem(testKey);
    return true;
  } catch {
    return false;
  }
}

/**
 * Get storage usage info
 */
export function getStorageInfo(): { used: number; available: boolean } {
  try {
    const data = localStorage.getItem(SESSION_STORAGE_KEY);
    return {
      used: data ? new Blob([data]).size : 0,
      available: isStorageAvailable(),
    };
  } catch {
    return { used: 0, available: false };
  }
}

// ─────────────────────────────────────────────────────────────
// Session Creation Helper
// ─────────────────────────────────────────────────────────────

/**
 * Create a new session snapshot from current state
 */
export function createSessionSnapshot(params: {
  hypothesis: string;
  steps: ThinkingStep[];
  tokenHistory: TokenUsage[];
  status: "completed" | "interrupted" | "error";
  cumulativeTokens?: number;
  qualityScore?: number;
  metadata?: {
    research_context?: string;
    constraints?: string[];
    preferences?: string[];
    plan_a?: string;
    plan_b?: string;
  };
}): SessionSnapshot {
  const id = `session-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

  return {
    session: {
      id,
      hypothesis: params.hypothesis,
      timestamp: new Date(),
      stepCount: params.steps.length,
      status: params.status,
      cumulativeTokens: params.cumulativeTokens,
      qualityScore: params.qualityScore,
    },
    steps: params.steps,
    tokenHistory: params.tokenHistory,
    metadata: params.metadata || {},
  };
}

// ─────────────────────────────────────────────────────────────
// Export as module object for convenience
// ─────────────────────────────────────────────────────────────

export const sessionStorage = {
  save: saveSession,
  getAll: getAllSessions,
  getSummaries: getSessionSummaries,
  get: getSession,
  delete: deleteSession,
  clear: clearAllSessions,
  isAvailable: isStorageAvailable,
  getInfo: getStorageInfo,
  createSnapshot: createSessionSnapshot,
};

export default sessionStorage;
