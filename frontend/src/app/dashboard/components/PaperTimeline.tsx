"use client";
import { useRef, useEffect } from "react";
import * as d3 from "d3";
import { PASTEL } from "../constants";

interface TimelineItem {
  id: string;
  title: string;
  journal: string;
  date: string; // ISO string
}

interface Props {
  data: TimelineItem[];
  onPaperClick?: (id: string) => void;
}

export default function PaperTimeline({ data, onPaperClick }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !data.length) return;
    const el = ref.current;
    d3.select(el).selectAll("*").remove();

    const margin = { top: 20, right: 20, bottom: 30, left: 20 };
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
      .style("background", "var(--background)")
      .style("border", "1px solid var(--oaria-border)")
      .style("border-radius", "10px")
      .style("padding", "8px 14px")
      .style("font-size", "13px")
      .style("line-height", "1.5")
      .style("box-shadow", "0 4px 20px rgba(0,0,0,0.08)")
      .style("pointer-events", "none")
      .style("z-index", "50")
      .style("color", "var(--foreground)")
      .style("max-width", "300px");

    const dates = data.map((d) => new Date(d.date));
    const extent = d3.extent(dates) as [Date, Date];

    const x = d3.scaleTime().domain(extent).range([0, width]).nice();

    const lineY = height / 2;

    // Timeline line
    svg
      .append("line")
      .attr("x1", 0)
      .attr("x2", width)
      .attr("y1", lineY)
      .attr("y2", lineY)
      .attr("stroke", "var(--oaria-border)")
      .attr("stroke-width", 2)
      .attr("stroke-dasharray", "4,4");

    const color = d3.scaleOrdinal<string>().range(PASTEL);

    // Dots
    svg
      .selectAll("circle")
      .data(data)
      .join("circle")
      .attr("cx", (d) => x(new Date(d.date)))
      .attr("cy", (_d, i) => lineY + (i % 2 === 0 ? -20 : 20))
      .attr("r", 0)
      .attr("fill", (_d, i) => color(String(i)))
      .attr("stroke", "white")
      .attr("stroke-width", 2)
      .style("cursor", "pointer")
      .on("mouseover", function (_event, d) {
        d3.select(this).transition().duration(200).attr("r", 10);
        const title = d.title.length > 60 ? d.title.slice(0, 58) + ".." : d.title;
        tip
          .style("visibility", "visible")
          .html(
            `<strong>${title}</strong><br/><span style="opacity:0.7">${d.journal || "Unknown"}</span><br/><span style="opacity:0.5">${new Date(d.date).toLocaleDateString("ko-KR")}</span>`
          );
      })
      .on("mousemove", function (event) {
        const [mx, my] = d3.pointer(event, el);
        tip.style("left", `${mx + 16}px`).style("top", `${my - 10}px`);
      })
      .on("mouseout", function () {
        d3.select(this).transition().duration(200).attr("r", 7);
        tip.style("visibility", "hidden");
      })
      .on("click", (_event, d) => onPaperClick?.(d.id))
      .transition()
      .duration(600)
      .delay((_d, i) => i * 80)
      .attr("r", 7);

    // Connector lines
    svg
      .selectAll(".connector")
      .data(data)
      .join("line")
      .attr("class", "connector")
      .attr("x1", (d) => x(new Date(d.date)))
      .attr("x2", (d) => x(new Date(d.date)))
      .attr("y1", lineY)
      .attr("y2", (_d, i) => lineY + (i % 2 === 0 ? -13 : 13))
      .attr("stroke", "var(--oaria-border)")
      .attr("stroke-width", 1);

    // X axis
    svg
      .append("g")
      .attr("transform", `translate(0,${height})`)
      .call(d3.axisBottom(x).ticks(5).tickFormat(d3.timeFormat("%m/%d") as unknown as (d: d3.NumberValue, i: number) => string))
      .call((g) => g.select(".domain").attr("stroke", "var(--oaria-border)"))
      .call((g) => g.selectAll(".tick line").attr("stroke", "var(--oaria-border)"))
      .call((g) =>
        g.selectAll("text").style("fill", "var(--oaria-text-secondary)").style("font-size", "10px")
      );
  }, [data, onPaperClick]);

  if (!data.length) {
    return (
      <div className="w-full h-full flex items-center justify-center text-sm text-[var(--oaria-text-secondary)]">
        타임라인 데이터가 부족합니다
      </div>
    );
  }

  return <div ref={ref} className="w-full h-full relative" />;
}
