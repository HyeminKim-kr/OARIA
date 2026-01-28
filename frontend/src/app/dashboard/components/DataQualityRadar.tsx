"use client";
import { useRef, useEffect } from "react";
import * as d3 from "d3";

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

// Theme-aware color function
function getThemeColors(isDark: boolean) {
  return {
    primary: isDark ? "#22D3EE" : "#0891B2",      // Cyan
    secondary: isDark ? "#60A5FA" : "#2563EB",    // Blue
    highlight: isDark ? "#FBBF24" : "#D97706",    // Amber
    danger: isDark ? "#F87171" : "#DC2626",       // Red
    success: isDark ? "#4ADE80" : "#16A34A",      // Green
    gradientStart: isDark ? "#22D3EE" : "#0891B2",
    gradientEnd: isDark ? "#60A5FA" : "#2563EB",
    bgCircle: isDark ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.02)",
    strokeCircle: isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)",
    axisLine: isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)",
    text: isDark ? "rgba(255,255,255,0.7)" : "rgba(0,0,0,0.7)",
    textMuted: isDark ? "rgba(255,255,255,0.4)" : "rgba(0,0,0,0.4)",
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
    const margin = 60;
    const radius = Math.min(width, height) / 2 - margin;

    if (radius <= 0) return;

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

    const COLORS = getThemeColors(isDark);

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

    // Tooltip
    const tip = d3
      .select(el)
      .append("div")
      .style("position", "absolute")
      .style("visibility", "hidden")
      .style("background", isDark ? "rgba(20,20,30,0.95)" : "rgba(255,255,255,0.98)")
      .style("border", `2px solid ${COLORS.primary}`)
      .style("border-radius", "12px")
      .style("padding", "14px 18px")
      .style("font-size", "12px")
      .style("box-shadow", `0 8px 32px rgba(6,214,160,0.25)`)
      .style("pointer-events", "none")
      .style("z-index", "100")
      .style("color", "var(--foreground)")
      .style("min-width", "180px")
      .style("backdrop-filter", "blur(10px)");

    // Axis labels and data points
    data.forEach((d, i) => {
      const angle = angleSlice * i - Math.PI / 2;
      const labelRadius = radius + 30;
      const labelX = Math.cos(angle) * labelRadius;
      const labelY = Math.sin(angle) * labelRadius;

      // Get color based on value (green for high, red for low)
      const getValueColor = (val: number) => {
        if (val >= 80) return COLORS.success;
        if (val >= 60) return COLORS.primary;
        if (val >= 40) return COLORS.highlight;
        return COLORS.danger;
      };

      // Axis label with value badge
      const labelGroup = g.append("g")
        .attr("transform", `translate(${labelX}, ${labelY})`)
        .style("cursor", "pointer");

      // Label text
      labelGroup.append("text")
        .attr("text-anchor", "middle")
        .attr("dy", "-0.5em")
        .text(d.axis)
        .style("font-size", "10px")
        .style("font-weight", "700")
        .style("fill", "var(--foreground)");

      // Value badge
      const badgeWidth = 36;
      const badgeHeight = 18;

      labelGroup.append("rect")
        .attr("x", -badgeWidth / 2)
        .attr("y", 2)
        .attr("width", badgeWidth)
        .attr("height", badgeHeight)
        .attr("rx", 9)
        .attr("fill", getValueColor(d.value))
        .attr("opacity", 0.9);

      labelGroup.append("text")
        .attr("text-anchor", "middle")
        .attr("dy", "1.4em")
        .text(`${d.value.toFixed(0)}%`)
        .style("font-size", "9px")
        .style("font-weight", "800")
        .style("fill", "white");

      // Data point
      const pointRadius = (d.value / 100) * radius;
      const pointX = Math.cos(angle) * pointRadius;
      const pointY = Math.sin(angle) * pointRadius;

      const point = g.append("g")
        .attr("transform", `translate(${pointX}, ${pointY})`)
        .style("cursor", "pointer");

      // Outer ring
      point.append("circle")
        .attr("r", 12)
        .attr("fill", getValueColor(d.value))
        .attr("opacity", 0.15);

      // Inner point
      point.append("circle")
        .attr("r", 0)
        .attr("fill", getValueColor(d.value))
        .attr("stroke", isDark ? "#1a1a2e" : "white")
        .attr("stroke-width", 2)
        .attr("filter", "url(#point-shadow)")
        .transition()
        .duration(600)
        .delay(i * 100 + 800)
        .ease(d3.easeBackOut.overshoot(2))
        .attr("r", 6);

      // Hover interactions
      const showTooltip = () => {
        point.select("circle:nth-child(2)")
          .transition().duration(150)
          .attr("r", 9);

        tip.style("visibility", "visible")
          .html(
            `<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
              <div style="width:10px;height:10px;border-radius:50%;background:${getValueColor(d.value)}"></div>
              <span style="font-weight:800;font-size:14px">${d.axis}</span>
            </div>
            <div style="font-size:11px;opacity:0.7;margin-bottom:8px">${d.description}</div>
            <div style="display:flex;justify-content:space-between;align-items:baseline;padding-top:8px;border-top:1px solid var(--oaria-border)">
              <span style="font-size:24px;font-weight:800;color:${getValueColor(d.value)}">${d.value.toFixed(1)}%</span>
              <span style="font-size:11px;opacity:0.6">${d.count.toLocaleString()} / ${d.total.toLocaleString()}</span>
            </div>`
          );
      };

      const hideTooltip = () => {
        point.select("circle:nth-child(2)")
          .transition().duration(150)
          .attr("r", 6);
        tip.style("visibility", "hidden");
      };

      const moveTooltip = (event: MouseEvent) => {
        const [mx, my] = d3.pointer(event, el);
        tip.style("left", `${mx + 15}px`).style("top", `${my - 10}px`);
      };

      point.on("mouseover", showTooltip)
        .on("mousemove", (e) => moveTooltip(e as unknown as MouseEvent))
        .on("mouseout", hideTooltip);

      labelGroup.on("mouseover", showTooltip)
        .on("mousemove", (e) => moveTooltip(e as unknown as MouseEvent))
        .on("mouseout", hideTooltip);
    });

    // Center score display
    const avgScore = data.reduce((sum, d) => sum + d.value, 0) / data.length;
    const scoreColor = avgScore >= 80 ? COLORS.success : avgScore >= 60 ? COLORS.primary : avgScore >= 40 ? COLORS.highlight : COLORS.danger;

    // Center circle background
    const centerRadius = 32;
    g.append("circle")
      .attr("r", centerRadius)
      .attr("fill", isDark ? "rgba(10,10,20,0.8)" : "rgba(255,255,255,0.95)")
      .attr("stroke", scoreColor)
      .attr("stroke-width", 3)
      .attr("filter", "url(#point-shadow)");

    // Score text
    g.append("text")
      .attr("text-anchor", "middle")
      .attr("dy", "0.1em")
      .text(avgScore.toFixed(0))
      .style("font-size", "20px")
      .style("font-weight", "800")
      .style("fill", scoreColor);

    g.append("text")
      .attr("text-anchor", "middle")
      .attr("dy", "1.8em")
      .text("SCORE")
      .style("font-size", "7px")
      .style("font-weight", "700")
      .style("letter-spacing", "1px")
      .style("fill", "var(--oaria-text-secondary)");

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
