"use client";
import { useRef, useEffect } from "react";
import * as d3 from "d3";
import * as topojson from "topojson-client";

interface CountryData {
  country: string;
  count: number;
  lat: number;
  lng: number;
}

interface Props {
  data: CountryData[];
}

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

// Country flag emoji mapping
const COUNTRY_FLAGS: Record<string, string> = {
  "USA": "🇺🇸", "UK": "🇬🇧", "China": "🇨🇳", "Japan": "🇯🇵",
  "Germany": "🇩🇪", "France": "🇫🇷", "Italy": "🇮🇹", "Spain": "🇪🇸",
  "Canada": "🇨🇦", "Australia": "🇦🇺", "South Korea": "🇰🇷", "India": "🇮🇳",
  "Brazil": "🇧🇷", "Netherlands": "🇳🇱", "Switzerland": "🇨🇭", "Sweden": "🇸🇪",
  "Belgium": "🇧🇪", "Austria": "🇦🇹", "Denmark": "🇩🇰", "Norway": "🇳🇴",
  "Finland": "🇫🇮", "Poland": "🇵🇱", "Russia": "🇷🇺", "Turkey": "🇹🇷",
  "Israel": "🇮🇱", "Iran": "🇮🇷", "Saudi Arabia": "🇸🇦", "Egypt": "🇪🇬",
  "South Africa": "🇿🇦", "Mexico": "🇲🇽", "Argentina": "🇦🇷", "Chile": "🇨🇱",
  "Colombia": "🇨🇴", "Taiwan": "🇹🇼", "Singapore": "🇸🇬", "Thailand": "🇹🇭",
  "Malaysia": "🇲🇾", "Indonesia": "🇮🇩", "Philippines": "🇵🇭", "Vietnam": "🇻🇳",
  "Pakistan": "🇵🇰", "Bangladesh": "🇧🇩", "Portugal": "🇵🇹", "Greece": "🇬🇷",
  "Czech Republic": "🇨🇿", "Ireland": "🇮🇪", "Hungary": "🇭🇺", "Romania": "🇷🇴",
  "New Zealand": "🇳🇿", "Nigeria": "🇳🇬", "Kenya": "🇰🇪", "Ethiopia": "🇪🇹", "Ghana": "🇬🇭",
};

const WORLD_ATLAS_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

// Vibrant color palette for bubbles
const BUBBLE_COLORS = [
  "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
  "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9",
  "#F8B500", "#00CED1", "#FF7F50", "#9370DB", "#20B2AA",
];

