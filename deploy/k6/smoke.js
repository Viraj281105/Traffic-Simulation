// Smoke: 1 virtual user, ~30 s. Proves the endpoints answer inside the SLO limits.
//   k6 run -e BASE_URL=http://127.0.0.1:8000 -e AUTH_TOKEN=... deploy/k6/smoke.js
import { sleep } from "k6";
import { baseThresholds, health, smallSimulation } from "./lib.js";

export const options = {
  vus: 1,
  duration: "30s",
  thresholds: baseThresholds(),
};

export default function () {
  health();
  smallSimulation();
  sleep(1);
}
