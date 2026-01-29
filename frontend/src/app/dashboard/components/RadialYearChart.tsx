"use client";
import { useRef, useEffect } from "react";
import * as d3 from "d3";
import { getChartPalette, getThemeColors } from "../constants";

interface RadialItem {
  year: number;
  count: number;
  label?: string; // optional override label (e.g. "Q1 2025")
}

interface Props {
  data: RadialItem[];
}

export default function RadialYearChart({ data }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !data.length) return;
    const el = ref.current;
    d3.select(el).selectAll("*").remove();

    // Detect dark mode
    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches
      || document.documentElement.classList.contains("dark");
    const theme = getThemeColors(isDark);
    const palette = getChartPalette(isDark);

    const width = el.clientWidth;
    const height = el.clientHeight;
    const radius = Math.min(width, height) / 2 - 30;
    if (radius <= 0) return;

    const svg = d3
      .select(el)
      .append("svg")
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${width / 2},${height / 2})`)
      .attr("stroke", "none")
      .attr("stroke-width", 0);

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

    const sorted = [...data].sort((a, b) => a.year - b.year);
    const maxCount = d3.max(sorted, (d) => d.count) || 1;

    const angleScale = d3
      .scaleBand()
      .domain(sorted.map((d) => d.label || String(d.year)))
      .range([0, 2 * Math.PI])
      .padding(0.12);

    const rScale = d3.scaleLinear().domain([0, maxCount]).range([radius * 0.25, radius]);

    const color = d3.scaleOrdinal<string>().range(palette);

    svg
      .selectAll("path")
      .data(sorted)
      .join("path")
      .attr("fill", (_d, i) => color(String(i)))
      .attr("opacity", 0.88)
      .attr("stroke", "none")
      .attr("stroke-width", 0)
      .style("cursor", "pointer")
      .on("mouseover", function () {
        d3.select(this).attr("opacity", 1);
        tip.style("visibility", "visible");
      })
      .on("mousemove", function (event) {
        const d = d3.select(this).datum() as RadialItem;
        const [mx, my] = d3.pointer(event, el);
        const lbl = d.label || `${d.year}년`;
        tip
          .html(`<strong>${lbl}</strong><br/>${d.count.toLocaleString()}건`)
          .style("left", `${mx + 16}px`)
          .style("top", `${my - 10}px`);
      })
      .on("mouseout", function () {
        d3.select(this).attr("opacity", 0.82);
        tip.style("visibility", "hidden");
      })
      // Entrance animation
      .attr("d", (d) => {
        const key = d.label || String(d.year);
        return d3
          .arc<RadialItem>()
          .innerRadius(radius * 0.25)
          .outerRadius(radius * 0.25)
          .startAngle(angleScale(key) || 0)
          .endAngle((angleScale(key) || 0) + angleScale.bandwidth())
          .padAngle(0.02)
          .cornerRadius(4)(d);
      })
      .transition()
      .duration(1000)
      .delay((_d, i) => i * 80)
      .attrTween("d", function (d) {
        const key = d.label || String(d.year);
        const interp = d3.interpolate(radius * 0.25, rScale(d.count));
        return (t) =>
          d3
            .arc<RadialItem>()
            .innerRadius(radius * 0.25)
            .outerRadius(interp(t))
            .startAngle(angleScale(key) || 0)
            .endAngle((angleScale(key) || 0) + angleScale.bandwidth())
            .padAngle(0.02)
            .cornerRadius(4)(d) || "";
      });

    // Labels
    svg
      .selectAll(".year-label")
      .data(sorted)
      .join("text")
      .attr("class", "year-label")
      .attr("transform", (d) => {
        const key = d.label || String(d.year);
        const angle = (angleScale(key) || 0) + angleScale.bandwidth() / 2;
        const r = radius + 14;
        const x = r * Math.sin(angle);
        const y = -r * Math.cos(angle);
        return `translate(${x},${y})`;
      })
      .attr("text-anchor", "middle")
      .attr("dy", "0.35em")
      .text((d) => {
        if (d.label) return d.label;
        return String(d.year).length > 4 ? String(d.year).slice(2) : String(d.year).slice(2);
      })
      .style("font-size", "10px")
      .style("fill", theme.textSecondary)
      .style("font-weight", "600");

    // Center label
    svg
      .append("text")
      .text("Distribution")
      .attr("text-anchor", "middle")
      .attr("dy", "0.35em")
      .style("font-size", "11px")
      .style("fill", theme.textSecondary)
      .style("font-weight", "500");
  }, [data]);

  if (!data.length) {
    return (
      <div className="w-full h-full flex items-center justify-center text-sm text-[var(--oaria-text-secondary)]">
        연도별 데이터가 부족합니다
      </div>
    );
  }

  return <div ref={ref} className="w-full h-full relative" />;
}
