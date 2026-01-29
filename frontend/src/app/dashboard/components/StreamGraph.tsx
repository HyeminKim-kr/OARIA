"use client";
import { useRef, useEffect } from "react";
import * as d3 from "d3";
import { getChartPalette, getThemeColors } from "../constants";

interface Props {
  data: Record<string, number>[];
  keys: string[];
  monthly?: boolean;
}

export default function StreamGraph({ data, keys, monthly }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !data.length || !keys.length) return;
    const el = ref.current;
    d3.select(el).selectAll("*").remove();

    // Detect dark mode
    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches
      || document.documentElement.classList.contains("dark");
    const theme = getThemeColors(isDark);
    const palette = getChartPalette(isDark);

    const margin = { top: 20, right: 20, bottom: 30, left: 50 };
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

    const x = d3
      .scaleLinear()
      .domain(d3.extent(data, (d) => d.year) as [number, number])
      .range([0, width]);

    const stack = d3
      .stack<Record<string, number>>()
      .keys(keys)
      .offset(d3.stackOffsetSilhouette)
      .order(d3.stackOrderInsideOut);

    const series = stack(data);

    const y = d3
      .scaleLinear()
      .domain([
        d3.min(series, (s) => d3.min(s, (d) => d[0])) || 0,
        d3.max(series, (s) => d3.max(s, (d) => d[1])) || 0,
      ])
      .range([height, 0]);

    const color = d3.scaleOrdinal<string>().domain(keys).range(palette);

    const area = d3
      .area<d3.SeriesPoint<Record<string, number>>>()
      .x((d) => x(d.data.year))
      .y0((d) => y(d[0]))
      .y1((d) => y(d[1]))
      .curve(d3.curveBasis);

    // Clip path for reveal animation
    const clipId = "stream-clip-" + Math.random().toString(36).slice(2);
    svg
      .append("defs")
      .append("clipPath")
      .attr("id", clipId)
      .append("rect")
      .attr("width", 0)
      .attr("height", height + 40)
      .attr("y", -20)
      .transition()
      .duration(1800)
      .ease(d3.easeCubicOut)
      .attr("width", width);

    const streams = svg
      .append("g")
      .attr("clip-path", `url(#${clipId})`)
      .selectAll("path")
      .data(series)
      .join("path")
      .attr("d", area)
      .attr("fill", (_d, i) => color(keys[i]))
      .attr("opacity", 0.88)
      .attr("stroke", theme.surface)
      .attr("stroke-width", 0.5)
      .style("cursor", "pointer")
      .on("mouseover", function (_event, d) {
        streams.attr("opacity", 0.3);
        d3.select(this).attr("opacity", 1).attr("stroke-width", 1.5);
        tip.style("visibility", "visible");
      })
      .on("mousemove", function (event, d) {
        const [mx, my] = d3.pointer(event, el);
        const bisect = d3.bisector((dd: Record<string, number>) => dd.year).left;
        const xVal = x.invert(d3.pointer(event, svg.node())[0]);
        const idx = Math.min(bisect(data, xVal), data.length - 1);
        const val = data[idx]?.[d.key] || 0;
        const yearVal = data[idx]?.year || 0;
        const timeLabel = monthly
          ? `${Math.floor(yearVal / 100)}.${String(yearVal % 100).padStart(2, "0")}`
          : `${yearVal}년`;
        tip
          .html(
            `<strong style="color:${color(d.key)}">${d.key}</strong><br/>${timeLabel}: <strong>${val}</strong>건`
          )
          .style("left", `${mx + 16}px`)
          .style("top", `${my - 10}px`);
      })
      .on("mouseout", function () {
        streams.attr("opacity", 0.82).attr("stroke-width", 0.5);
        tip.style("visibility", "hidden");
      });

    // X axis
    svg
      .append("g")
      .attr("transform", `translate(0,${height})`)
      .call(
        d3
          .axisBottom(x)
          .ticks(Math.min(data.length, 10))
          .tickFormat((d) => {
            const v = Number(d);
            if (monthly) {
              const yr = Math.floor(v / 100);
              const mo = v % 100;
              return `${yr}.${String(mo).padStart(2, "0")}`;
            }
            return String(v);
          })
      )
      .call((g) => g.select(".domain").attr("stroke", theme.border))
      .call((g) =>
        g.selectAll(".tick line").attr("stroke", theme.border)
      )
      .call((g) =>
        g
          .selectAll(".tick text")
          .style("fill", theme.axisText)
          .style("font-size", "11px")
      );

    // Legend
    const legend = svg
      .append("g")
      .attr("transform", `translate(${width - keys.length * 90}, -10)`);

    keys.forEach((key, i) => {
      const g = legend
        .append("g")
        .attr("transform", `translate(${i * 90}, 0)`);
      g.append("circle")
        .attr("r", 5)
        .attr("fill", color(key))
        .attr("cy", 0);
      g.append("text")
        .text(key.length > 10 ? key.slice(0, 10) + "..." : key)
        .attr("x", 10)
        .attr("y", 4)
        .style("font-size", "10px")
        .style("fill", theme.textSecondary);
    });
  }, [data, keys]);

  if (!data.length || !keys.length) {
    return (
      <div className="w-full h-full flex items-center justify-center text-sm text-[var(--oaria-text-secondary)]">
        키워드 트렌드 데이터가 부족합니다
      </div>
    );
  }

  return <div ref={ref} className="w-full h-full relative" />;
}
