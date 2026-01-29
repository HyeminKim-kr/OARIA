"use client";
import { useRef, useEffect } from "react";
import * as d3 from "d3";
import { getChartPalette, getThemeColors } from "../constants";

export interface BubbleData {
  keyword: string;
  count: number;
  growth: number;
}

interface Props {
  data: BubbleData[];
  onKeywordClick?: (keyword: string) => void;
}

export default function BubbleChart({ data, onKeywordClick }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !data.length) return;
    const el = ref.current;
    d3.select(el).selectAll("*").remove();

    const width = el.clientWidth;
    const height = el.clientHeight;
    if (width <= 0 || height <= 0) return;

    // Detect dark mode
    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches
      || document.documentElement.classList.contains("dark");
    const theme = getThemeColors(isDark);
    const palette = getChartPalette(isDark);

    const svg = d3
      .select(el)
      .append("svg")
      .attr("width", width)
      .attr("height", height);

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

    const maxCount = d3.max(data, (d) => d.count) || 1;
    const rScale = d3
      .scaleSqrt()
      .domain([0, maxCount])
      .range([12, Math.min(width, height) / 5]);

    const color = d3.scaleOrdinal<string>().range(palette);

    const nodes = data.map((d) => ({
      ...d,
      r: rScale(d.count),
      x: width / 2 + (Math.random() - 0.5) * 100,
      y: height / 2 + (Math.random() - 0.5) * 100,
      fx: null as number | null,
      fy: null as number | null,
    }));

    const sim = d3
      .forceSimulation(nodes)
      .force("charge", d3.forceManyBody().strength(5))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force(
        "collision",
        d3.forceCollide<(typeof nodes)[0]>().radius((d) => d.r + 3)
      )
      .force("x", d3.forceX(width / 2).strength(0.05))
      .force("y", d3.forceY(height / 2).strength(0.05));

    const node = svg
      .selectAll("g")
      .data(nodes)
      .join("g")
      .style("cursor", "pointer")
      .on("mouseover", function (_event, d) {
        d3.select(this).select("circle").attr("stroke-width", 3);
        tip
          .style("visibility", "visible")
          .html(
            `<strong>${d.keyword}</strong><br/>논문 ${d.count}건${d.growth > 0 ? `<br/><span style="color:#22c55e">+${d.growth.toFixed(0)}% growth</span>` : ""}`
          );
      })
      .on("mousemove", function (event) {
        const [mx, my] = d3.pointer(event, el);
        tip
          .style("left", `${mx + 16}px`)
          .style("top", `${my - 10}px`);
      })
      .on("mouseout", function () {
        d3.select(this).select("circle").attr("stroke-width", 1.5);
        tip.style("visibility", "hidden");
      })
      .on("click", (_event, d) => onKeywordClick?.(d.keyword))
      .call(
        d3
          .drag<SVGGElement, (typeof nodes)[0]>()
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

    node
      .append("circle")
      .attr("r", 0)
      .attr("fill", (_d, i) => color(String(i)))
      .attr("opacity", 0.88)
      .attr("stroke", theme.surface)
      .attr("stroke-width", 2)
      .transition()
      .duration(800)
      .delay((_d, i) => i * 60)
      .attr("r", (d) => d.r);

    // Text inside bubbles - use high contrast color (white or dark based on bubble color)
    node
      .append("text")
      .text((d) => (d.r > 25 ? (d.keyword.length > 14 ? d.keyword.slice(0, 12) + ".." : d.keyword) : ""))
      .attr("text-anchor", "middle")
      .attr("dy", "-0.2em")
      .style("font-size", (d) => `${Math.max(9, d.r / 3.5)}px`)
      .style("fill", "#FFFFFF") // Always white for visibility on colored bubbles
      .style("font-weight", "700")
      .style("text-shadow", "0 1px 2px rgba(0,0,0,0.3)")
      .style("pointer-events", "none");

    node
      .append("text")
      .text((d) => (d.r > 25 ? `${d.count}` : ""))
      .attr("text-anchor", "middle")
      .attr("dy", "1em")
      .style("font-size", (d) => `${Math.max(8, d.r / 4)}px`)
      .style("fill", "rgba(255,255,255,0.85)") // Slightly transparent white
      .style("text-shadow", "0 1px 2px rgba(0,0,0,0.2)")
      .style("pointer-events", "none");

    sim.on("tick", () => {
      node.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

    return () => {
      sim.stop();
    };
  }, [data, onKeywordClick]);

  if (!data.length) {
    return (
      <div className="w-full h-full flex items-center justify-center text-sm text-[var(--oaria-text-secondary)]">
        키워드 데이터가 부족합니다
      </div>
    );
  }

  return <div ref={ref} className="w-full h-full relative" />;
}
