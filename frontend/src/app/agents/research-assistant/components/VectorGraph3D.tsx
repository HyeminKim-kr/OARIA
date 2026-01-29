"use client";

import { useEffect, useRef, useCallback, useState, useMemo } from "react";
import dynamic from "next/dynamic";
import type { GraphNode, GraphLink, ActiveFilters } from "../types";
import { NODE_COLORS, LINK_COLORS } from "../constants";

// react-force-graph-3d를 동적 임포트 (SSR 비활성화)
const ForceGraph3D = dynamic(() => import("react-force-graph-3d"), {
  ssr: false,
  loading: () => null,
});

interface VectorGraph3DProps {
  nodes: GraphNode[];
  links: GraphLink[];
  activeFilters: ActiveFilters;
  minSimilarity: number;
  searchQuery: string;
  highlightNodes: Set<string>;
  highlightLinks: Set<GraphLink>;
  onNodeHover: (node: GraphNode | null) => void;
  onNodeClick: (node: GraphNode) => void;
  onStatsChange: (nodeCount: number, linkCount: number) => void;
}

// WebGL 지원 여부 확인
function isWebGLSupported(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext("webgl") || canvas.getContext("experimental-webgl"))
    );
  } catch {
    return false;
  }
}

interface Graph3DNode {
  id: string;
  label: string;
  type: string;
  color: string;
  size: number;
}

interface Graph3DLink {
  source: string;
  target: string;
  color: string;
}