export default function WorldMap({ data }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !data.length) return;
    const el = ref.current;
    d3.select(el).selectAll("*").remove();

    const width = el.clientWidth;
    const height = el.clientHeight;
    if (width <= 0 || height <= 0) return;

    // Calculate total for percentages
    const totalCount = data.reduce((sum, d) => sum + d.count, 0);

    const svg = d3
      .select(el)
      .append("svg")
      .attr("width", width)
      .attr("height", height)
      .style("border-radius", "12px");

    // Add defs for gradients
    const defs = svg.append("defs");

    // Create radial gradients for each bubble
    data.forEach((d, i) => {
      const baseColor = BUBBLE_COLORS[i % BUBBLE_COLORS.length];
      const grad = defs
        .append("radialGradient")
        .attr("id", `bubble-grad-${i}`)
        .attr("cx", "30%")
        .attr("cy", "30%")
        .attr("r", "70%");
      grad.append("stop").attr("offset", "0%").attr("stop-color", d3.color(baseColor)?.brighter(0.8)?.toString() || baseColor);
      grad.append("stop").attr("offset", "100%").attr("stop-color", baseColor);

      // Glow filter
      const filter = defs.append("filter").attr("id", `bubble-glow-${i}`).attr("x", "-50%").attr("y", "-50%").attr("width", "200%").attr("height", "200%");
      filter.append("feGaussianBlur").attr("in", "SourceGraphic").attr("stdDeviation", "4").attr("result", "blur");
      filter.append("feFlood").attr("flood-color", baseColor).attr("flood-opacity", "0.6").attr("result", "color");
      filter.append("feComposite").attr("in", "color").attr("in2", "blur").attr("operator", "in").attr("result", "glow");
      const merge = filter.append("feMerge");
      merge.append("feMergeNode").attr("in", "glow");
      merge.append("feMergeNode").attr("in", "SourceGraphic");
    });

    const g = svg.append("g");

    const projection = d3
      .geoNaturalEarth1()
      .scale(Math.min(width / 5.0, height / 2.4))
      .translate([width / 2, height / 2 + 10]);

    const pathGen = d3.geoPath().projection(projection);

    // Tooltip with enhanced styling
    const tip = d3
      .select(el)
      .append("div")
      .style("position", "absolute")
      .style("visibility", "hidden")
      .style("background", "var(--background)")
      .style("border", "1px solid var(--oaria-border)")
      .style("border-radius", "12px")
      .style("padding", "12px 18px")
      .style("font-size", "13px")
      .style("line-height", "1.6")
      .style("box-shadow", "0 8px 32px rgba(0,0,0,0.15)")
      .style("pointer-events", "none")
      .style("z-index", "50")
      .style("color", "var(--foreground)")
      .style("min-width", "160px")
      .style("backdrop-filter", "blur(8px)");

    const maxCount = d3.max(data, (d) => d.count) || 1;
    const rScale = d3.scaleSqrt().domain([1, maxCount]).range([6, 42]);

    // Fetch real world TopoJSON
    fetch(WORLD_ATLAS_URL)
      .then((res) => res.json())
      .then((world) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const countries = topojson.feature(world as any, (world as any).objects.countries) as unknown as d3.GeoPermissibleObjects;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const borders = topojson.mesh(world as any, (world as any).objects.countries, (a: any, b: any) => a !== b);

        // Detect dark mode
        const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches
          || document.documentElement.classList.contains("dark");

        // Ocean with gradient
        const oceanGrad = defs.append("linearGradient").attr("id", "ocean-grad").attr("x1", "0%").attr("y1", "0%").attr("x2", "100%").attr("y2", "100%");
        oceanGrad.append("stop").attr("offset", "0%").attr("stop-color", isDark ? "#0f0f1a" : "#e8f4f8");
        oceanGrad.append("stop").attr("offset", "100%").attr("stop-color", isDark ? "#1a1a2e" : "#f0f4f8");

        g.append("rect")
          .attr("width", width)
          .attr("height", height)
          .attr("fill", "url(#ocean-grad)");

        // Sphere outline
        g.append("path")
          .datum({ type: "Sphere" } as d3.GeoPermissibleObjects)
          .attr("d", pathGen)
          .attr("fill", "none")
          .attr("stroke", isDark ? "#3a3a5e" : "#a0b0c0")
          .attr("stroke-width", 1);

        // Graticule
        const graticule = d3.geoGraticule().step([30, 30]);
        g.append("path")
          .datum(graticule())
          .attr("d", pathGen)
          .attr("fill", "none")
          .attr("stroke", isDark ? "#2a2a4a" : "#c0cdd8")
          .attr("stroke-width", 0.3)
          .attr("stroke-opacity", isDark ? 0.4 : 0.35);

        // Countries
        g.append("g")
          .selectAll("path")
          .data((countries as { type: string; features: d3.GeoPermissibleObjects[] }).features)
          .join("path")
          .attr("d", pathGen as never)
          .attr("fill", isDark ? "#2a2a4a" : "#c8d6e5")
          .attr("fill-opacity", isDark ? 0.9 : 0.8)
          .attr("stroke", isDark ? "#3a3a5e" : "#a0b0c0")
          .attr("stroke-width", 0.5);

        // Borders
        g.append("path")
          .datum(borders as d3.GeoPermissibleObjects)
          .attr("d", pathGen)
          .attr("fill", "none")
          .attr("stroke", isDark ? "#4a4a6e" : "#8899aa")
          .attr("stroke-width", 0.6)
          .attr("stroke-opacity", 0.6);

        // --- Bubbles ---
        drawBubbles(g, data, projection, rScale, tip, el, totalCount, isDark);
      })
      .catch(() => {
        const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches
          || document.documentElement.classList.contains("dark");
        // Fallback: draw without real map
        g.append("path")
          .datum({ type: "Sphere" } as d3.GeoPermissibleObjects)
          .attr("d", pathGen)
          .attr("fill", isDark ? "#1a1a2e" : "#f0f4f8")
          .attr("stroke", isDark ? "#3a3a5e" : "#a0b0c0")
          .attr("stroke-width", 0.8);

        const graticule = d3.geoGraticule().step([20, 20]);
        g.append("path")
          .datum(graticule())
          .attr("d", pathGen)
          .attr("fill", "none")
          .attr("stroke", isDark ? "#2a2a4a" : "#c0cdd8")
          .attr("stroke-width", 0.3)
          .attr("stroke-opacity", 0.5);

        drawBubbles(g, data, projection, rScale, tip, el, totalCount, isDark);
      });

    svg.attr("opacity", 0).transition().duration(600).attr("opacity", 1);
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

