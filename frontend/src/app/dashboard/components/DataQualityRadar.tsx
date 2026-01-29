"use client";
import { useRef, useEffect } from "react";
import * as d3 from "d3";
import { BRAND, getThemeColors as getBaseThemeColors } from "../constants";

interface DataQualityMetric {
  axis: string;
  value: number; // 0-100 percentage
  count: number;
  total: number;
  description: string;
}

interface Props {
  data: DataQualityMetric[];
  totalPapers?: number; // Total papers in DB
  sampleSize?: number;  // Sample size used for calculation
}

// Brand-aligned theme colors for radar chart
function getRadarThemeColors(isDark: boolean) {
  const base = getBaseThemeColors(isDark);
  return {
    ...base,
    // Brand-aligned radar colors
    primary: isDark ? "#2DD4BF" : BRAND.teal,           // Teal
    secondary: isDark ? "#5EEAD4" : BRAND.lightTeal,    // Light Teal
    highlight: isDark ? "#FACC15" : "#CA8A04",          // Yellow/Amber
    danger: isDark ? "#FDA4AF" : BRAND.coral,           // Coral
    success: isDark ? "#4ADE80" : "#16A34A",            // Green
    gradientStart: isDark ? "#2DD4BF" : BRAND.teal,
    gradientEnd: isDark ? "#5EEAD4" : BRAND.lightTeal,
    bgCircle: isDark ? "rgba(45, 212, 191, 0.03)" : "rgba(13, 148, 136, 0.03)",
    strokeCircle: isDark ? "rgba(45, 212, 191, 0.15)" : "rgba(13, 148, 136, 0.1)",
    axisLine: isDark ? "rgba(148, 163, 184, 0.15)" : "rgba(15, 23, 42, 0.08)",
    text: isDark ? "#F8FAFC" : "#0F172A",
    textMuted: isDark ? "#94A3B8" : "#64748B",
  };
}

