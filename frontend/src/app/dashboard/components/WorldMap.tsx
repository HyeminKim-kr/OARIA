"use client";
import { useRef, useEffect } from "react";
import * as d3 from "d3";
import { PASTEL } from "../constants";

interface CountryData {
  country: string;
  count: number;
  lat: number;
  lng: number;
}

interface Props {
  data: CountryData[];
}

// Simplified world map outline (Natural Earth 110m simplified to key country centroids)
// We draw a basic equirectangular projection with bubble overlay
const COUNTRY_COORDS: Record<string, [number, number]> = {
  "USA": [-98, 39], "UK": [-1.5, 54], "China": [104, 35], "Japan": [138, 36],
  "Germany": [10, 51], "France": [2, 47], "Italy": [12, 42], "Spain": [-3.7, 40],
  "Canada": [-106, 56], "Australia": [134, -25], "South Korea": [128, 37],
  "India": [79, 21], "Brazil": [-51, -10], "Netherlands": [5.3, 52],
  "Switzerland": [8.2, 47], "Sweden": [18, 62], "Belgium": [4.5, 50.8],
  "Austria": [14, 47.5], "Denmark": [10, 56], "Norway": [10, 62],
  "Finland": [26, 64], "Poland": [20, 52], "Russia": [100, 60],
  "Turkey": [35, 39], "Israel": [35, 31.5], "Iran": [53, 32],
  "Saudi Arabia": [45, 24], "Egypt": [30, 27], "South Africa": [25, -29],
  "Mexico": [-102, 23], "Argentina": [-64, -34], "Chile": [-71, -30],
  "Colombia": [-74, 4], "Taiwan": [121, 24], "Singapore": [104, 1.3],
  "Thailand": [101, 15], "Malaysia": [102, 4], "Indonesia": [118, -2],
  "Philippines": [122, 12], "Vietnam": [106, 16], "Pakistan": [69, 30],
  "Bangladesh": [90, 24], "Portugal": [-8, 39.5], "Greece": [22, 39],
  "Czech Republic": [15.5, 50], "Ireland": [-8, 53], "Hungary": [19.5, 47],
  "Romania": [25, 46], "New Zealand": [174, -41], "Nigeria": [8, 10],
  "Kenya": [38, 1], "Ethiopia": [40, 9], "Ghana": [-1.5, 7.9],
};

// Very simplified world coastline for background (lon/lat pairs forming a basic outline)
function drawWorldOutline(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  projection: d3.GeoProjection,
  width: number,
  height: number
) {
  // Draw a simple graticule + outline rectangle
  const graticule = d3.geoGraticule().step([30, 30]);
  const path = d3.geoPath().projection(projection);

  // World boundary (sphere outline)
  g.append("path")
    .datum({ type: "Sphere" } as d3.GeoPermissibleObjects)
    .attr("d", path)
    .attr("fill", "var(--background)")
    .attr("stroke", "var(--oaria-border)")
    .attr("stroke-width", 0.5);

  // Graticule lines
  g.append("path")
    .datum(graticule())
    .attr("d", path)
    .attr("fill", "none")
    .attr("stroke", "var(--oaria-border)")
    .attr("stroke-width", 0.3)
    .attr("stroke-opacity", 0.5);

  // Simple land mass approximations (rough continental outlines as circles)
  const continents = [
    { cx: width * 0.25, cy: height * 0.38, rx: width * 0.08, ry: height * 0.15 }, // North America
    { cx: width * 0.30, cy: height * 0.62, rx: width * 0.04, ry: height * 0.12 }, // South America
    { cx: width * 0.50, cy: height * 0.35, rx: width * 0.08, ry: height * 0.12 }, // Europe
    { cx: width * 0.52, cy: height * 0.55, rx: width * 0.06, ry: height * 0.12 }, // Africa
    { cx: width * 0.68, cy: height * 0.40, rx: width * 0.12, ry: height * 0.14 }, // Asia
    { cx: width * 0.78, cy: height * 0.72, rx: width * 0.05, ry: height * 0.06 }, // Australia
  ];

  g.selectAll(".continent")
    .data(continents)
    .join("ellipse")
    .attr("class", "continent")
    .attr("cx", (d) => d.cx)
    .attr("cy", (d) => d.cy)
    .attr("rx", (d) => d.rx)
    .attr("ry", (d) => d.ry)
    .attr("fill", "var(--oaria-border)")
    .attr("opacity", 0.15);
}

