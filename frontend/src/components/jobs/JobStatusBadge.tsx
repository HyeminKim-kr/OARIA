"use client";

import {
  Clock,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Pause,
  RotateCcw,
} from "lucide-react";

type JobStatus =
  | "pending"
  | "queued"
  | "running"
  | "waiting_approval"
  | "approved"
  | "completed"
  | "failed"
  | "cancelled";

interface JobStatusBadgeProps {
  status: string;
  size?: "sm" | "md" | "lg";
  showIcon?: boolean;
  showLabel?: boolean;
}

const statusConfig: Record<
  JobStatus,
  {
    label: string;
    icon: React.ReactNode;
    bgColor: string;
    textColor: string;
    borderColor: string;
  }
> = {
  pending: {
    label: "대기 중",
    icon: <Clock size={14} />,
    bgColor: "bg-gray-100 dark:bg-gray-800",
    textColor: "text-gray-600 dark:text-gray-400",
    borderColor: "border-gray-200 dark:border-gray-700",
  },
  queued: {
    label: "큐 대기",
    icon: <Clock size={14} />,
    bgColor: "bg-blue-50 dark:bg-blue-900/20",
    textColor: "text-blue-600 dark:text-blue-400",
    borderColor: "border-blue-200 dark:border-blue-800",
  },
  running: {
    label: "실행 중",
    icon: <Loader2 size={14} className="animate-spin" />,
    bgColor: "bg-[var(--oaria-teal)]/10",
    textColor: "text-[var(--oaria-teal)]",
    borderColor: "border-[var(--oaria-teal)]/30",
  },
  waiting_approval: {
    label: "승인 대기",
    icon: <Pause size={14} />,
    bgColor: "bg-yellow-50 dark:bg-yellow-900/20",
    textColor: "text-yellow-600 dark:text-yellow-400",
    borderColor: "border-yellow-200 dark:border-yellow-800",
  },
  approved: {
    label: "승인됨",
    icon: <CheckCircle2 size={14} />,
    bgColor: "bg-green-50 dark:bg-green-900/20",
    textColor: "text-green-600 dark:text-green-400",
    borderColor: "border-green-200 dark:border-green-800",
  },
  completed: {
    label: "완료",
    icon: <CheckCircle2 size={14} />,
    bgColor: "bg-green-50 dark:bg-green-900/20",
    textColor: "text-green-600 dark:text-green-400",
    borderColor: "border-green-200 dark:border-green-800",
  },
  failed: {
    label: "실패",
    icon: <XCircle size={14} />,
    bgColor: "bg-red-50 dark:bg-red-900/20",
    textColor: "text-red-600 dark:text-red-400",
    borderColor: "border-red-200 dark:border-red-800",
  },
  cancelled: {
    label: "취소됨",
    icon: <AlertCircle size={14} />,
    bgColor: "bg-gray-100 dark:bg-gray-800",
    textColor: "text-gray-500 dark:text-gray-500",
    borderColor: "border-gray-200 dark:border-gray-700",
  },
};

export function JobStatusBadge({
  status,
  size = "md",
  showIcon = true,
  showLabel = true,
}: JobStatusBadgeProps) {
  const config = statusConfig[status as JobStatus] || statusConfig.pending;

  const sizeClasses = {
    sm: "text-xs px-1.5 py-0.5 gap-1",
    md: "text-sm px-2 py-1 gap-1.5",
    lg: "text-base px-3 py-1.5 gap-2",
  };

  return (
    <span
      className={`
        inline-flex items-center font-medium rounded-full border
        ${config.bgColor} ${config.textColor} ${config.borderColor}
        ${sizeClasses[size]}
      `}
    >
      {showIcon && config.icon}
      {showLabel && <span>{config.label}</span>}
    </span>
  );
}

// Progress indicator for running jobs
interface JobProgressProps {
  percent: number;
  detail?: string;
  size?: "sm" | "md";
}

export function JobProgress({ percent, detail, size = "md" }: JobProgressProps) {
  const height = size === "sm" ? "h-1" : "h-2";

  return (
    <div className="w-full">
      <div className={`w-full bg-gray-200 dark:bg-gray-700 rounded-full ${height} overflow-hidden`}>
        <div
          className={`bg-[var(--oaria-teal)] ${height} rounded-full transition-all duration-300`}
          style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
        />
      </div>
      {detail && (
        <p className="text-xs text-[var(--oaria-text-secondary)] mt-1 truncate">
          {detail}
        </p>
      )}
    </div>
  );
}

// Retry button for failed jobs
interface RetryButtonProps {
  onRetry: () => void;
  disabled?: boolean;
  size?: "sm" | "md";
}

export function RetryButton({ onRetry, disabled = false, size = "md" }: RetryButtonProps) {
  const sizeClasses = {
    sm: "text-xs px-2 py-1 gap-1",
    md: "text-sm px-3 py-1.5 gap-1.5",
  };

  return (
    <button
      onClick={onRetry}
      disabled={disabled}
      className={`
        inline-flex items-center font-medium rounded-lg
        bg-[var(--oaria-coral)]/10 text-[var(--oaria-coral)]
        hover:bg-[var(--oaria-coral)]/20
        disabled:opacity-50 disabled:cursor-not-allowed
        transition-colors
        ${sizeClasses[size]}
      `}
    >
      <RotateCcw size={size === "sm" ? 12 : 14} />
      <span>재시도</span>
    </button>
  );
}
