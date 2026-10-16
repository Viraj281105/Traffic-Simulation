import type { RoutedView } from "../../routing";

/** Every view the dashboard can show: a routed view, or the legacy
 *  single-vehicle polling view. */
export type ViewMode = RoutedView | "single";

/** Views that drive the live simulation stream. */
export const SIMULATION_VIEWS: ReadonlySet<ViewMode> = new Set([
  "signal",
  "roundabout",
  "comparative",
  "single",
]);

/** Single-control views: specialist tools with the full live metric panel,
 *  display toggles and scenario settings in the header. */
export const SINGLE_VIEWS: ReadonlySet<ViewMode> = new Set([
  "signal",
  "roundabout",
  "single",
]);

/** The places in the product. Compare is the guided path everyone starts on;
 *  Saved holds kept comparisons; Plan holds planning studies; the Research
 *  lab gathers every specialist tool. */
export type Section = "compare" | "saved" | "plan" | "research" | "admin";

const RESEARCH_VIEWS: ReadonlySet<ViewMode> = new Set([
  "research",
  "volume",
  "validation",
  "junction",
  "threeWay",
  "signal",
  "roundabout",
  "single",
]);

export function sectionOf(view: ViewMode): Section {
  if (view === "history") return "saved";
  if (view === "admin") return "admin";
  if (view === "planner") return "plan";
  if (RESEARCH_VIEWS.has(view)) return "research";
  return "compare";
}

export const RESEARCH_TABS: { view: RoutedView; label: string }[] = [
  { view: "research", label: "Overview" },
  { view: "junction", label: "Your own junction" },
  { view: "threeWay", label: "Three-way study" },
  { view: "validation", label: "Statistical validation" },
  { view: "volume", label: "Traffic-level sweep" },
  { view: "signal", label: "Signal on its own" },
  { view: "roundabout", label: "Roundabout on its own" },
];
