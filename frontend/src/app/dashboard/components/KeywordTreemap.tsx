"use client";
import { useRef, useEffect } from "react";
import * as d3 from "d3";
import { PASTEL_SOFT } from "../constants";

interface TreemapItem {
  name: string;
  value: number;
}

interface Props {
  data: TreemapItem[];
  onKeywordClick?: (keyword: string) => void;
}

export default function KeywordTreemap({ data, onKeywordClick }: Props) {
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
      .padding(3)
      .round(true)(root as d3.HierarchyRectangularNode<{ name: string; children?: TreemapItem[] }>);

    const svg = d3
      .select(el)
      .append("svg")
      .attr("width", width)
      .attr("height", height);

    const color = d3.scaleOrdinal<string>().range(PASTEL_SOFT);

    const leaves = (root as d3.HierarchyRectangularNode<{ name: string; children?: TreemapItem[] }>).leaves();

    const cell = svg
      .selectAll("g")
      .data(leaves)
      .join("g")
      .attr("transform", (d) => `translate(${d.x0},${d.y0})`)
      .style("cursor", "pointer")
      .on("mouseover", function (_event, d) {
        d3.select(this).select("rect").attr("stroke", "var(--oaria-teal)").attr("stroke-width", 2);
        tip
          .style("visibility", "visible")
          .html(`<strong>${d.data.name}</strong><br/>${d.value}건`);
      })
      .on("mousemove", function (event) {
        const [mx, my] = d3.pointer(event, el);
        tip.style("left", `${mx + 16}px`).style("top", `${my - 10}px`);
      })
      .on("mouseout", function () {
        d3.select(this).select("rect").attr("stroke", "var(--background)").attr("stroke-width", 1);
        tip.style("visibility", "hidden");
      })
      .on("click", (_event, d) => onKeywordClick?.(d.data.name));

    cell
      .append("rect")
      .attr("width", (d) => d.x1 - d.x0)
      .attr("height", (d) => d.y1 - d.y0)
      .attr("rx", 6)
      .attr("fill", (_d, i) => color(String(i)))
      .attr("stroke", "var(--background)")
      .attr("stroke-width", 1)
      .attr("opacity", 0)
      .transition()
      .duration(600)
      .delay((_d, i) => i * 30)
      .attr("opacity", 1);

    cell
      .append("text")
      .attr("x", 6)
      .attr("y", 16)
      .text((d) => {
        const w = d.x1 - d.x0;
        const h = d.y1 - d.y0;
        if (w < 40 || h < 22) return "";
        const name = d.data.name;
        const maxChars = Math.floor(w / 7);
        return name.length > maxChars ? name.slice(0, maxChars - 1) + ".." : name;
      })
      .style("font-size", "11px")
      .style("fill", "var(--foreground)")
      .style("font-weight", "600")
      .style("pointer-events", "none");

    cell
      .append("text")
      .attr("x", 6)
      .attr("y", 30)
      .text((d) => {
        const w = d.x1 - d.x0;
        const h = d.y1 - d.y0;
        return w > 40 && h > 34 ? `${d.value}` : "";
      })
      .style("font-size", "10px")
      .style("fill", "var(--oaria-text-secondary)")
      .style("pointer-events", "none");
  }, [data, onKeywordClick]);

  if (!data.length) {
    return (
      <div className="w-full h-full flex items-center justify-center text-sm text-[var(--oaria-text-secondary)]">
        키워드 트리맵 데이터가 부족합니다
      </div>
    );
  }

  return <div ref={ref} className="w-full h-full relative" />;
}
