"use client";

import type { GraphNode, GraphLink } from "@/lib/types";
import { NODE_COLORS, LINK_COLORS } from "@/lib/types";

interface NodeDetailPanelProps {
  node: GraphNode;
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
  // 연결된 노드들 찾기
  const connectedLinks = links.filter(
    (l) => l.source === node.id || l.target === node.id
  );

  const connectedNodes = connectedLinks.map((link) => {
    const connectedId = link.source === node.id ? link.target : link.source;
    const connectedNode = nodes.find((n) => n.id === connectedId);
    return {
      node: connectedNode,
      link,
      similarity: link.similarity ?? 1,
    };
  }).filter((item) => item.node);

  return (
    <div
      className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 rounded-xl overflow-hidden"
      style={{
        background: "rgba(10, 14, 26, 0.95)",
        backdropFilter: "blur(20px)",
        border: "1px solid rgba(255, 255, 255, 0.1)",
        width: "min(600px, 90vw)",
        maxHeight: "50vh",
      }}
    >
      {/* Header */}
      <div
        className="flex items-start justify-between p-4"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div className="flex-1 min-w-0 pr-4">
          <div className="flex items-center gap-2 mb-1">
            <span
              className="w-3 h-3 rounded-full"
              style={{ background: NODE_COLORS[node.type] }}
            />
            <span className="text-white/40 text-xs uppercase">{node.type}</span>
          </div>
          <h3 className="text-white font-semibold text-lg truncate">{node.label}</h3>
          {node.metadata?.journal && (
            <p className="text-blue-400 text-sm mt-1">{node.metadata.journal}</p>
          )}
        </div>
        <button
          onClick={onClose}
          className="w-8 h-8 rounded-lg flex items-center justify-center text-white/40 hover:text-white hover:bg-white/10 transition-all"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div className="p-4 overflow-y-auto" style={{ maxHeight: "calc(50vh - 100px)" }}>
        {/* Metadata */}
        {node.metadata && (
          <div className="grid grid-cols-2 gap-3 mb-4">
            {node.metadata.pmid && (
              <div className="p-3 rounded-lg" style={{ background: "rgba(255,255,255,0.03)" }}>
                <span className="text-white/40 text-[10px] uppercase block">PMID</span>
                <span className="text-white text-sm">{node.metadata.pmid}</span>
              </div>
            )}
            {node.metadata.pubdate && (
              <div className="p-3 rounded-lg" style={{ background: "rgba(255,255,255,0.03)" }}>
                <span className="text-white/40 text-[10px] uppercase block">Date</span>
                <span className="text-white text-sm">{node.metadata.pubdate}</span>
              </div>
            )}
            {node.metadata.certainty_score !== undefined && (
              <div className="p-3 rounded-lg" style={{ background: "rgba(255,255,255,0.03)" }}>
                <span className="text-white/40 text-[10px] uppercase block">Certainty</span>
                <span className="text-white text-sm">{Math.round(node.metadata.certainty_score * 100)}%</span>
              </div>
            )}
            {node.metadata.paper_count !== undefined && (
              <div className="p-3 rounded-lg" style={{ background: "rgba(255,255,255,0.03)" }}>
                <span className="text-white/40 text-[10px] uppercase block">Papers</span>
                <span className="text-white text-sm">{node.metadata.paper_count}</span>
              </div>
            )}
          </div>
        )}

        {/* Abstract */}
        {node.metadata?.abstract && (
          <div className="mb-4">
            <span className="text-white/40 text-[10px] uppercase block mb-2">Abstract</span>
            <p className="text-white/70 text-sm leading-relaxed">{node.metadata.abstract}</p>
          </div>
        )}

        {/* Connected Nodes */}
        {connectedNodes.length > 0 && (
          <div>
            <span className="text-white/40 text-[10px] uppercase block mb-2">
              Connected ({connectedNodes.length})
            </span>
            <div className="space-y-2">
              {connectedNodes.slice(0, 5).map(({ node: connNode, link, similarity }) => (
                connNode && (
                  <div
                    key={connNode.id}
                    className="flex items-center justify-between p-2 rounded-lg"
                    style={{ background: "rgba(255,255,255,0.03)" }}
                  >
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <span
                        className="w-2 h-2 rounded-full flex-shrink-0"
                        style={{ background: NODE_COLORS[connNode.type] }}
                      />
                      <span className="text-white text-sm truncate">{connNode.label}</span>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span
                        className="px-2 py-0.5 rounded text-[10px]"
                        style={{
                          background: `${LINK_COLORS[link.type]}33`,
                          color: LINK_COLORS[link.type],
                        }}
                      >
                        {link.type}
                      </span>
                      <span className="text-white/40 text-xs">
                        {Math.round(similarity * 100)}%
                      </span>
                    </div>
                  </div>
                )
              ))}
              {connectedNodes.length > 5 && (
                <p className="text-white/30 text-xs text-center">
                  +{connectedNodes.length - 5} more
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
