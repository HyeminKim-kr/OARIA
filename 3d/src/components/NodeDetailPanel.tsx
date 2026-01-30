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

  // 타입별 연결 노드 분류
  const connectedByType = {
    paper: connectedNodes.filter(({ node }) => node?.type === "paper"),
    author: connectedNodes.filter(({ node }) => node?.type === "author"),
    keyword: connectedNodes.filter(({ node }) => node?.type === "keyword"),
    concept: connectedNodes.filter(({ node }) => node?.type === "concept"),
  };

  // PubMed 링크 생성
  const pubmedUrl = node.metadata?.pmid
    ? `https://pubmed.ncbi.nlm.nih.gov/${node.metadata.pmid}/`
    : null;

  return (
    <div
      className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 rounded-xl overflow-hidden"
      style={{
        background: "rgba(10, 14, 26, 0.95)",
        backdropFilter: "blur(20px)",
        border: "1px solid rgba(255, 255, 255, 0.1)",
        width: "min(900px, 95vw)",
        maxHeight: "280px",
      }}
    >
      {/* Header - Compact */}
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <span
            className="w-3 h-3 rounded-full flex-shrink-0"
            style={{ background: NODE_COLORS[node.type], boxShadow: `0 0 8px ${NODE_COLORS[node.type]}` }}
          />
          <span className="text-white/50 text-[10px] uppercase tracking-wider">{node.type}</span>
          <h3 className="text-white font-semibold text-sm truncate flex-1">{node.label}</h3>
          {node.metadata?.journal && (
            <span className="text-blue-400 text-xs truncate max-w-[200px]">{node.metadata.journal}</span>
          )}
          {node.metadata?.pubdate && (
            <span className="text-white/40 text-xs">{node.metadata.pubdate}</span>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 ml-4">
          {/* 논문 바로가기 버튼 */}
          {pubmedUrl && (
            <a
              href={pubmedUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all hover:scale-105"
              style={{
                background: "linear-gradient(135deg, #2563eb, #7c3aed)",
                color: "white",
              }}
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
              논문 바로가기
            </a>
          )}
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-lg flex items-center justify-center text-white/40 hover:text-white hover:bg-white/10 transition-all"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Content - Horizontal Layout */}
      <div className="flex overflow-hidden" style={{ height: "220px" }}>
        {/* Left: Metadata & Abstract */}
        <div className="w-1/3 p-3 overflow-y-auto border-r border-white/5">
          {/* Metadata badges */}
          <div className="flex flex-wrap gap-1.5 mb-3">
            {node.metadata?.certainty_score !== undefined && (
              <span className="px-2 py-1 rounded-md text-[10px] bg-emerald-500/20 text-emerald-400 font-medium">
                {Math.round(node.metadata.certainty_score * 100)}% match
              </span>
            )}
            {node.metadata?.pmid && (
              <span className="px-2 py-1 rounded-md text-[10px] bg-blue-500/20 text-blue-400 font-medium">
                PMID: {node.metadata.pmid}
              </span>
            )}
            {node.metadata?.paper_count !== undefined && (
              <span className="px-2 py-1 rounded-md text-[10px] bg-violet-500/20 text-violet-400 font-medium">
                {node.metadata.paper_count} papers
              </span>
            )}
          </div>

          {/* Abstract */}
          {node.metadata?.abstract && (
            <div>
              <span className="text-white/40 text-[9px] uppercase block mb-1">Abstract</span>
              <p className="text-white/60 text-[11px] leading-relaxed line-clamp-6">
                {node.metadata.abstract}
              </p>
            </div>
          )}
        </div>

        {/* Right: Connected Nodes - Grid Layout */}
        <div className="flex-1 p-3 overflow-y-auto">
          <div className="grid grid-cols-2 gap-3 h-full">
            {/* Papers */}
            {connectedByType.paper.length > 0 && (
              <div className="rounded-lg p-2.5" style={{ background: `${NODE_COLORS.paper}10`, border: `1px solid ${NODE_COLORS.paper}20` }}>
                <div className="flex items-center gap-1.5 mb-2">
                  <span className="w-2 h-2 rounded-full" style={{ background: NODE_COLORS.paper }} />
                  <span className="text-[10px] text-white/60 uppercase font-medium">Papers ({connectedByType.paper.length})</span>
                </div>
                <div className="space-y-1 max-h-[140px] overflow-y-auto">
                  {connectedByType.paper.slice(0, 6).map(({ node: connNode, similarity }) => (
                    connNode && (
                      <div key={connNode.id} className="flex items-center justify-between gap-2 p-1.5 rounded bg-black/20">
                        <span className="text-white/80 text-[10px] truncate flex-1">{connNode.label}</span>
                        <span className="text-white/40 text-[9px] flex-shrink-0">{Math.round(similarity * 100)}%</span>
                      </div>
                    )
                  ))}
                  {connectedByType.paper.length > 6 && (
                    <span className="text-white/30 text-[9px]">+{connectedByType.paper.length - 6} more</span>
                  )}
                </div>
              </div>
            )}

            {/* Authors */}
            {connectedByType.author.length > 0 && (
              <div className="rounded-lg p-2.5" style={{ background: `${NODE_COLORS.author}10`, border: `1px solid ${NODE_COLORS.author}20` }}>
                <div className="flex items-center gap-1.5 mb-2">
                  <span className="w-2 h-2 rounded-full" style={{ background: NODE_COLORS.author }} />
                  <span className="text-[10px] text-white/60 uppercase font-medium">Authors ({connectedByType.author.length})</span>
                </div>
                <div className="flex flex-wrap gap-1 max-h-[140px] overflow-y-auto">
                  {connectedByType.author.slice(0, 8).map(({ node: connNode }) => (
                    connNode && (
                      <span
                        key={connNode.id}
                        className="px-2 py-0.5 rounded text-[10px] text-white/80"
                        style={{ background: `${NODE_COLORS.author}30` }}
                      >
                        {connNode.label}
                      </span>
                    )
                  ))}
                  {connectedByType.author.length > 8 && (
                    <span className="text-white/30 text-[9px]">+{connectedByType.author.length - 8}</span>
                  )}
                </div>
              </div>
            )}

            {/* Keywords */}
            {connectedByType.keyword.length > 0 && (
              <div className="rounded-lg p-2.5" style={{ background: `${NODE_COLORS.keyword}10`, border: `1px solid ${NODE_COLORS.keyword}20` }}>
                <div className="flex items-center gap-1.5 mb-2">
                  <span className="w-2 h-2 rounded-full" style={{ background: NODE_COLORS.keyword }} />
                  <span className="text-[10px] text-white/60 uppercase font-medium">Keywords ({connectedByType.keyword.length})</span>
                </div>
                <div className="flex flex-wrap gap-1 max-h-[140px] overflow-y-auto">
                  {connectedByType.keyword.slice(0, 10).map(({ node: connNode }) => (
                    connNode && (
                      <span
                        key={connNode.id}
                        className="px-2 py-0.5 rounded text-[10px] text-white/80"
                        style={{ background: `${NODE_COLORS.keyword}30` }}
                      >
                        {connNode.label}
                      </span>
                    )
                  ))}
                  {connectedByType.keyword.length > 10 && (
                    <span className="text-white/30 text-[9px]">+{connectedByType.keyword.length - 10}</span>
                  )}
                </div>
              </div>
            )}

            {/* Concepts */}
            {connectedByType.concept.length > 0 && (
              <div className="rounded-lg p-2.5" style={{ background: `${NODE_COLORS.concept}10`, border: `1px solid ${NODE_COLORS.concept}20` }}>
                <div className="flex items-center gap-1.5 mb-2">
                  <span className="w-2 h-2 rounded-full" style={{ background: NODE_COLORS.concept }} />
                  <span className="text-[10px] text-white/60 uppercase font-medium">Concepts ({connectedByType.concept.length})</span>
                </div>
                <div className="flex flex-wrap gap-1 max-h-[140px] overflow-y-auto">
                  {connectedByType.concept.slice(0, 8).map(({ node: connNode }) => (
                    connNode && (
                      <span
                        key={connNode.id}
                        className="px-2 py-0.5 rounded text-[10px] text-white/80"
                        style={{ background: `${NODE_COLORS.concept}30` }}
                      >
                        {connNode.label}
                      </span>
                    )
                  ))}
                  {connectedByType.concept.length > 8 && (
                    <span className="text-white/30 text-[9px]">+{connectedByType.concept.length - 8}</span>
                  )}
                </div>
              </div>
            )}

            {/* Empty state */}
            {connectedNodes.length === 0 && (
              <div className="col-span-2 flex items-center justify-center text-white/30 text-xs">
                No connected nodes
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
