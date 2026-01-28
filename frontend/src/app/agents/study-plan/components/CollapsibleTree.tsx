"use client";

import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronRight, ChevronDown, Copy, Check } from "lucide-react";

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

interface CollapsibleTreeProps {
  data: Record<string, unknown> | unknown[] | unknown;
  initialExpanded?: boolean;
  maxDepth?: number;
  highlightKeys?: string[];
  showCopyButton?: boolean;
  className?: string;
}

interface TreeNodeProps {
  keyName: string | number;
  value: unknown;
  depth: number;
  maxDepth: number;
  highlightKeys: string[];
  initialExpanded: boolean;
}

// ─────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────

const getValueType = (value: unknown): string => {
  if (value === null) return "null";
  if (value === undefined) return "undefined";
  if (Array.isArray(value)) return "array";
  return typeof value;
};

const getValueColor = (value: unknown): string => {
  const type = getValueType(value);
  switch (type) {
    case "string":
      return "text-green-600 dark:text-green-400";
    case "number":
      return "text-blue-600 dark:text-blue-400";
    case "boolean":
      return "text-purple-600 dark:text-purple-400";
    case "null":
    case "undefined":
      return "text-gray-400 dark:text-gray-500";
    default:
      return "text-[var(--oaria-text-primary)]";
  }
};

const formatValue = (value: unknown): string => {
  if (value === null) return "null";
  if (value === undefined) return "undefined";
  if (typeof value === "string") {
    // Truncate long strings
    if (value.length > 100) {
      return `"${value.slice(0, 100)}..."`;
    }
    return `"${value}"`;
  }
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return String(value);
  return String(value);
};

const isExpandable = (value: unknown): boolean => {
  if (value === null || value === undefined) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value).length > 0;
  return false;
};

// ─────────────────────────────────────────────────────────────
// TreeNode Component
// ─────────────────────────────────────────────────────────────

function TreeNode({
  keyName,
  value,
  depth,
  maxDepth,
  highlightKeys,
  initialExpanded,
}: TreeNodeProps) {
  const [expanded, setExpanded] = useState(initialExpanded && depth < 2);
  const expandable = isExpandable(value);
  const isHighlighted = highlightKeys.includes(String(keyName));

  // Max depth reached
  if (depth > maxDepth) {
    return (
      <div className="ml-4 text-xs text-gray-400">
        <span className="font-medium">{keyName}: </span>
        <span>{"{ ... }"}</span>
      </div>
    );
  }

  // Render expandable node (object or array)
  if (expandable && typeof value === "object" && value !== null) {
    const entries = Array.isArray(value)
      ? value.map((v, i) => [i, v] as [number, unknown])
      : Object.entries(value);
    const isArray = Array.isArray(value);
    const itemCount = entries.length;

    return (
      <div className="ml-2">
        <button
          onClick={() => setExpanded(!expanded)}
          className={`flex items-center gap-1 hover:bg-[var(--oaria-bg-secondary)] rounded px-1 -ml-1 transition-colors ${
            isHighlighted ? "bg-yellow-100 dark:bg-yellow-900/30" : ""
          }`}
        >
          <motion.div
            animate={{ rotate: expanded ? 90 : 0 }}
            transition={{ duration: 0.15 }}
          >
            <ChevronRight size={14} className="text-gray-400" />
          </motion.div>
          <span className="font-medium text-sm text-[var(--oaria-text-primary)]">
            {keyName}
          </span>
          <span className="text-xs text-gray-400 ml-1">
            {isArray ? `[${itemCount}]` : `{${itemCount}}`}
          </span>
        </button>

        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.15 }}
              className="ml-3 border-l border-gray-200 dark:border-gray-700 pl-2"
            >
              {entries.map(([k, v]) => (
                <TreeNode
                  key={String(k)}
                  keyName={k}
                  value={v}
                  depth={depth + 1}
                  maxDepth={maxDepth}
                  highlightKeys={highlightKeys}
                  initialExpanded={initialExpanded}
                />
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    );
  }

  // Render leaf node (primitive value)
  return (
    <div
      className={`ml-2 flex items-baseline gap-1 text-sm py-0.5 ${
        isHighlighted ? "bg-yellow-100 dark:bg-yellow-900/30 rounded px-1 -ml-1" : ""
      }`}
    >
      <span className="font-medium text-[var(--oaria-text-secondary)]">
        {keyName}:
      </span>
      <span className={`font-mono text-xs ${getValueColor(value)}`}>
        {formatValue(value)}
      </span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────

export function CollapsibleTree({
  data,
  initialExpanded = true,
  maxDepth = 5,
  highlightKeys = [],
  showCopyButton = true,
  className = "",
}: CollapsibleTreeProps) {
  const [copied, setCopied] = useState(false);

  // Handle copy
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  // Memoize entries
  const entries = useMemo(() => {
    if (data === null || data === undefined) return [];
    if (Array.isArray(data)) {
      return data.map((v, i) => [i, v] as [number, unknown]);
    }
    if (typeof data === "object") {
      return Object.entries(data);
    }
    return [];
  }, [data]);

  // Handle primitive values
  if (data === null || data === undefined || typeof data !== "object") {
    return (
      <div className={`text-sm ${className}`}>
        <span className={`font-mono ${getValueColor(data)}`}>
          {formatValue(data)}
        </span>
      </div>
    );
  }

  // Empty object/array
  if (entries.length === 0) {
    return (
      <div className={`text-sm text-gray-400 ${className}`}>
        {Array.isArray(data) ? "[]" : "{}"}
      </div>
    );
  }

  return (
    <div className={`relative ${className}`}>
      {/* Copy button */}
      {showCopyButton && (
        <button
          onClick={handleCopy}
          className="absolute top-0 right-0 p-1.5 rounded-md hover:bg-[var(--oaria-bg-secondary)] transition-colors"
          title="JSON 복사"
        >
          {copied ? (
            <Check size={14} className="text-green-500" />
          ) : (
            <Copy size={14} className="text-gray-400" />
          )}
        </button>
      )}

      {/* Tree */}
      <div className="font-mono text-xs">
        {entries.map(([key, value]) => (
          <TreeNode
            key={String(key)}
            keyName={key}
            value={value}
            depth={0}
            maxDepth={maxDepth}
            highlightKeys={highlightKeys}
            initialExpanded={initialExpanded}
          />
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Compact Variant (for inline display)
// ─────────────────────────────────────────────────────────────

interface CompactJsonProps {
  data: unknown;
  maxLength?: number;
  className?: string;
}

export function CompactJson({
  data,
  maxLength = 50,
  className = "",
}: CompactJsonProps) {
  const jsonStr = useMemo(() => {
    try {
      const str = JSON.stringify(data);
      if (str.length > maxLength) {
        return str.slice(0, maxLength) + "...";
      }
      return str;
    } catch {
      return String(data);
    }
  }, [data, maxLength]);

  return (
    <code
      className={`text-xs font-mono px-1.5 py-0.5 rounded bg-[var(--oaria-bg-secondary)] text-[var(--oaria-text-secondary)] ${className}`}
    >
      {jsonStr}
    </code>
  );
}
