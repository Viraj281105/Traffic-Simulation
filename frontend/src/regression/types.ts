/** Contract: GET /api/v3/regression/nightly?limit=30 (newest first).
 *  See src/CONTRACTS.md. Written by the Airflow nightly regression DAG. */

export type CheckStatus = "pass" | "fail" | "error" | "skipped";

export interface RegressionCheck {
  id: string;
  name: string;
  status: CheckStatus;
  /** Metric the check watches, e.g. "mean_delay". */
  metric?: string | null;
  /** The stored golden value and what the night produced. */
  expected?: number | null;
  actual?: number | null;
  /** Allowed absolute difference. */
  tolerance?: number | null;
  unit?: string | null;
  /** Server's explanation for a failure or error. */
  message?: string | null;
}

export interface NightlyRun {
  id: string;
  /** ISO timestamp the night started. */
  startedAt: string;
  gitCommit: string;
  status: "pass" | "fail" | "error";
  durationSeconds: number;
  checks: RegressionCheck[];
  /** Link to the Airflow run, if the server wants it shown. */
  logUrl?: string | null;
}

export interface NightlyRegression {
  generatedAt: string;
  runs: NightlyRun[];
}
