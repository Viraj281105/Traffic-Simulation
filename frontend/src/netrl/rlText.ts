import type { PairedComparisonRow, RlEvalDocument } from "./types";

export const METRIC_TEXT: Record<string, { label: string; unit: string }> = {
  mean_wait_s: { label: "Mean wait per entered vehicle", unit: "s" },
  mean_queue: { label: "Mean queue", unit: "vehicles" },
  throughput: { label: "Throughput", unit: "vehicles" },
  stopped_veh_s: { label: "Stopped vehicle-seconds", unit: "s" },
  total_wait_s: { label: "Total waiting time", unit: "s" },
  mean_delay_s: { label: "Mean delay", unit: "s" },
  vehicles: { label: "Vehicles", unit: "vehicles" },
  switches: { label: "Phase switches", unit: "count" },
  episode_return: { label: "Episode return", unit: "reward" },
  blocked: { label: "Vehicles blocked at entry", unit: "vehicles" },
};

export function metricLabel(id: string): string {
  const known = METRIC_TEXT[id] as { label: string } | undefined;
  return known?.label ?? id;
}

export function metricUnit(id: string): string {
  const known = METRIC_TEXT[id] as { unit: string } | undefined;
  return known?.unit ?? "";
}

/** The caveat that goes with every wait figure. */
export const WAIT_CAVEAT =
  "Mean wait here is stopped vehicle-seconds per entered vehicle: the time vehicles spent stopped in the network, divided by the vehicles that entered. It is not the delay of a finished trip, so do not compare it with the delay figures of other screens.";

/** Which way a comparison went, for colouring: favourable, unfavourable or
 *  no reliable difference. Read from the server's direction, never recomputed. */
export function outcome(row: PairedComparisonRow): "better" | "worse" | "none" {
  const c = row.comparison;
  if (c.direction === "none") return "none";
  const rlLower = c.direction === "a_lower";
  return rlLower === row.lower_is_better ? "better" : "worse";
}

/** One sentence on the interval and p-value of a row, from the server's numbers. */
export function statsLine(row: PairedComparisonRow): string {
  const c = row.comparison;
  const unit = metricUnit(row.metric);
  const level = `${String(Math.round(c.confidence * 100))}%`;
  const p = c.p_value < 0.001 ? "p < 0.001" : `p = ${c.p_value.toPrecision(2)}`;
  const suffix = unit ? ` ${unit}` : "";
  return `${row.rl} minus ${row.baseline}: ${c.difference.toFixed(2)}${suffix} on average (${level} interval ${c.ci_lower.toFixed(2)} to ${c.ci_upper.toFixed(2)}${suffix}; ${p}; ${c.method}, ${String(c.n_pairs)} paired seeds). ${row.lower_is_better ? "Lower is better." : "Higher is better."}`;
}

/** The per-seed values of a policy's metric, or null if it has none. */
export function seedValues(
  doc: RlEvalDocument,
  policy: string,
  metric: string,
): number[] | null {
  const entry = doc.policies[policy] as
    Record<string, number[] | number> | undefined;
  const values = entry?.[metric];
  return Array.isArray(values) ? values : null;
}

/** True when `value` looks like a network RL evaluation document. */
export function isEvalDocument(value: unknown): value is RlEvalDocument {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    v.format === "urbanflow-rl-eval" &&
    Array.isArray(v.seeds) &&
    typeof v.policies === "object" &&
    v.policies !== null &&
    Array.isArray(v.paired_comparisons)
  );
}
