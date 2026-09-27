/**
 * Chart colours and styles, as CSS custom properties so every chart follows
 * the active theme (styles/tokens.css). Signal is always amber and the
 * roundabout always teal, in every chart, map legend and table.
 */
import type { CSSProperties } from "react";

export const SERIES = {
  signal: "var(--series-signal)",
  roundabout: "var(--series-roundabout)",
  neutral: "var(--series-neutral)",
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  accent: "var(--color-accent)",
} as const;

export const CHART_GRID = "var(--chart-grid)";
export const CHART_AXIS = "var(--chart-axis)";

/** Recharts <Tooltip contentStyle>. */
export const TOOLTIP_STYLE: CSSProperties = {
  backgroundColor: "var(--color-surface-2)",
  borderColor: "var(--color-border-strong)",
  borderRadius: "var(--radius-sm)",
  color: "var(--color-text)",
  fontSize: 12,
};
