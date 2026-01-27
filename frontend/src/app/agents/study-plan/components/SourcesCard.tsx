"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BookOpen,
  FileText,
  Globe,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Quote,
} from "lucide-react";
import type { Source, PaperSource, SnippetSource, WebSource } from "../types";

interface SourcesCardProps {
  sources: Source[];
  summary?: string;
  action?: string;
  isLoading?: boolean;
}

export function SourcesCard({
  sources,
  summary,
  action,
  isLoading = false,
}: SourcesCardProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [selectedSource, setSelectedSource] = useState<number | null>(null);

  // Filter sources by type
  const paperSources = sources.filter((s): s is PaperSource => s.type === "paper");
  const snippetSources = sources.filter((s): s is SnippetSource => s.type === "snippet");
  const webSources = sources.filter((s): s is WebSource => s.type === "web");

  const totalCount = sources.length;
  const paperCount = paperSources.length;

  // Get relevance color
  const getRelevanceColor = (relevance?: number) => {
    if (!relevance) return "text-gray-400";
    if (relevance >= 0.8) return "text-green-500";
    if (relevance >= 0.6) return "text-yellow-500";
    return "text-orange-500";
  };

  // Get relevance label
  const getRelevanceLabel = (relevance?: number) => {
    if (!relevance) return "";
    return `${(relevance * 100).toFixed(0)}%`;
  };

  // Render individual paper source
  const renderPaperSource = (source: PaperSource, index: number) => {
    const isSelected = selectedSource === source.id;

    return (
      <motion.div
        key={`paper-${source.id}`}
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: index * 0.05 }}
        className={`
          group relative p-3 rounded-lg border transition-all cursor-pointer
          ${isSelected
            ? "border-[var(--oaria-teal)] bg-[var(--oaria-teal)]/5"
            : "border-transparent hover:border-[var(--oaria-border)] hover:bg-[var(--oaria-surface)]"
          }
        `}
        onClick={() => setSelectedSource(isSelected ? null : source.id)}
      >
        <div className="flex items-start gap-3">
          {/* Source Number Badge */}
          <div className="flex-shrink-0 w-6 h-6 rounded-full bg-[var(--oaria-teal)]/10 text-[var(--oaria-teal)] flex items-center justify-center text-xs font-bold">
            {source.id}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            {/* Title */}
            <h4 className="text-sm font-medium text-[var(--foreground)] line-clamp-2 group-hover:text-[var(--oaria-teal)] transition-colors">
              {source.title}
            </h4>

            {/* Meta Info */}
            <div className="flex items-center gap-2 mt-1 text-xs text-[var(--oaria-text-secondary)]">
              {source.journal && (
                <span className="truncate max-w-[150px]">{source.journal}</span>
              )}
              {source.year && (
                <>
                  <span className="opacity-50">·</span>
                  <span>{source.year}</span>
                </>
              )}
              {source.relevance !== undefined && (
                <>
                  <span className="opacity-50">·</span>
                  <span className={getRelevanceColor(source.relevance)}>
                    관련도 {getRelevanceLabel(source.relevance)}
                  </span>
                </>
              )}
            </div>

            {/* Authors (shown when selected) */}
            <AnimatePresence>
              {isSelected && source.authors && source.authors.length > 0 && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="mt-2 text-xs text-[var(--oaria-text-secondary)]"
                >
                  <span className="font-medium">저자:</span>{" "}
                  {source.authors.join(", ")}
                  {source.pmid && (
                    <a
                      href={`https://pubmed.ncbi.nlm.nih.gov/${source.pmid}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-2 inline-flex items-center gap-1 text-[var(--oaria-teal)] hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      PubMed <ExternalLink size={10} />
                    </a>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Icon */}
          <BookOpen
            size={16}
            className="flex-shrink-0 text-[var(--oaria-text-secondary)] opacity-50 group-hover:opacity-100"
          />
        </div>
      </motion.div>
    );
  };

  // Render snippet source
  const renderSnippetSource = (source: SnippetSource, index: number) => (
    <motion.div
      key={`snippet-${source.id}`}
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05 }}
      className="p-3 rounded-lg bg-[var(--oaria-surface)] border border-[var(--oaria-border)]"
    >
      <div className="flex items-start gap-2">
        <Quote size={14} className="flex-shrink-0 mt-1 text-purple-500 opacity-60" />
        <div className="flex-1 min-w-0">
          <p className="text-xs text-[var(--oaria-text-secondary)] italic line-clamp-3">
            "{source.text}"
          </p>
          {source.section && (
            <p className="mt-1 text-[10px] text-[var(--oaria-text-secondary)] opacity-60">
              — {source.section}
            </p>
          )}
        </div>
      </div>
    </motion.div>
  );

  // Render web source
  const renderWebSource = (source: WebSource) => (
    <a
      key={`web-${source.id}`}
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-2 p-2 rounded-lg hover:bg-[var(--oaria-surface)] transition-colors"
    >
      <Globe size={14} className="text-blue-500" />
      <span className="text-xs truncate flex-1">{source.title}</span>
      <ExternalLink size={12} className="text-[var(--oaria-text-secondary)]" />
    </a>
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border-2 border-[var(--oaria-teal)]/30 bg-[var(--oaria-teal)]/5 overflow-hidden"
    >
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-[var(--oaria-teal)]/10 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[var(--oaria-teal)]/20 flex items-center justify-center">
            <BookOpen size={18} className="text-[var(--oaria-teal)]" />
          </div>
          <div className="text-left">
            <h3 className="text-sm font-semibold text-[var(--foreground)]">
              Sources
            </h3>
            <p className="text-xs text-[var(--oaria-text-secondary)]">
              {paperCount > 0 && `논문 ${paperCount}편`}
              {snippetSources.length > 0 && ` · 인용 ${snippetSources.length}개`}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Total Count Badge */}
          <span className="px-2 py-0.5 rounded-full bg-[var(--oaria-teal)]/20 text-[var(--oaria-teal)] text-xs font-bold">
            {totalCount}
          </span>
          {isExpanded ? (
            <ChevronUp size={18} className="text-[var(--oaria-text-secondary)]" />
          ) : (
            <ChevronDown size={18} className="text-[var(--oaria-text-secondary)]" />
          )}
        </div>
      </button>

      {/* Summary Message */}
      {summary && (
        <div className="px-4 pb-3 -mt-1">
          <p className="text-sm text-[var(--oaria-teal)] font-medium">
            {summary}
          </p>
        </div>
      )}

      {/* Expanded Content */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="px-4 pb-4 space-y-1">
              {/* Paper Sources */}
              {paperSources.length > 0 && (
                <div className="space-y-1">
                  {paperSources.map((source, index) => renderPaperSource(source, index))}
                </div>
              )}

              {/* Snippet Sources */}
              {snippetSources.length > 0 && (
                <div className="mt-3 pt-3 border-t border-[var(--oaria-border)]">
                  <div className="flex items-center gap-2 mb-2">
                    <FileText size={14} className="text-purple-500" />
                    <span className="text-xs font-medium text-[var(--oaria-text-secondary)]">
                      관련 인용
                    </span>
                  </div>
                  <div className="space-y-2">
                    {snippetSources.map((source, index) => renderSnippetSource(source, index))}
                  </div>
                </div>
              )}

              {/* Web Sources */}
              {webSources.length > 0 && (
                <div className="mt-3 pt-3 border-t border-[var(--oaria-border)]">
                  <div className="flex items-center gap-2 mb-2">
                    <Globe size={14} className="text-blue-500" />
                    <span className="text-xs font-medium text-[var(--oaria-text-secondary)]">
                      웹 자료
                    </span>
                  </div>
                  <div className="space-y-1">
                    {webSources.map(renderWebSource)}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Loading Indicator */}
      {isLoading && (
        <div className="px-4 pb-4">
          <div className="flex items-center gap-2 text-[var(--oaria-text-secondary)]">
            <motion.div
              className="flex gap-1"
              animate={{ opacity: [0.5, 1, 0.5] }}
              transition={{ repeat: Infinity, duration: 1.5 }}
            >
              <span className="w-1.5 h-1.5 bg-[var(--oaria-teal)] rounded-full" />
              <span className="w-1.5 h-1.5 bg-[var(--oaria-teal)] rounded-full" />
              <span className="w-1.5 h-1.5 bg-[var(--oaria-teal)] rounded-full" />
            </motion.div>
            <span className="text-xs">더 많은 자료를 찾고 있어요...</span>
          </div>
        </div>
      )}
    </motion.div>
  );
}
