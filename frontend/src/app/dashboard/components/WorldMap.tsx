"use client";
import { useRef, useEffect, useState } from "react";
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

import { BRAND, getThemeColors } from "../constants";

const WORLD_ATLAS_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

// Brand-aligned color palette for map bubbles
const SOLID_COLORS_LIGHT = [
  BRAND.teal, "#0F766E", BRAND.coral, "#0891B2", "#7C3AED",
  "#059669", "#EA580C", "#2563EB", "#DB2777", "#CA8A04",
];

const SOLID_COLORS_DARK = [
  "#2DD4BF", "#5EEAD4", "#FDA4AF", "#22D3EE", "#A78BFA",
  "#34D399", "#FB923C", "#60A5FA", "#F472B6", "#FACC15",
];

export default function WorldMap({ data }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [zoomLevel, setZoomLevel] = useState(1);

  useEffect(() => {
    if (!ref.current || !data.length) return;
    const el = ref.current;
    d3.select(el).selectAll("*").remove();

    const width = el.clientWidth;
    const height = el.clientHeight;
    if (width <= 0 || height <= 0) return;

    const totalCount = data.reduce((sum, d) => sum + d.count, 0);

    const svg = d3
      .select(el)
      .append("svg")
      .attr("width", width)
      .attr("height", height)
      .style("border-radius", "12px")
      .style("cursor", "grab");

    const defs = svg.append("defs");

    // Main group for zoom/pan
    const mainG = svg.append("g");

    const projection = d3
      .geoNaturalEarth1()
      .scale(Math.min(width / 5.0, height / 2.4))
      .translate([width / 2, height / 2 + 10]);

    const pathGen = d3.geoPath().projection(projection);

    // Detect dark mode
    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches
      || document.documentElement.classList.contains("dark");
    const theme = getThemeColors(isDark);
    const SOLID_COLORS = isDark ? SOLID_COLORS_DARK : SOLID_COLORS_LIGHT;

    // Zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 8])
      .on("zoom", (event) => {
        mainG.attr("transform", event.transform);
        setZoomLevel(event.transform.k);

        // Update bubble text visibility based on zoom
        mainG.selectAll(".bubble-pct-text")
          .style("display", (d) => {
            const item = d as CountryData;
            const baseR = rScale(item.count);
            const scaledR = baseR * event.transform.k;
            return scaledR > 15 ? "block" : "none";
          })
          .style("font-size", (d) => {
            const item = d as CountryData;
            const baseR = rScale(item.count);
            const scaledR = baseR * event.transform.k;
            return scaledR > 30 ? "11px" : "8px";
          });

        // Update country labels visibility
        mainG.selectAll(".country-label")
          .style("display", (_d, i) => {
            if (event.transform.k > 1.5) return "block";
            return i < 10 ? "block" : "none";
          });
      })
      .on("start", () => svg.style("cursor", "grabbing"))
      .on("end", () => svg.style("cursor", "grab"));

    svg.call(zoom);

    // Double click to reset
    svg.on("dblclick.zoom", () => {
      svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity);
    });

    const maxCount = d3.max(data, (d) => d.count) || 1;
    // Reduced max range from 38 to 26 for better clarity in crowded areas
    const rScale = d3.scaleSqrt().domain([1, maxCount]).range([4, 26]);

    // Tooltip
    const tip = d3
      .select(el)
      .append("div")
      .style("position", "absolute")
      .style("visibility", "hidden")
      .style("background", theme.tooltipBg)
      .style("border", `1px solid ${theme.tooltipBorder}`)
      .style("border-radius", "12px")
      .style("padding", "14px 18px")
      .style("font-size", "13px")
      .style("line-height", "1.6")
      .style("box-shadow", `0 8px 32px ${theme.tooltipShadow}`)
      .style("pointer-events", "none")
      .style("z-index", "100")
      .style("color", theme.textPrimary)
      .style("min-width", "180px")
      .style("backdrop-filter", "blur(12px)");

    // Fetch world map
    fetch(WORLD_ATLAS_URL)
      .then((res) => res.json())
      .then((world) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const countries = topojson.feature(world as any, (world as any).objects.countries) as unknown as d3.GeoPermissibleObjects;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const borders = topojson.mesh(world as any, (world as any).objects.countries, (a: any, b: any) => a !== b);

        // Ocean gradient - high contrast for both modes
        const oceanGrad = defs.append("linearGradient")
          .attr("id", "ocean-gradient")
          .attr("x1", "0%").attr("y1", "0%")
          .attr("x2", "0%").attr("y2", "100%");
        oceanGrad.append("stop").attr("offset", "0%")
          .attr("stop-color", isDark ? "#0c1929" : "#e0f2fe");
        oceanGrad.append("stop").attr("offset", "100%")
          .attr("stop-color", isDark ? "#0a1220" : "#bae6fd");

        // Ocean background
        mainG.append("rect")
          .attr("width", width * 3)
          .attr("height", height * 3)
          .attr("x", -width)
          .attr("y", -height)
          .attr("fill", "url(#ocean-gradient)");

        // Graticule
        const graticule = d3.geoGraticule().step([20, 20]);
        mainG.append("path")
          .datum(graticule())
          .attr("d", pathGen)
          .attr("fill", "none")
          .attr("stroke", isDark ? "rgba(255,255,255,0.06)" : "rgba(14,116,144,0.12)")
          .attr("stroke-width", 0.5);

        // Countries - high visibility with brand-aligned colors
        mainG.append("g")
          .selectAll("path")
          .data((countries as { type: string; features: d3.GeoPermissibleObjects[] }).features)
          .join("path")
          .attr("d", pathGen as never)
          .attr("fill", isDark ? "#1e3a5f" : "#f0fdfa")
          .attr("stroke", isDark ? "#3d6a8f" : BRAND.teal)
          .attr("stroke-width", isDark ? 0.5 : 0.6)
          .attr("stroke-opacity", isDark ? 1 : 0.4);

        // Borders - using brand teal for light mode
        mainG.append("path")
          .datum(borders as d3.GeoPermissibleObjects)
          .attr("d", pathGen)
          .attr("fill", "none")
          .attr("stroke", isDark ? "#4d7a9f" : BRAND.teal)
          .attr("stroke-width", isDark ? 0.4 : 0.5)
          .attr("stroke-opacity", isDark ? 1 : 0.3);

        // Draw bubbles
        drawBubbles(mainG, defs, data, projection, rScale, tip, el, totalCount, isDark);
      })
      .catch(() => {
        // Fallback - use brand-aligned ocean color
        mainG.append("rect")
          .attr("width", width)
          .attr("height", height)
          .attr("fill", isDark ? "#0c1929" : "#e0f2fe");

        drawBubbles(mainG, defs, data, projection, rScale, tip, el, totalCount, isDark);
      });

    // Zoom controls
    const controlsG = svg.append("g")
      .attr("transform", `translate(${width - 45}, 15)`);

    const btnStyle = {
      width: 28,
      height: 28,
      rx: 6,
      fill: isDark ? "rgba(255,255,255,0.15)" : "rgba(13,148,136,0.7)",
      stroke: isDark ? "rgba(255,255,255,0.25)" : "rgba(13,148,136,0.9)",
    };

    // Zoom in button
    const zoomInBtn = controlsG.append("g")
      .style("cursor", "pointer")
      .on("click", () => svg.transition().duration(300).call(zoom.scaleBy, 1.5));

    zoomInBtn.append("rect")
      .attr("width", btnStyle.width).attr("height", btnStyle.height)
      .attr("rx", btnStyle.rx).attr("fill", btnStyle.fill).attr("stroke", btnStyle.stroke);
    zoomInBtn.append("text")
      .attr("x", 14).attr("y", 19)
      .attr("text-anchor", "middle")
      .text("+")
      .style("font-size", "16px")
      .style("font-weight", "600")
      .style("fill", "#FFFFFF")
      .style("text-shadow", "0 1px 2px rgba(0,0,0,0.5)");

    // Zoom out button
    const zoomOutBtn = controlsG.append("g")
      .attr("transform", "translate(0, 32)")
      .style("cursor", "pointer")
      .on("click", () => svg.transition().duration(300).call(zoom.scaleBy, 0.67));

    zoomOutBtn.append("rect")
      .attr("width", btnStyle.width).attr("height", btnStyle.height)
      .attr("rx", btnStyle.rx).attr("fill", btnStyle.fill).attr("stroke", btnStyle.stroke);
    zoomOutBtn.append("text")
      .attr("x", 14).attr("y", 18)
      .attr("text-anchor", "middle")
      .text("−")
      .style("font-size", "18px")
      .style("font-weight", "600")
      .style("fill", "#FFFFFF")
      .style("text-shadow", "0 1px 2px rgba(0,0,0,0.5)");

    // Reset button
    const resetBtn = controlsG.append("g")
      .attr("transform", "translate(0, 64)")
      .style("cursor", "pointer")
      .on("click", () => svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity));

    resetBtn.append("rect")
      .attr("width", btnStyle.width).attr("height", btnStyle.height)
      .attr("rx", btnStyle.rx).attr("fill", btnStyle.fill).attr("stroke", btnStyle.stroke);
    resetBtn.append("text")
      .attr("x", 14).attr("y", 18)
      .attr("text-anchor", "middle")
      .text("⟲")
      .style("font-size", "14px")
      .style("fill", "#FFFFFF")
      .style("text-shadow", "0 1px 2px rgba(0,0,0,0.5)");

    svg.attr("opacity", 0).transition().duration(600).attr("opacity", 1);
  }, [data]);

  if (!data.length) {
    return (
      <div className="w-full h-full flex items-center justify-center text-sm text-[var(--oaria-text-secondary)]">
        지역별 데이터가 부족합니다
      </div>
    );
  }

  return (
    <div className="w-full h-full relative">
      <div ref={ref} className="w-full h-full" />
      {zoomLevel > 1 && (
        <div className="absolute bottom-2 left-2 text-xs text-[var(--oaria-text-secondary)] bg-[var(--background)]/80 px-2 py-1 rounded">
          {zoomLevel.toFixed(1)}x • 더블클릭으로 리셋
        </div>
      )}
    </div>
  );
}

