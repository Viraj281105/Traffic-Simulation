/**
 * Plain-language wording for the Robustness Lab results page. The API reports
 * evidence, not a verdict: nothing here ranks alternatives or names a winner,
 * a missing number reads "not available" (never 0), a tie is a result, and
 * what a criterion has not assessed is said so.
 */
import type {
  Assumption,
  EligibilityClass,
  Tolerance,
} from "../../services/v3/experiments";

export const NOT_AVAILABLE = "not available";

const MINUS = "−"; // a real minus sign reads better than a hyphen

function signed(value: number, digits: number): string {
  const text = Math.abs(value).toFixed(digits);
  return value < 0 && Number(text) !== 0 ? MINUS + text : text;
}

/** A server number in seconds; null/undefined/non-finite is "not available". */
export function seconds(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return NOT_AVAILABLE;
  }
  return `${signed(value, digits)} s`;
}

export function secondsInterval(ci: readonly [number, number]): string {
  const [low, high] = ci;
  if (!Number.isFinite(low) || !Number.isFinite(high)) return NOT_AVAILABLE;
  return `${signed(low, 2)} to ${signed(high, 2)} s`;
}

export function percent(p: number | null | undefined): string {
  if (p === null || p === undefined || !Number.isFinite(p)) {
    return NOT_AVAILABLE;
  }
  return `${(p * 100).toFixed(0)} %`;
}

export function percentInterval(ci: readonly [number, number]): string {
  return `${percent(ci[0])} to ${percent(ci[1])}`;
}

/** What the primary indicator is, with its unit and which direction is good. */
export function indicatorText(key: string): string {
  switch (key) {
    case "averageDelay":
      return "mean delay";
    case "medianDelay":
      return "median delay";
    case "p95Delay":
      return "95th-percentile delay";
    default:
      return key;
  }
}

export function toleranceText(t: Tolerance): string {
  if (t.kind === "absolute" && t.value !== undefined) {
    return `two values count as a tie when they differ by at most ${t.value.toString()} s`;
  }
  const abs = t.absSeconds ?? 1;
  const rel = Math.round((t.relative ?? 0.05) * 100);
  return `two values count as a tie when they differ by at most ${abs.toString()} s or ${rel.toString()} % of the larger one`;
}

export const CLASS_TEXT: Record<
  EligibilityClass,
  { label: string; explanation: string }
> = {
  exploratory: {
    label: "Exploratory only",
    explanation:
      "Fewer than 30 valid conditions. No statement about robustness can be made from this experiment.",
  },
  indicative: {
    label: "Indicative",
    explanation:
      "30 or more valid conditions, but at least one criterion below is not met or not yet assessed. Read the proportions as a guide, not as a robustness statement.",
  },
  eligible: {
    label: "Eligible for robustness statements",
    explanation:
      "Adequately sampled for the declared assumptions. This does not mean the preference is large, that the model is correct, or that any real junction behaves this way.",
  },
};

const CRITERION_LABEL: Record<string, string> = {
  precision: "Precision",
  stability: "Stability (split-half)",
  replications: "Replications per condition",
  exclusions: "Excluded conditions",
  predeclaration: "Specification fixed before the run",
};

export function criterionLabel(id: string): string {
  return CRITERION_LABEL[id] ?? id;
}

export function criterionStatus(
  passed: boolean | null,
): "Met" | "Not met" | "Not assessed" {
  if (passed === true) return "Met";
  if (passed === false) return "Not met";
  return "Not assessed";
}

const REASON_LABEL: Record<string, string> = {
  validation_failed: "scenario invalid after the change",
  run_failed: "a simulation failed",
  timeout: "timed out",
  vehicle_limit: "vehicle limit reached",
  deadlock: "deadlock",
  no_completed_vehicles:
    "no vehicle finished its trip (the delay is undefined; the scenario may be too short)",
  non_finite: "indicator missing or not a number",
  missing_run: "a run is missing",
};

export function exclusionText(byReason: Record<string, number>): string {
  const parts = Object.entries(byReason).map(
    ([reason, count]) =>
      `${REASON_LABEL[reason] ?? reason}: ${count.toString()}`,
  );
  return parts.length ? parts.join("; ") : "none";
}

const FACTOR_LABEL: Record<string, string> = {
  demand_scale: "Demand (multiplier)",
  turning_shift: "Turning share (straight ↔ turning)",
  mix_shift: "Vehicle mix (light ↔ heavy)",
  headway_scale: "Driver headway (multiplier, a proxy)",
  desired_speed_scale: "Desired speed (multiplier)",
  max_acceleration_scale: "Maximum acceleration (multiplier)",
};

export function factorLabel(kind: string): string {
  return FACTOR_LABEL[kind] ?? kind;
}

export function distributionText(a: Assumption): string {
  const d = a.distribution;
  const params = Object.entries(d)
    .filter(([key]) => key !== "kind")
    .map(([key, value]) => `${key} ${String(value)}`);
  const name = d.kind.replace("_", " ");
  return params.length ? `${name} (${params.join(", ")})` : name;
}

export const BASIS_TEXT: Record<Assumption["basis"], string> = {
  assumed: "Assumed by the analyst",
  observed: "Observed data",
  user: "Supplied by the user",
};

export function boundsText(bounds: readonly [number, number]): string {
  return `${bounds[0].toString()} to ${bounds[1].toString()}`;
}
