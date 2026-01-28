/**
 * Export Utilities for Study Plan Agent
 *
 * Functions for converting session data to various export formats.
 */

import { ThinkingStep, TokenUsage, SessionSnapshot } from "../types";

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

export type ExportFormat = "json" | "csv" | "markdown" | "html";

export interface ExportOptions {
  includeTokenHistory?: boolean;
  includeMetadata?: boolean;
  includeFullResults?: boolean;
  maxResultLength?: number;
}

export interface ExportData {
  steps: ThinkingStep[];
  hypothesis: string;
  tokenHistory?: TokenUsage[];
  planA?: string;
  planB?: string;
  metadata?: Record<string, unknown>;
}

// ─────────────────────────────────────────────────────────────
// JSON Export
// ─────────────────────────────────────────────────────────────

export function toJson(data: ExportData, options: ExportOptions = {}): string {
  const {
    includeTokenHistory = true,
    includeMetadata = true,
    includeFullResults = false,
    maxResultLength = 500,
  } = options;

  const processStep = (step: ThinkingStep) => {
    const processed: Record<string, unknown> = {
      id: step.id,
      type: step.type,
      timestamp: step.timestamp.toISOString(),
      iteration: step.iteration,
      action: step.action,
      success: step.success,
      duration_ms: step.duration_ms,
    };

    if (step.message) {
      processed.message = step.message;
    }

    if (step.parameters) {
      processed.parameters = step.parameters;
    }

    if (step.result) {
      const resultStr = typeof step.result === "string"
        ? step.result
        : JSON.stringify(step.result);

      processed.result = includeFullResults
        ? step.result
        : resultStr.length > maxResultLength
        ? resultStr.slice(0, maxResultLength) + "..."
        : step.result;
    }

    if (step.error) {
      processed.error = step.error;
    }

    if (step.token_usage) {
      processed.token_usage = step.token_usage;
    }

    return processed;
  };

  const exportObj: Record<string, unknown> = {
    exportedAt: new Date().toISOString(),
    version: "1.0",
    hypothesis: data.hypothesis,
    stepCount: data.steps.length,
    steps: data.steps.map(processStep),
  };

  if (includeTokenHistory && data.tokenHistory?.length) {
    exportObj.tokenHistory = data.tokenHistory;
    exportObj.totalTokens = data.tokenHistory.reduce(
      (sum, t) => sum + (t.total_tokens || 0),
      0
    );
  }

  if (data.planA) {
    exportObj.planA = data.planA;
  }

  if (data.planB) {
    exportObj.planB = data.planB;
  }

  if (includeMetadata && data.metadata) {
    exportObj.metadata = data.metadata;
  }

  return JSON.stringify(exportObj, null, 2);
}

// ─────────────────────────────────────────────────────────────
// CSV Export
// ─────────────────────────────────────────────────────────────