export default function DataQualityRadar({ data, totalPapers, sampleSize }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !data.length) return;
    const el = ref.current;
    d3.select(el).selectAll("*").remove();

    const width = el.clientWidth;
    const height = el.clientHeight;
    // Dynamic margin based on container size for better spacing
    const margin = Math.max(50, Math.min(width, height) * 0.22);
    const radius = Math.min(width, height) / 2 - margin;

    if (radius <= 20) return;

    const svg = d3
      .select(el)
      .append("svg")
      .attr("width", width)
      .attr("height", height);

    const g = svg
      .append("g")
      .attr("transform", `translate(${width / 2}, ${height / 2})`);

    // Detect dark mode
    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches
      || document.documentElement.classList.contains("dark");

    const COLORS = getRadarThemeColors(isDark);

    const defs = svg.append("defs");

    // Gradient for the filled area
    const areaGrad = defs.append("linearGradient")
      .attr("id", "radar-area-grad")
      .attr("x1", "0%").attr("y1", "0%")
      .attr("x2", "100%").attr("y2", "100%");
    areaGrad.append("stop").attr("offset", "0%").attr("stop-color", COLORS.gradientStart).attr("stop-opacity", 0.4);
    areaGrad.append("stop").attr("offset", "100%").attr("stop-color", COLORS.gradientEnd).attr("stop-opacity", 0.15);

    // Glow filter for the line
    const glowFilter = defs.append("filter").attr("id", "line-glow")
      .attr("x", "-50%").attr("y", "-50%").attr("width", "200%").attr("height", "200%");
    glowFilter.append("feGaussianBlur").attr("in", "SourceGraphic").attr("stdDeviation", "2").attr("result", "blur");
    glowFilter.append("feFlood").attr("flood-color", COLORS.primary).attr("flood-opacity", "0.6");
    glowFilter.append("feComposite").attr("in2", "blur").attr("operator", "in");
    const glowMerge = glowFilter.append("feMerge");
    glowMerge.append("feMergeNode");
    glowMerge.append("feMergeNode").attr("in", "SourceGraphic");

    // Drop shadow for points
    const shadowFilter = defs.append("filter").attr("id", "point-shadow")
      .attr("x", "-50%").attr("y", "-50%").attr("width", "200%").attr("height", "200%");
    shadowFilter.append("feDropShadow")
      .attr("dx", "0").attr("dy", "2").attr("stdDeviation", "3")
      .attr("flood-color", COLORS.primary).attr("flood-opacity", "0.4");

    const angleSlice = (Math.PI * 2) / data.length;
    const levels = 4;

    // Background circles with gradient opacity
    for (let i = 1; i <= levels; i++) {
      const levelRadius = (radius / levels) * i;

      g.append("circle")
        .attr("r", levelRadius)
        .attr("fill", COLORS.bgCircle)
        .attr("stroke", COLORS.strokeCircle)
        .attr("stroke-width", 1);

      // Level percentage labels
      if (i > 0) {
        g.append("text")
          .attr("x", 4)
          .attr("y", -levelRadius + 4)
          .text(`${(i / levels) * 100}%`)
          .style("font-size", "8px")
          .style("fill", COLORS.textMuted)
          .style("font-weight", "500");
      }
    }

    // Draw axis lines
    data.forEach((_, i) => {
      const angle = angleSlice * i - Math.PI / 2;
      const x = Math.cos(angle) * radius;
      const y = Math.sin(angle) * radius;

      g.append("line")
        .attr("x1", 0).attr("y1", 0)
        .attr("x2", x).attr("y2", y)
        .attr("stroke", COLORS.axisLine)
        .attr("stroke-width", 1)
        .attr("stroke-dasharray", "4,4");
    });

    // Create the radar area path
    const radarLine = d3.lineRadial<DataQualityMetric>()
      .radius((d) => (d.value / 100) * radius)
      .angle((_, i) => i * angleSlice)
      .curve(d3.curveCardinalClosed.tension(0.2));

    // Animated radar area fill
    const areaPath = g.append("path")
      .datum(data)
      .attr("d", radarLine)
      .attr("fill", "url(#radar-area-grad)")
      .attr("stroke", "none")
      .attr("opacity", 0);

    areaPath.transition()
      .duration(800)
      .ease(d3.easeCubicOut)
      .attr("opacity", 1);

    // Animated radar line
    const linePath = g.append("path")
      .datum(data)
      .attr("d", radarLine)
      .attr("fill", "none")
      .attr("stroke", `url(#radar-area-grad)`)
      .attr("stroke-width", 3)
      .attr("filter", "url(#line-glow)")
      .attr("stroke-linecap", "round")
      .attr("stroke-linejoin", "round");

    const totalLength = (linePath.node() as SVGPathElement)?.getTotalLength?.() || 0;
    if (totalLength > 0) {
      linePath
        .attr("stroke-dasharray", `${totalLength} ${totalLength}`)
        .attr("stroke-dashoffset", totalLength)
        .transition()
        .duration(1200)
        .ease(d3.easeCubicInOut)
        .attr("stroke-dashoffset", 0);
    }

    // Tooltip - High contrast for both modes
    const tip = d3
      .select(el)
      .append("div")
      .style("position", "absolute")
      .style("visibility", "hidden")
      .style("background", isDark ? BRAND.darkBg : "#FFFFFF")
      .style("border", `1px solid ${isDark ? COLORS.primary : BRAND.border}`)
      .style("border-radius", "12px")
      .style("padding", "14px 18px")
      .style("font-size", "12px")
      .style("box-shadow", isDark ? "0 8px 32px rgba(0,0,0,0.4)" : "0 8px 32px rgba(0,0,0,0.12)")
      .style("pointer-events", "none")
      .style("z-index", "100")
      .style("color", isDark ? "#F8FAFC" : BRAND.deepNavy)
      .style("min-width", "180px")
      .style("backdrop-filter", "blur(10px)");

    // Get color based on value (green for high, red for low)
    const getValueColor = (val: number) => {
      if (val >= 80) return COLORS.success;
      if (val >= 60) return COLORS.primary;
      if (val >= 40) return COLORS.highlight;
      return COLORS.danger;
    };

    // Axis labels - positioned outside the chart cleanly
    data.forEach((d, i) => {
      const angle = angleSlice * i - Math.PI / 2;
      const labelRadius = radius + 18;
      const labelX = Math.cos(angle) * labelRadius;
      const labelY = Math.sin(angle) * labelRadius;

      // Determine text anchor based on position
      const isRight = labelX > 5;
      const isLeft = labelX < -5;
      const anchor = isRight ? "start" : isLeft ? "end" : "middle";

      // Adjust position for top/bottom labels
      const isTop = labelY < -5;
      const isBottom = labelY > 5;
      const dyOffset = isTop ? "-0.3em" : isBottom ? "0.8em" : "0.35em";

      const labelGroup = g.append("g")
        .attr("transform", `translate(${labelX}, ${labelY})`)
        .style("cursor", "pointer");

      // Compact label: "Name 85%"
      labelGroup.append("text")
        .attr("text-anchor", anchor)
        .attr("dy", dyOffset)
        .text(`${d.axis}`)
        .style("font-size", "9px")
        .style("font-weight", "600")
        .style("fill", COLORS.text);

      // Value text below/beside the label name
      const valueOffset = isTop ? 10 : isBottom ? -10 : 0;
      labelGroup.append("text")
        .attr("text-anchor", anchor)
        .attr("dy", isTop ? "0.8em" : isBottom ? "-0.4em" : "1.5em")
        .text(`${d.value.toFixed(0)}%`)
        .style("font-size", "10px")
        .style("font-weight", "800")
        .style("fill", getValueColor(d.value));

      // Hover for label
      labelGroup.on("mouseover", () => showTooltip(d, i))
        .on("mousemove", (e) => moveTooltip(e as unknown as MouseEvent))
        .on("mouseout", hideTooltip);
    });

    // Data points on the radar
    data.forEach((d, i) => {
      const angle = angleSlice * i - Math.PI / 2;
      const pointRadius = (d.value / 100) * radius;
      const pointX = Math.cos(angle) * pointRadius;
      const pointY = Math.sin(angle) * pointRadius;

      const point = g.append("g")
        .attr("transform", `translate(${pointX}, ${pointY})`)
        .style("cursor", "pointer");

      // Inner point only (no outer ring to reduce clutter)
      point.append("circle")
        .attr("r", 0)
        .attr("fill", getValueColor(d.value))
        .attr("stroke", isDark ? "#1a1a2e" : "white")
        .attr("stroke-width", 2)
        .transition()
        .duration(600)
        .delay(i * 80 + 600)
        .ease(d3.easeBackOut.overshoot(1.5))
        .attr("r", 5);

      point.on("mouseover", () => {
        point.select("circle").transition().duration(150).attr("r", 8);
        showTooltip(d, i);
      })
        .on("mousemove", (e) => moveTooltip(e as unknown as MouseEvent))
        .on("mouseout", () => {
          point.select("circle").transition().duration(150).attr("r", 5);
          hideTooltip();
        });
    });

    // Tooltip functions
    function showTooltip(d: DataQualityMetric, _i: number) {
      tip.style("visibility", "visible")
        .html(
          `<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
            <div style="width:10px;height:10px;border-radius:50%;background:${getValueColor(d.value)}"></div>
            <span style="font-weight:800;font-size:14px">${d.axis}</span>
          </div>
          <div style="font-size:11px;opacity:0.7;margin-bottom:8px">${d.description}</div>
          <div style="display:flex;justify-content:space-between;align-items:baseline;padding-top:8px;border-top:1px solid ${isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)"}">
            <span style="font-size:24px;font-weight:800;color:${getValueColor(d.value)}">${d.value.toFixed(1)}%</span>
            <span style="font-size:11px;opacity:0.6">${d.count.toLocaleString()} / ${d.total.toLocaleString()}</span>
          </div>`
        );
    }

    function hideTooltip() {
      tip.style("visibility", "hidden");
    }

    function moveTooltip(event: MouseEvent) {
      const [mx, my] = d3.pointer(event, el);
      tip.style("left", `${mx + 15}px`).style("top", `${my - 10}px`);
    }

    // Center score display - minimal design
    const avgScore = data.reduce((sum, d) => sum + d.value, 0) / data.length;
    const scoreColor = avgScore >= 80 ? COLORS.success : avgScore >= 60 ? COLORS.primary : avgScore >= 40 ? COLORS.highlight : COLORS.danger;

    // Center circle - compact size
    const centerRadius = Math.min(20, radius * 0.25);
    g.append("circle")
      .attr("r", centerRadius)
      .attr("fill", isDark ? "rgba(15,23,42,0.9)" : "rgba(255,255,255,0.95)")
      .attr("stroke", scoreColor)
      .attr("stroke-width", 2);

    // Score number only
    g.append("text")
      .attr("text-anchor", "middle")
      .attr("dy", "0.35em")
      .text(avgScore.toFixed(0))
      .style("font-size", `${Math.min(14, centerRadius * 0.8)}px`)
      .style("font-weight", "800")
      .style("fill", scoreColor);

    // Sample info at bottom
    if (sampleSize && totalPapers) {
      svg.append("text")
        .attr("x", width / 2)
        .attr("y", height - 8)
        .attr("text-anchor", "middle")
        .text(`Based on ${sampleSize.toLocaleString()} of ${totalPapers.toLocaleString()} papers`)
        .style("font-size", "9px")
        .style("fill", "var(--oaria-text-secondary)")
        .style("opacity", 0.6);
    }

  }, [data, totalPapers, sampleSize]);

  if (!data.length) {
    return (
      <div className="w-full h-full flex items-center justify-center text-sm text-[var(--oaria-text-secondary)]">
        데이터 품질 정보가 부족합니다
      </div>
    );
  }

  return <div ref={ref} className="w-full h-full relative" />;
}

export type { DataQualityMetric };
