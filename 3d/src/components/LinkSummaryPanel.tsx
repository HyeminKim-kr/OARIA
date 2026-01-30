"use client";

import type { GraphNode, GraphLink } from "@/lib/types";
import { LINK_COLORS } from "@/lib/types";

interface LinkSummaryPanelProps {
  links: GraphLink[];
  nodes: GraphNode[];
}

export default function LinkSummaryPanel({ links, nodes }: LinkSummaryPanelProps) {
  // Link 타입별 분류
  const simLinks = links.filter((l) => l.type === "similar");
  const authLinks = links.filter((l) => l.type === "authored");
  const kwLinks = links.filter((l) => l.type === "contains");

  // 평균 유사도
  const avgSim = simLinks.length
    ? simLinks.reduce((s, l) => s + (l.similarity || 0), 0) / simLinks.length
    : 0;

  // Top Authors
  const authorIds = new Set<string>();
  authLinks.forEach((l) => {
    const sourceId = typeof l.source === "string" ? l.source : l.source;
    const targetId = typeof l.target === "string" ? l.target : l.target;
    [sourceId, targetId].forEach((id) => {
      const n = nodes.find((x) => x.id === id);
      if (n?.type === "author") authorIds.add(n.label);
    });
  });

  // Top Keywords
  const kwCount: Record<string, number> = {};
  kwLinks.forEach((l) => {
    const sourceId = typeof l.source === "string" ? l.source : l.source;
    const targetId = typeof l.target === "string" ? l.target : l.target;
    [sourceId, targetId].forEach((id) => {
      const n = nodes.find((x) => x.id === id);
      if (n?.type === "keyword") {
        kwCount[n.label] = (kwCount[n.label] || 0) + 1;
      }
    });
  });
  const topKw = Object.entries(kwCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  return (
    <div
      className="w-64 rounded-2xl overflow-hidden shadow-2xl"
      style={{
        background: "rgba(10, 14, 26, 0.82)",
        backdropFilter: "blur(20px)",
        border: "1px solid rgba(255, 255, 255, 0.08)",
      }}
    >
      {/* Header */}
      <div className="p-5 pb-3">
        <div className="text-[9px] font-bold text-slate-500 uppercase tracking-[0.1em] mb-1">
          Edge Summary
        </div>
        <p className="text-slate-600 text-[10px]">3 types of connections</p>
      </div>

      {/* Similar Links */}
      <div
        className="mx-4 mb-3 rounded-xl overflow-hidden"
        style={{
          background: `${LINK_COLORS.similar}08`,
          border: `1px solid ${LINK_COLORS.similar}15`,
        }}
      >
        <div className="p-3.5">
          <div className="flex items-center gap-2 mb-2">
            <div
              className="w-5 h-5 rounded-md flex items-center justify-center"
              style={{ background: `${LINK_COLORS.similar}30` }}
            >
              <svg className="w-3 h-3" style={{ color: LINK_COLORS.similar }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
              </svg>
            </div>
            <span className="text-[11px] font-bold text-slate-300">Similar</span>
            <span className="ml-auto text-[10px] font-mono font-bold text-slate-500">
              {simLinks.length}
            </span>
          </div>
          <p className="text-[10px] text-slate-500 leading-relaxed mb-2">
            논문 간 벡터 유사도 기반 연결
          </p>
          <div className="flex items-center gap-2">
            <span className="text-[9px] text-slate-600 uppercase font-bold">
              Avg Sim
            </span>
            <div
              className="flex-1 h-1.5 rounded-full overflow-hidden"
              style={{ background: "rgba(255,255,255,0.06)" }}
            >
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${avgSim * 100}%`,
                  background: LINK_COLORS.similar,
                }}
              />
            </div>
            <span
              className="text-[10px] font-mono font-bold"
              style={{ color: LINK_COLORS.similar }}
            >
              {(avgSim * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      </div>

      {/* Authored Links */}
      <div
        className="mx-4 mb-3 rounded-xl overflow-hidden"
        style={{
          background: `${LINK_COLORS.authored}08`,
          border: `1px solid ${LINK_COLORS.authored}15`,
        }}
      >
        <div className="p-3.5">
          <div className="flex items-center gap-2 mb-2">
            <div
              className="w-5 h-5 rounded-md flex items-center justify-center"
              style={{ background: `${LINK_COLORS.authored}30` }}
            >
              <svg className="w-3 h-3" style={{ color: LINK_COLORS.authored }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </div>
            <span className="text-[11px] font-bold text-slate-300">Authored</span>
            <span className="ml-auto text-[10px] font-mono font-bold text-slate-500">
              {authLinks.length}
            </span>
          </div>
          <p className="text-[10px] text-slate-500 leading-relaxed mb-2">
            저자-논문 관계
          </p>
          <div className="flex flex-wrap gap-1">
            {[...authorIds].slice(0, 4).map((author) => (
              <span
                key={author}
                className="text-[10px] px-2 py-0.5 rounded-md font-medium"
                style={{
                  background: `${LINK_COLORS.authored}12`,
                  color: LINK_COLORS.authored,
                  border: `1px solid ${LINK_COLORS.authored}20`,
                }}
              >
                {author}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Contains Links */}
      <div
        className="mx-4 mb-4 rounded-xl overflow-hidden"
        style={{
          background: `${LINK_COLORS.contains}08`,
          border: `1px solid ${LINK_COLORS.contains}15`,
        }}
      >
        <div className="p-3.5">
          <div className="flex items-center gap-2 mb-2">
            <div
              className="w-5 h-5 rounded-md flex items-center justify-center"
              style={{ background: `${LINK_COLORS.contains}30` }}
            >
              <svg className="w-3 h-3" style={{ color: LINK_COLORS.contains }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
              </svg>
            </div>
            <span className="text-[11px] font-bold text-slate-300">Contains</span>
            <span className="ml-auto text-[10px] font-mono font-bold text-slate-500">
              {kwLinks.length}
            </span>
          </div>
          <p className="text-[10px] text-slate-500 leading-relaxed mb-2">
            논문-키워드 관계
          </p>
          <div className="flex flex-wrap gap-1">
            {topKw.map(([kw, count]) => (
              <span
                key={kw}
                className="text-[10px] px-2 py-0.5 rounded-md font-medium"
                style={{
                  background: `${LINK_COLORS.contains}12`,
                  color: "#f39c12",
                  border: `1px solid ${LINK_COLORS.contains}20`,
                }}
              >
                {kw}{" "}
                <span className="opacity-60">{count}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
