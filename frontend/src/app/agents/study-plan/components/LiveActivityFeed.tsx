"use client";

import { motion, AnimatePresence } from "framer-motion";
import {
  Brain,
  Zap,
  CheckCircle,
  AlertCircle,
  X,
  Sparkles,
} from "lucide-react";
import { useEffect, useRef } from "react";
import type { ActivityLog } from "../types";

interface LiveActivityFeedProps {
  logs: ActivityLog[];
  isLoading: boolean;
  elapsedTime: number;
  onClose: () => void;
}

export function LiveActivityFeed({
  logs,
  isLoading,
  elapsedTime,
  onClose,
}: LiveActivityFeedProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto scroll to bottom on new logs
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  const getLogIcon = (type: ActivityLog["type"]) => {
    switch (type) {
      case "thinking":
        return <Brain size={14} className="text-purple-500" />;
      case "action":
        return <Zap size={14} className="text-yellow-500" />;
      case "result":
        return <CheckCircle size={14} className="text-green-500" />;
      case "error":
        return <AlertCircle size={14} className="text-red-500" />;
      default:
        return <Sparkles size={14} className="text-blue-500" />;
    }
  };

  const getLogBg = (type: ActivityLog["type"]) => {
    switch (type) {
      case "thinking":
        return "bg-purple-500/10 border-purple-500/20";
      case "action":
        return "bg-yellow-500/10 border-yellow-500/20";
      case "result":
        return "bg-green-500/10 border-green-500/20";
      case "error":
        return "bg-red-500/10 border-red-500/20";
      default:
        return "bg-blue-500/10 border-blue-500/20";
    }
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString("ko-KR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  return (
    <motion.div
      initial={{ x: 300, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 300, opacity: 0 }}
      className="w-80 border-l border-[var(--oaria-border)] bg-[var(--background)] flex flex-col h-full"
    >
      {/* Header */}
      <div className="p-4 border-b border-[var(--oaria-border)] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="relative">
            <Sparkles size={18} className="text-[var(--oaria-teal)]" />
            {isLoading && (
              <motion.div
                className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-[var(--oaria-teal)] rounded-full"
                animate={{ scale: [1, 1.5, 1] }}
                transition={{ repeat: Infinity, duration: 1 }}
              />
            )}
          </div>
          <span className="font-semibold text-sm">실시간 활동</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-[var(--oaria-text-secondary)]">
            {Math.floor(elapsedTime / 60)}:{(elapsedTime % 60).toString().padStart(2, "0")}
          </span>
          <button
            onClick={onClose}
            className="p-1 hover:bg-[var(--oaria-border)] rounded transition-colors"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Activity Feed */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-3 space-y-2"
      >
        <AnimatePresence initial={false}>
          {logs.map((log) => (
            <motion.div
              key={log.id}
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{
                type: "spring",
                stiffness: 500,
                damping: 30,
              }}
              className={`
                p-3 rounded-lg border
                ${getLogBg(log.type)}
              `}
            >
              <div className="flex items-start gap-2">
                <div className="mt-0.5">{getLogIcon(log.type)}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-semibold truncate">{log.title}</p>
                    <span className="text-[10px] text-[var(--oaria-text-secondary)] whitespace-nowrap">
                      {formatTime(log.timestamp)}
                    </span>
                  </div>
                  <p className="text-xs text-[var(--oaria-text-secondary)] mt-1 whitespace-pre-wrap line-clamp-3">
                    {log.description}
                  </p>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {/* Loading indicator */}
        {isLoading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-2 p-3 text-[var(--oaria-text-secondary)]"
          >
            <motion.div
              className="flex gap-1"
              animate={{ opacity: [0.5, 1, 0.5] }}
              transition={{ repeat: Infinity, duration: 1.5 }}
            >
              <span className="w-1.5 h-1.5 bg-[var(--oaria-teal)] rounded-full" />
              <span className="w-1.5 h-1.5 bg-[var(--oaria-teal)] rounded-full" />
              <span className="w-1.5 h-1.5 bg-[var(--oaria-teal)] rounded-full" />
            </motion.div>
            <span className="text-xs">에이전트가 작업 중입니다...</span>
          </motion.div>
        )}
      </div>

      {/* Summary Footer */}
      <div className="p-3 border-t border-[var(--oaria-border)] bg-[var(--oaria-border)]/30">
        <div className="grid grid-cols-3 gap-2 text-center">
          <div>
            <p className="text-lg font-bold text-purple-500">
              {logs.filter((l) => l.type === "thinking").length}
            </p>
            <p className="text-[10px] text-[var(--oaria-text-secondary)]">분석</p>
          </div>
          <div>
            <p className="text-lg font-bold text-yellow-500">
              {logs.filter((l) => l.type === "action").length}
            </p>
            <p className="text-[10px] text-[var(--oaria-text-secondary)]">실행</p>
          </div>
          <div>
            <p className="text-lg font-bold text-green-500">
              {logs.filter((l) => l.type === "result").length}
            </p>
            <p className="text-[10px] text-[var(--oaria-text-secondary)]">완료</p>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
