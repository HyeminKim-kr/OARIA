"use client";

import { X, ExternalLink } from "lucide-react";
import type { GraphNode, GraphLink } from "../types";
import { NODE_COLORS, LINK_COLORS, LINK_LABELS } from "../constants";

interface NodeDetailPanelProps {
  node: GraphNode | null;
  nodes: GraphNode[];
  links: GraphLink[];
  onClose: () => void;
}

export default function NodeDetailPanel({
  node,
  nodes,
  links,
  onClose,
}: NodeDetailPanelProps) {
  if (!node) return null;

  // 연결된 링크 찾기
  const connectedLinks = links.filter((l) => {
    const sourceId = typeof l.source === "string" ? l.source : l.source.id;
    const targetId = typeof l.target === "string" ? l.target : l.target.id;
    return sourceId === node.id || targetId === node.id;
  });

  // 링크 타입별 그룹화
  const grouped: Record<string, Array<{ node: GraphNode; link: GraphLink }>> = {
    similar: [],
    authored: [],
    contains: [],
  };

  connectedLinks.forEach((l) => {
    const sourceId = typeof l.source === "string" ? l.source : l.source.id;
    const targetId = typeof l.target === "string" ? l.target : l.target.id;
    const otherId = sourceId === node.id ? targetId : sourceId;
    const otherNode = nodes.find((n) => n.id === otherId);
    if (otherNode && grouped[l.type]) {
      grouped[l.type].push({ node: otherNode, link: l });
    }
  });

  const nodeColor = NODE_COLORS[node.type] || "#888";
  const nodeIcon = node.type === "paper" ? "📄" : node.type === "author" ? "👤" : "🏷️";

  return (
    <div
      className="absolute bottom-0 left-0 right-0 z-[110] transform transition-transform duration-300 ease-out"
      style={{ animation: "slideUp 0.3s ease-out" }}
    >
      <style jsx>{`
        @keyframes slideUp {
          from {
            transform: translateY(100%);
          }
          to {
            transform: translateY(0);
          }
        }
      `}</style>

      {/* Top Gradient Line */}
      <div
        className="h-px w-full"
        style={{
          background:
            "linear-gradient(90deg,transparent,rgba(59,130,246,0.5) 30%,rgba(139,92,246,0.5) 70%,transparent)",
        }}
      />

      {/* Panel Content */}
      <div
        className="max-w-6xl mx-auto overflow-hidden"
        style={{
          background: "rgba(8,12,24,0.94)",
          backdropFilter: "blur(24px)",
          borderLeft: "1px solid rgba(255,255,255,0.06)",
          borderRight: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        <div className="flex h-72">
          {/* Color Strip */}
          <div
            className="w-1.5 shrink-0"
            style={{
              background: `linear-gradient(180deg,${nodeColor},${nodeColor}80)`,
            }}
          />

          {/* Main Content */}
          <div className="flex-1 p-6 flex flex-col min-w-0 overflow-y-auto">
            {/* Header */}
            <div className="flex items-center gap-3 mb-3">
              <span
                className="px-2.5 py-1 rounded-md text-[10px] font-bold uppercase text-white tracking-wider"
                style={{ background: nodeColor }}
              >
                {node.type}
              </span>
              <span className="text-slate-600 text-xs">{nodeIcon}</span>
              <button
                onClick={onClose}
                className="ml-auto w-7 h-7 rounded-md flex items-center justify-center text-slate-600 hover:text-white hover:bg-white/10 transition-all"
              >
                <X size={16} />
              </button>
            </div>

            {/* Title */}
            <h3 className="text-white font-bold text-xl leading-snug mb-3 tracking-tight">
              {node.label}
            </h3>

            {/* Metadata */}
            {node.type === "paper" && node.metadata && (
              <>
                <div className="flex flex-wrap gap-3 text-xs mb-4">
                  <span
                    className="px-2 py-0.5 rounded"
                    style={{
                      background: `${nodeColor}20`,
                      color: nodeColor,
                      border: `1px solid ${nodeColor}40`,
                    }}
                  >
                    {node.metadata.journal || "N/A"}
                  </span>
                  <span className="text-slate-500">{node.metadata.pubdate || ""}</span>
                  <span className="text-slate-500 font-mono">
                    PMID: {node.metadata.pmid || ""}
                  </span>
                </div>

                {/* Abstract */}
                <div className="flex-1 min-h-0 relative">
                  <p className="text-slate-400 text-sm leading-relaxed">
                    {node.metadata.abstract || ""}
                  </p>
                  <div
                    className="absolute bottom-0 left-0 right-0 h-10 pointer-events-none"
                    style={{
                      background: "linear-gradient(transparent,rgba(8,12,24,0.94))",
                    }}
                  />
                </div>
              </>
            )}

            {node.type === "author" && node.metadata && (
              <div className="text-slate-400 text-sm">
                📝 {node.metadata.paper_count} papers published
              </div>
            )}
          </div>

          {/* Divider */}
          <div
            className="w-px self-stretch my-4"
            style={{
              background:
                "linear-gradient(transparent,rgba(255,255,255,0.08),transparent)",
            }}
          />

          {/* Connections Panel */}
          <div className="w-80 p-5 flex flex-col overflow-y-auto shrink-0">
            <div className="text-[9px] font-bold text-slate-500 uppercase tracking-[0.1em] mb-3">
              Connections
            </div>

            <div className="space-y-3 flex-1 text-xs">
              {Object.entries(grouped).map(([type, items]) => {
                if (!items.length) return null;
                const linkColor = LINK_COLORS[type] || "#666";

                return (
                  <div key={type} className="mb-3">
                    <div className="flex items-center gap-2 mb-2">
                      <span
                        className="w-1 h-3 rounded-full"
                        style={{ background: linkColor }}
                      />
                      <span
                        className="text-[9px] font-bold uppercase tracking-[0.12em]"
                        style={{ color: linkColor }}
                      >
                        {LINK_LABELS[type] || type}
                      </span>
                      <span className="text-[10px] font-mono text-slate-600 ml-auto">
                        {items.length}
                      </span>
                    </div>

                    {items.slice(0, 5).map(({ node: n, link: l }) => (
                      <div
                        key={n.id}
                        className="py-2 px-2.5 rounded-lg mb-1 transition-all hover:bg-white/[0.04]"
                        style={{
                          background: "rgba(255,255,255,0.02)",
                          border: "1px solid rgba(255,255,255,0.04)",
                        }}
                      >
                        <div className="flex items-center gap-2">
                          <span
                            className="w-2 h-2 rounded-full shrink-0"
                            style={{
                              background: NODE_COLORS[n.type],
                              boxShadow: `0 0 4px ${NODE_COLORS[n.type]}60`,
                            }}
                          />
                          <span className="text-slate-300 text-[11px] font-medium truncate flex-1">
                            {n.label}
                          </span>
                        </div>

                        {l.type === "similar" && l.similarity && (
                          <div className="flex items-center gap-2 mt-1">
                            <div
                              className="flex-1 h-[3px] rounded-full overflow-hidden"
                              style={{ background: "rgba(255,255,255,0.06)" }}
                            >
                              <div
                                className="h-full rounded-full"
                                style={{
                                  width: `${l.similarity * 100}%`,
                                  background: linkColor,
                                  opacity: 0.7,
                                }}
                              />
                            </div>
                            <span
                              className="text-[10px] font-mono font-bold"
                              style={{ color: linkColor }}
                            >
                              {(l.similarity * 100).toFixed(0)}%
                            </span>
                          </div>
                        )}
                      </div>
                    ))}

                    {items.length > 5 && (
                      <div className="text-[10px] text-slate-600 text-center mt-1">
                        +{items.length - 5} more
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Footer Stats */}
            <div className="mt-3 pt-3 border-t border-white/[0.06] flex items-center gap-5">
              <div>
                <span className="text-[9px] text-slate-600 font-bold uppercase tracking-wider block mb-0.5">
                  Citations
                </span>
                <span className="text-base font-mono font-bold text-white">
                  {node.type === "paper"
                    ? Math.floor(Math.random() * 2000 + 100).toLocaleString()
                    : "--"}
                </span>
              </div>
              <div>
                <span className="text-[9px] text-slate-600 font-bold uppercase tracking-wider block mb-0.5">
                  Certainty
                </span>
                <span className="text-base font-mono font-bold text-white">
                  {node.metadata?.certainty_score
                    ? `${(node.metadata.certainty_score * 100).toFixed(0)}%`
                    : "--"}
                </span>
              </div>

              {node.type === "paper" && node.metadata?.pmid && (
                <a
                  href={`https://pubmed.ncbi.nlm.nih.gov/${node.metadata.pmid}/`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ml-auto px-4 py-2 text-white text-[11px] font-bold rounded-lg transition-all hover:scale-105 flex items-center gap-1"
                  style={{
                    background: "linear-gradient(135deg,#2563eb,#7c3aed)",
                    boxShadow: "0 4px 12px rgba(37,99,235,0.3)",
                  }}
                >
                  PubMed
                  <ExternalLink size={12} />
                </a>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
