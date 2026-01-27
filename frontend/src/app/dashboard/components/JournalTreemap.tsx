"use client";
import { useRef, useEffect } from "react";
import * as d3 from "d3";

interface TreemapItem {
  name: string;
  value: number;
  pct: number; // percentage of total
}

interface Props {
  data: TreemapItem[];
}

// BTC market-cap style: gradient fills, bold proportional blocks, glow on hover
const GRADIENT_PAIRS: [string, string][] = [
  ["#7EC8E3", "#4A98B5"], // blue
  ["#B8A9D9", "#8B7AB5"], // purple
  ["#82D9A8", "#52B07A"], // green
  ["#F2A6B3", "#D07888"], // pink
  ["#F5C6A0", "#D0996E"], // orange
  ["#A3D9C7", "#6FB09A"], // teal
  ["#C9ABEB", "#9B7DC0"], // lavender
  ["#F7DFA0", "#D4B56C"], // gold
  ["#9DC6E0", "#6B98B5"], // steel
  ["#E4ACC4", "#BA7E98"], // rose
  ["#B5D99C", "#88B06C"], // lime
  ["#DBA8C7", "#B07A9C"], // mauve
];

export default function JournalTreemap({ data }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !data.length) return;
    const el = ref.current;
    d3.select(el).selectAll("*").remove();

    const width = el.clientWidth;
    const height = el.clientHeight;
    if (width <= 0 || height <= 0) return;

    const tip = d3
      .select(el)
      .append("div")
      .style("position", "absolute")
      .style("visibility", "hidden")
      .style("background", "var(--background)")
      .style("border", "1px solid var(--oaria-border)")
      .style("border-radius", "10px")
      .style("padding", "8px 14px")
      .style("font-size", "13px")
      .style("box-shadow", "0 4px 20px rgba(0,0,0,0.08)")
      .style("pointer-events", "none")
      .style("z-index", "50")
      .style("color", "var(--foreground)");

    const root = d3
      .hierarchy({ name: "root", children: data })
      .sum((d) => (d as unknown as TreemapItem).value)
      .sort((a, b) => (b.value || 0) - (a.value || 0));

    d3.treemap<{ name: string; children?: TreemapItem[] }>()
      .size([width, height])
      .padding(2)
      .paddingInner(3)
      .round(true)(root as d3.HierarchyRectangularNode<{ name: string; children?: TreemapItem[] }>);

    const svg = d3
      .select(el)
      .append("svg")
      .attr("width", width)
      .attr("height", height);

    const defs = svg.append("defs");

    const leaves = (root as d3.HierarchyRectangularNode<{ name: string; children?: TreemapItem[] }>).leaves();

    // Create gradients per cell
    leaves.forEach((d, i) => {
      const [c1, c2] = GRADIENT_PAIRS[i % GRADIENT_PAIRS.length];
      const grad = defs
        .append("linearGradient")
        .attr("id", `jt-grad-${i}`)
        .attr("x1", "0%").attr("y1", "0%")
        .attr("x2", "100%").attr("y2", "100%");
      grad.append("stop").attr("offset", "0%").attr("stop-color", c1);
      grad.append("stop").attr("offset", "100%").attr("stop-color", c2);

      // Glow filter
      const filter = defs.append("filter").attr("id", `jt-glow-${i}`);
      filter.append("feGaussianBlur").attr("stdDeviation", "3").attr("result", "blur");
      filter.append("feFlood").attr("flood-color", c1).attr("flood-opacity", "0.4").attr("result", "color");
      filter.append("feComposite").attr("in", "color").attr("in2", "blur").attr("operator", "in").attr("result", "glow");
      const feMerge = filter.append("feMerge");
      feMerge.append("feMergeNode").attr("in", "glow");
      feMerge.append("feMergeNode").attr("in", "SourceGraphic");
    });

    const cell = svg
      .selectAll("g")
      .data(leaves)
      .join("g")
      .attr("transform", (d) => `translate(${d.x0},${d.y0})`)
      .style("cursor", "pointer")
      .on("mouseover", function (_event, d) {
        const i = leaves.indexOf(d);
        d3.select(this).select("rect")
          .attr("filter", `url(#jt-glow-${i})`)
          .transition().duration(200)
          .attr("opacity", 1);
        const item = d.data as unknown as TreemapItem;
        tip
          .style("visibility", "visible")
          .html(`<strong>${item.name}</strong><br/>${(d.value || 0).toLocaleString()}편 · ${item.pct?.toFixed(1) || 0}%`);
      })
      .on("mousemove", function (event) {
        const [mx, my] = d3.pointer(event, el);
        tip.style("left", `${mx + 16}px`).style("top", `${my - 10}px`);
      })
      .on("mouseout", function () {
        d3.select(this).select("rect")
          .attr("filter", null)
          .transition().duration(200)
          .attr("opacity", 0.88);
        tip.style("visibility", "hidden");
      });

    // Rect with gradient
    cell
      .append("rect")
      .attr("width", (d) => Math.max(0, d.x1 - d.x0))
      .attr("height", (d) => Math.max(0, d.y1 - d.y0))
      .attr("rx", 8)
      .attr("fill", (_d, i) => `url(#jt-grad-${i})`)
      .attr("opacity", 0)
      .transition()
      .duration(700)
      .delay((_d, i) => i * 40)
      .attr("opacity", 0.88);

    // Journal name (bold, large for big cells)
    cell
      .append("text")
      .attr("x", 8)
      .attr("y", 20)
      .text((d) => {
        const w = d.x1 - d.x0;
        const h = d.y1 - d.y0;
        if (w < 50 || h < 28) return "";
        const name = (d.data as unknown as TreemapItem).name;
        const maxChars = Math.floor(w / 7);
        return name.length > maxChars ? name.slice(0, maxChars - 1) + ".." : name;
      })
      .style("font-size", (d) => {
        const w = d.x1 - d.x0;
        return w > 200 ? "13px" : w > 120 ? "11px" : "10px";
      })
      .style("fill", "white")
      .style("font-weight", "700")
      .style("pointer-events", "none")
      .style("text-shadow", "0 1px 3px rgba(0,0,0,0.3)");

    // Percentage (BTC market cap style)
    cell
      .append("text")
      .attr("x", 8)
      .attr("y", (d) => {
        const h = d.y1 - d.y0;
        return h > 55 ? 38 : 33;
      })
      .text((d) => {
        const w = d.x1 - d.x0;
        const h = d.y1 - d.y0;
        if (w < 50 || h < 40) return "";
        const item = d.data as unknown as TreemapItem;
        return `${item.pct?.toFixed(1) || 0}%`;
      })
      .style("font-size", (d) => {
        const w = d.x1 - d.x0;
        return w > 200 ? "18px" : w > 120 ? "14px" : "11px";
      })
      .style("fill", "rgba(255,255,255,0.85)")
      .style("font-weight", "800")
      .style("pointer-events", "none")
      .style("text-shadow", "0 1px 3px rgba(0,0,0,0.3)");

    // Count (small, bottom-left for large cells)
    cell
      .append("text")
      .attr("x", 8)
      .attr("y", (d) => Math.max(0, d.y1 - d.y0) - 8)
      .text((d) => {
        const w = d.x1 - d.x0;
        const h = d.y1 - d.y0;
        if (w < 70 || h < 60) return "";
        return `${(d.value || 0).toLocaleString()} papers`;
      })
      .style("font-size", "9px")
      .style("fill", "rgba(255,255,255,0.6)")
      .style("font-weight", "500")
      .style("pointer-events", "none");
  }, [data]);

  if (!data.length) {
    return (
      <div className="w-full h-full flex items-center justify-center text-sm text-[var(--oaria-text-secondary)]">
        저널 데이터가 부족합니다
      </div>
    );
  }

  return <div ref={ref} className="w-full h-full relative" />;
}
