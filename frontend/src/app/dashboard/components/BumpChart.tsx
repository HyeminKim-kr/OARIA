"use client";
import { useRef, useEffect } from "react";
import * as d3 from "d3";
import { getChartPalette, getThemeColors } from "../constants";

interface BumpItem {
  period: string;     // e.g. "2025.01"
  keyword: string;
  rank: number;       // 1 = top
  count: number;
}

interface Props {
  data: BumpItem[];
  keywords: string[];
  periods: string[];
}

export default function BumpChart({ data, keywords, periods }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !data.length || !keywords.length || !periods.length) return;
    const el = ref.current;
    d3.select(el).selectAll("*").remove();

    // Detect dark mode
    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches
      || document.documentElement.classList.contains("dark");
    const theme = getThemeColors(isDark);
    const palette = getChartPalette(isDark);

    const margin = { top: 24, right: 130, bottom: 32, left: 50 };
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

    const x = d3.scalePoint<string>()
      .domain(periods)
      .range(periods.length === 1 ? [width / 2, width / 2] : [0, width])
      .padding(0.5);
    const y = d3.scaleLinear().domain([1, keywords.length]).range([0, height]);
    const color = d3.scaleOrdinal<string>().domain(keywords).range(palette);

    // Build lookup: period+keyword → item
    const lookup = new Map<string, BumpItem>();
    data.forEach((d) => lookup.set(`${d.period}||${d.keyword}`, d));

    // X axis
    svg
      .append("g")
      .attr("transform", `translate(0,${height + 8})`)
      .call(d3.axisBottom(x).tickSize(0))
      .call((g) => g.select(".domain").remove())
      .call((g) =>
        g.selectAll("text")
          .style("fill", theme.axisText)
          .style("font-size", "10px")
      );

    // Y axis (rank labels)
    svg
      .append("g")
      .attr("transform", "translate(-12,0)")
      .call(
        d3.axisLeft(y)
          .ticks(keywords.length)
          .tickValues(d3.range(1, keywords.length + 1))
          .tickFormat((d) => `#${d}`)
          .tickSize(0)
      )
      .call((g) => g.select(".domain").remove())
      .call((g) =>
        g.selectAll("text")
          .style("fill", theme.axisText)
          .style("font-size", "10px")
          .style("font-weight", "600")
      );

    // Horizontal grid lines
    svg
      .append("g")
      .selectAll("line")
      .data(d3.range(1, keywords.length + 1))
      .join("line")
      .attr("x1", 0)
      .attr("x2", width)
      .attr("y1", (d) => y(d))
      .attr("y2", (d) => y(d))
      .attr("stroke", theme.gridLine)
      .attr("stroke-width", 1)
      .attr("stroke-opacity", 1);

    // Lines for each keyword
    const line = d3
      .line<{ period: string; rank: number }>()
      .x((d) => x(d.period)!)
      .y((d) => y(d.rank))
      .curve(d3.curveMonotoneX);

    keywords.forEach((kw) => {
      const points = periods
        .map((p) => {
          const item = lookup.get(`${p}||${kw}`);
          return item ? { period: p, rank: item.rank } : null;
        })
        .filter(Boolean) as { period: string; rank: number }[];

      if (points.length === 0) return;

      // Line (only if 2+ points)
      if (points.length >= 2) {
        const path = svg
          .append("path")
          .datum(points)
          .attr("fill", "none")
          .attr("stroke", color(kw))
          .attr("stroke-width", 3)
          .attr("stroke-linecap", "round")
          .attr("opacity", 0.75)
          .attr("d", line);

        // Animate line drawing
        const totalLength = (path.node() as SVGPathElement)?.getTotalLength?.() || 0;
        if (totalLength > 0) {
          path
            .attr("stroke-dasharray", `${totalLength} ${totalLength}`)
            .attr("stroke-dashoffset", totalLength)
            .transition()
            .duration(1500)
            .ease(d3.easeCubicOut)
            .attr("stroke-dashoffset", 0);
        }
      }

      // Dots
      svg
        .selectAll(`.dot-${kw.replace(/\W/g, "")}`)
        .data(points)
        .join("circle")
        .attr("cx", (d) => x(d.period)!)
        .attr("cy", (d) => y(d.rank))
        .attr("r", 0)
        .attr("fill", color(kw))
        .attr("stroke", theme.surface)
        .attr("stroke-width", 2)
        .style("cursor", "pointer")
        .on("mouseover", function (_event, d) {
          d3.select(this).transition().duration(150).attr("r", 7);
          const item = lookup.get(`${d.period}||${kw}`);
          tip
            .style("visibility", "visible")
            .html(
              `<strong style="color:${color(kw)}">${kw}</strong><br/>` +
              `${d.period} — #${d.rank}<br/>` +
              `<span style="opacity:0.7">${item?.count || 0}건</span>`
            );
        })
        .on("mousemove", function (event) {
          const [mx, my] = d3.pointer(event, el);
          tip.style("left", `${mx + 16}px`).style("top", `${my - 10}px`);
        })
        .on("mouseout", function () {
          d3.select(this).transition().duration(150).attr("r", 5);
          tip.style("visibility", "hidden");
        })
        .transition()
        .duration(800)
        .delay((_d, i) => i * 100 + 400)
        .attr("r", 5);
    });

    // Right-side legend (final rank labels)
    const lastPeriod = periods[periods.length - 1];
    keywords.forEach((kw) => {
      const item = lookup.get(`${lastPeriod}||${kw}`);
      if (!item) return;

      svg
        .append("text")
        .attr("x", width + 10)
        .attr("y", y(item.rank))
        .attr("dy", "0.35em")
        .text(kw.length > 16 ? kw.slice(0, 14) + ".." : kw)
        .style("font-size", "10px")
        .style("fill", color(kw))
        .style("font-weight", "600");
    });
  }, [data, keywords, periods]);

  if (!data.length) {
    return (
      <div className="w-full h-full flex items-center justify-center text-sm text-[var(--oaria-text-secondary)]">
        랭킹 데이터가 부족합니다. 논문을 더 수집해주세요.
      </div>
    );
  }

  return <div ref={ref} className="w-full h-full relative" />;
}
