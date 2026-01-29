"use client";

import { useEffect, useRef, useCallback, useState, useMemo } from "react";
import type { GraphNode, GraphLink, ActiveFilters } from "../types";
import { NODE_COLORS, LINK_COLORS } from "../constants";

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
  const graphRef = useRef<any>(null);
  const [isClient, setIsClient] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [webglSupported, setWebglSupported] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

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
      color: highlightNodes.size && highlightNodes.has(n.id)
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

  // 크기 업데이트 (ResizeObserver 사용)
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

    // 초기 측정 (약간의 지연 후)
    const timer = setTimeout(updateDimensions, 100);

    // ResizeObserver로 크기 변화 감지
    const resizeObserver = new ResizeObserver(updateDimensions);
    resizeObserver.observe(containerRef.current);

    window.addEventListener("resize", updateDimensions);

    return () => {
      clearTimeout(timer);
      resizeObserver.disconnect();
      window.removeEventListener("resize", updateDimensions);
    };
  }, [isClient]);

  // 3D 그래프 초기화
  useEffect(() => {
    if (!isClient || !webglSupported) return;
    if (dimensions.width === 0 || dimensions.height === 0) return;

    let mounted = true;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let graph: any = null;

    const initGraph = async () => {
      // 컨테이너가 DOM에 마운트되었는지 확인
      if (!containerRef.current || !document.body.contains(containerRef.current)) {
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        // 3d-force-graph 동적 임포트
        const ForceGraph3DModule = await import("3d-force-graph");

        // 컴포넌트가 언마운트되었으면 중단
        if (!mounted || !containerRef.current) return;

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const ForceGraph3D = ForceGraph3DModule.default as any;

        // 기존 그래프 정리
        if (graphRef.current) {
          try {
            graphRef.current._destructor?.();
          } catch {
            // ignore
          }
          graphRef.current = null;
        }

        // 컨테이너 초기화
        containerRef.current.innerHTML = "";

        // DOM에 완전히 렌더링될 때까지 대기
        await new Promise(resolve => requestAnimationFrame(resolve));

        if (!mounted || !containerRef.current) return;

        // 컨테이너의 실제 크기 다시 확인
        const rect = containerRef.current.getBoundingClientRect();
        const width = rect.width || dimensions.width;
        const height = rect.height || dimensions.height;

        if (width <= 0 || height <= 0) {
          throw new Error("Invalid container dimensions");
        }

        // 3D 그래프 생성
        graph = ForceGraph3D(containerRef.current)
          .width(width)
          .height(height)
          .graphData(graphData)
          .backgroundColor("rgba(0,0,0,0)")
          .nodeLabel((node: Graph3DNode) => `${node.label} (${node.type})`)
          .nodeColor((node: Graph3DNode) => node.color)
          .nodeVal((node: Graph3DNode) => node.size)
          .nodeOpacity(0.9)
          .linkColor((link: Graph3DLink) => link.color)
          .linkWidth(0.5)
          .linkOpacity(0.6)
          .linkDirectionalParticles(1)
          .linkDirectionalParticleWidth(1)
          .linkDirectionalParticleSpeed(0.005)
          .onNodeHover((node: Graph3DNode | null) => {
            if (containerRef.current) {
              containerRef.current.style.cursor = node ? "pointer" : "grab";
            }
          })
          .onNodeClick((node: Graph3DNode) => {
            const originalNode = nodes.find((n) => n.id === node.id);
            if (originalNode) onNodeClick(originalNode);
          })
          .enableNodeDrag(true)
          .enableNavigationControls(true)
          .showNavInfo(false);

        // 카메라 초기 위치
        graph.cameraPosition({ x: 0, y: 0, z: 400 });

        if (mounted) {
          graphRef.current = graph;
          onStatsChange(graphData.nodes.length, graphData.links.length);
          setIsLoading(false);
        }
      } catch (err) {
        console.error("3D Graph initialization error:", err);
        if (mounted) {
          setError("3D 그래프를 초기화하는 중 오류가 발생했습니다. 2D 모드를 사용해 주세요.");
          setIsLoading(false);
        }
      }
    };

    // 초기화를 약간 지연시켜 DOM이 안정화되도록 함
    const timer = setTimeout(initGraph, 200);

    return () => {
      mounted = false;
      clearTimeout(timer);
      if (graphRef.current) {
        try {
          graphRef.current._destructor?.();
        } catch {
          // ignore
        }
        graphRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isClient, webglSupported, dimensions.width, dimensions.height]);

  // 데이터 업데이트
  useEffect(() => {
    if (!graphRef.current || !isClient || !webglSupported || isLoading) return;

    graphRef.current.graphData(graphData);
    onStatsChange(graphData.nodes.length, graphData.links.length);
  }, [graphData, isClient, webglSupported, isLoading, onStatsChange]);

  // 크기 업데이트
  useEffect(() => {
    if (!graphRef.current || !dimensions.width || !dimensions.height) return;
    graphRef.current.width(dimensions.width).height(dimensions.height);
  }, [dimensions]);

  // 줌 컨트롤
  const handleZoomIn = useCallback(() => {
    if (graphRef.current) {
      const { x, y, z } = graphRef.current.cameraPosition();
      graphRef.current.cameraPosition({ x, y, z: z * 0.7 }, undefined, 300);
    }
  }, []);

  const handleZoomOut = useCallback(() => {
    if (graphRef.current) {
      const { x, y, z } = graphRef.current.cameraPosition();
      graphRef.current.cameraPosition({ x, y, z: z * 1.3 }, undefined, 300);
    }
  }, []);

  const handleZoomReset = useCallback(() => {
    if (graphRef.current) {
      graphRef.current.cameraPosition({ x: 0, y: 0, z: 400 }, { x: 0, y: 0, z: 0 }, 500);
    }
  }, []);

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
            3D 그래프를 표시하려면 WebGL을 지원하는 브라우저가 필요합니다.
            2D 모드를 사용해 주세요.
          </p>
        </div>
      </div>
    );
  }

  // 에러 발생 시
  if (error) {
    return (
      <div className="absolute inset-0 w-full h-full flex items-center justify-center">
        <div className="text-center p-8 max-w-md">
          <div className="w-16 h-16 rounded-2xl bg-red-500/10 flex items-center justify-center mx-auto mb-4">
            <span className="text-3xl">⚠️</span>
          </div>
          <h3 className="text-white font-bold text-lg mb-2">3D 그래프 오류</h3>
          <p className="text-slate-400 text-sm mb-4">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-slate-600 text-white rounded-lg text-sm hover:bg-slate-700 transition-colors"
          >
            페이지 새로고침
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="absolute inset-0 w-full h-full">
      {/* 컨테이너는 항상 렌더링 (dimensions 측정을 위해) */}
      <div ref={containerRef} className="w-full h-full" />

      {/* 로딩 UI - 컨테이너 위에 오버레이 */}
      {isLoading && (
        <div className="absolute inset-0 w-full h-full flex items-center justify-center bg-transparent">
          <div className="flex flex-col items-center gap-4">
            <div className="w-12 h-12 border-4 border-purple-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-white/60 text-sm">3D 그래프 초기화 중...</span>
          </div>
        </div>
      )}

      {/* Zoom Controls - 로딩 완료 후에만 표시 */}
      {!isLoading && (
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
      )}
    </div>
  );
}
