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
  onClick: () => void;
  onHover: (hover: boolean) => void;
}

function NodeMesh({ node, position, isHighlighted, onClick, onHover }: NodeMeshProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);

  const color = NODE_COLORS[node.type] || "#888888";
  const size = node.type === "paper" ? 1.2 : node.type === "author" ? 0.9 : 0.6;

  useFrame(() => {
    if (meshRef.current) {
      const targetScale = hovered || isHighlighted ? 1.3 : 1;
      meshRef.current.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 0.1);
    }
  });

  return (
    <group position={position}>
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
          color={isHighlighted ? "#ff6600" : color}
          emissive={isHighlighted ? "#ff6600" : color}
          emissiveIntensity={hovered ? 0.5 : isHighlighted ? 0.3 : 0.1}
          transparent
          opacity={0.9}
        />
      </mesh>
      {(hovered || isHighlighted) && (
        <Html
          position={[0, size + 0.8, 0]}
          center
          style={{ pointerEvents: "none" }}
        >
          <div
            className="px-3 py-2 rounded-xl text-white text-xs font-medium"
            style={{
              background: "rgba(10, 14, 26, 0.95)",
              backdropFilter: "blur(12px)",
              border: "1px solid rgba(255, 255, 255, 0.15)",
              maxWidth: "280px",
              boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
            }}
          >
            {/* Header with type badge */}
            <div className="flex items-center gap-2 mb-1.5">
              <span
                className="w-2 h-2 rounded-full flex-shrink-0"
                style={{ background: NODE_COLORS[node.type] }}
              />
              <span className="text-gray-400 text-[10px] uppercase tracking-wide">{node.type}</span>
              {node.metadata?.pubdate && (
                <span className="text-gray-500 text-[10px] ml-auto">{node.metadata.pubdate}</span>
              )}
            </div>

            {/* Title */}
            <div className="font-semibold text-sm leading-tight mb-1.5 line-clamp-2">{node.label}</div>

            {/* Journal */}
            {node.metadata?.journal && (
              <div className="text-blue-400 text-[10px] mb-1.5 truncate">{node.metadata.journal}</div>
            )}

            {/* Quick stats */}
            <div className="flex flex-wrap gap-1.5 mt-2">
              {node.metadata?.certainty_score !== undefined && (
                <span className="px-1.5 py-0.5 rounded text-[9px] bg-green-500/20 text-green-400">
                  {Math.round(node.metadata.certainty_score * 100)}% match
                </span>
              )}
              {node.metadata?.paper_count !== undefined && (
                <span className="px-1.5 py-0.5 rounded text-[9px] bg-purple-500/20 text-purple-400">
                  {node.metadata.paper_count} papers
                </span>
              )}
              {node.metadata?.domain && (
                <span className="px-1.5 py-0.5 rounded text-[9px] bg-orange-500/20 text-orange-400">
                  {node.metadata.domain}
                </span>
              )}
            </div>

            {/* Abstract preview */}
            {node.metadata?.abstract && (
              <div className="mt-2 pt-2 border-t border-white/10">
                <p className="text-gray-400 text-[10px] leading-relaxed line-clamp-2">
                  {node.metadata.abstract.slice(0, 120)}...
                </p>
              </div>
            )}

            {/* Click hint */}
            <div className="mt-2 pt-1.5 border-t border-white/5 text-center">
              <span className="text-gray-500 text-[9px]">Click for details</span>
            </div>
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
}

function LinkLine({ start, end, type, isHighlighted }: LinkLineProps) {
  const color = isHighlighted ? "#60a5fa" : LINK_COLORS[type] || "#64748b";

  return (
    <Line
      points={[start, end]}
      color={color}
      lineWidth={isHighlighted ? 2 : 0.5}
      transparent
      opacity={isHighlighted ? 0.8 : 0.4}
    />
  );
}

interface SceneProps {
  nodes: GraphNode[];
  links: GraphLink[];
  activeFilters: ActiveFilters;
  minSimilarity: number;
  searchQuery: string;
  onNodeClick: (node: GraphNode) => void;
  onStatsChange: (nodeCount: number, linkCount: number) => void;
}

function Scene({
  nodes,
  links,
  activeFilters,
  minSimilarity,
  searchQuery,
  onNodeClick,
  onStatsChange,
}: SceneProps) {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const { camera } = useThree();

  // 노드 위치 계산 (force-directed 시뮬레이션 대체)
  const nodePositions = useMemo(() => {
    const positions = new Map<string, [number, number, number]>();
    const filteredNodes = nodes.filter((n) => activeFilters[n.type as keyof ActiveFilters]);

    filteredNodes.forEach((node, index) => {
      // 타입별로 그룹화하여 배치
      const typeIndex = ["paper", "author", "keyword", "concept"].indexOf(node.type);
      const angleOffset = (typeIndex * Math.PI) / 2;
      const radius = 15 + typeIndex * 5;
      const nodesOfType = filteredNodes.filter((n) => n.type === node.type);
      const indexInType = nodesOfType.indexOf(node);
      const angleStep = (2 * Math.PI) / Math.max(nodesOfType.length, 1);
      const angle = angleOffset + indexInType * angleStep;

      // 3D 분포를 위해 y값도 변화
      const yOffset = (Math.random() - 0.5) * 10;

      positions.set(node.id, [
        Math.cos(angle) * radius,
        yOffset,
        Math.sin(angle) * radius,
      ]);
    });

    return positions;
  }, [nodes, activeFilters]);

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

  // 하이라이트 노드/링크 계산
  const { highlightNodes, highlightLinks } = useMemo(() => {
    const highlightNodes = new Set<string>();
    const highlightLinks = new Set<string>();

    if (hoveredNode) {
      highlightNodes.add(hoveredNode);
      filteredLinks.forEach((l) => {
        if (l.source === hoveredNode || l.target === hoveredNode) {
          highlightLinks.add(`${l.source}-${l.target}`);
          highlightNodes.add(l.source);
          highlightNodes.add(l.target);
        }
      });
    }

    return { highlightNodes, highlightLinks };
  }, [hoveredNode, filteredLinks]);

  // 카메라 초기 위치 설정
  useEffect(() => {
    camera.position.set(30, 20, 30);
    camera.lookAt(0, 0, 0);
  }, [camera]);

  return (
    <>
      {/* Ambient Light */}
      <ambientLight intensity={0.4} />
      <pointLight position={[50, 50, 50]} intensity={1} />
      <pointLight position={[-50, -50, -50]} intensity={0.5} />

      {/* Links */}
      {filteredLinks.map((link) => {
        const startPos = nodePositions.get(link.source);
        const endPos = nodePositions.get(link.target);
        if (!startPos || !endPos) return null;

        const linkId = `${link.source}-${link.target}`;
        return (
          <LinkLine
            key={linkId}
            start={startPos}
            end={endPos}
            type={link.type}
            isHighlighted={highlightLinks.has(linkId)}
          />
        );
      })}

      {/* Nodes */}
      {filteredNodes.map((node) => {
        const position = nodePositions.get(node.id);
        if (!position) return null;

        return (
          <NodeMesh
            key={node.id}
            node={node}
            position={position}
            isHighlighted={highlightNodes.has(node.id)}
            onClick={() => onNodeClick(node)}
            onHover={(hover) => setHoveredNode(hover ? node.id : null)}
          />
        );
      })}

      {/* Controls */}
      <OrbitControls
        enableDamping
        dampingFactor={0.05}
        minDistance={10}
        maxDistance={100}
        autoRotate={false}
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
  onNodeClick: (node: GraphNode) => void;
  onStatsChange: (nodeCount: number, linkCount: number) => void;
}

export default function VectorGraph3D({
  nodes,
  links,
  activeFilters,
  minSimilarity,
  searchQuery,
  onNodeClick,
  onStatsChange,
}: VectorGraph3DProps) {
  return (
    <div className="w-full h-full">
      <Canvas
        camera={{ position: [30, 20, 30], fov: 60 }}
        gl={{ antialias: true, alpha: true }}
        style={{ background: "transparent" }}
      >
        <Scene
          nodes={nodes}
          links={links}
          activeFilters={activeFilters}
          minSimilarity={minSimilarity}
          searchQuery={searchQuery}
          onNodeClick={onNodeClick}
          onStatsChange={onStatsChange}
        />
      </Canvas>
    </div>
  );
}
