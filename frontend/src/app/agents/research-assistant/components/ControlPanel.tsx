"use client";

import { Search } from "lucide-react";
import type { ActiveFilters } from "../types";
import { NODE_COLORS } from "../constants";

interface ControlPanelProps {
  nodeCount: number;
  linkCount: number;
  activeFilters: ActiveFilters;
  onFilterToggle: (type: keyof ActiveFilters) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  minSimilarity: number;
  onSimilarityChange: (value: number) => void;
}

export default function ControlPanel({
  nodeCount,
  linkCount,
  activeFilters,
  onFilterToggle,
  searchQuery,
  onSearchChange,
  minSimilarity,
  onSimilarityChange,
}: ControlPanelProps) {
  const filterButtons = [
    { type: "paper" as const, label: "Paper", color: NODE_COLORS.paper },
    { type: "author" as const, label: "Author", color: NODE_COLORS.author },
    { type: "keyword" as const, label: "Keyword", color: NODE_COLORS.keyword },
  ];

  return (
    <div
      className="absolute top-5 left-5 z-[110] w-60 rounded-2xl overflow-hidden shadow-2xl"
      style={{
        background: "rgba(10, 14, 26, 0.82)",
        backdropFilter: "blur(20px)",
        border: "1px solid rgba(255, 255, 255, 0.08)",
      }}
    >
      {/* Header */}
      <div className="p-5 pb-4">
        <div className="flex items-center gap-2.5 mb-1">
          <div
            className="w-2 h-2 rounded-full bg-blue-500"
            style={{ boxShadow: "0 0 8px #3b82f680" }}
          />
          <h2 className="text-white font-bold text-base tracking-tight">
            Vector Graph
          </h2>
          <span className="ml-auto text-[9px] font-mono text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded">
            v4
          </span>
        </div>
        <p className="text-slate-500 text-[11px] font-medium ml-[18px]">
          {nodeCount} nodes · {linkCount} links
        </p>
      </div>

      {/* Node Type Filters */}
      <div className="px-5 pb-4">
        <div className="text-[9px] font-bold text-slate-500 uppercase tracking-[0.1em] mb-2.5">
          Node Types
        </div>
        <div className="flex flex-wrap gap-1.5">
          {filterButtons.map(({ type, label, color }) => (
            <button
              key={type}
              onClick={() => onFilterToggle(type)}
              className="px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-all hover:scale-105"
              style={{
                border: `1.5px solid ${color}`,
                background: activeFilters[type] ? color : "transparent",
                color: activeFilters[type] ? "#fff" : color,
                boxShadow: activeFilters[type] ? `0 2px 8px ${color}4d` : "none",
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="mx-5 border-t border-white/[0.06]" />

      {/* Search */}
      <div className="p-5 pb-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search nodes..."
            className="w-full pl-9 pr-3 py-2.5 rounded-lg text-xs text-white placeholder-slate-600 outline-none focus:ring-1 focus:ring-blue-500/50 transition-all"
            style={{
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(255,255,255,0.08)",
            }}
          />
        </div>
      </div>

      <div className="mx-5 border-t border-white/[0.06]" />

      {/* Similarity Slider */}
      <div className="p-5 pb-4">
        <div className="flex justify-between items-center mb-3">
          <span className="text-[9px] font-bold text-slate-500 uppercase tracking-[0.1em]">
            Similarity
          </span>
          <span className="text-xs font-mono font-bold text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded">
            {minSimilarity.toFixed(2)}
          </span>
        </div>
        <input
          type="range"
          min="0.5"
          max="0.95"
          step="0.05"
          value={minSimilarity}
          onChange={(e) => onSimilarityChange(parseFloat(e.target.value))}
          className="w-full accent-blue-500 h-1"
        />
      </div>

      <div className="mx-5 border-t border-white/[0.06]" />

      {/* Instructions */}
      <div className="p-5 pb-4">
        <div className="text-[9px] font-bold text-slate-500 uppercase tracking-[0.1em] mb-2">
          Controls
        </div>
        <div className="space-y-1 text-[10px] text-slate-500">
          <div className="flex items-center gap-2">
            <span className="w-4 text-center">🖱</span>
            <span>Drag to rotate</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-4 text-center">⚲</span>
            <span>Scroll to zoom</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-4 text-center">👆</span>
            <span>Click node for details</span>
          </div>
        </div>
      </div>
    </div>
  );
}
