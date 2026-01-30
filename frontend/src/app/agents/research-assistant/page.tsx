"use client";

import { useState, useCallback, useMemo, useRef, useEffect } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import {
  Search,
  Bot,
  MessageSquare,
  BarChart3,
  BookOpen,
  Sparkles,
  X,
  ArrowRight,
  FileText,
  TrendingUp,
  Library,
  Brain,
  Box,
  Layers,
} from "lucide-react";
import type { GraphNode, GraphLink, ActiveFilters, ViewMode } from "./types";
import { generateSampleGraphData, EXAMPLE_QUESTIONS } from "./constants";
import { researchAssistantApi } from "@/lib/api";
import {
  ControlPanel,
  LinkSummaryPanel,
  NodeDetailPanel,
  QuestionInputPanel,
} from "./components";

// Graph 컴포넌트를 동적으로 로드 (SSR 비활성화)
const VectorGraph2D = dynamic(() => import("./components/VectorGraph2D"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center">
      <div className="flex items-center gap-3 text-slate-400">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-sm">Loading 2D Graph...</span>
      </div>
    </div>
  ),
});

// 3D Graph는 별도 서버(port 10000)에서 iframe으로 로드
const GRAPH_3D_URL = process.env.NEXT_PUBLIC_3D_GRAPH_URL || "http://oaria.3d.sday.me";

// ─────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────

