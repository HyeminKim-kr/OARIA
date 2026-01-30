"use client";

import { useRef, useMemo, useState, useEffect } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Html, Line } from "@react-three/drei";
import * as THREE from "three";
import type { GraphNode, GraphLink, ActiveFilters } from "@/lib/types";
import { NODE_COLORS, LINK_COLORS } from "@/lib/types";

interface NodeMeshProps {
  node: GraphNode;
  position: [number, number, number];
  isHighlighted: boolean;
  isDimmed: boolean;
  isSelected: boolean;
  onClick: () => void;
  onHover: (hover: boolean) => void;
}

function NodeMesh({ node, position, isHighlighted, isDimmed, isSelected, onClick, onHover }: NodeMeshProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);

  const color = NODE_COLORS[node.type] || "#888888";
  // 노드 크기 축소 (더 작고 깔끔하게)
  const size = node.type === "paper" ? 0.6 : node.type === "author" ? 0.45 : 0.35;

  // 라벨 truncate (더 짧게)
  const truncatedLabel = node.label.length > 15 ? node.label.slice(0, 15) + "..." : node.label;

  // 선택/하이라이트 상태에 따른 색상 (선택된 노드는 빨간색으로 강조)
  const displayColor = isSelected ? "#ff2222" : isHighlighted ? "#ff6633" : color;
  const opacity = isDimmed ? 0.2 : 0.95;

  useFrame(() => {
    if (meshRef.current) {
      // 선택된 노드는 더 크게
      const targetScale = isSelected ? 2.0 : hovered || isHighlighted ? 1.5 : isDimmed ? 0.7 : 1;
      meshRef.current.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 0.1);
    }
  });

  return (
    <group position={position}>
      {/* Node sphere */}
      <mesh
        ref={meshRef}
        onClick={(e) => {
          e.stopPropagation();
          onClick();
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHovered(true);
          onHover(true);
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          setHovered(false);
          onHover(false);
          document.body.style.cursor = "default";
        }}
      >
        <sphereGeometry args={[size, 32, 32]} />
        <meshStandardMaterial
          color={displayColor}
          emissive={displayColor}
          emissiveIntensity={isSelected ? 1.0 : hovered ? 0.6 : isHighlighted ? 0.5 : isDimmed ? 0.03 : 0.15}
          transparent
          opacity={opacity}
          roughness={0.2}
          metalness={0.2}
        />
      </mesh>

      {/* Glow effect for highlighted/selected nodes */}
      {(isSelected || hovered || isHighlighted) && !isDimmed && (
        <mesh>
          <sphereGeometry args={[size * (isSelected ? 2.0 : 1.4), 16, 16]} />
          <meshBasicMaterial
            color={displayColor}
            transparent
            opacity={isSelected ? 0.4 : 0.2}
          />
        </mesh>
      )}

      {/* Always visible label (like 2D) */}
      <Html
        position={[0, -(size + 0.3), 0]}
        center
        style={{ pointerEvents: "none" }}
        distanceFactor={12}
      >
        <div
          className="text-center whitespace-nowrap"
          style={{
            color: isSelected ? "#fff" : isHighlighted ? "#fff" : isDimmed ? "rgba(255,255,255,0.2)" : "rgba(255,255,255,0.8)",
            fontSize: "9px",
            fontWeight: isSelected ? 600 : isHighlighted ? 500 : 400,
            textShadow: "0 1px 4px rgba(0,0,0,0.9), 0 0 8px rgba(0,0,0,0.5)",
            maxWidth: "100px",
            overflow: "hidden",
            textOverflow: "ellipsis",
            letterSpacing: "0.02em",
          }}
        >
          {truncatedLabel}
        </div>
      </Html>

      {/* Detailed tooltip on hover */}
      {hovered && (
        <Html
          position={[0, size + 1.5, 0]}
          center
          style={{ pointerEvents: "none" }}
        >
          <div
            className="px-3 py-2.5 rounded-xl text-white text-xs"
            style={{
              background: "rgba(10, 14, 26, 0.95)",
              backdropFilter: "blur(16px)",
              border: "1px solid rgba(255, 255, 255, 0.12)",
              minWidth: "180px",
              maxWidth: "300px",
              boxShadow: "0 8px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.05)",
            }}
          >
            {/* Type badge */}
            <div className="flex items-center gap-2 mb-2">
              <span
                className="w-2.5 h-2.5 rounded-full"
                style={{ background: NODE_COLORS[node.type], boxShadow: `0 0 6px ${NODE_COLORS[node.type]}` }}
              />
              <span className="text-gray-400 text-[10px] uppercase tracking-wider font-medium">{node.type}</span>
              {node.metadata?.pubdate && (
                <span className="text-gray-500 text-[10px] ml-auto">{node.metadata.pubdate}</span>
              )}
            </div>

            {/* Title */}
            <div className="font-semibold text-sm leading-snug mb-2">{node.label}</div>

            {/* Journal */}
            {node.metadata?.journal && (
              <div className="text-blue-400 text-[11px] mb-2">{node.metadata.journal}</div>
            )}

            {/* Stats */}
            <div className="flex flex-wrap gap-1.5">
              {node.metadata?.certainty_score !== undefined && (
                <span className="px-2 py-0.5 rounded-md text-[9px] bg-emerald-500/20 text-emerald-400 font-medium">
                  {Math.round(node.metadata.certainty_score * 100)}% match
                </span>
              )}
              {node.metadata?.paper_count !== undefined && (
                <span className="px-2 py-0.5 rounded-md text-[9px] bg-violet-500/20 text-violet-400 font-medium">
                  {node.metadata.paper_count} papers
                </span>
              )}
            </div>

            {/* Abstract preview */}
            {node.metadata?.abstract && (
              <div className="mt-2 pt-2 border-t border-white/10">
                <p className="text-gray-400 text-[10px] leading-relaxed line-clamp-2">
                  {node.metadata.abstract.slice(0, 100)}...
                </p>
              </div>
            )}
          </div>
        </Html>
      )}
    </group>
  );
}

