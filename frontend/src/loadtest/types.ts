/**
 * Contract: the load-test summary (`urbanflow-loadtest-summary` v1).
 *
 * This is a contract this frontend DEFINES; no backend produces it yet. A
 * k6 script writes it from `handleSummary(data)` (reducing k6's end-of-test
 * summary to the fields below) to `loadtest-summary.json`, and either
 *
 *   1. the API serves the newest one at `GET /api/v3/loadtests/latest`
 *      (JSON body = this document; 404 = no result yet; same bearer token and
 *      error envelope as the other /api/v3 endpoints), or
 *   2. the person opens the file in the Load tests tab.
 *
 * See src/CONTRACTS_P5.md for the k6 field mapping. A value k6 could not
 * report is `null`, never 0. Times are milliseconds; `errorRate` is a
 * fraction 0..1 (`http_req_failed` rate).
 */

export interface LatencyMs {
  avg: number | null;
  min: number | null;
  med: number | null;
  p90: number | null;
  p95: number | null;
  p99: number | null;
  max: number | null;
}

export interface LoadThreshold {
  /** What the test script called it. */
  name: string;
  /** The k6 metric the rule is on, e.g. "http_req_duration". */
  metric: string;
  /** The rule, e.g. "p(95)<500". */
  expression: string;
  /** True when the run met the rule. */
  passed: boolean;
}

export interface EndpointResult {
  /** A short name for the endpoint, e.g. "GET /api/v2/network-metrics/simulate". */
  name: string;
  requests: number;
  p95Ms: number | null;
  errorRate: number | null;
}

export interface LoadTestSummary {
  format: "urbanflow-loadtest-summary";
  version: 1;
  /** ISO 8601 time the test finished. */
  generatedAt: string;
  tool: string;
  toolVersion?: string;
  /** The base URL that was tested. */
  target: string;
  /** The test script or scenario name. */
  scenario: string;
  durationSeconds: number;
  /** Virtual users: the most that ran at once, and the configured limit. */
  vus: { peak: number; max: number };
  requests: {
    total: number;
    ratePerSecond: number | null;
    failed: number;
    errorRate: number | null;
  };
  latencyMs: LatencyMs;
  checks: { passes: number; fails: number };
  thresholds: LoadThreshold[];
  endpoints?: EndpointResult[];
}
