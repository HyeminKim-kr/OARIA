"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import type { GraphNode, GraphLink, ActiveFilters } from "../types";
import { NODE_COLORS, LINK_COLORS, CLUSTER_COLORS } from "../constants";

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

  // 필터링된 데이터 계산
  const getFilteredData = useCallback(() => {
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

  // 클라이언트 사이드 확인
  useEffect(() => {
    setIsClient(true);
  }, []);

  // 그래프 초기화
  useEffect(() => {
    if (!isClient || !containerRef.current) return;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let graph: any = null;

    const initGraph = async () => {
      // 3d-force-graph (non-React version) 사용
      const ForceGraph3D = (await import("3d-force-graph")).default;
      const THREEModule = await import("three");

      if (!containerRef.current) return;

      const filteredData = getFilteredData();

      graph = new ForceGraph3D(containerRef.current)
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        .graphData(filteredData as any)
        .backgroundColor("rgba(0,0,0,0)")
        .nodeResolution(16)
        .nodeRelSize(6)
        .nodeVal((node: unknown) => {
          const n = node as GraphNode;
          return n.type === "paper" ? 10 : n.type === "author" ? 6 : 4;
        })
        .nodeColor((node: unknown) => {
          const n = node as GraphNode;
          if (highlightNodes.size && highlightNodes.has(n.id)) return "#ff6600";
          return NODE_COLORS[n.type] || "#888";
        })
        .nodeOpacity(0.9)
        .nodeLabel(() => "")
        .linkWidth((link: unknown) => {
          const l = link as GraphLink;
          return highlightLinks.has(l) ? 3 : 0.6;
        })
        .linkColor((link: unknown) => {
          const l = link as GraphLink;
          if (highlightLinks.has(l)) return "#60a5fa";
          return LINK_COLORS[l.type] || "#1e293b";
        })
        .linkOpacity(0.5)
        .linkDirectionalParticles((link: unknown) => {
          const l = link as GraphLink;
          return highlightLinks.has(l) ? 5 : 0;
        })
        .linkDirectionalParticleWidth(2.5)
        .linkDirectionalParticleSpeed(0.004)
        .linkDirectionalParticleColor((link: unknown) => {
          const l = link as GraphLink;
          return LINK_COLORS[l.type] || "#60a5fa";
        })
        .onNodeHover((node: unknown) => {
          const n = node as GraphNode | null;
          if (containerRef.current) {
            containerRef.current.style.cursor = n ? "pointer" : "move";
          }
          onNodeHover(n);
        })
        .onNodeClick((node: unknown) => {
          const n = node as GraphNode;
          onNodeClick(n);
          // 카메라 이동
          const dist = 150;
          const ratio = 1 + dist / Math.hypot(n.x || 0, n.y || 0, n.z || 0);
          graph?.cameraPosition(
            {
              x: (n.x || 0) * ratio,
              y: (n.y || 0) * ratio,
              z: (n.z || 0) * ratio,
            },
            { x: n.x || 0, y: n.y || 0, z: n.z || 0 },
            2000
          );
        });

      // 초기 카메라 위치
      graph.cameraPosition({ z: 500 });

      // 클러스터 시각화
      graph.onEngineStop(() => {
        if (graph) {
          buildClusterHulls(graph.scene(), filteredData.nodes, THREEModule);
        }
      });

      graphRef.current = graph;
      onStatsChange(filteredData.nodes.length, filteredData.links.length);
    };

    initGraph();

    return () => {
      // Cleanup
      if (graph) {
        graph._destructor?.();
      }
      if (containerRef.current) {
        containerRef.current.innerHTML = "";
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isClient]);

  // 데이터 업데이트
  useEffect(() => {
    if (!graphRef.current) return;

    const filteredData = getFilteredData();
    graphRef.current.graphData(filteredData);
    onStatsChange(filteredData.nodes.length, filteredData.links.length);
  }, [activeFilters, minSimilarity, searchQuery, highlightNodes, highlightLinks, getFilteredData, onStatsChange]);

  // 클러스터 헐 빌드
  const buildClusterHulls = (
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    scene: any,
    graphNodes: GraphNode[],
    THREEModule: typeof import("three")
  ) => {
    // 기존 클러스터 메시 제거
    const toRemove = scene.children.filter(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (c: any) => c.userData?.isCluster
    );
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    toRemove.forEach((m: any) => scene.remove(m));

    // 클러스터별 노드 그룹화
    const clusters: Record<string, GraphNode[]> = {};
    graphNodes.filter((n) => n.cluster).forEach((n) => {
      if (!clusters[n.cluster!]) clusters[n.cluster!] = [];
      clusters[n.cluster!].push(n);
    });

    for (const [clusterId, clusterNodes] of Object.entries(clusters)) {
      if (clusterNodes.length < 2) continue;
      const cfg = CLUSTER_COLORS[clusterId] || { color: "#888", label: clusterId };

      // 클러스터 중심
      const cx =
        clusterNodes.reduce((s, n) => s + (n.x || 0), 0) / clusterNodes.length;
      const cy =
        clusterNodes.reduce((s, n) => s + (n.y || 0), 0) / clusterNodes.length;
      const cz =
        clusterNodes.reduce((s, n) => s + (n.z || 0), 0) / clusterNodes.length;

      // 반지름
      const maxDist = Math.max(
        ...clusterNodes.map((n) =>
          Math.sqrt(
            ((n.x || 0) - cx) ** 2 + ((n.y || 0) - cy) ** 2 + ((n.z || 0) - cz) ** 2
          )
        )
      );
      const radius = maxDist + 25;

      // 반투명 구체
      const geo = new THREEModule.SphereGeometry(radius, 32, 32);
      const mat = new THREEModule.MeshBasicMaterial({
        color: cfg.color,
        transparent: true,
        opacity: 0.04,
        side: THREEModule.DoubleSide,
        depthWrite: false,
      });
      const mesh = new THREEModule.Mesh(geo, mat);
      mesh.position.set(cx, cy, cz);
      mesh.userData = { isCluster: true };
      scene.add(mesh);

      // 와이어프레임
      const wireGeo = new THREEModule.SphereGeometry(radius, 16, 16);
      const wireMat = new THREEModule.MeshBasicMaterial({
        color: cfg.color,
        transparent: true,
        opacity: 0.12,
        wireframe: true,
        depthWrite: false,
      });
      const wire = new THREEModule.Mesh(wireGeo, wireMat);
      wire.position.set(cx, cy, cz);
      wire.userData = { isCluster: true };
      scene.add(wire);
    }
  };

  // 줌 컨트롤
  const handleZoomIn = useCallback(() => {
    if (graphRef.current) {
      const camera = graphRef.current.camera();
      const dist = camera.position.length();
      graphRef.current.cameraPosition({ z: dist * 0.7 }, null, 500);
    }
  }, []);

  const handleZoomOut = useCallback(() => {
    if (graphRef.current) {
      const camera = graphRef.current.camera();
      const dist = camera.position.length();
      graphRef.current.cameraPosition({ z: dist * 1.5 }, null, 500);
    }
  }, []);

  const handleZoomReset = useCallback(() => {
    if (graphRef.current) {
      graphRef.current.cameraPosition({ x: 0, y: 0, z: 500 }, { x: 0, y: 0, z: 0 }, 1000);
    }
  }, []);

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full cursor-move" />

      {/* Zoom Controls - 우측 하단 */}
      <div className="absolute bottom-6 right-6 flex gap-2">
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
