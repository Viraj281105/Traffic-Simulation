// Shared helpers for the k6 scripts (WRITTEN, not run: k6 is not installed here).
// Thresholds come from deploy/observability/slo.json so the dashboards, alerts and
// load tests agree. open() resolves relative to this file at init time.
import http from "k6/http";
import { check } from "k6";

const slo = JSON.parse(open("../observability/slo.json"));

function find(id) {
  const s = slo.slos.find((x) => x.id === id);
  if (!s) throw new Error("SLO not found: " + id);
  return s;
}

export const BASE_URL = (__ENV.BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
// The v2 routes need a verified token (or run the backend with auth disabled in a test stack).
const TOKEN = __ENV.AUTH_TOKEN || "";

export const apiP95Ms = find("api_latency_p95").objective_seconds * 1000;
export const simulateP95Ms = find("network_simulate_p95").objective_seconds * 1000;
export const maxErrorRate = 1 - find("api_availability").objective;

export function headers() {
  const h = { "Content-Type": "application/json" };
  if (TOKEN) h.Authorization = "Bearer " + TOKEN;
  return h;
}

export function health() {
  const res = http.get(BASE_URL + "/health", { tags: { name: "health" } });
  check(res, { "health 200": (r) => r.status === 200 });
  return res;
}

// A small simulation: 2x2 grid, 2 simulated minutes.
export function smallSimulation() {
  const body = JSON.stringify({ grid: { rows: 2, cols: 2 }, duration: 120, seed: 1 });
  const res = http.post(BASE_URL + "/api/v2/network-metrics/simulate", body, {
    headers: headers(),
    tags: { name: "simulate_small" },
  });
  check(res, {
    "simulate 200": (r) => r.status === 200,
    "has network totals": (r) => r.status === 200 && r.json("network") !== undefined,
  });
  return res;
}

// The SLO-sized call: default 3x3 grid, 600 simulated seconds.
export function slo3x3Simulation() {
  const res = http.post(
    BASE_URL + "/api/v2/network-metrics/simulate",
    JSON.stringify({ grid: { preset: "3x3" }, duration: 600, seed: 1 }),
    { headers: headers(), tags: { name: "simulate_3x3" } },
  );
  check(res, { "simulate 3x3 200": (r) => r.status === 200 });
  return res;
}

export function baseThresholds() {
  return {
    http_req_failed: ["rate<" + maxErrorRate],
    "http_req_duration{name:health}": ["p(95)<" + apiP95Ms],
    "http_req_duration{name:simulate_small}": ["p(95)<" + simulateP95Ms],
    checks: ["rate>0.99"],
  };
}
