"use client";

import { useState } from "react";
import type { ActiveFilters } from "@/lib/types";
import { NODE_COLORS } from "@/lib/types";

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
  const [isExpanded, setIsExpanded] = useState(true);

  const filterTypes: Array<{ key: keyof ActiveFilters; label: string }> = [
    { key: "paper", label: "Papers" },
    { key: "author", label: "Authors" },
    { key: "keyword", label: "Keywords" },
    { key: "concept", label: "Concepts" },
  ];

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        background: "rgba(10, 14, 26, 0.9)",
        backdropFilter: "blur(20px)",
        border: "1px solid rgba(255, 255, 255, 0.1)",
        width: "280px",
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
        style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div className="flex items-center gap-2">
          <span className="text-white text-sm font-semibold">Controls</span>
          <span className="px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400 text-[10px] font-medium">
            {nodeCount} nodes
          </span>
          <span className="px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-400 text-[10px] font-medium">
            {linkCount} links
          </span>
        </div>
        <svg
          className={`w-4 h-4 text-white/40 transition-transform ${isExpanded ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>

      {isExpanded && (
        <div className="p-4 space-y-4">
          {/* Search */}
          <div>
            <label className="text-white/40 text-[10px] uppercase tracking-wider mb-2 block">
              Search
            </label>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Filter nodes..."
              className="w-full px-3 py-2 rounded-lg text-white text-sm placeholder-white/30 outline-none transition-colors"
              style={{
                background: "rgba(255,255,255,0.05)",
                border: "1px solid rgba(255,255,255,0.1)",
              }}
            />
          </div>

          {/* Filters */}
          <div>
            <label className="text-white/40 text-[10px] uppercase tracking-wider mb-2 block">
              Node Types
            </label>
            <div className="flex flex-wrap gap-2">
              {filterTypes.map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => onFilterToggle(key)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    activeFilters[key]
                      ? "text-white"
                      : "text-white/30 hover:text-white/50"
                  }`}
                  style={{
                    background: activeFilters[key]
                      ? `${NODE_COLORS[key]}33`
                      : "rgba(255,255,255,0.03)",
                    border: `1px solid ${activeFilters[key] ? NODE_COLORS[key] : "rgba(255,255,255,0.1)"}`,
                  }}
                >
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ background: NODE_COLORS[key] }}
                  />
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Similarity Threshold */}
          <div>
            <label className="text-white/40 text-[10px] uppercase tracking-wider mb-2 flex items-center justify-between">
              <span>Similarity Threshold</span>
              <span className="text-white font-medium">{Math.round(minSimilarity * 100)}%</span>
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={minSimilarity}
              onChange={(e) => onSimilarityChange(parseFloat(e.target.value))}
              className="w-full h-1 rounded-full appearance-none cursor-pointer"
              style={{
                background: `linear-gradient(to right, #3b82f6 0%, #3b82f6 ${minSimilarity * 100}%, rgba(255,255,255,0.1) ${minSimilarity * 100}%, rgba(255,255,255,0.1) 100%)`,
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
