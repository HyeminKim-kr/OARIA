"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Download,
  FileJson,
  FileText,
  FileSpreadsheet,
  Check,
  ChevronDown,
  Loader2,
} from "lucide-react";
import { ThinkingStep, TokenUsage } from "../types";

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

type ExportFormat = "json" | "csv" | "markdown";

interface ExportButtonProps {
  steps: ThinkingStep[];
  hypothesis: string;
  tokenHistory?: TokenUsage[];
  planA?: string;
  planB?: string;
  metadata?: Record<string, unknown>;
  disabled?: boolean;
  className?: string;
}

interface ExportOption {
  format: ExportFormat;
  label: string;
  icon: React.ReactNode;
  description: string;
}

// ─────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────

const EXPORT_OPTIONS: ExportOption[] = [
  {
    format: "json",
    label: "JSON",
    icon: <FileJson size={16} />,
    description: "전체 데이터 (재사용 가능)",
  },
  {
    format: "csv",
    label: "CSV",
    icon: <FileSpreadsheet size={16} />,
    description: "스프레드시트 형식",
  },
  {
    format: "markdown",
    label: "Markdown",
    icon: <FileText size={16} />,
    description: "읽기 쉬운 보고서 형식",
  },
];

// ─────────────────────────────────────────────────────────────
// Export Functions
// ─────────────────────────────────────────────────────────────

function exportToJson(data: {
  steps: ThinkingStep[];
  hypothesis: string;
  tokenHistory?: TokenUsage[];
  planA?: string;
  planB?: string;
  metadata?: Record<string, unknown>;
}): string {
  return JSON.stringify(
    {
      exportedAt: new Date().toISOString(),
      hypothesis: data.hypothesis,
      stepCount: data.steps.length,
      totalTokens: data.tokenHistory?.reduce(
        (sum, t) => sum + (t.total_tokens || 0),
        0
      ),
      metadata: data.metadata,
      steps: data.steps.map((step) => ({
        id: step.id,
        type: step.type,
        timestamp: step.timestamp.toISOString(),
        iteration: step.iteration,
        action: step.action,
        message: step.message,
        parameters: step.parameters,
        result: step.result,
        success: step.success,
        error: step.error,
        duration_ms: step.duration_ms,
        token_usage: step.token_usage,
      })),
      tokenHistory: data.tokenHistory,
      planA: data.planA,
      planB: data.planB,
    },
    null,
    2
  );
}

function exportToCsv(steps: ThinkingStep[]): string {
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
    "Error",
    "Message",
  ];

  const rows = steps.map((step) => [
    step.id,
    step.type,
    step.timestamp.toISOString(),
    step.iteration ?? "",
    step.action ?? "",
    step.success ?? "",
    step.duration_ms ?? "",
    step.token_usage?.prompt_tokens ?? "",
    step.token_usage?.completion_tokens ?? "",
    step.error ?? "",
    (step.message ?? "").replace(/"/g, '""'), // Escape quotes
  ]);

  const csvContent = [
    headers.join(","),
    ...rows.map((row) => row.map((cell) => `"${cell}"`).join(",")),
  ].join("\n");

  return csvContent;
}

