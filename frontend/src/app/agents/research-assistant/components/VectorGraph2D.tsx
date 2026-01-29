"use client";

import { useEffect, useRef, useCallback, useState, useMemo } from "react";
import type { GraphNode, GraphLink, ActiveFilters } from "../types";
import { NODE_COLORS, LINK_COLORS } from "../constants";

interface VectorGraph2DProps {
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

interface SimNode extends GraphNode {
    x?: number;
    y?: number;
    vx?: number;
    vy?: number;
    fx?: number | null;
    fy?: number | null;
}

interface SimLink {
    source: SimNode | string;
    target: SimNode | string;
    type: string;
    similarity?: number;
}

export default function VectorGraph2D({
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
}: VectorGraph2DProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const svgRef = useRef<SVGSVGElement>(null);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const simulationRef = useRef<any>(null);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const zoomRef = useRef<any>(null);
    const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
    const isInitializedRef = useRef(false);

    // highlightNodes를 배열로 변환 (메모이제이션)
    const highlightNodeIds = useMemo(() => Array.from(highlightNodes), [highlightNodes]);

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

        return { nodes: filteredNodes as SimNode[], links: filteredLinks as SimLink[] };
    }, [nodes, links, activeFilters, minSimilarity, searchQuery]);

    // 크기 업데이트
    useEffect(() => {
        const updateDimensions = () => {
            if (containerRef.current) {
                const width = containerRef.current.clientWidth;
                const height = containerRef.current.clientHeight;
                if (width > 0 && height > 0) {
                    setDimensions({ width, height });
                }
            }
        };

        updateDimensions();
        window.addEventListener("resize", updateDimensions);
        return () => window.removeEventListener("resize", updateDimensions);
    }, []);

    // D3 시뮬레이션 초기화 (한 번만)
    useEffect(() => {
        if (!dimensions.width || !dimensions.height || isInitializedRef.current) return;

        const initSimulation = async () => {
            try {
                const d3 = await import("d3");

                // 노드 복사본 생성
                const nodesCopy: SimNode[] = filteredData.nodes.map((n) => ({ ...n }));

                // 링크 복사본 생성
                const linksCopy: SimLink[] = filteredData.links.map((l) => ({
                    ...l,
                    source: typeof l.source === "string" ? l.source : l.source.id,
                    target: typeof l.target === "string" ? l.target : l.target.id,
                }));

                // 시뮬레이션 생성
                const simulation = d3
                    .forceSimulation(nodesCopy)
                    .force(
                        "link",
                        d3
                            .forceLink<SimNode, SimLink>(linksCopy)
                            .id((d) => d.id)
                            .distance(80)
                    )
                    .force("charge", d3.forceManyBody().strength(-300))
                    .force("center", d3.forceCenter(dimensions.width / 2, dimensions.height / 2))
                    .force("collision", d3.forceCollide().radius(30));

                simulationRef.current = simulation;

                // SVG 요소 설정
                const svg = d3.select(svgRef.current);
                svg.selectAll("*").remove();

                // 줌 설정
                const g = svg.append("g");
                const zoom = d3.zoom<SVGSVGElement, unknown>()
                    .scaleExtent([0.1, 4])
                    .on("zoom", (event) => {
                        g.attr("transform", event.transform);
                    });

                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                svg.call(zoom as any);
                zoomRef.current = zoom;

                // 링크 그룹
                const linkGroup = g.append("g").attr("class", "links");
                const linkElements = linkGroup
                    .selectAll("line")
                    .data(linksCopy)
                    .join("line")
                    .attr("stroke", (d) => LINK_COLORS[d.type] || "#1e293b")
                    .attr("stroke-width", 1)
                    .attr("stroke-opacity", 0.5);

                // 노드 그룹
                const nodeGroup = g.append("g").attr("class", "nodes");
                const nodeElements = nodeGroup
                    .selectAll("g")
                    .data(nodesCopy)
                    .join("g")
                    .style("cursor", "pointer");

                // 드래그 핸들러 (타입 any 사용)
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                const dragHandler = d3.drag<any, SimNode>()
                    .on("start", (event, d) => {
                        if (!event.active) simulation.alphaTarget(0.3).restart();
                        d.fx = d.x;
                        d.fy = d.y;
                    })
                    .on("drag", (event, d) => {
                        d.fx = event.x;
                        d.fy = event.y;
                    })
                    .on("end", (event, d) => {
                        if (!event.active) simulation.alphaTarget(0);
                        d.fx = null;
                        d.fy = null;
                    });

                nodeElements.call(dragHandler);

                // 노드 원
                nodeElements
                    .append("circle")
                    .attr("r", (d) => (d.type === "paper" ? 12 : d.type === "author" ? 8 : 6))
                    .attr("fill", (d) => NODE_COLORS[d.type] || "#888")
                    .attr("stroke", "#fff")
                    .attr("stroke-width", 1.5)
                    .attr("stroke-opacity", 0.8);

                // 노드 라벨
                nodeElements
                    .append("text")
                    .text((d) => d.label.length > 15 ? d.label.slice(0, 15) + "..." : d.label)
                    .attr("font-size", "10px")
                    .attr("fill", "#fff")
                    .attr("text-anchor", "middle")
                    .attr("dy", (d) => (d.type === "paper" ? 22 : d.type === "author" ? 18 : 14))
                    .attr("opacity", 0.7);

                // 이벤트 핸들러 - onNodeHover는 부모 상태를 변경하므로
                // 무한 루프를 방지하기 위해 debounce 없이 직접 호출
                nodeElements
                    .on("mouseenter", function(event, d) {
                        // 하이라이트 효과
                        d3.select(this).select("circle")
                            .attr("stroke", "#60a5fa")
                            .attr("stroke-width", 3);
                    })
                    .on("mouseleave", function() {
                        // 하이라이트 제거
                        d3.select(this).select("circle")
                            .attr("stroke", "#fff")
                            .attr("stroke-width", 1.5);
                    })
                    .on("click", (event, d) => {
                        const originalNode = nodes.find((n) => n.id === d.id);
                        if (originalNode) onNodeClick(originalNode);
                    });

                // 시뮬레이션 틱
                simulation.on("tick", () => {
                    linkElements
                        .attr("x1", (d) => (d.source as SimNode).x || 0)
                        .attr("y1", (d) => (d.source as SimNode).y || 0)
                        .attr("x2", (d) => (d.target as SimNode).x || 0)
                        .attr("y2", (d) => (d.target as SimNode).y || 0);

                    nodeElements.attr("transform", (d) => `translate(${d.x || 0}, ${d.y || 0})`);
                });

                onStatsChange(filteredData.nodes.length, filteredData.links.length);
                isInitializedRef.current = true;
            } catch (err) {
                console.error("2D Graph initialization error:", err);
            }
        };

        initSimulation();

        return () => {
            if (simulationRef.current) {
                simulationRef.current.stop();
            }
            isInitializedRef.current = false;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [dimensions.width, dimensions.height]);

    // 필터/검색 변경 시 그래프 업데이트
    useEffect(() => {
        if (!simulationRef.current || !svgRef.current || !isInitializedRef.current) return;

        const updateGraph = async () => {
            const d3 = await import("d3");

            // 노드 복사본 생성
            const nodesCopy: SimNode[] = filteredData.nodes.map((n) => ({ ...n }));

            // 링크 복사본 생성
            const linksCopy: SimLink[] = filteredData.links.map((l) => ({
                ...l,
                source: typeof l.source === "string" ? l.source : l.source.id,
                target: typeof l.target === "string" ? l.target : l.target.id,
            }));

            // 기존 시뮬레이션 중지
            simulationRef.current.stop();

            // 새 시뮬레이션 생성
            const simulation = d3
                .forceSimulation(nodesCopy)
                .force(
                    "link",
                    d3
                        .forceLink<SimNode, SimLink>(linksCopy)
                        .id((d) => d.id)
                        .distance(80)
                )
                .force("charge", d3.forceManyBody().strength(-300))
                .force("center", d3.forceCenter(dimensions.width / 2, dimensions.height / 2))
                .force("collision", d3.forceCollide().radius(30));

            simulationRef.current = simulation;

            // SVG 업데이트
            const svg = d3.select(svgRef.current);
            const g = svg.select("g");

            // 링크 업데이트
            const linkElements = g.select(".links")
                .selectAll("line")
                .data(linksCopy)
                .join("line")
                .attr("stroke", (d) => LINK_COLORS[d.type] || "#1e293b")
                .attr("stroke-width", 1)
                .attr("stroke-opacity", 0.5);

            // 노드 업데이트
            const nodeElements = g.select(".nodes")
                .selectAll<SVGGElement, SimNode>("g")
                .data(nodesCopy, (d) => d.id)
                .join(
                    (enter) => {
                        const g = enter.append("g").style("cursor", "pointer");
                        g.append("circle")
                            .attr("r", (d) => (d.type === "paper" ? 12 : d.type === "author" ? 8 : 6))
                            .attr("fill", (d) => NODE_COLORS[d.type] || "#888")
                            .attr("stroke", "#fff")
                            .attr("stroke-width", 1.5)
                            .attr("stroke-opacity", 0.8);
                        g.append("text")
                            .text((d) => d.label.length > 15 ? d.label.slice(0, 15) + "..." : d.label)
                            .attr("font-size", "10px")
                            .attr("fill", "#fff")
                            .attr("text-anchor", "middle")
                            .attr("dy", (d) => (d.type === "paper" ? 22 : d.type === "author" ? 18 : 14))
                            .attr("opacity", 0.7);
                        return g;
                    },
                    (update) => update,
                    (exit) => exit.remove()
                );

            // 드래그 핸들러
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const dragHandler = d3.drag<any, SimNode>()
                .on("start", (event, d) => {
                    if (!event.active) simulation.alphaTarget(0.3).restart();
                    d.fx = d.x;
                    d.fy = d.y;
                })
                .on("drag", (event, d) => {
                    d.fx = event.x;
                    d.fy = event.y;
                })
                .on("end", (event, d) => {
                    if (!event.active) simulation.alphaTarget(0);
                    d.fx = null;
                    d.fy = null;
                });

            nodeElements.call(dragHandler);

            // 이벤트 핸들러
            nodeElements
                .on("mouseenter", function() {
                    d3.select(this).select("circle")
                        .attr("stroke", "#60a5fa")
                        .attr("stroke-width", 3);
                })
                .on("mouseleave", function() {
                    d3.select(this).select("circle")
                        .attr("stroke", "#fff")
                        .attr("stroke-width", 1.5);
                })
                .on("click", (event, d) => {
                    const originalNode = nodes.find((n) => n.id === d.id);
                    if (originalNode) onNodeClick(originalNode);
                });

            // 시뮬레이션 틱
            simulation.on("tick", () => {
                linkElements
                    .attr("x1", (d) => (d.source as SimNode).x || 0)
                    .attr("y1", (d) => (d.source as SimNode).y || 0)
                    .attr("x2", (d) => (d.target as SimNode).x || 0)
                    .attr("y2", (d) => (d.target as SimNode).y || 0);

                nodeElements.attr("transform", (d) => `translate(${d.x || 0}, ${d.y || 0})`);
            });

            onStatsChange(filteredData.nodes.length, filteredData.links.length);
        };

        updateGraph();
    }, [filteredData, dimensions.width, dimensions.height, nodes, onNodeClick, onStatsChange]);

    // 줌 컨트롤
    const handleZoomIn = useCallback(async () => {
        if (!svgRef.current || !zoomRef.current) return;
        const d3 = await import("d3");
        const svg = d3.select(svgRef.current);
        svg.transition().duration(300).call(zoomRef.current.scaleBy, 1.3);
    }, []);

    const handleZoomOut = useCallback(async () => {
        if (!svgRef.current || !zoomRef.current) return;
        const d3 = await import("d3");
        const svg = d3.select(svgRef.current);
        svg.transition().duration(300).call(zoomRef.current.scaleBy, 0.7);
    }, []);

    const handleZoomReset = useCallback(async () => {
        if (!svgRef.current || !zoomRef.current) return;
        const d3 = await import("d3");
        const svg = d3.select(svgRef.current);
        svg.transition().duration(500).call(zoomRef.current.transform, d3.zoomIdentity);
    }, []);

    return (
        <div ref={containerRef} className="absolute inset-0 w-full h-full">
            <svg
                ref={svgRef}
                className="w-full h-full"
                style={{ background: "transparent" }}
            />

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