export function toCsv(steps: ThinkingStep[]): string {
  const escapeCell = (value: unknown): string => {
    if (value === null || value === undefined) return "";
    const str = String(value);
    // Escape quotes and wrap in quotes if contains comma, newline, or quote
    if (str.includes(",") || str.includes("\n") || str.includes('"')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const headers = [
    "ID",
    "Type",
    "Timestamp",
    "Iteration",
    "Action",
    "Success",
    "Duration (ms)",
    "Prompt Tokens",
    "Completion Tokens",
    "Total Tokens",
    "Error",
    "Message",
  ];

  const rows = steps.map((step) => [
    escapeCell(step.id),
    escapeCell(step.type),
    escapeCell(step.timestamp.toISOString()),
    escapeCell(step.iteration),
    escapeCell(step.action),
    escapeCell(step.success),
    escapeCell(step.duration_ms),
    escapeCell(step.token_usage?.prompt_tokens),
    escapeCell(step.token_usage?.completion_tokens),
    escapeCell(step.token_usage?.total_tokens),
    escapeCell(step.error),
    escapeCell(step.message?.slice(0, 200)),
  ]);

  return [headers.join(","), ...rows.map((row) => row.join(","))].join("\n");
}

// ─────────────────────────────────────────────────────────────
// Markdown Export
// ─────────────────────────────────────────────────────────────

export function toMarkdown(data: ExportData): string {
  const lines: string[] = [];

  // Header
  lines.push("# Study Plan Agent Report");
  lines.push("");
  lines.push(`> Generated: ${new Date().toLocaleString()}`);
  lines.push("");

  // Hypothesis
  lines.push("## Hypothesis");
  lines.push("");
  lines.push(data.hypothesis);
  lines.push("");

  // Summary
  const successCount = data.steps.filter((s) => s.success === true).length;
  const failCount = data.steps.filter((s) => s.success === false).length;
  const totalTokens = data.tokenHistory?.reduce(
    (sum, t) => sum + (t.total_tokens || 0),
    0
  );
  const estimatedCost = data.tokenHistory?.reduce(
    (sum, t) => sum + (t.estimated_cost || 0),
    0
  );

  lines.push("## Summary");
  lines.push("");
  lines.push("| Metric | Value |");
  lines.push("|--------|-------|");
  lines.push(`| Total Steps | ${data.steps.length} |`);
  lines.push(`| Successful | ${successCount} |`);
  lines.push(`| Failed | ${failCount} |`);
  if (totalTokens) {
    lines.push(`| Total Tokens | ${totalTokens.toLocaleString()} |`);
  }
  if (estimatedCost) {
    lines.push(`| Estimated Cost | $${estimatedCost.toFixed(4)} |`);
  }
  lines.push("");

  // Execution Timeline
  lines.push("## Execution Timeline");
  lines.push("");

  data.steps.forEach((step, index) => {
    const statusIcon = step.success === true ? "✅" : step.success === false ? "❌" : "⏳";

    lines.push(`### ${statusIcon} Step ${index + 1}: ${step.type}`);
    lines.push("");

    if (step.iteration !== undefined) {
      lines.push(`**Iteration:** ${step.iteration}`);
      lines.push("");
    }

    if (step.action) {
      lines.push(`**Action:** \`${step.action}\``);
      lines.push("");
    }

    if (step.message) {
      lines.push("**Message:**");
      lines.push(`> ${step.message.split("\n").join("\n> ")}`);
      lines.push("");
    }

    if (step.parameters && Object.keys(step.parameters).length > 0) {
      lines.push("**Parameters:**");
      lines.push("```json");
      lines.push(JSON.stringify(step.parameters, null, 2).slice(0, 500));
      lines.push("```");
      lines.push("");
    }

    if (step.error) {
      lines.push("**Error:**");
      lines.push(`\`\`\`\n${step.error}\n\`\`\``);
      lines.push("");
    }

    if (step.duration_ms) {
      lines.push(`*Duration: ${step.duration_ms}ms*`);
      lines.push("");
    }

    lines.push("---");
    lines.push("");
  });

  // Plans
  if (data.planA) {
    lines.push("## Plan A (Primary)");
    lines.push("");
    lines.push(data.planA);
    lines.push("");
  }

  if (data.planB) {
    lines.push("## Plan B (Alternative)");
    lines.push("");
    lines.push(data.planB);
    lines.push("");
  }

  return lines.join("\n");
}

// ─────────────────────────────────────────────────────────────
// Session Snapshot Export
// ─────────────────────────────────────────────────────────────

export function snapshotToExportData(snapshot: SessionSnapshot): ExportData {
  return {
    steps: snapshot.steps,
    hypothesis: snapshot.session.hypothesis,
    tokenHistory: snapshot.tokenHistory,
    planA: snapshot.metadata.plan_a,
    planB: snapshot.metadata.plan_b,
    metadata: {
      sessionId: snapshot.session.id,
      timestamp: snapshot.session.timestamp.toISOString(),
      status: snapshot.session.status,
      qualityScore: snapshot.session.qualityScore,
      research_context: snapshot.metadata.research_context,
      constraints: snapshot.metadata.constraints,
      preferences: snapshot.metadata.preferences,
    },
  };
}

// ─────────────────────────────────────────────────────────────
// Download Helper
// ─────────────────────────────────────────────────────────────

export function downloadFile(
  content: string,
  filename: string,
  mimeType: string
): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function downloadExport(
  data: ExportData,
  format: ExportFormat,
  baseFilename: string = "study-plan-export"
): void {
  const timestamp = new Date().toISOString().slice(0, 10);
  let content: string;
  let filename: string;
  let mimeType: string;

  switch (format) {
    case "json":
      content = toJson(data);
      filename = `${baseFilename}-${timestamp}.json`;
      mimeType = "application/json";
      break;

    case "csv":
      content = toCsv(data.steps);
      filename = `${baseFilename}-${timestamp}.csv`;
      mimeType = "text/csv";
      break;

    case "markdown":
      content = toMarkdown(data);
      filename = `${baseFilename}-${timestamp}.md`;
      mimeType = "text/markdown";
      break;

    default:
      throw new Error(`Unsupported export format: ${format}`);
  }

  downloadFile(content, filename, mimeType);
}

// ─────────────────────────────────────────────────────────────
// Module Export
// ─────────────────────────────────────────────────────────────

export const exportUtils = {
  toJson,
  toCsv,
  toMarkdown,
  snapshotToExportData,
  downloadFile,
  downloadExport,
};

export default exportUtils;