interface LinkLineProps {
  start: [number, number, number];
  end: [number, number, number];
  type: string;
  isHighlighted: boolean;
  isDimmed: boolean;
  similarity?: number;
}

function LinkLine({ start, end, type, isHighlighted, isDimmed, similarity }: LinkLineProps) {
  const color = isHighlighted ? "#60a5fa" : LINK_COLORS[type] || "#334155";
  const opacity = isDimmed ? 0.08 : isHighlighted ? 0.9 : (similarity ?? 0.5) * 0.6;

  return (
    <Line
      points={[start, end]}
      color={color}
      lineWidth={isHighlighted ? 2.5 : isDimmed ? 0.3 : 1}
      transparent
      opacity={opacity}
    />
  );
}

interface SceneProps {
  nodes: GraphNode[];
  links: GraphLink[];
  activeFilters: ActiveFilters;
  minSimilarity: number;
  searchQuery: string;
  selectedNodeId: string | null;
  onNodeClick: (node: GraphNode) => void;
  onStatsChange: (nodeCount: number, linkCount: number) => void;
}

function Scene({
  nodes,
  links,
  activeFilters,
  minSimilarity,
  searchQuery,
  selectedNodeId,
  onNodeClick,
  onStatsChange,
}: SceneProps) {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const { camera } = useThree();

  // 노드 위치 계산 (연결된 노드끼리 클러스터링)
  const nodePositions = useMemo(() => {
    const positions = new Map<string, [number, number, number]>();
    const filteredNodes = nodes.filter((n) => activeFilters[n.type as keyof ActiveFilters]);
    const nodeIds = new Set(filteredNodes.map((n) => n.id));

    // 연결 정보 구축
    const connections = new Map<string, Set<string>>();
    filteredNodes.forEach((n) => connections.set(n.id, new Set()));

    links.forEach((link) => {
      if (nodeIds.has(link.source) && nodeIds.has(link.target)) {
        connections.get(link.source)?.add(link.target);
        connections.get(link.target)?.add(link.source);
      }
    });

    // 연결된 클러스터 찾기 (Union-Find)
    const parent = new Map<string, string>();
    filteredNodes.forEach((n) => parent.set(n.id, n.id));

    const find = (id: string): string => {
      if (parent.get(id) !== id) {
        parent.set(id, find(parent.get(id)!));
      }
      return parent.get(id)!;
    };

    const union = (a: string, b: string) => {
      const rootA = find(a);
      const rootB = find(b);
      if (rootA !== rootB) {
        parent.set(rootA, rootB);
      }
    };

    links.forEach((link) => {
      if (nodeIds.has(link.source) && nodeIds.has(link.target)) {
        union(link.source, link.target);
      }
    });

    // 클러스터별로 노드 그룹화
    const clusters = new Map<string, GraphNode[]>();
    filteredNodes.forEach((node) => {
      const root = find(node.id);
      if (!clusters.has(root)) {
        clusters.set(root, []);
      }
      clusters.get(root)!.push(node);
    });

    // 클러스터 정렬 (큰 클러스터가 중앙에)
    const sortedClusters = [...clusters.values()].sort((a, b) => b.length - a.length);

    // Golden ratio for distribution
    const phi = Math.PI * (3 - Math.sqrt(5));

    // 각 클러스터 배치
    sortedClusters.forEach((clusterNodes, clusterIndex) => {
      const isMainCluster = clusterIndex === 0 && clusterNodes.length > 3;
      const isSingleNode = clusterNodes.length === 1;

      // 클러스터 중심 위치 계산
      let clusterCenterX = 0;
      let clusterCenterY = 0;
      let clusterCenterZ = 0;

      if (isMainCluster) {
        // 메인 클러스터는 중앙에
        clusterCenterX = 0;
        clusterCenterY = 0;
        clusterCenterZ = 0;
      } else if (isSingleNode) {
        // 연결 없는 단일 노드는 외곽에 배치
        const angle = (clusterIndex / Math.max(sortedClusters.length - 1, 1)) * Math.PI * 2;
        const outerRadius = 45 + Math.random() * 10;
        clusterCenterX = Math.cos(angle) * outerRadius;
        clusterCenterY = (Math.random() - 0.5) * 20;
        clusterCenterZ = Math.sin(angle) * outerRadius;
      } else {
        // 작은 클러스터는 중간 거리에 배치
        const angle = (clusterIndex / Math.max(sortedClusters.length, 1)) * Math.PI * 2;
        const midRadius = 25 + clusterIndex * 5;
        clusterCenterX = Math.cos(angle) * midRadius;
        clusterCenterY = (clusterIndex % 3 - 1) * 8;
        clusterCenterZ = Math.sin(angle) * midRadius;
      }

      // 클러스터 내 노드들 배치
      clusterNodes.forEach((node, indexInCluster) => {
        const connectionCount = connections.get(node.id)?.size || 0;
        const typeIndex = ["paper", "author", "keyword", "concept"].indexOf(node.type);

        if (isSingleNode) {
          // 단일 노드는 클러스터 중심에
          positions.set(node.id, [clusterCenterX, clusterCenterY, clusterCenterZ]);
        } else {
          // 연결 많은 노드는 중심 가까이
          const distanceFromCenter = Math.max(3, 12 - connectionCount * 1.5) + typeIndex * 2;

          // 클러스터 내 분포
          const y = 1 - (indexInCluster / Math.max(clusterNodes.length - 1, 1)) * 2;
          const radiusAtY = Math.sqrt(1 - y * y);
          const theta = phi * indexInCluster;

          const x = clusterCenterX + Math.cos(theta) * radiusAtY * distanceFromCenter;
          const z = clusterCenterZ + Math.sin(theta) * radiusAtY * distanceFromCenter;
          const yPos = clusterCenterY + y * distanceFromCenter * 0.5;

          positions.set(node.id, [x, yPos, z]);
        }
      });
    });

    return positions;
  }, [nodes, links, activeFilters]);

  // 필터링된 노드와 링크
  const { filteredNodes, filteredLinks } = useMemo(() => {
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
      return (
        nodeIds.has(l.source) &&
        nodeIds.has(l.target) &&
        (l.similarity ?? 1) >= minSimilarity
      );
    });

    return { filteredNodes, filteredLinks };
  }, [nodes, links, activeFilters, minSimilarity, searchQuery]);

  // Stats 업데이트
  useEffect(() => {
    onStatsChange(filteredNodes.length, filteredLinks.length);
  }, [filteredNodes.length, filteredLinks.length, onStatsChange]);

  // 하이라이트 노드/링크 계산 (hover 또는 selected)
  const { highlightNodes, highlightLinks, hasSelection } = useMemo(() => {
    const highlightNodes = new Set<string>();
    const highlightLinks = new Set<string>();

    // 선택된 노드가 있으면 해당 노드와 연결된 노드들 하이라이트
    const targetNode = hoveredNode || selectedNodeId;

    if (targetNode) {
      highlightNodes.add(targetNode);
      filteredLinks.forEach((l) => {
        if (l.source === targetNode || l.target === targetNode) {
          highlightLinks.add(`${l.source}-${l.target}`);
          highlightNodes.add(l.source);
          highlightNodes.add(l.target);
        }
      });
    }

    return { highlightNodes, highlightLinks, hasSelection: !!selectedNodeId };
  }, [hoveredNode, selectedNodeId, filteredLinks]);

  // 카메라 초기 위치 설정
  useEffect(() => {
    camera.position.set(40, 25, 40);
    camera.lookAt(0, 0, 0);
  }, [camera]);

  return (
    <>
      {/* Lighting */}
      <ambientLight intensity={0.5} />
      <pointLight position={[60, 60, 60]} intensity={1.2} color="#ffffff" />
      <pointLight position={[-40, -40, -40]} intensity={0.4} color="#6366f1" />
      <pointLight position={[0, 50, 0]} intensity={0.3} color="#8b5cf6" />

      {/* Links */}
      {filteredLinks.map((link) => {
        const startPos = nodePositions.get(link.source);
        const endPos = nodePositions.get(link.target);
        if (!startPos || !endPos) return null;

        const linkId = `${link.source}-${link.target}`;
        const isLinkHighlighted = highlightLinks.has(linkId);
        const isLinkDimmed = hasSelection && !isLinkHighlighted;

        return (
          <LinkLine
            key={linkId}
            start={startPos}
            end={endPos}
            type={link.type}
            isHighlighted={isLinkHighlighted}
            isDimmed={isLinkDimmed}
            similarity={link.similarity}
          />
        );
      })}

      {/* Nodes */}
      {filteredNodes.map((node) => {
        const position = nodePositions.get(node.id);
        if (!position) return null;

        const isNodeHighlighted = highlightNodes.has(node.id);
        const isNodeSelected = node.id === selectedNodeId;
        const isNodeDimmed = hasSelection && !isNodeHighlighted;

        return (
          <NodeMesh
            key={node.id}
            node={node}
            position={position}
            isHighlighted={isNodeHighlighted}
            isDimmed={isNodeDimmed}
            isSelected={isNodeSelected}
            onClick={() => onNodeClick(node)}
            onHover={(hover) => setHoveredNode(hover ? node.id : null)}
          />
        );
      })}

      {/* Controls */}
      <OrbitControls
        enableDamping
        dampingFactor={0.05}
        minDistance={15}
        maxDistance={150}
        autoRotate={false}
        rotateSpeed={0.5}
        zoomSpeed={0.8}
      />
    </>
  );
}

interface VectorGraph3DProps {
  nodes: GraphNode[];
  links: GraphLink[];
  activeFilters: ActiveFilters;
  minSimilarity: number;
  searchQuery: string;
  selectedNodeId: string | null;
  onNodeClick: (node: GraphNode) => void;
  onStatsChange: (nodeCount: number, linkCount: number) => void;
}

export default function VectorGraph3D({
  nodes,
  links,
  activeFilters,
  minSimilarity,
  searchQuery,
  selectedNodeId,
  onNodeClick,
  onStatsChange,
}: VectorGraph3DProps) {
  return (
    <div className="w-full h-full">
      <Canvas
        camera={{ position: [40, 25, 40], fov: 55 }}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        style={{ background: "transparent" }}
        dpr={[1, 2]}
      >
        <Scene
          nodes={nodes}
          links={links}
          activeFilters={activeFilters}
          minSimilarity={minSimilarity}
          searchQuery={searchQuery}
          selectedNodeId={selectedNodeId}
          onNodeClick={onNodeClick}
          onStatsChange={onStatsChange}
        />
      </Canvas>
    </div>
  );
}