export default function WorldMap({ data }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !data.length) return;
    const el = ref.current;
    d3.select(el).selectAll("*").remove();

    const width = el.clientWidth;
    const height = el.clientHeight;
    if (width <= 0 || height <= 0) return;

    const svg = d3
      .select(el)
      .append("svg")
      .attr("width", width)
      .attr("height", height);

    const g = svg.append("g");

    const projection = d3
      .geoNaturalEarth1()
      .scale(width / 5.5)
      .translate([width / 2, height / 2]);

    drawWorldOutline(g, projection, width, height);

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

    const maxCount = d3.max(data, (d) => d.count) || 1;
    const rScale = d3.scaleSqrt().domain([1, maxCount]).range([4, 28]);
    const color = d3.scaleOrdinal<string>().range(PASTEL);

    // Bubbles
    const bubbles = g
      .selectAll(".bubble")
      .data(data)
      .join("g")
      .attr("class", "bubble")
      .attr("transform", (d) => {
        const [x, y] = projection([d.lng, d.lat]) || [0, 0];
        return `translate(${x},${y})`;
      })
      .style("cursor", "pointer");

    // Pulse ring
    bubbles
      .append("circle")
      .attr("r", (d) => rScale(d.count) + 4)
      .attr("fill", "none")
      .attr("stroke", (_d, i) => color(String(i)))
      .attr("stroke-width", 1)
      .attr("opacity", 0)
      .transition()
      .duration(1200)
      .delay((_d, i) => i * 60)
      .attr("opacity", 0.3)
      .transition()
      .duration(1500)
      .attr("r", (d) => rScale(d.count) + 12)
      .attr("opacity", 0);

    // Main circle
    bubbles
      .append("circle")
      .attr("r", 0)
      .attr("fill", (_d, i) => color(String(i)))
      .attr("opacity", 0.7)
      .attr("stroke", "white")
      .attr("stroke-width", 1.5)
      .on("mouseover", function (_event, d) {
        d3.select(this).transition().duration(200).attr("r", rScale(d.count) + 3).attr("opacity", 1);
        tip
          .style("visibility", "visible")
          .html(`<strong>${d.country}</strong><br/>${d.count.toLocaleString()}건 논문`);
      })
      .on("mousemove", function (event) {
        const [mx, my] = d3.pointer(event, el);
        tip.style("left", `${mx + 16}px`).style("top", `${my - 10}px`);
      })
      .on("mouseout", function (_event, d) {
        d3.select(this).transition().duration(200).attr("r", rScale(d.count)).attr("opacity", 0.7);
        tip.style("visibility", "hidden");
      })
      .transition()
      .duration(800)
      .delay((_d, i) => i * 60)
      .attr("r", (d) => rScale(d.count));

    // Country labels for top entries
    const topData = data.slice(0, 8);
    bubbles
      .filter((_d, i) => i < topData.length)
      .append("text")
      .text((d) => d.country)
      .attr("dy", (d) => -(rScale(d.count) + 6))
      .attr("text-anchor", "middle")
      .style("font-size", "9px")
      .style("fill", "var(--oaria-text-secondary)")
      .style("font-weight", "500")
      .style("pointer-events", "none")
      .attr("opacity", 0)
      .transition()
      .duration(600)
      .delay((_d, i) => i * 60 + 400)
      .attr("opacity", 1);

    // Fade-in
    svg.attr("opacity", 0).transition().duration(500).attr("opacity", 1);
  }, [data]);

  if (!data.length) {
    return (
      <div className="w-full h-full flex items-center justify-center text-sm text-[var(--oaria-text-secondary)]">
        지역별 데이터가 부족합니다
      </div>
    );
  }

  return <div ref={ref} className="w-full h-full relative" />;
}

export { COUNTRY_COORDS };
export type { CountryData };
