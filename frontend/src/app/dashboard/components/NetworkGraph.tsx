"use client";
import { useRef, useEffect } from "react";
import * as d3 from "d3";
import { getChartPalette, getThemeColors } from "../constants";

interface NetworkNode extends d3.SimulationNodeDatum {
  id: string;
  count: number;
}

interface NetworkLink extends d3.SimulationLinkDatum<NetworkNode> {
  weight: number;
}

interface Props {
  nodes: NetworkNode[];
  links: NetworkLink[];
  onNodeClick?: (keyword: string) => void;
}

export default function NetworkGraph({ nodes, links, onNodeClick }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !nodes.length) return;
    const el = ref.current;
    d3.select(el).selectAll("*").remove();

    // Detect dark mode
    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches
      || document.documentElement.classList.contains("dark");
    const theme = getThemeColors(isDark);
    const palette = getChartPalette(isDark);

    const width = el.clientWidth;
    const height = el.clientHeight;
    if (width <= 0 || height <= 0) return;

    const svg = d3
      .select(el)
      .append("svg")
      .attr("width", width)
      .attr("height", height);

    // Zoom container
    const g = svg.append("g");

    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 5])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });

    svg.call(zoom);

    // Zoom controls hint
    svg
      .append("text")
      .attr("x", 8)
      .attr("y", height - 8)
      .text("scroll to zoom · drag to pan")
      .style("font-size", "9px")
      .style("fill", theme.textMuted)
      .style("opacity", 0.8);

    const tip = d3
      .select(el)
      .append("div")
      .style("position", "absolute")
      .style("visibility", "hidden")
      .style("background", theme.tooltipBg)
      .style("border", `1px solid ${theme.tooltipBorder}`)
      .style("border-radius", "10px")
      .style("padding", "8px 14px")
      .style("font-size", "13px")
      .style("box-shadow", `0 4px 20px ${theme.tooltipShadow}`)
      .style("pointer-events", "none")
      .style("z-index", "50")
      .style("color", theme.textPrimary);

    const maxCount = d3.max(nodes, (d) => d.count) || 1;
    const rScale = d3.scaleSqrt().domain([1, maxCount]).range([5, 22]);
    const color = d3.scaleOrdinal<string>().range(palette);

    const maxWeight = d3.max(links, (d) => d.weight) || 1;
    const linkWidth = d3.scaleLinear().domain([1, maxWeight]).range([0.5, 3]);
    const linkOpacity = d3.scaleLinear().domain([1, maxWeight]).range([isDark ? 0.2 : 0.25, isDark ? 0.6 : 0.7]);

    const sim = d3
      .forceSimulation<NetworkNode>(nodes)
      .force(
        "link",
        d3
          .forceLink<NetworkNode, NetworkLink>(links)
          .id((d) => d.id)
          .distance(80)
      )
      .force("charge", d3.forceManyBody().strength(-120))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force(
        "collision",
        d3.forceCollide<NetworkNode>().radius((d) => rScale(d.count) + 4)
      );

    const linkEl = g
      .append("g")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", theme.textSecondary)
      .attr("stroke-opacity", (d) => linkOpacity(d.weight))
      .attr("stroke-width", (d) => linkWidth(d.weight));

    const nodeGroup = g
      .append("g")
      .selectAll("g")
      .data(nodes)
      .join("g")
      .style("cursor", "pointer")
      .on("mouseover", function (_event, d) {
        const connected = new Set<string>();
        connected.add(d.id);
        links.forEach((l) => {
          const s = typeof l.source === "object" ? (l.source as NetworkNode).id : l.source;
          const t = typeof l.target === "object" ? (l.target as NetworkNode).id : l.target;
          if (s === d.id) connected.add(t as string);
          if (t === d.id) connected.add(s as string);
        });

        nodeGroup
          .select("circle")
          .attr("opacity", (n) => (connected.has((n as NetworkNode).id) ? 1 : 0.15));
        linkEl.attr("stroke-opacity", (l) => {
          const s = typeof l.source === "object" ? (l.source as NetworkNode).id : l.source;
          const t = typeof l.target === "object" ? (l.target as NetworkNode).id : l.target;
          return s === d.id || t === d.id ? 0.7 : 0.03;
        });

        tip
          .style("visibility", "visible")
          .html(`<strong>${d.id}</strong><br/>${d.count}건 등장`);
      })
      .on("mousemove", function (event) {
        const [mx, my] = d3.pointer(event, el);
        tip.style("left", `${mx + 16}px`).style("top", `${my - 10}px`);
      })
      .on("mouseout", function () {
        nodeGroup.select("circle").attr("opacity", 0.85);
        linkEl.attr("stroke-opacity", (d) => linkOpacity(d.weight));
        tip.style("visibility", "hidden");
      })
      .on("click", (_event, d) => onNodeClick?.(d.id))
      .call(
        d3
          .drag<SVGGElement, NetworkNode>()
          .on("start", (event, d) => {
            if (!event.active) sim.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) sim.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          }) as any
      );

    nodeGroup
      .append("circle")
      .attr("r", (d) => rScale(d.count))
      .attr("fill", (_d, i) => color(String(i)))
      .attr("opacity", 0.9)
      .attr("stroke", theme.surface)
      .attr("stroke-width", 2);

    // Text inside nodes - use white for visibility on colored circles
    nodeGroup
      .append("text")
      .text((d) => (rScale(d.count) > 10 ? (d.id.length > 12 ? d.id.slice(0, 10) + ".." : d.id) : ""))
      .attr("text-anchor", "middle")
      .attr("dy", "0.35em")
      .style("font-size", "9px")
      .style("fill", "#FFFFFF")
      .style("font-weight", "600")
      .style("text-shadow", "0 1px 2px rgba(0,0,0,0.4)")
      .style("pointer-events", "none");

    sim.on("tick", () => {
      linkEl
        .attr("x1", (d) => (d.source as NetworkNode).x!)
        .attr("y1", (d) => (d.source as NetworkNode).y!)
        .attr("x2", (d) => (d.target as NetworkNode).x!)
        .attr("y2", (d) => (d.target as NetworkNode).y!);
      nodeGroup.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

    // Fade-in
    svg.attr("opacity", 0).transition().duration(600).attr("opacity", 1);

    return () => {
      sim.stop();
    };
  }, [nodes, links, onNodeClick]);

  if (!nodes.length) {
    return (
      <div className="w-full h-full flex items-center justify-center text-sm text-[var(--oaria-text-secondary)]">
        네트워크 데이터가 부족합니다
      </div>
    );
  }

  return <div ref={ref} className="w-full h-full relative" />;
}