function drawBubbles(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  data: CountryData[],
  projection: d3.GeoProjection,
  rScale: d3.ScalePower<number, number>,
  tip: d3.Selection<HTMLDivElement, unknown, null, undefined>,
  el: HTMLDivElement,
  totalCount: number,
  isDark = false
) {
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

  // Outer glow ring
  bubbles
    .append("circle")
    .attr("class", "glow-ring")
    .attr("r", (d) => rScale(d.count) + 6)
    .attr("fill", "none")
    .attr("stroke", (_d, i) => BUBBLE_COLORS[i % BUBBLE_COLORS.length])
    .attr("stroke-width", 2)
    .attr("stroke-opacity", 0.2)
    .style("pointer-events", "none");

  // Shadow / glow for bubbles
  bubbles
    .append("circle")
    .attr("r", (d) => rScale(d.count) + 4)
    .attr("fill", (_d, i) => BUBBLE_COLORS[i % BUBBLE_COLORS.length])
    .attr("opacity", 0.25)
    .attr("filter", "blur(6px)")
    .style("pointer-events", "none");

  // Main circle with gradient
  bubbles
    .append("circle")
    .attr("class", "main-bubble")
    .attr("r", 0)
    .attr("fill", (_d, i) => `url(#bubble-grad-${i})`)
    .attr("stroke", isDark ? "rgba(255,255,255,0.3)" : "rgba(255,255,255,0.8)")
    .attr("stroke-width", (d) => (rScale(d.count) > 20 ? 2.5 : 1.5))
    .style("filter", "drop-shadow(0 2px 4px rgba(0,0,0,0.2))")
    .on("mouseover", function (_event, d) {
      const i = data.indexOf(d);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      d3.select((this as any).parentNode).select(".glow-ring")
        .transition().duration(200)
        .attr("stroke-opacity", 0.5)
        .attr("stroke-width", 3);
      d3.select(this).transition().duration(200)
        .attr("r", rScale(d.count) + 6)
        .attr("stroke-width", 3)
        .style("filter", `drop-shadow(0 4px 12px ${BUBBLE_COLORS[i % BUBBLE_COLORS.length]}66)`);

      const rank = data.indexOf(d) + 1;
      const pct = ((d.count / totalCount) * 100).toFixed(1);
      const flag = COUNTRY_FLAGS[d.country] || "🌍";

      tip
        .style("visibility", "visible")
        .html(
          `<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">` +
          `<span style="font-size:24px">${flag}</span>` +
          `<div>` +
          `<strong style="font-size:15px">${d.country}</strong>` +
          `<span style="opacity:0.5;margin-left:6px">#${rank}</span>` +
          `</div></div>` +
          `<div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:4px">` +
          `<span style="font-size:22px;font-weight:800;color:${BUBBLE_COLORS[i % BUBBLE_COLORS.length]}">${d.count.toLocaleString()}</span>` +
          `<span style="opacity:0.6;font-size:12px">papers</span>` +
          `</div>` +
          `<div style="margin-top:6px;padding-top:6px;border-top:1px solid var(--oaria-border);display:flex;justify-content:space-between">` +
          `<span style="opacity:0.6;font-size:12px">전체 대비</span>` +
          `<span style="font-weight:700;font-size:14px">${pct}%</span>` +
          `</div>`
        );
    })
    .on("mousemove", function (event) {
      const [mx, my] = d3.pointer(event, el);
      tip.style("left", `${mx + 20}px`).style("top", `${my - 10}px`);
    })
    .on("mouseout", function (_event, d) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      d3.select((this as any).parentNode).select(".glow-ring")
        .transition().duration(200)
        .attr("stroke-opacity", 0.2)
        .attr("stroke-width", 2);
      d3.select(this).transition().duration(200)
        .attr("r", rScale(d.count))
        .attr("stroke-width", rScale(d.count) > 20 ? 2.5 : 1.5)
        .style("filter", "drop-shadow(0 2px 4px rgba(0,0,0,0.2))");
      tip.style("visibility", "hidden");
    })
    .transition()
    .duration(800)
    .delay((_d, i) => i * 50)
    .ease(d3.easeElasticOut.amplitude(1).period(0.4))
    .attr("r", (d) => rScale(d.count));

  // Percentage inside bubbles (for larger ones)
  bubbles
    .filter((d) => rScale(d.count) > 22)
    .append("text")
    .text((d) => `${((d.count / totalCount) * 100).toFixed(0)}%`)
    .attr("text-anchor", "middle")
    .attr("dy", "0.35em")
    .style("font-size", (d) => (rScale(d.count) > 32 ? "13px" : "10px"))
    .style("fill", "white")
    .style("font-weight", "800")
    .style("pointer-events", "none")
    .style("text-shadow", "0 1px 3px rgba(0,0,0,0.5)")
    .attr("opacity", 0)
    .transition()
    .duration(500)
    .delay((_d, i) => i * 50 + 500)
    .attr("opacity", 1);

  // Country labels outside small bubbles
  bubbles
    .filter((_d, i) => i < 10)
    .filter((d) => rScale(d.count) <= 22)
    .append("text")
    .text((d) => d.country)
    .attr("dy", (d) => rScale(d.count) + 14)
    .attr("text-anchor", "middle")
    .style("font-size", "9px")
    .style("fill", "var(--oaria-text-secondary)")
    .style("font-weight", "600")
    .style("pointer-events", "none")
    .style("text-shadow", isDark ? "0 1px 2px rgba(0,0,0,0.8)" : "0 1px 2px rgba(255,255,255,0.8)")
    .attr("opacity", 0)
    .transition()
    .duration(500)
    .delay((_d, i) => i * 50 + 500)
    .attr("opacity", 0.9);

  // Country labels for large bubbles above
  bubbles
    .filter((d) => rScale(d.count) > 22)
    .append("text")
    .text((d) => d.country)
    .attr("dy", (d) => -(rScale(d.count) + 10))
    .attr("text-anchor", "middle")
    .style("font-size", "11px")
    .style("fill", "var(--foreground)")
    .style("font-weight", "700")
    .style("pointer-events", "none")
    .style("text-shadow", isDark ? "0 1px 3px rgba(0,0,0,0.8)" : "0 1px 3px rgba(255,255,255,0.9)")
    .attr("opacity", 0)
    .transition()
    .duration(500)
    .delay((_d, i) => i * 50 + 500)
    .attr("opacity", 1);
}

export { COUNTRY_COORDS };
export type { CountryData };
