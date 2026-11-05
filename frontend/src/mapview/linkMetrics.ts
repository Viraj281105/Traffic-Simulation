import type { LinkMetrics } from "../netmetrics/types";
import type { MapData, MapLink } from "./types";

export interface LinkMetricOption {
  key: string;
  label: string;
  unit: string;
  /** Fixed top of the colour scale (a 0..1 ratio); otherwise the largest
   *  value on the map. */
  fixedMax?: number;
}

/** Plain labels for every link metric the map can colour by. */
export const LINK_METRIC_LABELS: Record<
  string,
  Omit<LinkMetricOption, "key">
> = {
  length: { label: "Length", unit: "m" },
  lanes: { label: "Lanes", unit: "" },
  speed: { label: "Free-flow speed", unit: "m/s" },
  meanOccupancyRatio: {
    label: "Average fullness",
    unit: "of capacity",
    fixedMax: 1,
  },
  peakOccupancyRatio: {
    label: "Peak fullness",
    unit: "of capacity",
    fixedMax: 1,
  },
  flowVph: { label: "Flow", unit: "veh/h" },
  passed: { label: "Vehicles passed", unit: "vehicles" },
  meanQueue: { label: "Average queue", unit: "vehicles" },
  peakQueue: { label: "Peak queue", unit: "vehicles" },
  meanOccupancy: { label: "Average vehicles on link", unit: "vehicles" },
  peakOccupancy: { label: "Peak vehicles on link", unit: "vehicles" },
  densityVehPerKmLane: { label: "Density", unit: "veh/km/lane" },
  blockedSeconds: { label: "Time blocked by the next link", unit: "s" },
};

const GEOMETRY = ["length", "lanes", "speed"] as const;

function describe(key: string): Omit<LinkMetricOption, "key"> | undefined {
  return key in LINK_METRIC_LABELS ? LINK_METRIC_LABELS[key] : undefined;
}

/** The metrics the viewer can colour by: link geometry (always there, so the
 *  list is never empty), the `value` the server attached, and the run's
 *  per-link metrics when given. */
export function metricOptions(
  map: MapData,
  perLink?: Record<string, LinkMetrics>,
): [LinkMetricOption, ...LinkMetricOption[]] {
  const options: LinkMetricOption[] = [];
  const add = (key: string, describeAs: string = key) => {
    const known = describe(describeAs);
    options.push({
      key,
      label: known ? known.label : describeAs,
      unit: known ? known.unit : "",
      fixedMax: known?.fixedMax,
    });
  };
  if (map.valueLabel && map.links.some((l) => l.value !== undefined)) {
    add("value", map.valueLabel);
  }
  const rows = perLink ? Object.values(perLink) : [];
  const first = rows.length > 0 ? rows[0] : undefined;
  if (first) {
    for (const key of Object.keys(first)) {
      if (describe(key)) add(key);
    }
  }
  for (const key of GEOMETRY) add(key);
  return options as [LinkMetricOption, ...LinkMetricOption[]];
}

/** The value of `key` on a link, or null when the run gave none. */
export function linkValue(
  link: MapLink,
  key: string,
  perLink?: Record<string, LinkMetrics>,
): number | null {
  if (key === "value") return link.value ?? null;
  if (key === "length" || key === "lanes" || key === "speed") return link[key];
  const row = perLink?.[link.id] as Record<string, number> | undefined;
  const v = row?.[key];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}
