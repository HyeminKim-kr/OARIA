"use client";

import { useState, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Brain,
  ChevronRight,
  Loader2,
  CheckCircle2,
  Zap,
  Eye,
  Target,
  AlertTriangle,
  Sparkles,
} from "lucide-react";
import type { ThinkingStep, Source, ObservationDetails } from "../types";
import { SourcesCard } from "./SourcesCard";
import { ObservationDetailsCard } from "./ObservationDetailsCard";

interface ExtendedThinkingPanelProps {
  steps: ThinkingStep[];
  currentStep: ThinkingStep | null;
  isLoading: boolean;
  isCompleted?: boolean;
  elapsedTime?: number;
}

export function ExtendedThinkingPanel({
  steps,
  currentStep,
  isLoading,
  isCompleted = false,
  elapsedTime = 0,
}: ExtendedThinkingPanelProps) {
  // Track which sections are expanded
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());

  // Toggle section expansion
  const toggleSection = useCallback((id: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  // Check if section is expanded
  const isSectionExpanded = useCallback(
    (id: string, isCurrent: boolean) => {
      // Current step is always expanded
      if (isCurrent && isLoading) return true;
      return expandedSections.has(id);
    },
    [isLoading, expandedSections]
  );

  // Group steps: thinking steps become sections, others become sub-items
  const groupedSteps = useMemo(() => {
    const groups: Array<{
      id: string;
      title: string;
      bullets: string[];
      subSteps: ThinkingStep[];
      status: "in_progress" | "completed";
      sources?: Source[];
      summary?: string;
      observationDetails?: ObservationDetails;
    }> = [];

    let currentGroup: (typeof groups)[0] | null = null;

    for (const step of steps) {
      if (step.type === "thinking") {
        // Start a new group
        if (currentGroup) {
          groups.push(currentGroup);
        }
        currentGroup = {
          id: step.id,
          title: step.title || `반복 ${step.iteration}: 분석 중`,
          bullets: step.bullets || [],
          subSteps: [],
          status: step.status || "completed",
        };
      } else if (currentGroup) {
        // Add to current group
        currentGroup.subSteps.push(step);

        // If observation has sources or details, add to group
        if (step.type === "observation") {
          if (step.sources) {
            currentGroup.sources = step.sources as Source[];
          }
          if (step.observationDetails) {
            currentGroup.observationDetails = step.observationDetails;
          }
          currentGroup.summary = step.summary;
        }
      } else {
        // No current group - create one for orphan steps
        groups.push({
          id: step.id,
          title: getStepTitle(step),
          bullets: step.message ? [step.message] : [],
          subSteps: [step],
          status: "completed",
          sources: step.type === "observation" ? (step.sources as Source[]) : undefined,
          summary: step.summary,
          observationDetails: step.type === "observation" ? step.observationDetails : undefined,
        });
      }
    }

    // Push last group
    if (currentGroup) {
      groups.push(currentGroup);
    }

    return groups;
  }, [steps]);

  // Get title for non-thinking steps
  function getStepTitle(step: ThinkingStep): string {
    switch (step.type) {
      case "acting":
        return `도구 실행: ${step.action}`;
      case "observation":
        return step.summary || `결과: ${step.action}`;
      case "goal_check":
        return step.achieved ? "목표 달성 확인" : "진행 상황 점검";
      case "recovery":
        return "오류 복구 시도";
      case "started":
        return "에이전트 시작";
      default:
        return "처리 중";
    }
  }

  // Get icon for step type
  function getStepIcon(type: ThinkingStep["type"]) {
    switch (type) {
      case "thinking":
        return <Brain size={14} className="text-purple-500" />;
      case "acting":
        return <Zap size={14} className="text-blue-500" />;
      case "observation":
        return <Eye size={14} className="text-green-500" />;
      case "goal_check":
        return <Target size={14} className="text-orange-500" />;
      case "recovery":
        return <AlertTriangle size={14} className="text-red-500" />;
      default:
        return <Sparkles size={14} className="text-[var(--oaria-teal)]" />;
    }
  }

  // Render a thinking section
  const renderSection = (
    group: (typeof groupedSteps)[0],
    index: number,
    isCurrent: boolean
  ) => {
    const isExpanded = isSectionExpanded(group.id, isCurrent);
    const hasContent = group.bullets.length > 0 || group.subSteps.length > 0 || group.sources;

    return (
      <motion.div
        key={group.id}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: index * 0.05 }}
        className={`rounded-lg overflow-hidden ${
          isCurrent && isLoading
            ? "bg-purple-500/5 border border-purple-500/20"
            : "bg-[var(--oaria-surface)] border border-[var(--oaria-border)]"
        }`}
      >
        {/* Section Header */}
        <button
          onClick={() => hasContent && toggleSection(group.id)}
          className={`w-full px-4 py-3 flex items-center gap-3 text-left transition-colors ${
            hasContent ? "hover:bg-[var(--oaria-border)]/30 cursor-pointer" : "cursor-default"
          }`}
        >
          {/* Expand/Collapse Icon */}
          {hasContent ? (
            <motion.div
              animate={{ rotate: isExpanded ? 90 : 0 }}
              transition={{ duration: 0.2 }}
              className="text-[var(--oaria-text-secondary)]"
            >
              <ChevronRight size={16} />
            </motion.div>
          ) : (
            <div className="w-4" />
          )}

          {/* Status Icon */}
          {isCurrent && isLoading ? (
            <Loader2 size={16} className="text-purple-500 animate-spin" />
          ) : (
            <CheckCircle2 size={16} className="text-green-500" />
          )}

          {/* Title */}
          <span className="flex-1 text-sm font-medium text-[var(--foreground)]">
            {group.title}
          </span>

          {/* Loading indicator for current section */}
          {isCurrent && isLoading && (
            <span className="text-xs text-purple-500 font-medium">
              분석 중...
            </span>
          )}
        </button>

        {/* Expanded Content */}
        <AnimatePresence>
          {isExpanded && hasContent && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div className="px-4 pb-4 pt-1 space-y-3">
                {/* Bullets */}
                {group.bullets.length > 0 && (
                  <ul className="space-y-2 pl-6">
                    {group.bullets.map((bullet, i) => (
                      <motion.li
                        key={i}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.05 }}
                        className="text-sm text-[var(--oaria-text-secondary)] relative before:content-['•'] before:absolute before:-left-4 before:text-[var(--oaria-teal)]"
                      >
                        {bullet}
                      </motion.li>
                    ))}
                  </ul>
                )}

                {/* Observation Details Card (detailed results) */}
                {group.observationDetails && (
                  <ObservationDetailsCard
                    details={group.observationDetails}
                    action={group.subSteps.find(s => s.type === "observation")?.action}
                  />
                )}

                {/* Sources Card (if observation has sources) */}
                {group.sources && group.sources.length > 0 && (
                  <div className="mt-3">
                    <SourcesCard
                      sources={group.sources}
                      summary={group.summary}
                      isLoading={isCurrent && isLoading}
                    />
                  </div>
                )}

                {/* Sub-steps summary (acting, observation status) */}
                {group.subSteps.length > 0 && !group.observationDetails && !group.sources && (
                  <div className="mt-2 space-y-2 pl-6 border-l-2 border-[var(--oaria-border)]">
                    {group.subSteps.map((subStep) => (
                      <div
                        key={subStep.id}
                        className="flex items-start gap-2 text-xs"
                      >
                        {getStepIcon(subStep.type)}
                        <div className="flex-1">
                          <span className="font-medium">
                            {subStep.action || subStep.type}
                          </span>
                          {subStep.type === "observation" && (
                            <span
                              className={`ml-2 ${
                                subStep.success ? "text-green-500" : "text-red-500"
                              }`}
                            >
                              {subStep.success ? "성공" : "실패"}
                              {subStep.duration_ms && ` (${subStep.duration_ms}ms)`}
                            </span>
                          )}
                          {subStep.summary && (
                            <p className="text-[var(--oaria-text-secondary)] mt-1">
                              {subStep.summary}
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    );
  };

  return (
    <div className="bg-[var(--background)] border-2 border-[var(--oaria-border)] rounded-2xl overflow-hidden">
      {/* Header */}
      <div
        className={`px-4 py-3 border-b border-[var(--oaria-border)] ${
          isCompleted
            ? "bg-gradient-to-r from-green-500/10 to-emerald-500/10"
            : "bg-gradient-to-r from-purple-500/5 to-blue-500/5"
        }`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Icon with animation */}
            <div className="relative">
              {isCompleted ? (
                <CheckCircle2 size={20} className="text-green-500" />
              ) : (
                <motion.div
                  animate={isLoading ? { scale: [1, 1.1, 1] } : {}}
                  transition={{ repeat: Infinity, duration: 1.5 }}
                >
                  <Brain size={20} className="text-purple-500" />
                </motion.div>
              )}
              {isLoading && !isCompleted && (
                <motion.div
                  className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-purple-500 rounded-full"
                  animate={{ scale: [1, 1.5, 1], opacity: [1, 0.5, 1] }}
                  transition={{ repeat: Infinity, duration: 1 }}
                />
              )}
            </div>

            {/* Title */}
            <h3 className="font-semibold text-sm">
              {isCompleted ? "사고 과정 완료" : "잘 생각하기"}
            </h3>

            {/* Loading dots */}
            {isLoading && !isCompleted && (
              <motion.div
                className="flex gap-1"
                animate={{ opacity: [0.5, 1, 0.5] }}
                transition={{ repeat: Infinity, duration: 1.5 }}
              >
                <span className="w-1 h-1 rounded-full bg-purple-500" />
                <span className="w-1 h-1 rounded-full bg-purple-500" />
                <span className="w-1 h-1 rounded-full bg-purple-500" />
              </motion.div>
            )}
          </div>

          {/* Time & Stats */}
          <div className="flex items-center gap-3 text-xs text-[var(--oaria-text-secondary)]">
            {elapsedTime > 0 && (
              <span className="font-mono">
                {Math.floor(elapsedTime / 60)}:{(elapsedTime % 60).toString().padStart(2, "0")}
              </span>
            )}
            <span>{groupedSteps.length}개 단계</span>
          </div>
        </div>
      </div>

      {/* Sections */}
      <div className="p-4 space-y-2">
        {groupedSteps.map((group, index) => {
          const isCurrent = currentStep?.id === group.id ||
            (index === groupedSteps.length - 1 && isLoading);
          return renderSection(group, index, isCurrent);
        })}

        {/* Current step if not in a group yet */}
        {currentStep && !groupedSteps.some((g) => g.id === currentStep.id) && isLoading && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-lg bg-purple-500/5 border border-purple-500/20 px-4 py-3"
          >
            <div className="flex items-center gap-3">
              <Loader2 size={16} className="text-purple-500 animate-spin" />
              <span className="text-sm text-[var(--foreground)]">
                {currentStep.title || "분석 중..."}
              </span>
            </div>
            {currentStep.bullets && currentStep.bullets.length > 0 && (
              <ul className="mt-2 space-y-1 pl-7">
                {currentStep.bullets.map((bullet, i) => (
                  <li
                    key={i}
                    className="text-sm text-[var(--oaria-text-secondary)] relative before:content-['•'] before:absolute before:-left-4 before:text-[var(--oaria-teal)]"
                  >
                    {bullet}
                  </li>
                ))}
              </ul>
            )}
          </motion.div>
        )}

        {/* Empty state */}
        {groupedSteps.length === 0 && !currentStep && (
          <div className="flex items-center justify-center py-8 text-[var(--oaria-text-secondary)]">
            {isLoading ? (
              <div className="flex items-center gap-2">
                <Loader2 size={16} className="animate-spin" />
                <span className="text-sm">에이전트 초기화 중...</span>
              </div>
            ) : (
              <span className="text-sm">사고 과정이 여기에 표시됩니다</span>
            )}
          </div>
        )}
      </div>

      {/* Completion summary */}
      {isCompleted && (
        <div className="px-4 pb-4">
          <div className="rounded-lg bg-green-500/10 border border-green-500/20 px-4 py-3">
            <div className="flex items-center gap-2 text-green-600">
              <CheckCircle2 size={16} />
              <span className="text-sm font-medium">
                {groupedSteps.length}개 단계를 거쳐 분석을 완료했어요
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
