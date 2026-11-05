import { num } from "../netcommon/format";
import type { MetricKey, MetricRow } from "./types";

export const METRIC_LABEL: Record<MetricKey, { label: string; unit: string }> =
  {
    delaySeconds: { label: "Delay", unit: "s" },
    stops: { label: "Stops", unit: "" },
    fuelLitres: { label: "Fuel", unit: "L" },
    co2Kg: { label: "CO2", unit: "kg" },
  };
export const KEYS = Object.keys(METRIC_LABEL) as MetricKey[];
export const TONES = ["a", "b", "c", "d"] as const;

/** "-4 s (-4.5 to -3.5)": the change per vehicle with its paired interval. */
export function changeText(row: MetricRow, unit: string): string {
  const u = unit ? ` ${unit}` : "";
  const head = `${num(row.change, 3)}${u}`;
  const p = row.paired;
  return p ? `${head} (${num(p.ci_lower, 3)} to ${num(p.ci_upper, 3)})` : head;
}
