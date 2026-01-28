"use client";
import { useRef, useEffect } from "react";
import * as d3 from "d3";

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
    const margin = { top: 20, right: 30, bottom: 20, left: 10 };

    if (width <= 0 || height <= 0) return;

    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches
      || document.documentElement.classList.contains("dark");

    const svg = d3
      .select(el)
      .append("svg")
      .attr("width", width)
      .attr("height", height);

    const defs = svg.append("defs");

    // Gradient for bars
    const gradient = defs.append("linearGradient")
      .attr("id", "lollipop-grad")
      .attr("x1", "0%").attr("y1", "0%")
      .attr("x2", "100%").attr("y2", "0%");
    gradient.append("stop").attr("offset", "0%")
      .attr("stop-color", isDark ? "#3B82F6" : "#60A5FA");
    gradient.append("stop").attr("offset", "100%")
      .attr("stop-color", isDark ? "#8B5CF6" : "#A78BFA");

    // Glow filter
    const glowFilter = defs.append("filter")
      .attr("id", "lollipop-glow")
      .attr("x", "-50%").attr("y", "-50%")
      .attr("width", "200%").attr("height", "200%");
    glowFilter.append("feDropShadow")
      .attr("dx", "0").attr("dy", "0")
      .attr("stdDeviation", "3")
      .attr("flood-color", isDark ? "#3B82F6" : "#60A5FA")
      .attr("flood-opacity", "0.4");

    const maxCount = d3.max(data, d => d.value) || 1;
    const barMaxWidth = width - margin.left - margin.right - 100;

    const xScale = d3.scaleLinear()
      .domain([0, maxCount])
      .range([0, barMaxWidth]);

    const yScale = d3.scaleBand()
      .domain(data.map(d => d.label))
      .range([margin.top, height - margin.bottom])
      .padding(0.4);

    const g = svg.append("g")
      .attr("transform", `translate(${margin.left}, 0)`);

    // Tooltip
    const tip = d3.select(el)
      .append("div")
      .style("position", "absolute")
      .style("visibility", "hidden")
      .style("background", isDark ? "rgba(15,15,25,0.95)" : "rgba(255,255,255,0.98)")
      .style("border", `1px solid ${isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)"}`)
      .style("border-radius", "10px")
      .style("padding", "10px 14px")
      .style("font-size", "12px")
      .style("box-shadow", "0 4px 20px rgba(0,0,0,0.15)")
      .style("pointer-events", "none")
      .style("z-index", "50")
      .style("backdrop-filter", "blur(8px)");

    // Create rows
    const rows = g.selectAll(".journal-row")
      .data(data)
      .join("g")
      .attr("class", "journal-row")
      .attr("transform", d => `translate(0, ${yScale(d.label)})`)
      .style("cursor", "pointer");

    // Background track
    rows.append("rect")
      .attr("x", 0)
      .attr("y", (yScale.bandwidth() - 4) / 2)
      .attr("width", barMaxWidth)
      .attr("height", 4)
      .attr("rx", 2)
      .attr("fill", isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)");

    // Animated bar (stem)
    rows.append("rect")
      .attr("class", "lollipop-stem")
      .attr("x", 0)
      .attr("y", (yScale.bandwidth() - 4) / 2)
      .attr("width", 0)
      .attr("height", 4)
      .attr("rx", 2)
      .attr("fill", "url(#lollipop-grad)")
      .transition()
      .duration(800)
      .delay((_, i) => i * 60)
      .ease(d3.easeElasticOut.amplitude(1).period(0.5))
      .attr("width", d => xScale(d.value));

    // Lollipop head (circle)
    rows.append("circle")
      .attr("class", "lollipop-head")
      .attr("cx", 0)
      .attr("cy", yScale.bandwidth() / 2)
      .attr("r", 0)
      .attr("fill", isDark ? "#8B5CF6" : "#A78BFA")
      .attr("stroke", isDark ? "#1a1a2e" : "white")
      .attr("stroke-width", 2)
      .attr("filter", "url(#lollipop-glow)")
      .transition()
      .duration(800)
      .delay((_, i) => i * 60)
      .ease(d3.easeElasticOut.amplitude(1).period(0.4))
      .attr("cx", d => xScale(d.value))
      .attr("r", 8);

    // Rank badge
    rows.append("circle")
      .attr("cx", -20)
      .attr("cy", yScale.bandwidth() / 2)
      .attr("r", 10)
      .attr("fill", isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.05)")
      .attr("stroke", isDark ? "rgba(255,255,255,0.2)" : "rgba(0,0,0,0.1)")
      .attr("stroke-width", 1);

    rows.append("text")
      .attr("x", -20)
      .attr("y", yScale.bandwidth() / 2)
      .attr("dy", "0.35em")
      .attr("text-anchor", "middle")
      .text((_, i) => i + 1)
      .style("font-size", "9px")
      .style("font-weight", "700")
      .style("fill", "var(--foreground)");

    // Count badge (right side)
    rows.append("rect")
      .attr("x", barMaxWidth + 8)
      .attr("y", (yScale.bandwidth() - 18) / 2)
      .attr("width", 50)
      .attr("height", 18)
      .attr("rx", 9)
      .attr("fill", isDark ? "rgba(139,92,246,0.2)" : "rgba(167,139,250,0.2)");

    rows.append("text")
      .attr("x", barMaxWidth + 33)
      .attr("y", yScale.bandwidth() / 2)
      .attr("dy", "0.35em")
      .attr("text-anchor", "middle")
      .text(d => d.value.toLocaleString())
      .style("font-size", "10px")
      .style("font-weight", "700")
      .style("fill", isDark ? "#A78BFA" : "#7C3AED");

    // Journal name (truncated)
    rows.append("text")
      .attr("x", 5)
      .attr("y", yScale.bandwidth() / 2 - 10)
      .text(d => {
        const maxLen = Math.floor(barMaxWidth / 7);
        return d.label.length > maxLen ? d.label.slice(0, maxLen - 2) + "..." : d.label;
      })
      .style("font-size", "10px")
      .style("font-weight", "600")
      .style("fill", "var(--foreground)")
      .attr("opacity", 0)
      .transition()
      .duration(400)
      .delay((_, i) => i * 60 + 300)
      .attr("opacity", 1);

    // Hover interactions
    rows
      .on("mouseover", function (event, d) {
        const i = data.indexOf(d);
        d3.select(this).select(".lollipop-head")
          .transition().duration(150)
          .attr("r", 11);
        d3.select(this).select(".lollipop-stem")
          .transition().duration(150)
          .attr("height", 6)
          .attr("y", (yScale.bandwidth() - 6) / 2);

        tip.style("visibility", "visible")
          .html(
            `<div style="font-weight:700;margin-bottom:6px">${d.label}</div>
            <div style="display:flex;gap:16px;font-size:11px">
              <div>
                <span style="opacity:0.5">Rank</span>
                <span style="margin-left:4px;font-weight:700">#${i + 1}</span>
              </div>
              <div>
                <span style="opacity:0.5">Papers</span>
                <span style="margin-left:4px;font-weight:700;color:${isDark ? "#A78BFA" : "#7C3AED"}">${d.value.toLocaleString()}</span>
              </div>
            </div>`
          );
      })
      .on("mousemove", function (event) {
        const [mx, my] = d3.pointer(event, el);
        tip.style("left", `${mx + 15}px`).style("top", `${my - 10}px`);
      })
      .on("mouseout", function () {
        d3.select(this).select(".lollipop-head")
          .transition().duration(150)
          .attr("r", 8);
        d3.select(this).select(".lollipop-stem")
          .transition().duration(150)
          .attr("height", 4)
          .attr("y", (yScale.bandwidth() - 4) / 2);
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
