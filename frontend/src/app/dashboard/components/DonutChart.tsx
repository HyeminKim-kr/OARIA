"use client";
import { useRef, useEffect } from "react";
import * as d3 from "d3";
import { PASTEL } from "../constants";

interface Slice {
  label: string;
  value: number;
}

interface Props {
  data: Slice[];
  centerLabel?: string;
}

export default function DonutChart({ data, centerLabel }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !data.length) return;
    const el = ref.current;
    d3.select(el).selectAll("*").remove();

    const width = el.clientWidth;
    const height = el.clientHeight;
    const radius = Math.min(width, height) / 2 - 10;
    if (radius <= 0) return;

    const svg = d3
      .select(el)
      .append("svg")
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${width / 2},${height / 2})`);

    const tip = d3
      .select(el)
      .append("div")
      .style("position", "absolute")
      .style("visibility", "hidden")
      .style("background", "var(--background)")
      .style("border", "1px solid var(--oaria-border)")
      .style("border-radius", "10px")
      .style("padding", "8px 14px")
      .style("font-size", "13px")
      .style("box-shadow", "0 4px 20px rgba(0,0,0,0.08)")
      .style("pointer-events", "none")
      .style("z-index", "50")
      .style("color", "var(--foreground)");

    const color = d3.scaleOrdinal<string>().range(PASTEL);
    const pie = d3
      .pie<Slice>()
      .value((d) => d.value)
      .sort(null)
      .padAngle(0.03);

    const arc = d3
      .arc<d3.PieArcDatum<Slice>>()
      .innerRadius(radius * 0.6)
      .outerRadius(radius);

    const arcHover = d3
      .arc<d3.PieArcDatum<Slice>>()
      .innerRadius(radius * 0.58)
      .outerRadius(radius + 6);

    const total = d3.sum(data, (d) => d.value);

    const arcs = svg
      .selectAll("path")
      .data(pie(data))
      .join("path")
      .attr("fill", (_d, i) => color(String(i)))
      .attr("opacity", 0.85)
      .attr("stroke", "var(--background)")
      .attr("stroke-width", 2)
      .style("cursor", "pointer")
      .on("mouseover", function (_event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr("d", arcHover as never)
          .attr("opacity", 1);
        tip
          .style("visibility", "visible")
          .html(
            `<strong>${d.data.label}</strong><br/>${d.data.value}건 (${((d.data.value / total) * 100).toFixed(1)}%)`
          );
      })
      .on("mousemove", function (event) {
        const [mx, my] = d3.pointer(event, el);
        tip.style("left", `${mx + 16}px`).style("top", `${my - 10}px`);
      })
      .on("mouseout", function () {
        d3.select(this)
          .transition()
          .duration(200)
          .attr("d", arc as never)
          .attr("opacity", 0.85);
        tip.style("visibility", "hidden");
      });

    // Entrance animation
    arcs
      .transition()
      .duration(1000)
      .attrTween("d", function (d) {
        const interpolate = d3.interpolate({ startAngle: 0, endAngle: 0 }, d);
        return (t) => arc(interpolate(t)) || "";
      });

    // Center text
    if (centerLabel) {
      svg
        .append("text")
        .text(centerLabel)
        .attr("text-anchor", "middle")
        .attr("dy", "-0.2em")
        .style("font-size", "13px")
        .style("fill", "var(--oaria-text-secondary)")
        .style("font-weight", "500");
      svg
        .append("text")
        .text(total.toLocaleString())
        .attr("text-anchor", "middle")
        .attr("dy", "1.2em")
        .style("font-size", "20px")
        .style("fill", "var(--foreground)")
        .style("font-weight", "700");
    }
  }, [data, centerLabel]);

  if (!data.length) {
    return (
      <div className="w-full h-full flex items-center justify-center text-sm text-[var(--oaria-text-secondary)]">
        데이터가 부족합니다
      </div>
    );
  }

  return <div ref={ref} className="w-full h-full relative" />;
}
