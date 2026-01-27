"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { Coins, TrendingUp, AlertTriangle } from "lucide-react";
import { TokenUsage } from "../types";

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

interface TokenTrackerProps {
  current: TokenUsage | null;
  cumulative: TokenUsage | null;
  history?: TokenUsage[];
  showChart?: boolean;
  warningThreshold?: number; // Token count warning threshold
  className?: string;
}

// ─────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────

function formatNumber(num: number): string {
  if (num >= 1000000) {
    return `${(num / 1000000).toFixed(1)}M`;
  }
  if (num >= 1000) {
    return `${(num / 1000).toFixed(1)}K`;
  }
  return num.toString();
}

function formatCost(cost: number): string {
  if (cost < 0.01) {
    return `$${cost.toFixed(4)}`;
  }
  return `$${cost.toFixed(2)}`;
}

function estimateCost(tokens: TokenUsage): number {
  // GPT-4 pricing (approximate)
  const promptRate = 0.03 / 1000; // $0.03 per 1K tokens
  const completionRate = 0.06 / 1000; // $0.06 per 1K tokens

  return (
    tokens.prompt_tokens * promptRate +
    tokens.completion_tokens * completionRate
  );
}

// ─────────────────────────────────────────────────────────────
// Mini Chart Component
// ─────────────────────────────────────────────────────────────

interface MiniChartProps {
  data: number[];
  color: string;
  height?: number;
}

function MiniChart({ data, color, height = 24 }: MiniChartProps) {
  if (data.length < 2) return null;

  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;

  const points = data.map((value, index) => {
    const x = (index / (data.length - 1)) * 100;
    const y = height - ((value - min) / range) * height;
    return `${x},${y}`;
  });

  return (
    <svg
      width="100%"
      height={height}
      viewBox={`0 0 100 ${height}`}
      preserveAspectRatio="none"
      className="overflow-visible"
    >
      <polyline
        points={points.join(" ")}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────

export function TokenTracker({
  current,
  cumulative,
  history = [],
  showChart = true,
  warningThreshold = 50000,
  className = "",
}: TokenTrackerProps) {
  // Calculate estimated costs
  const currentCost = useMemo(
    () => (current ? estimateCost(current) : 0),
    [current]
  );

  const cumulativeCost = useMemo(
    () =>
      cumulative?.estimated_cost ?? (cumulative ? estimateCost(cumulative) : 0),
    [cumulative]
  );

  // Extract chart data from history
  const chartData = useMemo(() => {
    if (history.length < 2) return [];
    return history.map((h) => h.total_tokens);
  }, [history]);

  // Check if over warning threshold
  const isOverThreshold =
    cumulative && cumulative.total_tokens > warningThreshold;

  return (
    <div
      className={`bg-[var(--oaria-bg-secondary)] rounded-lg p-3 ${className}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Coins size={14} className="text-yellow-500" />
          <span className="text-xs font-medium text-[var(--oaria-text-secondary)]">
            토큰 사용량
          </span>
        </div>
        {isOverThreshold && (
          <div className="flex items-center gap-1 text-orange-500">
            <AlertTriangle size={12} />
            <span className="text-xs">높음</span>
          </div>
        )}
      </div>

      {/* Cumulative Stats */}
      {cumulative && (
        <div className="mb-3">
          <div className="flex items-baseline gap-2">
            <motion.span
              key={cumulative.total_tokens}
              initial={{ opacity: 0, y: -5 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-lg font-semibold text-[var(--oaria-text-primary)]"
            >
              {formatNumber(cumulative.total_tokens)}
            </motion.span>
            <span className="text-xs text-[var(--oaria-text-tertiary)]">
              총 토큰
            </span>
          </div>

          {/* Cost estimate */}
          <div className="text-xs text-[var(--oaria-text-tertiary)] mt-0.5">
            예상 비용:{" "}
            <span className="text-green-600 dark:text-green-400">
              {formatCost(cumulativeCost)}
            </span>
          </div>
        </div>
      )}

      {/* Mini Chart */}
      {showChart && chartData.length > 1 && (
        <div className="mb-3 h-6 px-1">
          <MiniChart
            data={chartData}
            color={isOverThreshold ? "#f97316" : "#3b82f6"}
          />
        </div>
      )}

      {/* Current Step Stats */}
      {current && (
        <div className="border-t border-[var(--oaria-border)] pt-2 mt-2">
          <div className="flex items-center gap-1 mb-1.5">
            <TrendingUp size={10} className="text-blue-500" />
            <span className="text-xs text-[var(--oaria-text-tertiary)]">
              현재 단계
            </span>
          </div>

          <div className="grid grid-cols-3 gap-2 text-xs">
            <div>
              <div className="text-[var(--oaria-text-tertiary)]">입력</div>
              <div className="font-medium text-[var(--oaria-text-primary)]">
                {formatNumber(current.prompt_tokens)}
              </div>
            </div>
            <div>
              <div className="text-[var(--oaria-text-tertiary)]">출력</div>
              <div className="font-medium text-[var(--oaria-text-primary)]">
                {formatNumber(current.completion_tokens)}
              </div>
            </div>
            <div>
              <div className="text-[var(--oaria-text-tertiary)]">비용</div>
              <div className="font-medium text-green-600 dark:text-green-400">
                {formatCost(currentCost)}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Breakdown (collapsed by default, expandable) */}
      {cumulative && (
        <details className="mt-2">
          <summary className="text-xs text-[var(--oaria-text-tertiary)] cursor-pointer hover:text-[var(--oaria-text-secondary)]">
            상세 내역
          </summary>
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
            <div className="bg-[var(--oaria-bg-primary)] rounded p-2">
              <div className="text-[var(--oaria-text-tertiary)]">프롬프트</div>
              <div className="font-mono text-[var(--oaria-text-primary)]">
                {cumulative.prompt_tokens.toLocaleString()}
              </div>
            </div>
            <div className="bg-[var(--oaria-bg-primary)] rounded p-2">
              <div className="text-[var(--oaria-text-tertiary)]">완료</div>
              <div className="font-mono text-[var(--oaria-text-primary)]">
                {cumulative.completion_tokens.toLocaleString()}
              </div>
            </div>
          </div>
        </details>
      )}

      {/* Empty State */}
      {!current && !cumulative && (
        <div className="text-xs text-[var(--oaria-text-tertiary)] text-center py-2">
          토큰 사용량 데이터 없음
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Compact Variant
// ─────────────────────────────────────────────────────────────

interface CompactTokenTrackerProps {
  cumulative: TokenUsage | null;
  className?: string;
}

export function CompactTokenTracker({
  cumulative,
  className = "",
}: CompactTokenTrackerProps) {
  const cost = useMemo(
    () =>
      cumulative?.estimated_cost ?? (cumulative ? estimateCost(cumulative) : 0),
    [cumulative]
  );

  if (!cumulative) return null;

  return (
    <div
      className={`flex items-center gap-2 text-xs text-[var(--oaria-text-tertiary)] ${className}`}
    >
      <Coins size={12} className="text-yellow-500" />
      <span>{formatNumber(cumulative.total_tokens)}</span>
      <span className="text-green-600 dark:text-green-400">
        {formatCost(cost)}
      </span>
    </div>
  );
}

export default TokenTracker;