function drawBubbles(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  defs: d3.Selection<SVGDefsElement, unknown, null, undefined>,
  data: CountryData[],
  projection: d3.GeoProjection,
  rScale: d3.ScalePower<number, number>,
  tip: d3.Selection<HTMLDivElement, unknown, null, undefined>,
  el: HTMLDivElement,
  totalCount: number,
  isDark: boolean
) {
  // Get the correct color palette based on theme
  const BUBBLE_COLORS = isDark ? SOLID_COLORS_DARK : SOLID_COLORS_LIGHT;

  // Create gradients for each bubble - more vibrant for light mode
  data.forEach((_, i) => {
    const color = BUBBLE_COLORS[i % BUBBLE_COLORS.length];
    const grad = defs.append("radialGradient")
      .attr("id", `bubble-grad-${i}`)
      .attr("cx", "30%").attr("cy", "30%").attr("r", "70%");
    grad.append("stop").attr("offset", "0%")
      .attr("stop-color", d3.color(color)?.brighter(isDark ? 0.5 : 0.3)?.toString() || color)
      .attr("stop-opacity", isDark ? 0.9 : 0.95);
    grad.append("stop").attr("offset", "100%")
      .attr("stop-color", d3.color(color)?.darker(isDark ? 0 : 0.1)?.toString() || color)
      .attr("stop-opacity", isDark ? 0.75 : 0.9);
  });

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

  // Refined shadow/glow - smaller and more subtle
  bubbles
    .append("circle")
    .attr("r", (d) => rScale(d.count) + 2)
    .attr("fill", (_d, i) => BUBBLE_COLORS[i % BUBBLE_COLORS.length])
    .attr("opacity", isDark ? 0.15 : 0.25)
    .attr("filter", "blur(3px)")
    .style("pointer-events", "none");

  // Main bubble with gradient - sharper stroke
  bubbles
    .append("circle")
    .attr("class", "main-bubble")
    .attr("r", 0)
    .attr("fill", (_d, i) => `url(#bubble-grad-${i})`)
    .attr("stroke", isDark ? "rgba(255,255,255,0.5)" : "rgba(255,255,255,1.0)")
    .attr("stroke-width", isDark ? 1.2 : 1.5)
    .style("filter", isDark ? "none" : "drop-shadow(0 1px 2px rgba(0,0,0,0.2))")
    .on("mouseover", function (_event, d) {
      const i = data.indexOf(d);
      d3.select(this)
        .transition().duration(200)
        .attr("r", rScale(d.count) * 1.15)
        .attr("stroke-width", 2);

      const rank = i + 1;
      const pct = ((d.count / totalCount) * 100).toFixed(1);
      const flag = COUNTRY_FLAGS[d.country] || "🌍";

      tip.style("visibility", "visible")
        .html(
          `<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;padding-bottom:10px;border-bottom:1px solid ${isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)"}">
            <span style="font-size:28px">${flag}</span>
            <div>
              <div style="font-size:16px;font-weight:700">${d.country}</div>
              <div style="font-size:11px;opacity:0.6">Rank #${rank}</div>
            </div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div>
              <div style="font-size:10px;opacity:0.5;margin-bottom:2px">논문 수</div>
              <div style="font-size:20px;font-weight:800;color:${BUBBLE_COLORS[i % BUBBLE_COLORS.length]}">${d.count.toLocaleString()}</div>
            </div>
            <div>
              <div style="font-size:10px;opacity:0.5;margin-bottom:2px">전체 비율</div>
              <div style="font-size:20px;font-weight:800">${pct}%</div>
            </div>
          </div>`
        );
    })
    .on("mousemove", function (event) {
      const [mx, my] = d3.pointer(event, el);
      tip.style("left", `${mx + 20}px`).style("top", `${my - 10}px`);
    })
    .on("mouseout", function (_event, d) {
      d3.select(this)
        .transition().duration(200)
        .attr("r", rScale(d.count))
        .attr("stroke-width", 1.2);
      tip.style("visibility", "hidden");
    })
    .transition()
    .duration(700)
    .delay((_d, i) => i * 40)
    .ease(d3.easeBackOut.overshoot(1.2))
    .attr("r", (d) => rScale(d.count));

  // Percentage text inside bubbles (visible based on zoom)
  bubbles
    .append("text")
    .attr("class", "bubble-pct-text")
    .datum((d) => d)
    .text((d) => `${((d.count / totalCount) * 100).toFixed(0)}%`)
    .attr("text-anchor", "middle")
    .attr("dy", "0.35em")
    .style("font-size", (d) => rScale(d.count) > 25 ? "11px" : "8px")
    .style("font-weight", "700")
    .style("fill", "white")
    .style("pointer-events", "none")
    .style("text-shadow", "0 1px 2px rgba(0,0,0,0.5)")
    .style("display", (d) => rScale(d.count) > 18 ? "block" : "none")
    .attr("opacity", 0)
    .transition()
    .duration(400)
    .delay((_d, i) => i * 40 + 500)
    .attr("opacity", 1);

  // Country labels - white text with shadow for visibility
  bubbles
    .filter((_d, i) => i < 15)
    .append("text")
    .attr("class", "country-label")
    .text((d) => d.country)
    .attr("dy", (d) => rScale(d.count) + 12)
    .attr("text-anchor", "middle")
    .style("font-size", "9px")
    .style("font-weight", "700")
    .style("fill", "#FFFFFF")
    .style("pointer-events", "none")
    .style("text-shadow", "0 0 6px rgba(0,0,0,0.8), 0 1px 3px rgba(0,0,0,0.9), 0 0 12px rgba(0,0,0,0.5)")
    .style("display", (_d, i) => i < 10 ? "block" : "none")
    .attr("opacity", 0)
    .transition()
    .duration(400)
    .delay((_d, i) => i * 40 + 600)
    .attr("opacity", 1);
}

export { COUNTRY_COORDS };
export type { CountryData };
