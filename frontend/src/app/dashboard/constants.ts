// OARIA Brand Colors from docs/brand/brand-assets.md
export const BRAND = {
  // Primary Colors
  teal: "#0D9488",
  lightTeal: "#14B8A6",
  coral: "#F97066",

  // Neutral Colors
  deepNavy: "#1E293B",
  darkBg: "#0F172A",
  lightRing: "#CBD5E1",
  darkRing: "#334155",
  tagline: "#94A3B8",
  border: "#E2E8F0",
  background: "#F8FAFC",

  // Text Colors
  textPrimary: "#1E293B",
  textSecondary: "#64748B",
  textMuted: "#94A3B8",
};

// Brand-aligned chart color palette
// Primary: Teal-based, Secondary: Coral accent, Extended: Complementary colors
export const PASTEL = [
  "#0D9488", // OARIA Teal (primary)
  "#14B8A6", // Light Teal
  "#F97066", // Living Coral (accent)
  "#0F766E", // Dark Teal
  "#FB923C", // Orange accent
  "#115E59", // Deep Teal
  "#0EA5E9", // Sky Blue
  "#6366F1", // Indigo
  "#8B5CF6", // Violet
  "#EC4899", // Pink
  "#22C55E", // Green
  "#EAB308", // Yellow
];

// Higher contrast colors for light mode backgrounds
export const PASTEL_LIGHT = [
  "#0D9488", // OARIA Teal
  "#0F766E", // Dark Teal
  "#F97066", // Coral
  "#0891B2", // Cyan Dark
  "#EA580C", // Orange Dark
  "#115E59", // Deep Teal
  "#0284C7", // Sky Dark
  "#4F46E5", // Indigo Dark
  "#7C3AED", // Violet Dark
  "#DB2777", // Pink Dark
  "#16A34A", // Green Dark
  "#CA8A04", // Yellow Dark
];

// Softer colors for dark mode with good visibility
export const PASTEL_DARK = [
  "#2DD4BF", // Teal Light
  "#5EEAD4", // Teal Lighter
  "#FDA4AF", // Coral Light
  "#22D3EE", // Cyan Light
  "#FB923C", // Orange
  "#99F6E4", // Teal Lightest
  "#38BDF8", // Sky Light
  "#818CF8", // Indigo Light
  "#A78BFA", // Violet Light
  "#F472B6", // Pink Light
  "#4ADE80", // Green Light
  "#FACC15", // Yellow Light
];

// Soft background colors (for treemaps, etc.)
export const PASTEL_SOFT = [
  "rgba(13, 148, 136, 0.15)",  // Teal soft
  "rgba(20, 184, 166, 0.15)",  // Light Teal soft
  "rgba(249, 112, 102, 0.15)", // Coral soft
  "rgba(15, 118, 110, 0.15)",  // Dark Teal soft
  "rgba(251, 146, 60, 0.15)",  // Orange soft
  "rgba(17, 94, 89, 0.15)",    // Deep Teal soft
  "rgba(14, 165, 233, 0.15)",  // Sky soft
  "rgba(99, 102, 241, 0.15)",  // Indigo soft
  "rgba(139, 92, 246, 0.15)",  // Violet soft
  "rgba(236, 72, 153, 0.15)",  // Pink soft
];

// Helper to get theme-aware colors
export function getThemeColors(isDark: boolean) {
  return {
    // Primary brand colors
    primary: isDark ? "#2DD4BF" : "#0D9488",
    primaryHover: isDark ? "#5EEAD4" : "#14B8A6",
    accent: isDark ? "#FDA4AF" : "#F97066",

    // Background & Surface
    background: isDark ? "#0F172A" : "#F8FAFC",
    surface: isDark ? "#1E293B" : "#FFFFFF",
    surfaceHover: isDark ? "#334155" : "#F1F5F9",

    // Text with HIGH CONTRAST
    textPrimary: isDark ? "#F8FAFC" : "#0F172A",
    textSecondary: isDark ? "#CBD5E1" : "#475569",
    textMuted: isDark ? "#94A3B8" : "#64748B",
    textOnColor: isDark ? "#0F172A" : "#FFFFFF", // Text on colored backgrounds

    // Borders
    border: isDark ? "#334155" : "#E2E8F0",
    borderHover: isDark ? "#475569" : "#CBD5E1",

    // Chart-specific
    gridLine: isDark ? "rgba(148, 163, 184, 0.15)" : "rgba(15, 23, 42, 0.08)",
    axisText: isDark ? "#94A3B8" : "#64748B",

    // Tooltip
    tooltipBg: isDark ? "rgba(15, 23, 42, 0.95)" : "rgba(255, 255, 255, 0.98)",
    tooltipBorder: isDark ? "rgba(51, 65, 85, 0.8)" : "rgba(226, 232, 240, 0.8)",
    tooltipShadow: isDark ? "rgba(0, 0, 0, 0.4)" : "rgba(0, 0, 0, 0.1)",
  };
}

// Get appropriate palette based on theme
export function getChartPalette(isDark: boolean): string[] {
  return isDark ? PASTEL_DARK : PASTEL_LIGHT;
}
