/**
 * Plain-language wording for the planner. The planning API reports evidence,
 * not a verdict: nothing here ranks alternatives or picks a winner, a missing
 * number reads "not available" (never 0), and a tie or an inconclusive
 * comparison says so.
 */
import type {
  BaselineComparison,
  PlanningApiError,
  Verdict,
} from "../../services/v2/planning";

export const NOT_AVAILABLE = "not available";

/** A server number for display; null/undefined/non-finite is "not available". */
export function formatNumber(
  value: number | null | undefined,
  digits = 2,
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return NOT_AVAILABLE;
  }
  return value.toFixed(digits);
}

export function formatInterval(
  low: number | null | undefined,
  high: number | null | undefined,
): string {
  if (
    low === null ||
    low === undefined ||
    high === null ||
    high === undefined ||
    !Number.isFinite(low) ||
    !Number.isFinite(high)
  ) {
    return NOT_AVAILABLE;
  }
  return `${formatNumber(low)} to ${formatNumber(high)}`;
}

export const VERDICT_TEXT: Record<Verdict, string> = {
  better: "Better than the baseline",
  worse: "Worse than the baseline",
  tie: "Tie — within the tie tolerance",
  inconclusive: "Inconclusive — the seeds could not separate them",
  unavailable: "Not available",
};

/** The server's verdict in words; an unknown value is shown as sent. */
export function verdictText(row: Pick<BaselineComparison, "verdict">): string {
  const known: Partial<Record<string, string>> = VERDICT_TEXT;
  return known[row.verdict] ?? row.verdict;
}

export const METRIC_TEXT: Record<string, string> = {
  averageDelay: "Mean delay (s/vehicle)",
  throughput: "Vehicles served",
  averageQueueLength: "Mean queue (vehicles)",
  maxQueueLength: "Longest queue (vehicles)",
  averageWaitTime: "Mean wait (s)",
  averageStopsPerVehicle: "Stops per vehicle",
  collisionCount: "Simulated collisions",
  travelTimeReliability: "Travel-time reliability",
};

export function metricText(key: string): string {
  return METRIC_TEXT[key] ?? key;
}

/** What the validity block's ``fieldCalibration`` means for a reader. The
 *  status is an agreement rating against observations a user supplied; no
 *  model parameter is ever fitted, so nothing here says "calibrated". */
export function fieldCalibrationText(status: string): string {
  if (status === "not_provided") {
    return "Not field-calibrated: no observed traffic data were attached to this study.";
  }
  return (
    `Observed-data comparison attached (agreement rating: ${status}). ` +
    "This compares the simulation with counts supplied by a user; the model " +
    "was not tuned to them, so the study is still not field-calibrated."
  );
}

/** Why a planning call failed, in words a planner can act on. */
export function failureText(error: PlanningApiError): string {
  if (error.status === 0) {
    return "The UrbanFlow server could not be reached. Check your connection and that the server is running, then try again.";
  }
  if (error.status === 429) {
    return `The server is already running its maximum of two planning studies. Wait for one to finish, then start this one again. (${error.message})`;
  }
  if (error.status === 401 || error.status === 403) {
    return "You need to be signed in to plan studies. Sign in and try again.";
  }
  if (error.status === 404) {
    return "That study was not found. It may belong to another account, or the id may be wrong.";
  }
  if (error.status === 413) {
    return "The study is too large to send. Reduce the scenario and try again.";
  }
  if (error.status === 422 || error.status === 400) {
    return `The server could not accept this study: ${error.reasons.join("; ")}`;
  }
  return `The server reported an error (${error.status.toString()}): ${error.message}`;
}

/** Strip the API's location prefix ("alternatives.0.strategy: ...") into
 *  something readable while keeping the field name. */
export function plainValidationError(message: string): string {
  return message
    .replace(/^subject\.scenario\.?/, "Scenario ")
    .replace(/^alternatives\.(\d+)/, (_, i: string) => {
      return `Alternative ${(Number(i) + 1).toString()}`;
    })
    .replace(/^repetitions\./, "Repetitions: ")
    .replace(/^demand\./, "Demand: ");
}
