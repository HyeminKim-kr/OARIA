"use client";

import { useState, useCallback, useEffect } from "react";
import dynamic from "next/dynamic";
import type { GraphNode, GraphLink, ActiveFilters } from "@/lib/types";
import { researchAssistantApi, setAccessToken } from "@/lib/api";
import { ControlPanel, NodeDetailPanel, QuestionInputPanel } from "@/components";

// Three.js 컴포넌트는 클라이언트에서만 로드
const VectorGraph3D = dynamic(() => import("@/components/VectorGraph3D"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center">
      <div className="flex items-center gap-3 text-slate-400">
        <div className="w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-sm">Loading 3D Graph...</span>
      </div>
    </div>
  ),
});

export default function Home() {
  // 초기에는 빈 그래프 (질문 입력 후 데이터 로드)
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; links: GraphLink[] }>({
    nodes: [],
    links: [],
  });
  const [currentQuery, setCurrentQuery] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showQuestionInput, setShowQuestionInput] = useState(true);

  // Controls
  const [activeFilters, setActiveFilters] = useState<ActiveFilters>({
    paper: true,
    author: true,
    keyword: true,
    concept: true,
  });
  const [searchQuery, setSearchQuery] = useState("");
  const [minSimilarity, setMinSimilarity] = useState(0.7);

  // Selected node
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  // Stats
  const [nodeCount, setNodeCount] = useState(0);
  const [linkCount, setLinkCount] = useState(0);

  // Filter toggle handler
  const handleFilterToggle = useCallback((type: keyof ActiveFilters) => {
    setActiveFilters((prev) => ({ ...prev, [type]: !prev[type] }));
  }, []);

  // Node click handler
  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNode(node);
  }, []);

  // Stats change handler
  const handleStatsChange = useCallback((nodes: number, links: number) => {
    setNodeCount(nodes);
    setLinkCount(links);
  }, []);

  // Question submit handler - API 호출
  const handleQuestionSubmit = useCallback(async (question: string) => {
    setIsLoading(true);
    setCurrentQuery(question);
    setError(null);

    try {
      const response = await researchAssistantApi.searchVectorGraph({
        query: question,
        limit: 50,
        min_similarity: 0.6,
        include_authors: true,
        include_keywords: true,
      });

      const newNodes: GraphNode[] = response.nodes.map((node) => ({
        id: node.id,
        type: node.type,
        label: node.label,
        cluster: node.cluster,
        metadata: node.metadata,
      }));

      const newLinks: GraphLink[] = response.links.map((link) => ({
        source: link.source,
        target: link.target,
        type: link.type,
        similarity: link.similarity,
        weight: link.weight,
        evidence_hint: link.evidence_hint,
      }));

      setGraphData({ nodes: newNodes, links: newLinks });
      setShowQuestionInput(false);
    } catch (err) {
      console.error("Vector search error:", err);
      setError("API 연결 실패. 다시 시도해주세요.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 부모 창에서 메시지 수신 (iframe 통신)
  useEffect(() => {
    const handleMessage = async (event: MessageEvent) => {
      // 보안을 위해 origin 체크 (필요시 특정 도메인으로 제한)
      const { type, payload } = event.data || {};

      if (type === "SET_TOKEN") {
        setAccessToken(payload.token);
      }

      if (type === "SEARCH_QUERY") {
        const query = payload.query;
        if (!query) return;

        setCurrentQuery(query);
        setIsLoading(true);
        setError(null);

        try {
          const response = await researchAssistantApi.searchVectorGraph({
            query,
            limit: 50,
            min_similarity: 0.6,
            include_authors: true,
            include_keywords: true,
          });

          const newNodes: GraphNode[] = response.nodes.map((node) => ({
            id: node.id,
            type: node.type,
            label: node.label,
            cluster: node.cluster,
            metadata: node.metadata,
          }));

          const newLinks: GraphLink[] = response.links.map((link) => ({
            source: link.source,
            target: link.target,
            type: link.type,
            similarity: link.similarity,
            weight: link.weight,
            evidence_hint: link.evidence_hint,
          }));

          setGraphData({ nodes: newNodes, links: newLinks });
          setShowQuestionInput(false);
        } catch (err) {
          console.error("Vector search error:", err);
          setError("Failed to fetch data.");
        } finally {
          setIsLoading(false);
        }
      }

      if (type === "SET_GRAPH_DATA") {
        // 직접 데이터 전달
        const { nodes, links } = payload;
        if (nodes && links) {
          setGraphData({ nodes, links });
          setCurrentQuery(payload.query || "");
          setShowQuestionInput(false);
        }
      }
    };

    window.addEventListener("message", handleMessage);

    // 부모에게 준비 완료 알림
    if (window.parent !== window) {
      window.parent.postMessage({ type: "READY" }, "*");
    }

    return () => {
      window.removeEventListener("message", handleMessage);
    };
  }, []);

  // URL 파라미터에서 쿼리 읽기
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const query = params.get("query");
    const token = params.get("token");

    if (token) {
      setAccessToken(token);
    }

    if (query) {
      setCurrentQuery(query);
      setIsLoading(true);
      setShowQuestionInput(false); // URL에 쿼리가 있으면 입력창 숨김
      researchAssistantApi.searchVectorGraph({
        query,
        limit: 50,
        min_similarity: 0.6,
        include_authors: true,
        include_keywords: true,
      })
        .then((response) => {
          const newNodes: GraphNode[] = response.nodes.map((node) => ({
            id: node.id,
            type: node.type,
            label: node.label,
            cluster: node.cluster,
            metadata: node.metadata,
          }));

          const newLinks: GraphLink[] = response.links.map((link) => ({
            source: link.source,
            target: link.target,
            type: link.type,
            similarity: link.similarity,
            weight: link.weight,
            evidence_hint: link.evidence_hint,
          }));

          setGraphData({ nodes: newNodes, links: newLinks });
        })
        .catch((err) => {
          console.error("Vector search error:", err);
          setError("Failed to fetch data.");
        })
        .finally(() => {
          setIsLoading(false);
        });
    }
  }, []);

  return (
    <div
      className="w-screen h-screen overflow-hidden relative"
      style={{
        background: "linear-gradient(135deg, #060a14 0%, #0a1020 40%, #0e1830 100%)",
      }}
    >
      {/* Grid Pattern Overlay */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.025]"
        style={{
          backgroundImage: "radial-gradient(circle, #fff 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />

      {/* Header - Query 및 상태 표시 */}
      <div className="absolute top-4 left-4 right-4 z-20 flex items-center justify-between">
        {/* Left: Current Query */}
        <div className="flex items-center gap-3">
          {currentQuery && !showQuestionInput && (
            <div className="px-3 py-1.5 rounded-lg bg-purple-600/20 text-purple-400 text-xs font-medium flex items-center gap-2 max-w-md truncate">
              <svg className="w-3 h-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <span className="truncate">{currentQuery}</span>
            </div>
          )}
          {isLoading && (
            <div className="flex items-center gap-2 text-white/60 text-xs">
              <div className="w-4 h-4 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
              Loading...
            </div>
          )}
          {error && (
            <div className="px-3 py-1.5 rounded-lg bg-red-500/20 text-red-400 text-xs">
              {error}
            </div>
          )}
        </div>

        {/* Right: New Query Button */}
        {!showQuestionInput && currentQuery && (
          <button
            onClick={() => setShowQuestionInput(true)}
            className="px-4 py-2 rounded-lg text-white text-xs font-medium flex items-center gap-2 transition-all hover:scale-105"
            style={{
              background: "linear-gradient(135deg, #7c3aed, #a855f7)",
              boxShadow: "0 4px 12px rgba(124,58,237,0.3)",
            }}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            새 질문
          </button>
        )}
      </div>

      {/* 3D Graph */}
      <VectorGraph3D
        nodes={graphData.nodes}
        links={graphData.links}
        activeFilters={activeFilters}
        minSimilarity={minSimilarity}
        searchQuery={searchQuery}
        onNodeClick={handleNodeClick}
        onStatsChange={handleStatsChange}
      />

      {/* Control Panel */}
      <div className="absolute top-20 left-4 z-10">
        <ControlPanel
          nodeCount={nodeCount}
          linkCount={linkCount}
          activeFilters={activeFilters}
          onFilterToggle={handleFilterToggle}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          minSimilarity={minSimilarity}
          onSimilarityChange={setMinSimilarity}
        />
      </div>

      {/* Node Detail Panel */}
      {selectedNode && (
        <NodeDetailPanel
          node={selectedNode}
          nodes={graphData.nodes}
          links={graphData.links}
          onClose={() => setSelectedNode(null)}
        />
      )}

      {/* Zoom Controls */}
      {!showQuestionInput && graphData.nodes.length > 0 && (
        <div className="absolute bottom-6 right-6 flex gap-2 z-10">
          <div
            className="px-4 py-2 rounded-lg text-white/40 text-xs"
            style={{
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.06)",
            }}
          >
            Scroll to zoom / Drag to rotate
          </div>
        </div>
      )}

      {/* Question Input Panel - 처음 또는 새 질문 시 표시 */}
      {showQuestionInput && (
        <QuestionInputPanel
          onSubmit={handleQuestionSubmit}
          isProcessing={isLoading}
        />
      )}
    </div>
  );
}
