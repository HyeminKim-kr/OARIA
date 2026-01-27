"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertTriangle,
  RefreshCw,
  SkipForward,
  User,
  Clock,
  ChevronRight,
} from "lucide-react";
import { RecoveryOption, RiskLevel } from "../types";

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

interface RecoverySelectorProps {
  options: RecoveryOption[];
  error: string;
  action?: string;
  onSelect: (optionId: string) => void;
  onTimeout?: () => void;
  timeoutSeconds?: number;
  defaultOptionId?: string;
  className?: string;
}

// ─────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────

const RISK_COLORS: Record<RiskLevel, { bg: string; text: string; border: string }> = {
  low: {
    bg: "bg-green-50 dark:bg-green-900/20",
    text: "text-green-600 dark:text-green-400",
    border: "border-green-200 dark:border-green-800",
  },
  medium: {
    bg: "bg-yellow-50 dark:bg-yellow-900/20",
    text: "text-yellow-600 dark:text-yellow-400",
    border: "border-yellow-200 dark:border-yellow-800",
  },
  high: {
    bg: "bg-red-50 dark:bg-red-900/20",
    text: "text-red-600 dark:text-red-400",
    border: "border-red-200 dark:border-red-800",
  },
};

const RISK_LABELS: Record<RiskLevel, string> = {
  low: "안전",
  medium: "주의",
  high: "위험",
};

// ─────────────────────────────────────────────────────────────
// Helper Components
// ─────────────────────────────────────────────────────────────

function getOptionIcon(optionId: string) {
  switch (optionId) {
    case "retry":
    case "retry_with_backoff":
      return <RefreshCw size={16} />;
    case "skip":
    case "skip_action":
      return <SkipForward size={16} />;
    case "user_input":
    case "ask_user":
      return <User size={16} />;
    default:
      return <ChevronRight size={16} />;
  }
}

interface CountdownTimerProps {
  seconds: number;
  onComplete: () => void;
  isActive: boolean;
}

function CountdownTimer({ seconds, onComplete, isActive }: CountdownTimerProps) {
  const [remaining, setRemaining] = useState(seconds);

  useEffect(() => {
    if (!isActive) return;

    setRemaining(seconds);
    const interval = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          onComplete();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [seconds, onComplete, isActive]);

  const progress = (remaining / seconds) * 100;

  return (
    <div className="flex items-center gap-2">
      <Clock size={14} className="text-[var(--oaria-text-tertiary)]" />
      <div className="flex-1 h-1.5 bg-[var(--oaria-bg-tertiary)] rounded-full overflow-hidden">
        <motion.div
          className="h-full bg-blue-500"
          initial={{ width: "100%" }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.5 }}
        />
      </div>
      <span className="text-xs text-[var(--oaria-text-tertiary)] min-w-[2rem] text-right">
        {remaining}초
      </span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────

export function RecoverySelector({
  options,
  error,
  action,
  onSelect,
  onTimeout,
  timeoutSeconds = 30,
  defaultOptionId,
  className = "",
}: RecoverySelectorProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isTimerActive, setIsTimerActive] = useState(true);

  // Determine default option
  const effectiveDefaultId = defaultOptionId || options[0]?.id;

  // Handle timeout
  const handleTimeout = useCallback(() => {
    if (onTimeout) {
      onTimeout();
    } else if (effectiveDefaultId) {
      onSelect(effectiveDefaultId);
    }
  }, [onTimeout, onSelect, effectiveDefaultId]);

  // Handle selection
  const handleSelect = (optionId: string) => {
    setSelectedId(optionId);
    setIsTimerActive(false);
    onSelect(optionId);
  };

  // Pause timer on hover/focus
  const handlePause = () => setIsTimerActive(false);
  const handleResume = () => setIsTimerActive(true);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className={`bg-[var(--oaria-bg-secondary)] border border-orange-200 dark:border-orange-800 rounded-lg p-4 ${className}`}
      onMouseEnter={handlePause}
      onMouseLeave={handleResume}
    >
      {/* Header */}
      <div className="flex items-start gap-3 mb-4">
        <div className="p-2 bg-orange-100 dark:bg-orange-900/30 rounded-lg">
          <AlertTriangle size={20} className="text-orange-500" />
        </div>
        <div className="flex-1">
          <h4 className="font-medium text-[var(--oaria-text-primary)]">
            복구 필요
          </h4>
          <p className="text-sm text-[var(--oaria-text-secondary)] mt-0.5">
            {action && (
              <span className="font-mono text-xs bg-[var(--oaria-bg-tertiary)] px-1.5 py-0.5 rounded mr-2">
                {action}
              </span>
            )}
            {error}
          </p>
        </div>
      </div>

      {/* Timer */}
      {selectedId === null && (
        <div className="mb-4">
          <CountdownTimer
            seconds={timeoutSeconds}
            onComplete={handleTimeout}
            isActive={isTimerActive}
          />
          <p className="text-xs text-[var(--oaria-text-tertiary)] mt-1">
            시간 초과 시{" "}
            <span className="font-medium">
              {options.find((o) => o.id === effectiveDefaultId)?.label || "기본 옵션"}
            </span>
            이 자동 선택됩니다
          </p>
        </div>
      )}

      {/* Options */}
      <div className="space-y-2">
        {options.map((option) => {
          const colors = RISK_COLORS[option.risk_level];
          const isSelected = selectedId === option.id;
          const isDefault = option.id === effectiveDefaultId;

          return (
            <button
              key={option.id}
              onClick={() => handleSelect(option.id)}
              disabled={selectedId !== null}
              className={`w-full text-left p-3 rounded-lg border transition-all ${
                isSelected
                  ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                  : `${colors.border} ${colors.bg} hover:border-blue-300 dark:hover:border-blue-700`
              } ${selectedId !== null && !isSelected ? "opacity-50" : ""}`}
            >
              <div className="flex items-center gap-3">
                <div
                  className={`p-1.5 rounded ${
                    isSelected ? "bg-blue-100 dark:bg-blue-900/30 text-blue-600" : `${colors.bg} ${colors.text}`
                  }`}
                >
                  {getOptionIcon(option.id)}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm text-[var(--oaria-text-primary)]">
                      {option.label}
                    </span>
                    {isDefault && (
                      <span className="text-xs px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded">
                        기본값
                      </span>
                    )}
                    <span className={`text-xs ${colors.text}`}>
                      {RISK_LABELS[option.risk_level]}
                    </span>
                  </div>
                  <p className="text-xs text-[var(--oaria-text-tertiary)] mt-0.5">
                    {option.description}
                  </p>
                  {option.estimated_time && (
                    <p className="text-xs text-[var(--oaria-text-tertiary)] mt-0.5 flex items-center gap-1">
                      <Clock size={10} />
                      예상 소요 시간: {option.estimated_time}
                    </p>
                  )}
                </div>
                {isSelected && (
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    className="text-blue-500"
                  >
                    <RefreshCw size={16} className="animate-spin" />
                  </motion.div>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* Selected feedback */}
      <AnimatePresence>
        {selectedId && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-3 pt-3 border-t border-[var(--oaria-border)]"
          >
            <p className="text-sm text-blue-600 dark:text-blue-400 flex items-center gap-2">
              <RefreshCw size={14} className="animate-spin" />
              복구 전략 실행 중...
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default RecoverySelector;
