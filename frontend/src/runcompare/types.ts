/** Contract: GET /api/v3/runs/compare?a={runId}&b={runId}. See src/CONTRACTS.md.
 *  The server reads both runs from the run store (Parquet, queried with
 *  DuckDB) and returns the diff; the screen only lays it out. */

export interface RunRef {
  runId: string;
  label: string;
  createdAt: string;
}

/** One line of the run manifest compared across the two runs. */
export interface ManifestField {
  /** e.g. "seed", "config_hash", "code_version", "input_version". */
  field: string;
  label: string;
  a: string | null;
  b: string | null;
  same: boolean;
}

export interface MetricDiff {
  id: string;
  label: string;
  unit: string;
  lowerIsBetter: boolean;
  a: number | null;
  b: number | null;
  /** b minus a. Null when either side is missing. */
  delta: number | null;
  /** Delta as a fraction of a (0.1 = 10% higher). Null when a is 0 or missing. */
  deltaFraction: number | null;
}

export interface RunDiff {
  a: RunRef;
  b: RunRef;
  /** True when seed, config and input versions all match. */
  sameInputs: boolean;
  manifest: ManifestField[];
  metrics: MetricDiff[];
}