export default function ResearchAssistantPage() {
  // View mode
  const [viewMode, setViewMode] = useState<ViewMode>("landing");

  // Graph dimension mode (2d or 3d)
  const [graphMode, setGraphMode] = useState<"2d" | "3d">("2d");

  // Graph data
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; links: GraphLink[] }>(() =>
    generateSampleGraphData()
  );

  // Current query
  const [currentQuery, setCurrentQuery] = useState<string>("");

  // Graph controls
  const [activeFilters, setActiveFilters] = useState<ActiveFilters>({
    paper: true,
    author: true,
    keyword: true,
    concept: true,
  });
  const [searchQuery, setSearchQuery] = useState("");
  const [minSimilarity, setMinSimilarity] = useState(0.7);

  // Highlight state
  const [highlightNodes, setHighlightNodes] = useState<Set<string>>(new Set());
  const [highlightLinks, setHighlightLinks] = useState<Set<GraphLink>>(
    new Set()
  );

  // Selected node
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  // Stats
  const [nodeCount, setNodeCount] = useState(0);
  const [linkCount, setLinkCount] = useState(0);

  // Question input
  const [showQuestionInput, setShowQuestionInput] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  // 3D Graph iframe ref
  const iframe3DRef = useRef<HTMLIFrameElement>(null);
  const [iframe3DReady, setIframe3DReady] = useState(false);

  // iframe 통신: 그래프 데이터 전송
  useEffect(() => {
    if (graphMode === "3d" && iframe3DReady && iframe3DRef.current?.contentWindow) {
      // 토큰 전송
      const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
      if (token) {
        iframe3DRef.current.contentWindow.postMessage({
          type: "SET_TOKEN",
          payload: { token },
        }, "*");
      }

      // 그래프 데이터 전송
      iframe3DRef.current.contentWindow.postMessage({
        type: "SET_GRAPH_DATA",
        payload: {
          nodes: graphData.nodes,
          links: graphData.links,
          query: currentQuery,
        },
      }, "*");
    }
  }, [graphMode, iframe3DReady, graphData, currentQuery]);

  // iframe 메시지 수신 (3D 그래프에서 READY 신호)
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === "READY") {
        setIframe3DReady(true);
      }
    };
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  // Filter toggle handler
  const handleFilterToggle = useCallback((type: keyof ActiveFilters) => {
    setActiveFilters((prev) => ({ ...prev, [type]: !prev[type] }));
  }, []);

  // Node hover handler
  const handleNodeHover = useCallback(
    (node: GraphNode | null) => {
      const newHighlightNodes = new Set<string>();
      const newHighlightLinks = new Set<GraphLink>();

      if (node) {
        newHighlightNodes.add(node.id);
        graphData.links.forEach((l) => {
          const sourceId = typeof l.source === "string" ? l.source : l.source.id;
          const targetId = typeof l.target === "string" ? l.target : l.target.id;
          if (sourceId === node.id || targetId === node.id) {
            newHighlightLinks.add(l);
            newHighlightNodes.add(sourceId);
            newHighlightNodes.add(targetId);
          }
        });
      }

      setHighlightNodes(newHighlightNodes);
      setHighlightLinks(newHighlightLinks);
    },
    [graphData.links]
  );

  // Node click handler
  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNode(node);
  }, []);

  // Stats change handler
  const handleStatsChange = useCallback((nodes: number, links: number) => {
    setNodeCount(nodes);
    setLinkCount(links);
  }, []);

  // Question submit handler - API 호출하여 벡터 그래프 데이터 가져오기
  const handleQuestionSubmit = useCallback(async (question: string) => {
    setIsProcessing(true);
    setCurrentQuery(question);
    console.log("Research Question:", question);

    try {
      // 벡터 API 호출
      const response = await researchAssistantApi.searchVectorGraph({
        query: question,
        limit: 50,
        min_similarity: 0.6,
        include_authors: true,
        include_keywords: true,
      });

      // 그래프 데이터 업데이트
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
      console.log(`Loaded ${newNodes.length} nodes and ${newLinks.length} links`);
    } catch (error) {
      console.error("Vector search error:", error);
      // API 실패 시 샘플 데이터 유지 (또는 에러 처리)
    } finally {
      setIsProcessing(false);
      setShowQuestionInput(false);
    }
  }, []);

  // Filtered links for summary panel
  const filteredLinks = useMemo(() => {
    const nodeIds = new Set(
      graphData.nodes
        .filter((n) => activeFilters[n.type as keyof ActiveFilters])
        .map((n) => n.id)
    );
    return graphData.links.filter((l) => {
      const sourceId = typeof l.source === "string" ? l.source : l.source.id;
      const targetId = typeof l.target === "string" ? l.target : l.target.id;
      return (
        nodeIds.has(sourceId) &&
        nodeIds.has(targetId) &&
        (l.similarity ?? 1) >= minSimilarity
      );
    });
  }, [graphData, activeFilters, minSimilarity]);

  // ─────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────

  return (
    <>
      {/* Graph View - Fullscreen Overlay */}
      {viewMode === "graph" && (
        <div
          className="fixed inset-0 z-[200]"
          style={{
            background:
              "linear-gradient(135deg, #060a14 0%, #0a1020 40%, #0e1830 100%)",
          }}
        >
          {/* Grid Pattern Overlay */}
          <div
            className="absolute inset-0 pointer-events-none opacity-[0.025]"
            style={{
              backgroundImage:
                "radial-gradient(circle, #fff 1px, transparent 1px)",
              backgroundSize: "48px 48px",
            }}
          />

          {/* Top Bar - X button and 2D/3D toggle */}
          <div className="absolute top-4 left-0 right-0 z-[220] flex items-center justify-between px-5">
            {/* Left: Mode indicator & Current Query (2D 모드에서만 쿼리 표시) */}
            <div className="flex items-center gap-3">
              <div className={`px-3 py-1.5 rounded-lg text-white text-xs font-medium flex items-center gap-1.5 ${graphMode === "2d" ? "bg-blue-600" : "bg-purple-600"}`}>
                <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
                {graphMode === "2d" ? "2D" : "3D"} Force Graph
              </div>
              {graphMode === "2d" && currentQuery && (
                <div className="px-3 py-1.5 rounded-lg bg-blue-600/20 text-blue-400 text-xs font-medium flex items-center gap-1.5 max-w-md truncate">
                  <Search size={12} />
                  <span className="truncate">{currentQuery}</span>
                </div>
              )}
            </div>

            {/* Center: 2D/3D Toggle */}
            <div
              className="flex items-center rounded-lg overflow-hidden"
              style={{
                background: "rgba(10, 14, 26, 0.9)",
                backdropFilter: "blur(20px)",
                border: "1px solid rgba(255, 255, 255, 0.1)",
              }}
            >
              <button
                onClick={() => setGraphMode("2d")}
                className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium transition-all ${
                  graphMode === "2d"
                    ? "bg-blue-600 text-white"
                    : "text-white/50 hover:text-white hover:bg-white/10"
                }`}
              >
                <Layers size={16} />
                2D
              </button>
              <button
                onClick={() => setGraphMode("3d")}
                className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium transition-all ${
                  graphMode === "3d"
                    ? "bg-purple-600 text-white"
                    : "text-white/50 hover:text-white hover:bg-white/10"
                }`}
              >
                <Box size={16} />
                3D
              </button>
            </div>

            {/* Right: Close Button */}
            <button
              onClick={() => setViewMode("landing")}
              className="w-10 h-10 rounded-lg flex items-center justify-center text-white/60 hover:text-white hover:bg-white/10 transition-all cursor-pointer group"
              style={{
                background: "rgba(10, 14, 26, 0.9)",
                backdropFilter: "blur(20px)",
                border: "1px solid rgba(255, 255, 255, 0.1)",
              }}
            >
              <X
                size={20}
                className="group-hover:rotate-90 transition-transform duration-300"
              />
            </button>
          </div>

          {/* Vector Graph - 2D or 3D based on mode */}
          {graphMode === "2d" ? (
            <VectorGraph2D
              nodes={graphData.nodes}
              links={graphData.links}
              activeFilters={activeFilters}
              minSimilarity={minSimilarity}
              searchQuery={searchQuery}
              highlightNodes={highlightNodes}
              highlightLinks={highlightLinks}
              onNodeHover={handleNodeHover}
              onNodeClick={handleNodeClick}
              onStatsChange={handleStatsChange}
            />
          ) : (
            /* 3D Graph - iframe으로 별도 서버에서 로드 */
            <iframe
              ref={iframe3DRef}
              src={GRAPH_3D_URL}
              className="absolute inset-0 w-full h-full border-0"
              style={{ background: "transparent" }}
              allow="accelerometer; autoplay; encrypted-media; gyroscope"
              onLoad={() => {
                // iframe 로드 완료 시 데이터 전송 시도
                if (iframe3DRef.current?.contentWindow) {
                  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
                  if (token) {
                    iframe3DRef.current.contentWindow.postMessage({
                      type: "SET_TOKEN",
                      payload: { token },
                    }, "*");
                  }
                  iframe3DRef.current.contentWindow.postMessage({
                    type: "SET_GRAPH_DATA",
                    payload: {
                      nodes: graphData.nodes,
                      links: graphData.links,
                      query: currentQuery,
                    },
                  }, "*");
                }
              }}
            />
          )}

          {/* Control Panel - Left side, below top bar (2D 모드에서만 표시) */}
          {graphMode === "2d" && (
            <div className="absolute top-20 left-5 z-[210]">
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
          )}

          {/* Link Summary Panel - Right side, below top bar (2D 모드에서만 표시) */}
          {graphMode === "2d" && (
            <div className="absolute top-20 right-5 z-[210]">
              <LinkSummaryPanel links={filteredLinks} nodes={graphData.nodes} />
            </div>
          )}

          {/* Node Detail Panel (2D 모드에서만 표시) */}
          {graphMode === "2d" && selectedNode && (
            <NodeDetailPanel
              node={selectedNode}
              nodes={graphData.nodes}
              links={graphData.links}
              onClose={() => setSelectedNode(null)}
            />
          )}

          {/* Question Input Toggle Button */}
          {!showQuestionInput && !selectedNode && (
            <button
              onClick={() => setShowQuestionInput(true)}
              className="absolute bottom-6 left-1/2 -translate-x-1/2 z-[215] px-6 py-3 rounded-xl text-white font-bold flex items-center gap-3 shadow-xl hover:shadow-2xl transition-all hover:scale-105"
              style={{
                background: "linear-gradient(135deg, #2563eb, #7c3aed)",
                boxShadow: "0 8px 32px rgba(37,99,235,0.4)",
              }}
            >
              <Sparkles size={20} />
              새로운 연구 질문
            </button>
          )}

          {/* Question Input Panel */}
          {showQuestionInput && !selectedNode && (
            <QuestionInputPanel
              onSubmit={handleQuestionSubmit}
              isProcessing={isProcessing}
              onClose={() => setShowQuestionInput(false)}
            />
          )}
        </div>
      )}

      {/* Normal Page Layout */}
      <div className="h-full flex flex-col">
        {/* Header with Tabs */}
        <div className="bg-[var(--background)]">
          <div className="flex items-center justify-center">
            <div className="flex items-center gap-6">
              <Link
                href="/ask"
                className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
              >
                <MessageSquare size={20} />
                Ask AI
              </Link>
              <Link
                href="/main"
                className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
              >
                <Search size={20} />
                Search Papers
              </Link>
              <Link
                href="/agents"
                className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-[var(--oaria-teal)] text-[var(--oaria-teal)]"
              >
                <Bot size={20} />
                Agents
              </Link>
              <Link
                href="/dashboard"
                className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
              >
                <BarChart3 size={20} />
                Dashboard
              </Link>
            </div>
          </div>
        </div>

        {/* Main Content - Landing View */}
        <div className="flex-1 overflow-auto">
          <div className="h-full overflow-y-auto">
            <div className="max-w-5xl mx-auto px-6 py-8">
              {/* Hero Section */}
              <div className="text-center mb-12">
                <div
                  className="w-24 h-24 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-2xl"
                  style={{
                    background: "linear-gradient(135deg, #1E293B, #334155)",
                  }}
                >
                  <Brain size={48} className="text-white" />
                </div>
                <h1 className="font-[family-name:var(--font-outfit)] text-4xl font-bold mb-4 bg-gradient-to-r from-slate-900 to-slate-600 dark:from-white dark:to-slate-400 bg-clip-text text-transparent">
                  Research Assistant
                </h1>
                <p className="font-[family-name:var(--font-dm-sans)] text-lg text-[var(--oaria-text-secondary)] max-w-2xl mx-auto mb-2">
                  <span className="font-semibold text-blue-600">
                    Vector-Based Reasoning Engine
                  </span>
                </p>
                <p className="font-[family-name:var(--font-dm-sans)] text-base text-[var(--oaria-text-secondary)] max-w-2xl mx-auto mb-8">
                  복잡한 연구 질문을 구조화하고, 의미 기반 벡터 공간에서 지식들을
                  연결하며, 시각적 그래프 구조로 표현합니다. 2D/3D 모드 전환을 지원합니다.
                </p>
                <button
                  onClick={() => setViewMode("graph")}
                  className="inline-flex items-center gap-3 px-8 py-4 rounded-xl text-white font-bold text-lg shadow-xl hover:shadow-2xl transition-all hover:scale-105"
                  style={{
                    background: "linear-gradient(135deg, #1E293B, #0F172A)",
                  }}
                >
                  <Sparkles size={24} />
                  Vector Graph 시작하기
                  <ArrowRight size={20} />
                </button>
              </div>

              {/* Feature Cards */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-12">
                <div className="p-5 rounded-xl border border-[var(--oaria-border)] bg-[var(--background)] hover:shadow-lg transition-shadow">
                  <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mb-3">
                    <FileText size={20} className="text-blue-600" />
                  </div>
                  <h3 className="font-[family-name:var(--font-outfit)] text-base font-semibold mb-1">
                    의미 분해
                  </h3>
                  <p className="font-[family-name:var(--font-dm-sans)] text-xs text-[var(--oaria-text-secondary)]">
                    연구 질문을 핵심 개념 노드로 분해
                  </p>
                </div>
                <div className="p-5 rounded-xl border border-[var(--oaria-border)] bg-[var(--background)] hover:shadow-lg transition-shadow">
                  <div className="w-10 h-10 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center mb-3">
                    <TrendingUp size={20} className="text-green-600" />
                  </div>
                  <h3 className="font-[family-name:var(--font-outfit)] text-base font-semibold mb-1">
                    관계 매핑
                  </h3>
                  <p className="font-[family-name:var(--font-dm-sans)] text-xs text-[var(--oaria-text-secondary)]">
                    노드 간 가중치 엣지 연결
                  </p>
                </div>
                <div className="p-5 rounded-xl border border-[var(--oaria-border)] bg-[var(--background)] hover:shadow-lg transition-shadow">
                  <div className="w-10 h-10 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center mb-3">
                    <Library size={20} className="text-purple-600" />
                  </div>
                  <h3 className="font-[family-name:var(--font-outfit)] text-base font-semibold mb-1">
                    2D/3D 시각화
                  </h3>
                  <p className="font-[family-name:var(--font-dm-sans)] text-xs text-[var(--oaria-text-secondary)]">
                    Semantic Graph 인터랙티브 탐색
                  </p>
                </div>
                <div className="p-5 rounded-xl border border-[var(--oaria-border)] bg-[var(--background)] hover:shadow-lg transition-shadow">
                  <div className="w-10 h-10 rounded-lg bg-orange-100 dark:bg-orange-900/30 flex items-center justify-center mb-3">
                    <Brain size={20} className="text-orange-600" />
                  </div>
                  <h3 className="font-[family-name:var(--font-outfit)] text-base font-semibold mb-1">
                    추론 실행
                  </h3>
                  <p className="font-[family-name:var(--font-dm-sans)] text-xs text-[var(--oaria-text-secondary)]">
                    Chain-of-Thought 경로 탐색
                  </p>
                </div>
              </div>

              {/* Example Questions */}
              <div className="mb-12">
                <h2 className="font-[family-name:var(--font-outfit)] text-xl font-semibold mb-6 text-center">
                  이런 질문을 해보세요
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {EXAMPLE_QUESTIONS.map((category) => (
                    <div key={category.category}>
                      <div className="flex items-center gap-2 mb-3">
                        <span className="text-[var(--oaria-text-secondary)]">
                          {category.category === "논문 분석" && (
                            <FileText size={16} />
                          )}
                          {category.category === "연구 동향" && (
                            <TrendingUp size={16} />
                          )}
                          {category.category === "문헌 고찰" && (
                            <Library size={16} />
                          )}
                        </span>
                        <span className="font-[family-name:var(--font-dm-sans)] text-sm font-medium text-[var(--oaria-text-secondary)]">
                          {category.category}
                        </span>
                      </div>
                      <div className="space-y-2">
                        {category.questions.map((question, idx) => (
                          <button
                            key={idx}
                            onClick={() => {
                              setViewMode("graph");
                              handleQuestionSubmit(question);
                            }}
                            className="w-full text-left p-3 rounded-lg border border-[var(--oaria-border)] hover:border-[#1E293B] hover:bg-[#1E293B]/5 transition-colors"
                          >
                            <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--foreground)]">
                              {question}
                            </p>
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* System Objective */}
              <div
                className="rounded-2xl p-6 mb-8"
                style={{
                  background:
                    "linear-gradient(135deg, rgba(30,41,59,0.05), rgba(30,41,59,0.02))",
                  border: "1px solid rgba(30,41,59,0.1)",
                }}
              >
                <h3 className="font-[family-name:var(--font-outfit)] text-lg font-semibold mb-4 flex items-center gap-2">
                  <BookOpen size={20} className="text-slate-600" />
                  System Objective
                </h3>
                <div className="space-y-2 text-sm text-[var(--oaria-text-secondary)]">
                  <p>
                    1. 입력된 연구 질문을 의미 단위로 분해
                  </p>
                  <p>
                    2. 각 의미 단위를 벡터 노드(Vector Node)로 정의
                  </p>
                  <p>
                    3. 노드 간 관계를 가중치가 있는 엣지로 연결
                  </p>
                  <p>
                    4. 전체를 Semantic Graph로 시각화 (2D/3D 전환 가능)
                  </p>
                  <p>
                    5. 추론 경로를 따라 노드들을 순차적으로 탐색
                  </p>
                  <p>
                    6. 최종 결론을 신뢰도, 근거 노드, 반례 가능성과 함께 제시
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
