"use client";
import { useRef, useEffect } from "react";
import * as d3 from "d3";
import { PASTEL } from "../constants";

interface AuthorItem {
  label: string;
  value: number;
}

interface Props {
  data: AuthorItem[];
}

export default function TopAuthorsBar({ data }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !data.length) return;
    const el = ref.current;
    d3.select(el).selectAll("*").remove();

    const margin = { top: 5, right: 40, bottom: 5, left: 110 };
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

    const y = d3
      .scaleBand()
      .domain(data.map((d) => d.label))
      .range([0, height])
      .padding(0.25);

    const x = d3
      .scaleLinear()
      .domain([0, d3.max(data, (d) => d.value) || 1])
      .range([0, width]);

    const color = d3.scaleOrdinal<string>().range(PASTEL);

    // Bars
    svg
      .selectAll("rect")
      .data(data)
      .join("rect")
      .attr("y", (d) => y(d.label) || 0)
      .attr("height", y.bandwidth())
      .attr("x", 0)
      .attr("rx", 6)
      .attr("fill", (_d, i) => color(String(i)))
      .attr("opacity", 0.8)
      .attr("width", 0)
      .transition()
      .duration(800)
      .delay((_d, i) => i * 50)
      .attr("width", (d) => x(d.value));

    // Author initials circle
    svg
      .selectAll(".avatar")
      .data(data)
      .join("circle")
      .attr("class", "avatar")
      .attr("cx", -20)
      .attr("cy", (d) => (y(d.label) || 0) + y.bandwidth() / 2)
      .attr("r", 10)
      .attr("fill", (_d, i) => color(String(i)))
      .attr("opacity", 0.3);

    // Labels
    svg
      .selectAll(".label")
      .data(data)
      .join("text")
      .attr("class", "label")
      .attr("x", -34)
      .attr("y", (d) => (y(d.label) || 0) + y.bandwidth() / 2)
      .attr("dy", "0.35em")
      .attr("text-anchor", "end")
      .text((d) => (d.label.length > 14 ? d.label.slice(0, 12) + ".." : d.label))
      .style("font-size", "11px")
      .style("fill", "var(--oaria-text-secondary)");

    // Values
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
      .style("fill", "var(--oaria-text-secondary)")
      .style("font-weight", "600")
      .attr("opacity", 0)
      .transition()
      .duration(800)
      .delay((_d, i) => i * 50 + 400)
      .attr("opacity", 1);
  }, [data]);

  if (!data.length) {
    return (
      <div className="w-full h-full flex items-center justify-center text-sm text-[var(--oaria-text-secondary)]">
        저자 데이터가 부족합니다
      </div>
    );
  }

  return <div ref={ref} className="w-full h-full relative" />;
}
