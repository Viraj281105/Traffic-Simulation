// Spike: sudden jump from 2 to 50 virtual users, hold, then recover. The thresholds are
// looser than the SLO (2x latency, 5x error budget) because the point is to see the
// system degrade gracefully and return to normal, not to meet the steady-state SLO.
//   k6 run -e BASE_URL=... -e AUTH_TOKEN=... deploy/k6/spike.js
import { sleep } from "k6";
import { apiP95Ms, health, maxErrorRate, simulateP95Ms, smallSimulation } from "./lib.js";

export const options = {
  stages: [
    { duration: "30s", target: 2 },
    { duration: "10s", target: 50 },
    { duration: "1m", target: 50 },
    { duration: "10s", target: 2 },
    { duration: "1m", target: 2 }, // recovery window
    { duration: "10s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<" + maxErrorRate * 5],
    "http_req_duration{name:health}": ["p(95)<" + apiP95Ms * 2],
    "http_req_duration{name:simulate_small}": ["p(95)<" + simulateP95Ms * 2],
  },
};

export default function () {
  health();
  smallSimulation();
  sleep(0.5);
}
