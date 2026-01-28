"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { motion } from "framer-motion";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Rewind,
  FastForward,
} from "lucide-react";
import { ThinkingStep } from "../types";

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

interface TimelinePlayerProps {
  steps: ThinkingStep[];
  currentIndex: number;
  onIndexChange: (index: number) => void;
  isPlaying: boolean;
  onPlayPause: (playing: boolean) => void;
  playbackSpeed?: number;
  onSpeedChange?: (speed: number) => void;
  className?: string;
}

// ─────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────

const PLAYBACK_SPEEDS = [0.5, 1, 1.5, 2, 4];
const DEFAULT_STEP_DURATION = 1500; // ms between steps at 1x speed

// ─────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────

export function TimelinePlayer({
  steps,
  currentIndex,
  onIndexChange,
  isPlaying,
  onPlayPause,
  playbackSpeed = 1,
  onSpeedChange,
  className = "",
}: TimelinePlayerProps) {
  const [isDragging, setIsDragging] = useState(false);
  const progressRef = useRef<HTMLDivElement>(null);
  const playIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Calculate progress
  const progress = steps.length > 0 ? (currentIndex / (steps.length - 1)) * 100 : 0;

  // Auto-play logic
  useEffect(() => {
    if (isPlaying && !isDragging) {
      playIntervalRef.current = setInterval(() => {
        onIndexChange(Math.min(currentIndex + 1, steps.length - 1));
      }, DEFAULT_STEP_DURATION / playbackSpeed);
    }

    return () => {
      if (playIntervalRef.current) {
        clearInterval(playIntervalRef.current);
      }
    };
  }, [isPlaying, currentIndex, steps.length, playbackSpeed, isDragging, onIndexChange]);

  // Stop at end
  useEffect(() => {
    if (currentIndex >= steps.length - 1 && isPlaying) {
      onPlayPause(false);
    }
  }, [currentIndex, steps.length, isPlaying, onPlayPause]);

  // Handle progress bar click/drag
  const handleProgressInteraction = useCallback(
    (clientX: number) => {
      if (!progressRef.current || steps.length === 0) return;

      const rect = progressRef.current.getBoundingClientRect();
      const x = clientX - rect.left;
      const percentage = Math.max(0, Math.min(1, x / rect.width));
      const newIndex = Math.round(percentage * (steps.length - 1));
      onIndexChange(newIndex);
    },
    [steps.length, onIndexChange]
  );

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    handleProgressInteraction(e.clientX);
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (isDragging) {
      handleProgressInteraction(e.clientX);
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  useEffect(() => {
    if (isDragging) {
      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp);
    }
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging]);

  // Navigation handlers
  const goToStart = () => onIndexChange(0);
  const goToEnd = () => onIndexChange(steps.length - 1);
  const goBack = () => onIndexChange(Math.max(0, currentIndex - 1));
  const goForward = () => onIndexChange(Math.min(steps.length - 1, currentIndex + 1));

  // Speed change
  const cycleSpeed = () => {
    if (!onSpeedChange) return;
    const currentSpeedIndex = PLAYBACK_SPEEDS.indexOf(playbackSpeed);
    const nextIndex = (currentSpeedIndex + 1) % PLAYBACK_SPEEDS.length;
    onSpeedChange(PLAYBACK_SPEEDS[nextIndex]);
  };

  // Format step number
  const formatStepNumber = (index: number) => {
    const step = steps[index];
    if (step?.iteration) {
      return `#${step.iteration}`;
    }
    return `${index + 1}/${steps.length}`;
  };

  if (steps.length === 0) {
    return null;
  }

  return (
    <div
      className={`bg-[var(--oaria-bg-secondary)] rounded-lg p-3 ${className}`}
    >
      {/* Progress Bar */}
      <div
        ref={progressRef}
        className="relative h-2 bg-[var(--oaria-bg-tertiary)] rounded-full cursor-pointer mb-3"
        onMouseDown={handleMouseDown}
      >
        {/* Progress fill */}
        <motion.div
          className="absolute inset-y-0 left-0 bg-blue-500 rounded-full"
          initial={false}
          animate={{ width: `${progress}%` }}
          transition={{ duration: isDragging ? 0 : 0.1 }}
        />

        {/* Step markers */}
        <div className="absolute inset-0 flex justify-between px-0.5">
          {steps.map((step, index) => {
            const isActive = index <= currentIndex;
            const isCurrentStep = index === currentIndex;

            return (
              <div
                key={step.id}
                className={`w-1 h-full rounded-full transition-colors ${
                  isCurrentStep
                    ? "bg-blue-600 scale-125"
                    : isActive
                    ? "bg-blue-400"
                    : "bg-gray-300 dark:bg-gray-600"
                }`}
                style={{ transform: isCurrentStep ? "scale(1.5)" : "scale(1)" }}
              />
            );
          })}
        </div>

        {/* Draggable thumb */}
        <motion.div
          className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-white border-2 border-blue-500 rounded-full shadow-md cursor-grab"
          initial={false}
          animate={{ left: `calc(${progress}% - 8px)` }}
          transition={{ duration: isDragging ? 0 : 0.1 }}
          style={{ cursor: isDragging ? "grabbing" : "grab" }}
        />
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between">
        {/* Left: Step indicator */}
        <div className="text-xs text-[var(--oaria-text-tertiary)] min-w-[60px]">
          <span className="font-medium text-[var(--oaria-text-primary)]">
            {formatStepNumber(currentIndex)}
          </span>
        </div>

        {/* Center: Playback controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={goToStart}
            disabled={currentIndex === 0}
            className="p-1.5 rounded hover:bg-[var(--oaria-bg-tertiary)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="처음으로"
          >
            <Rewind size={16} className="text-[var(--oaria-text-secondary)]" />
          </button>

          <button
            onClick={goBack}
            disabled={currentIndex === 0}
            className="p-1.5 rounded hover:bg-[var(--oaria-bg-tertiary)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="이전"
          >
            <SkipBack size={16} className="text-[var(--oaria-text-secondary)]" />
          </button>

          <button
            onClick={() => onPlayPause(!isPlaying)}
            className="p-2 rounded-full bg-blue-500 hover:bg-blue-600 transition-colors mx-1"
            title={isPlaying ? "일시정지" : "재생"}
          >
            {isPlaying ? (
              <Pause size={18} className="text-white" />
            ) : (
              <Play size={18} className="text-white ml-0.5" />
            )}
          </button>

          <button
            onClick={goForward}
            disabled={currentIndex >= steps.length - 1}
            className="p-1.5 rounded hover:bg-[var(--oaria-bg-tertiary)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="다음"
          >
            <SkipForward size={16} className="text-[var(--oaria-text-secondary)]" />
          </button>

          <button
            onClick={goToEnd}
            disabled={currentIndex >= steps.length - 1}
            className="p-1.5 rounded hover:bg-[var(--oaria-bg-tertiary)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="끝으로"
          >
            <FastForward size={16} className="text-[var(--oaria-text-secondary)]" />
          </button>
        </div>

        {/* Right: Speed control */}
        <div className="min-w-[60px] text-right">
          <button
            onClick={cycleSpeed}
            disabled={!onSpeedChange}
            className="text-xs px-2 py-1 rounded bg-[var(--oaria-bg-tertiary)] hover:bg-[var(--oaria-bg-primary)] transition-colors disabled:opacity-50"
            title="재생 속도"
          >
            {playbackSpeed}x
          </button>
        </div>
      </div>

      {/* Current step type indicator */}
      {steps[currentIndex] && (
        <div className="mt-2 pt-2 border-t border-[var(--oaria-border)]">
          <div className="flex items-center gap-2 text-xs">
            <span className="px-2 py-0.5 rounded bg-[var(--oaria-bg-tertiary)] text-[var(--oaria-text-secondary)] font-medium">
              {steps[currentIndex].type}
            </span>
            {steps[currentIndex].action && (
              <span className="text-[var(--oaria-text-tertiary)]">
                {steps[currentIndex].action}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default TimelinePlayer;
