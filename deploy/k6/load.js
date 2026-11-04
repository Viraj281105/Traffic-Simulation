// Load: ramp to 10 virtual users, hold 5 minutes, ramp down. Mix of health checks,
// small simulations and the SLO-sized 3x3 call (10 % of iterations).
//   k6 run -e BASE_URL=... -e AUTH_TOKEN=... deploy/k6/load.js
import { sleep } from "k6";
import { baseThresholds, health, simulateP95Ms, slo3x3Simulation, smallSimulation } from "./lib.js";

export const options = {
  stages: [
    { duration: "1m", target: 10 },
    { duration: "5m", target: 10 },
    { duration: "30s", target: 0 },
  ],
  thresholds: Object.assign(baseThresholds(), {
    "http_req_duration{name:simulate_3x3}": ["p(95)<" + simulateP95Ms],
  }),
};

export default function () {
  health();
  if (Math.random() < 0.1) {
    slo3x3Simulation();
  } else {
    smallSimulation();
  }
  sleep(1);
}
