"use client";
import { useRef, useEffect } from "react";
import * as d3 from "d3";
import { BRAND, getThemeColors } from "../constants";

interface JournalData {
  label: string;
  value: number;
}

interface Props {
  data: JournalData[];
}

export default function JournalLollipop({ data }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !data.length) return;
    const el = ref.current;
    d3.select(el).selectAll("*").remove();

    const width = el.clientWidth;
    const height = el.clientHeight;
    const margin = { top: 8, right: 50, bottom: 8, left: 10 };

    if (width <= 0 || height <= 0) return;

    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches
      || document.documentElement.classList.contains("dark");
    const theme = getThemeColors(isDark);

    const svg = d3
      .select(el)
      .append("svg")
      .attr("width", width)
      .attr("height", height);

    const defs = svg.append("defs");

    // Brand gradient for bars
    const gradient = defs.append("linearGradient")
      .attr("id", "journal-bar-grad")
      .attr("x1", "0%").attr("y1", "0%")
      .attr("x2", "100%").attr("y2", "0%");
    gradient.append("stop").attr("offset", "0%")
      .attr("stop-color", isDark ? BRAND.lightTeal : BRAND.teal);
    gradient.append("stop").attr("offset", "100%")
      .attr("stop-color", isDark ? "#5EEAD4" : BRAND.lightTeal);

    const maxCount = d3.max(data, d => d.value) || 1;
    const barMaxWidth = width - margin.left - margin.right - 10;

    const xScale = d3.scaleLinear()
      .domain([0, maxCount])
      .range([0, barMaxWidth]);

    const yScale = d3.scaleBand()
      .domain(data.map(d => d.label))
      .range([margin.top, height - margin.bottom])
      .padding(0.35);

    const g = svg.append("g")
      .attr("transform", `translate(${margin.left}, 0)`);

    // Tooltip
    const tip = d3.select(el)
      .append("div")
      .style("position", "absolute")
      .style("visibility", "hidden")
      .style("background", theme.tooltipBg)
      .style("border", `1px solid ${theme.border}`)
      .style("border-radius", "8px")
      .style("padding", "10px 14px")
      .style("font-size", "12px")
      .style("box-shadow", `0 4px 16px ${theme.tooltipShadow}`)
      .style("pointer-events", "none")
      .style("z-index", "50")
      .style("color", theme.textPrimary)
      .style("backdrop-filter", "blur(8px)");

    // Create rows
    const rows = g.selectAll(".journal-row")
      .data(data)
      .join("g")
      .attr("class", "journal-row")
      .attr("transform", d => `translate(0, ${yScale(d.label)})`)
      .style("cursor", "pointer");

    const barHeight = Math.min(yScale.bandwidth(), 20);
    const barY = (yScale.bandwidth() - barHeight) / 2;

    // Background track - subtle
    rows.append("rect")
      .attr("x", 0)
      .attr("y", barY)
      .attr("width", barMaxWidth)
      .attr("height", barHeight)
      .attr("rx", barHeight / 2)
      .attr("fill", isDark ? "rgba(45, 212, 191, 0.08)" : "rgba(13, 148, 136, 0.06)");

    // Animated gradient bar
    rows.append("rect")
      .attr("class", "journal-bar")
      .attr("x", 0)
      .attr("y", barY)
      .attr("width", 0)
      .attr("height", barHeight)
      .attr("rx", barHeight / 2)
      .attr("fill", "url(#journal-bar-grad)")
      .transition()
      .duration(800)
      .delay((_, i) => i * 50)
      .ease(d3.easeCubicOut)
      .attr("width", d => xScale(d.value));

    // Journal name inside bar (left side)
    rows.append("text")
      .attr("x", 8)
      .attr("y", yScale.bandwidth() / 2)
      .attr("dy", "0.35em")
      .text(d => {
        const maxLen = Math.floor(barMaxWidth / 8);
        return d.label.length > maxLen ? d.label.slice(0, maxLen - 2) + "..." : d.label;
      })
      .style("font-size", "10px")
      .style("font-weight", "600")
      .style("fill", "#FFFFFF")
      .style("text-shadow", "0 1px 2px rgba(0,0,0,0.3)")
      .attr("opacity", 0)
      .transition()
      .duration(400)
      .delay((_, i) => i * 50 + 400)
      .attr("opacity", 1);

    // Count badge (right side of bar)
    rows.append("text")
      .attr("x", d => xScale(d.value) + 6)
      .attr("y", yScale.bandwidth() / 2)
      .attr("dy", "0.35em")
      .text(d => d.value.toLocaleString())
      .style("font-size", "10px")
      .style("font-weight", "700")
      .style("fill", isDark ? BRAND.lightTeal : BRAND.teal)
      .attr("opacity", 0)
      .transition()
      .duration(400)
      .delay((_, i) => i * 50 + 600)
      .attr("opacity", 1);

    // Hover interactions
    rows
      .on("mouseover", function (event, d) {
        const i = data.indexOf(d);
        d3.select(this).select(".journal-bar")
          .transition().duration(150)
          .attr("height", barHeight + 4)
          .attr("y", barY - 2);

        tip.style("visibility", "visible")
          .html(
            `<div style="font-weight:700;margin-bottom:6px;color:${theme.textPrimary}">${d.label}</div>
            <div style="display:flex;gap:16px;font-size:11px">
              <div>
                <span style="color:${theme.textSecondary}">Rank</span>
                <span style="margin-left:4px;font-weight:700;color:${theme.textPrimary}">#${i + 1}</span>
              </div>
              <div>
                <span style="color:${theme.textSecondary}">Papers</span>
                <span style="margin-left:4px;font-weight:700;color:${isDark ? BRAND.lightTeal : BRAND.teal}">${d.value.toLocaleString()}</span>
              </div>
            </div>`
          );
      })
      .on("mousemove", function (event) {
        const [mx, my] = d3.pointer(event, el);
        tip.style("left", `${mx + 15}px`).style("top", `${my - 10}px`);
      })
      .on("mouseout", function () {
        d3.select(this).select(".journal-bar")
          .transition().duration(150)
          .attr("height", barHeight)
          .attr("y", barY);
        tip.style("visibility", "hidden");
      });

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
