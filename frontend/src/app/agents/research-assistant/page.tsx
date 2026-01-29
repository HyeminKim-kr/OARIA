"use client";

import { useState, useCallback, useMemo } from "react";
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
} from "lucide-react";
import type { GraphNode, GraphLink, ActiveFilters, ViewMode } from "./types";
import { generateSampleGraphData, EXAMPLE_QUESTIONS } from "./constants";
import {
  ControlPanel,
  LinkSummaryPanel,
  NodeDetailPanel,
  QuestionInputPanel,
} from "./components";

// VectorGraph3D를 동적으로 로드 (SSR 비활성화)
const VectorGraph3D = dynamic(() => import("./components/VectorGraph3D"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center">
      <div className="flex items-center gap-3 text-slate-400">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-sm">Loading 3D Graph...</span>
      </div>
    </div>
  ),
});

// ─────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────

export default function ResearchAssistantPage() {
  // View mode
  const [viewMode, setViewMode] = useState<ViewMode>("landing");

  // Graph data
  const [graphData] = useState<{ nodes: GraphNode[]; links: GraphLink[] }>(() =>
    generateSampleGraphData()
  );

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

  // Question submit handler
  const handleQuestionSubmit = useCallback((question: string) => {
    setIsProcessing(true);
    console.log("Research Question:", question);

    // TODO: 실제 API 호출 및 그래프 데이터 업데이트
    setTimeout(() => {
      setIsProcessing(false);
      setShowQuestionInput(false);
    }, 2000);
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
    <div className="h-full flex flex-col overflow-hidden">
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

      {/* Main Content */}
      <div className="flex-1 overflow-hidden">
        {viewMode === "landing" ? (
          // ─────────────────────────────────────────────────────────────
          // Landing View
          // ─────────────────────────────────────────────────────────────
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
                    Vector-Based 3D Reasoning Engine
                  </span>
                </p>
                <p className="font-[family-name:var(--font-dm-sans)] text-base text-[var(--oaria-text-secondary)] max-w-2xl mx-auto mb-8">
                  복잡한 연구 질문을 구조화하고, 의미 기반 벡터 공간에서 지식들을
                  연결하며, 시각적으로 아름다운 3D 그래프 구조로 표현합니다.
                </p>
                <button
                  onClick={() => setViewMode("graph")}
                  className="inline-flex items-center gap-3 px-8 py-4 rounded-xl text-white font-bold text-lg shadow-xl hover:shadow-2xl transition-all hover:scale-105"
                  style={{
                    background: "linear-gradient(135deg, #1E293B, #0F172A)",
                  }}
                >
                  <Sparkles size={24} />
                  3D Vector Graph 시작하기
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
                    3D 시각화
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
                            onClick={() => setViewMode("graph")}
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
                    4. 전체를 3D Semantic Graph로 시각화
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
        ) : (
          // ─────────────────────────────────────────────────────────────
          // Graph View
          // ─────────────────────────────────────────────────────────────
          <div
            className="relative w-full h-full"
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

            {/* Close Button */}
            <button
              onClick={() => setViewMode("landing")}
              className="absolute top-5 right-5 z-[120] w-10 h-10 rounded-lg flex items-center justify-center text-white/50 hover:text-white hover:bg-white/10 transition-all cursor-pointer group"
              style={{
                background: "rgba(10, 14, 26, 0.82)",
                backdropFilter: "blur(20px)",
                border: "1px solid rgba(255, 255, 255, 0.08)",
              }}
            >
              <X
                size={20}
                className="group-hover:rotate-90 transition-transform duration-300"
              />
            </button>

            {/* 3D Vector Graph */}
            <VectorGraph3D
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

            {/* Control Panel */}
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

            {/* Link Summary Panel */}
            <LinkSummaryPanel links={filteredLinks} nodes={graphData.nodes} />

            {/* Node Detail Panel */}
            {selectedNode && (
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
                className="absolute bottom-6 left-1/2 -translate-x-1/2 z-[115] px-6 py-3 rounded-xl text-white font-bold flex items-center gap-3 shadow-xl hover:shadow-2xl transition-all hover:scale-105"
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
      </div>
    </div>
  );
}