function exportToMarkdown(data: {
  steps: ThinkingStep[];
  hypothesis: string;
  planA?: string;
  planB?: string;
  tokenHistory?: TokenUsage[];
}): string {
  const lines: string[] = [];

  // Header
  lines.push("# Study Plan Agent - Thinking Process Report");
  lines.push("");
  lines.push(`**Generated:** ${new Date().toISOString()}`);
  lines.push(`**Total Steps:** ${data.steps.length}`);
  lines.push("");

  // Hypothesis
  lines.push("## Hypothesis");
  lines.push("");
  lines.push(data.hypothesis);
  lines.push("");

  // Summary statistics
  const successCount = data.steps.filter((s) => s.success === true).length;
  const failCount = data.steps.filter((s) => s.success === false).length;
  const totalTokens = data.tokenHistory?.reduce(
    (sum, t) => sum + (t.total_tokens || 0),
    0
  );

  lines.push("## Summary");
  lines.push("");
  lines.push(`- Successful actions: ${successCount}`);
  lines.push(`- Failed actions: ${failCount}`);
  if (totalTokens) {
    lines.push(`- Total tokens used: ${totalTokens.toLocaleString()}`);
  }
  lines.push("");

  // Steps
  lines.push("## Execution Steps");
  lines.push("");

  data.steps.forEach((step, index) => {
    lines.push(`### Step ${index + 1}: ${step.type}`);
    lines.push("");

    if (step.iteration) {
      lines.push(`**Iteration:** ${step.iteration}`);
    }

    if (step.action) {
      lines.push(`**Action:** \`${step.action}\``);
    }

    if (step.message) {
      lines.push("");
      lines.push(step.message);
    }

    if (step.success !== undefined) {
      lines.push("");
      lines.push(`**Result:** ${step.success ? "Success" : "Failed"}`);
    }

    if (step.error) {
      lines.push("");
      lines.push(`**Error:** ${step.error}`);
    }

    if (step.duration_ms) {
      lines.push(`**Duration:** ${step.duration_ms}ms`);
    }

    lines.push("");
    lines.push("---");
    lines.push("");
  });

  // Plans
  if (data.planA) {
    lines.push("## Plan A");
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
// Download Helper
// ─────────────────────────────────────────────────────────────

function downloadFile(content: string, filename: string, mimeType: string) {
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

// ─────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────

export function ExportButton({
  steps,
  hypothesis,
  tokenHistory,
  planA,
  planB,
  metadata,
  disabled = false,
  className = "",
}: ExportButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [exported, setExported] = useState<ExportFormat | null>(null);

  const handleExport = useCallback(
    async (format: ExportFormat) => {
      if (disabled || steps.length === 0) return;

      setExporting(format);

      try {
        // Simulate a brief delay for UX
        await new Promise((resolve) => setTimeout(resolve, 300));

        const timestamp = new Date().toISOString().slice(0, 10);
        let content: string;
        let filename: string;
        let mimeType: string;

        switch (format) {
          case "json":
            content = exportToJson({
              steps,
              hypothesis,
              tokenHistory,
              planA,
              planB,
              metadata,
            });
            filename = `study-plan-export-${timestamp}.json`;
            mimeType = "application/json";
            break;

          case "csv":
            content = exportToCsv(steps);
            filename = `study-plan-steps-${timestamp}.csv`;
            mimeType = "text/csv";
            break;

          case "markdown":
            content = exportToMarkdown({
              steps,
              hypothesis,
              planA,
              planB,
              tokenHistory,
            });
            filename = `study-plan-report-${timestamp}.md`;
            mimeType = "text/markdown";
            break;
        }

        downloadFile(content, filename, mimeType);
        setExported(format);
        setTimeout(() => setExported(null), 2000);
      } catch (error) {
        console.error("Export failed:", error);
      } finally {
        setExporting(null);
        setIsOpen(false);
      }
    },
    [steps, hypothesis, tokenHistory, planA, planB, metadata, disabled]
  );

  const isDisabled = disabled || !steps || steps.length === 0;

  return (
    <div className={`relative ${className}`}>
      {/* Main button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={isDisabled}
        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors ${
          isDisabled
            ? "bg-gray-100 dark:bg-gray-800 text-gray-400 cursor-not-allowed"
            : "bg-[var(--oaria-bg-secondary)] hover:bg-[var(--oaria-bg-tertiary)] text-[var(--oaria-text-primary)]"
        }`}
      >
        <Download size={14} />
        <span>내보내기</span>
        <ChevronDown
          size={14}
          className={`transition-transform ${isOpen ? "rotate-180" : ""}`}
        />
      </button>

      {/* Dropdown menu */}
      <AnimatePresence>
        {isOpen && !isDisabled && (
          <>
            {/* Backdrop */}
            <div
              className="fixed inset-0 z-10"
              onClick={() => setIsOpen(false)}
            />

            {/* Menu */}
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="absolute right-0 top-full mt-1 z-20 min-w-[200px] bg-[var(--oaria-bg-primary)] border border-[var(--oaria-border)] rounded-lg shadow-lg overflow-hidden"
            >
              {EXPORT_OPTIONS.map((option) => {
                const isExporting = exporting === option.format;
                const isExported = exported === option.format;

                return (
                  <button
                    key={option.format}
                    onClick={() => handleExport(option.format)}
                    disabled={isExporting}
                    className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-[var(--oaria-bg-secondary)] transition-colors text-left"
                  >
                    <div
                      className={`p-1.5 rounded ${
                        isExported
                          ? "bg-green-100 dark:bg-green-900/30 text-green-600"
                          : "bg-[var(--oaria-bg-secondary)] text-[var(--oaria-text-secondary)]"
                      }`}
                    >
                      {isExporting ? (
                        <Loader2 size={16} className="animate-spin" />
                      ) : isExported ? (
                        <Check size={16} />
                      ) : (
                        option.icon
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="text-sm font-medium text-[var(--oaria-text-primary)]">
                        {option.label}
                      </div>
                      <div className="text-xs text-[var(--oaria-text-tertiary)]">
                        {option.description}
                      </div>
                    </div>
                  </button>
                );
              })}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}

export default ExportButton;
