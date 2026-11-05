/** Fixtures for the load-test summary contract (loadtest/types.ts). Not real
 *  measurements. */
import type { LoadTestSummary } from "./types";

export const passingSummary: LoadTestSummary = {
  format: "urbanflow-loadtest-summary",
  version: 1,
  generatedAt: "2026-11-03T22:14:05Z",
  tool: "k6",
  toolVersion: "0.54.0",
  target: "https://staging.urbanflow.example",
  scenario: "network-metrics-smoke",
  durationSeconds: 120,
  vus: { peak: 20, max: 20 },
  requests: {
    total: 4310,
    ratePerSecond: 35.9,
    failed: 4,
    errorRate: 0.0009,
  },
  latencyMs: {
    avg: 182.4,
    min: 41.2,
    med: 150.3,
    p90: 318.7,
    p95: 402.5,
    p99: 611.9,
    max: 934.1,
  },
  checks: { passes: 8612, fails: 8 },
  thresholds: [
    {
      name: "p95 latency",
      metric: "http_req_duration",
      expression: "p(95)<500",
      passed: true,
    },
    {
      name: "error rate",
      metric: "http_req_failed",
      expression: "rate<0.01",
      passed: true,
    },
  ],
  endpoints: [
    {
      name: "POST /api/v2/network-metrics/simulate",
      requests: 2150,
      p95Ms: 455.1,
      errorRate: 0.001,
    },
    {
      name: "GET /api/v2/network-metrics/grid",
      requests: 2160,
      p95Ms: 88.4,
      errorRate: 0,
    },
  ],
};

export const failingSummary: LoadTestSummary = {
  ...passingSummary,
  requests: {
    total: 3980,
    ratePerSecond: 33.2,
    failed: 212,
    errorRate: 0.0533,
  },
  latencyMs: { ...passingSummary.latencyMs, p95: 1260.4, p99: 2210.8 },
  thresholds: [
    {
      name: "p95 latency",
      metric: "http_req_duration",
      expression: "p(95)<500",
      passed: false,
    },
    {
      name: "error rate",
      metric: "http_req_failed",
      expression: "rate<0.01",
      passed: false,
    },
  ],
};
