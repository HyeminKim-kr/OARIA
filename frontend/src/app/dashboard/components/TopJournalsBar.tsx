"use client";
import { useRef, useEffect } from "react";
import * as d3 from "d3";
import { getChartPalette, getThemeColors } from "../constants";

interface BarItem {
  label: string;
  value: number;
}

interface Props {
  data: BarItem[];
  accentIndex?: number;
}

export default function TopJournalsBar({ data, accentIndex }: Props) {
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

    const margin = { top: 5, right: 40, bottom: 5, left: 130 };
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

    const y = d3
      .scaleBand()
      .domain(data.map((d) => d.label))
      .range([0, height])
      .padding(0.25);

    const x = d3
      .scaleLinear()
      .domain([0, d3.max(data, (d) => d.value) || 1])
      .range([0, width]);

    const color = d3.scaleOrdinal<string>().range(palette);

    svg
      .selectAll("rect")
      .data(data)
      .join("rect")
      .attr("y", (d) => y(d.label) || 0)
      .attr("height", y.bandwidth())
      .attr("x", 0)
      .attr("rx", 6)
      .attr("fill", (_d, i) => (i === accentIndex ? theme.primary : color(String(i))))
      .attr("opacity", 0.9)
      .style("cursor", "pointer")
      .attr("width", 0)
      .transition()
      .duration(800)
      .delay((_d, i) => i * 60)
      .attr("width", (d) => x(d.value))
      .attr("opacity", 0.9);

    // Re-attach events
    svg
      .selectAll("rect")
      .on("mouseover", function () {
        d3.select(this).attr("opacity", 1);
        tip.style("visibility", "visible");
      })
      .on("mousemove", function (event) {
        const d = d3.select(this).datum() as BarItem;
        const [mx, my] = d3.pointer(event, el);
        tip
          .html(`<strong>${d.label}</strong><br/>${d.value}건`)
          .style("left", `${mx + 16}px`)
          .style("top", `${my - 10}px`);
      })
      .on("mouseout", function () {
        d3.select(this).attr("opacity", 0.8);
        tip.style("visibility", "hidden");
      });

    // Labels
    svg
      .selectAll(".label")
      .data(data)
      .join("text")
      .attr("class", "label")
      .attr("x", -6)
      .attr("y", (d) => (y(d.label) || 0) + y.bandwidth() / 2)
      .attr("dy", "0.35em")
      .attr("text-anchor", "end")
      .text((d) => (d.label.length > 18 ? d.label.slice(0, 16) + ".." : d.label))
      .style("font-size", "11px")
      .style("fill", theme.textSecondary)
      .style("font-weight", "500");

    // Value labels
    svg
      .selectAll(".val")
      .data(data)
      .join("text")
      .attr("class", "val")
      .attr("x", (d) => x(d.value) + 6)
      .attr("y", (d) => (y(d.label) || 0) + y.bandwidth() / 2)
      .attr("dy", "0.35em")
      .text((d) => d.value)
      .style("font-size", "11px")
      .style("fill", theme.textPrimary)
      .style("font-weight", "700")
      .attr("opacity", 0)
      .transition()
      .duration(800)
      .delay((_d, i) => i * 60 + 400)
      .attr("opacity", 1);
  }, [data, accentIndex]);

  if (!data.length) {
    return (
      <div className="w-full h-full flex items-center justify-center text-sm text-[var(--oaria-text-secondary)]">
        저널 데이터가 부족합니다
      </div>
    );
  }

  return <div ref={ref} className="w-full h-full relative" />;
}
