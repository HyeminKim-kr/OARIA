"use client";
import { useRef, useEffect } from "react";
import * as d3 from "d3";
import { BRAND, getThemeColors } from "../constants";

interface HeatCell {
  journal: string;
  year: number;
  count: number;
}

interface Props {
  data: HeatCell[];
}

export default function HeatmapChart({ data }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !data.length) return;
    const el = ref.current;
    d3.select(el).selectAll("*").remove();

    // Detect dark mode
    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches
      || document.documentElement.classList.contains("dark");
    const theme = getThemeColors(isDark);

    const margin = { top: 10, right: 10, bottom: 30, left: 120 };
    const width = el.clientWidth - margin.left - margin.right;
    const height = el.clientHeight - margin.top - margin.bottom;
    if (width <= 0 || height <= 0) return;

    const svg = d3
      .select(el)
      .append("svg")
      .attr("width", el.clientWidth)
      .attr("height", el.clientHeight)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

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

    const years = [...new Set(data.map((d) => d.year))].sort();
    const journals = [...new Set(data.map((d) => d.journal))];

    const x = d3.scaleBand().domain(years.map(String)).range([0, width]).padding(0.08);
    const y = d3.scaleBand().domain(journals).range([0, height]).padding(0.08);

    const maxCount = d3.max(data, (d) => d.count) || 1;
    // Brand-aligned heatmap colors: light teal to primary teal
    const colorScale = d3
      .scaleSequential()
      .domain([0, maxCount])
      .interpolator(isDark
        ? d3.interpolateRgb("#1E293B", BRAND.lightTeal) // Dark: navy to teal
        : d3.interpolateRgb("#F0FDFA", BRAND.teal)      // Light: very light teal to teal
      );

    svg
      .selectAll("rect")
      .data(data)
      .join("rect")
      .attr("x", (d) => x(String(d.year)) || 0)
      .attr("y", (d) => y(d.journal) || 0)
      .attr("width", x.bandwidth())
      .attr("height", y.bandwidth())
      .attr("rx", 4)
      .attr("fill", (d) => colorScale(d.count))
      .attr("stroke", theme.surface)
      .attr("stroke-width", 1)
      .style("cursor", "pointer")
      .attr("opacity", 0)
      .transition()
      .duration(600)
      .delay((_d, i) => i * 15)
      .attr("opacity", 1);

    // Re-select for events (transitions don't support events)
    svg
      .selectAll("rect")
      .on("mouseover", function (_event, _d) {
        d3.select(this).attr("stroke", theme.primary).attr("stroke-width", 2);
        tip.style("visibility", "visible");
      })
      .on("mousemove", function (event) {
        const d = d3.select(this).datum() as HeatCell;
        const [mx, my] = d3.pointer(event, el);
        tip
          .html(`<strong>${d.journal}</strong><br/>${d.year}년: <strong style="color:${theme.primary}">${d.count}</strong>건`)
          .style("left", `${mx + 16}px`)
          .style("top", `${my - 10}px`);
      })
      .on("mouseout", function () {
        d3.select(this).attr("stroke", theme.surface).attr("stroke-width", 1);
        tip.style("visibility", "hidden");
      });

    // X axis
    svg
      .append("g")
      .attr("transform", `translate(0,${height})`)
      .call(d3.axisBottom(x).tickSize(0))
      .call((g) => g.select(".domain").remove())
      .call((g) =>
        g
          .selectAll("text")
          .style("fill", theme.axisText)
          .style("font-size", "10px")
      );

    // Y axis
    svg
      .append("g")
      .call(d3.axisLeft(y).tickSize(0))
      .call((g) => g.select(".domain").remove())
      .call((g) =>
        g
          .selectAll("text")
          .style("fill", theme.axisText)
          .style("font-size", "10px")
          .text((d) => {
            const s = d as string;
            return s.length > 18 ? s.slice(0, 16) + ".." : s;
          })
      );
  }, [data]);

  if (!data.length) {
    return (
      <div className="w-full h-full flex items-center justify-center text-sm text-[var(--oaria-text-secondary)]">
        저널 히트맵 데이터가 부족합니다
      </div>
    );
  }

  return <div ref={ref} className="w-full h-full relative" />;
}
