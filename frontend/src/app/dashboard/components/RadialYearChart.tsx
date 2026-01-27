"use client";
import { useRef, useEffect } from "react";
import * as d3 from "d3";
import { PASTEL } from "../constants";

interface RadialItem {
  year: number;
  count: number;
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

    const sorted = [...data].sort((a, b) => a.year - b.year);
    const maxCount = d3.max(sorted, (d) => d.count) || 1;

    const angleScale = d3
      .scaleBand()
      .domain(sorted.map((d) => String(d.year)))
      .range([0, 2 * Math.PI])
      .padding(0.12);

    const rScale = d3.scaleLinear().domain([0, maxCount]).range([radius * 0.25, radius]);

    const color = d3.scaleOrdinal<string>().range(PASTEL);

    const arc = d3
      .arc<RadialItem>()
      .innerRadius(radius * 0.25)
      .outerRadius((d) => rScale(d.count))
      .startAngle((d) => angleScale(String(d.year)) || 0)
      .endAngle((d) => (angleScale(String(d.year)) || 0) + angleScale.bandwidth())
      .padAngle(0.02)
      .cornerRadius(4);

    svg
      .selectAll("path")
      .data(sorted)
      .join("path")
      .attr("fill", (_d, i) => color(String(i)))
      .attr("opacity", 0.82)
      .attr("stroke", "var(--background)")
      .attr("stroke-width", 1)
      .style("cursor", "pointer")
      .on("mouseover", function () {
        d3.select(this).attr("opacity", 1);
        tip.style("visibility", "visible");
      })
      .on("mousemove", function (event) {
        const d = d3.select(this).datum() as RadialItem;
        const [mx, my] = d3.pointer(event, el);
        tip
          .html(`<strong>${d.year}년</strong><br/>${d.count.toLocaleString()}건`)
          .style("left", `${mx + 16}px`)
          .style("top", `${my - 10}px`);
      })
      .on("mouseout", function () {
        d3.select(this).attr("opacity", 0.82);
        tip.style("visibility", "hidden");
      })
      // Entrance animation
      .attr("d", (d) =>
        d3
          .arc<RadialItem>()
          .innerRadius(radius * 0.25)
          .outerRadius(radius * 0.25)
          .startAngle(angleScale(String(d.year)) || 0)
          .endAngle((angleScale(String(d.year)) || 0) + angleScale.bandwidth())
          .padAngle(0.02)
          .cornerRadius(4)(d)
      )
      .transition()
      .duration(1000)
      .delay((_d, i) => i * 80)
      .attrTween("d", function (d) {
        const interp = d3.interpolate(radius * 0.25, rScale(d.count));
        return (t) =>
          d3
            .arc<RadialItem>()
            .innerRadius(radius * 0.25)
            .outerRadius(interp(t))
            .startAngle(angleScale(String(d.year)) || 0)
            .endAngle((angleScale(String(d.year)) || 0) + angleScale.bandwidth())
            .padAngle(0.02)
            .cornerRadius(4)(d) || "";
      });

    // Year labels
    svg
      .selectAll(".year-label")
      .data(sorted)
      .join("text")
      .attr("class", "year-label")
      .attr("transform", (d) => {
        const angle = (angleScale(String(d.year)) || 0) + angleScale.bandwidth() / 2;
        const r = radius + 14;
        const x = r * Math.sin(angle);
        const y = -r * Math.cos(angle);
        return `translate(${x},${y})`;
      })
      .attr("text-anchor", "middle")
      .attr("dy", "0.35em")
      .text((d) => String(d.year).slice(2))
      .style("font-size", "10px")
      .style("fill", "var(--oaria-text-secondary)")
      .style("font-weight", "500");

    // Center label
    svg
      .append("text")
      .text("Year")
      .attr("text-anchor", "middle")
      .attr("dy", "-0.2em")
      .style("font-size", "11px")
      .style("fill", "var(--oaria-text-secondary)");
    svg
      .append("text")
      .text("Distribution")
      .attr("text-anchor", "middle")
      .attr("dy", "1em")
      .style("font-size", "11px")
      .style("fill", "var(--oaria-text-secondary)");
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