export default function VectorGraph3D({
  nodes,
  links,
  activeFilters,
  minSimilarity,
  searchQuery,
  highlightNodes,
  highlightLinks,
  onNodeHover,
  onNodeClick,
  onStatsChange,
}: VectorGraph3DProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fgRef = useRef<any>(null);
  const [isClient, setIsClient] = useState(false);
  const [webglSupported, setWebglSupported] = useState(true);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  // 필터링된 데이터 계산
  const filteredData = useMemo(() => {
    const search = searchQuery.toLowerCase();

    const filteredNodes = nodes.filter((n) => {
      if (!activeFilters[n.type as keyof ActiveFilters]) return false;
      if (
        search &&
        !n.label.toLowerCase().includes(search) &&
        !(n.metadata?.journal || "").toLowerCase().includes(search)
      )
        return false;
      return true;
    });

    const nodeIds = new Set(filteredNodes.map((n) => n.id));

    const filteredLinks = links.filter((l) => {
      const sourceId = typeof l.source === "string" ? l.source : l.source.id;
      const targetId = typeof l.target === "string" ? l.target : l.target.id;
      return (
        nodeIds.has(sourceId) &&
        nodeIds.has(targetId) &&
        (l.similarity ?? 1) >= minSimilarity
      );
    });

    return { nodes: filteredNodes, links: filteredLinks };
  }, [nodes, links, activeFilters, minSimilarity, searchQuery]);

  // 그래프 데이터 준비
  const graphData = useMemo(() => {
    const graphNodes: Graph3DNode[] = filteredData.nodes.map((n) => ({
      id: n.id,
      label: n.label,
      type: n.type,
      color:
        highlightNodes.size && highlightNodes.has(n.id)
          ? "#ff6600"
          : NODE_COLORS[n.type] || "#888",
      size: n.type === "paper" ? 8 : n.type === "author" ? 6 : 4,
    }));

    const graphLinks: Graph3DLink[] = filteredData.links.map((l) => {
      const sourceId = typeof l.source === "string" ? l.source : l.source.id;
      const targetId = typeof l.target === "string" ? l.target : l.target.id;
      return {
        source: sourceId,
        target: targetId,
        color: highlightLinks.has(l)
          ? "rgba(96, 165, 250, 0.8)"
          : LINK_COLORS[l.type] || "rgba(100, 116, 139, 0.4)",
      };
    });

    return { nodes: graphNodes, links: graphLinks };
  }, [filteredData, highlightNodes, highlightLinks]);

  // 클라이언트 사이드 확인
  useEffect(() => {
    setIsClient(true);
    setWebglSupported(isWebGLSupported());
  }, []);

  // 크기 업데이트
  useEffect(() => {
    if (!containerRef.current) return;

    const updateDimensions = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
          setDimensions({ width: rect.width, height: rect.height });
        }
      }
    };

    updateDimensions();

    const resizeObserver = new ResizeObserver(updateDimensions);
    resizeObserver.observe(containerRef.current);

    window.addEventListener("resize", updateDimensions);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("resize", updateDimensions);
    };
  }, [isClient]);

  // Stats 업데이트
  useEffect(() => {
    onStatsChange(graphData.nodes.length, graphData.links.length);
  }, [graphData.nodes.length, graphData.links.length, onStatsChange]);

  // 줌 컨트롤
  const handleZoomIn = useCallback(() => {
    if (fgRef.current) {
      const { x, y, z } = fgRef.current.cameraPosition();
      fgRef.current.cameraPosition({ x, y, z: z * 0.7 }, undefined, 300);
    }
  }, []);

  const handleZoomOut = useCallback(() => {
    if (fgRef.current) {
      const { x, y, z } = fgRef.current.cameraPosition();
      fgRef.current.cameraPosition({ x, y, z: z * 1.3 }, undefined, 300);
    }
  }, []);

  const handleZoomReset = useCallback(() => {
    if (fgRef.current) {
      fgRef.current.cameraPosition(
        { x: 0, y: 0, z: 400 },
        { x: 0, y: 0, z: 0 },
        500
      );
    }
  }, []);

  // 노드 클릭 핸들러
  const handleNodeClick = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (node: any) => {
      const originalNode = nodes.find((n) => n.id === node.id);
      if (originalNode) onNodeClick(originalNode);
    },
    [nodes, onNodeClick]
  );

  // WebGL 미지원 시
  if (!webglSupported) {
    return (
      <div className="absolute inset-0 w-full h-full flex items-center justify-center">
        <div className="text-center p-8 max-w-md">
          <div className="w-16 h-16 rounded-2xl bg-red-500/10 flex items-center justify-center mx-auto mb-4">
            <span className="text-3xl">⚠️</span>
          </div>
          <h3 className="text-white font-bold text-lg mb-2">WebGL 미지원</h3>
          <p className="text-slate-400 text-sm mb-4">
            3D 그래프를 표시하려면 WebGL을 지원하는 브라우저가 필요합니다. 2D
            모드를 사용해 주세요.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="absolute inset-0 w-full h-full">
      <div ref={containerRef} className="w-full h-full">
        {isClient && (
          <ForceGraph3D
            ref={fgRef}
            width={dimensions.width}
            height={dimensions.height}
            graphData={graphData}
            backgroundColor="rgba(0,0,0,0)"
            nodeLabel="label"
            nodeColor="color"
            nodeVal="size"
            nodeOpacity={0.9}
            linkColor="color"
            linkWidth={0.5}
            linkOpacity={0.6}
            linkDirectionalParticles={1}
            linkDirectionalParticleWidth={1}
            linkDirectionalParticleSpeed={0.005}
            onNodeClick={handleNodeClick}
            enableNodeDrag={true}
            enableNavigationControls={true}
            showNavInfo={false}
          />
        )}
      </div>

      {/* Zoom Controls */}
      <div className="absolute bottom-6 right-6 flex gap-2 z-10">
        <button
          onClick={handleZoomIn}
          className="w-10 h-10 rounded-lg flex items-center justify-center text-white/60 hover:text-white text-xl font-bold transition-all hover:bg-white/10"
          style={{
            background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          +
        </button>
        <button
          onClick={handleZoomOut}
          className="w-10 h-10 rounded-lg flex items-center justify-center text-white/60 hover:text-white text-xl font-bold transition-all hover:bg-white/10"
          style={{
            background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          -
        </button>
        <button
          onClick={handleZoomReset}
          className="px-4 h-10 rounded-lg text-white/40 hover:text-white text-[10px] font-semibold uppercase tracking-wider transition-all hover:bg-white/10"
          style={{
            background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          Reset
        </button>
      </div>
    </div>
  );
}
