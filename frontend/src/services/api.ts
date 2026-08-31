/**
 * REST API client for the traffic simulation backend.
 * Base URL: http://localhost:8000
 * Pure TypeScript — zero React imports.
 */

const BASE = "http://localhost:8000";

async function post(path: string): Promise<unknown> {
  const res = await fetch(`${BASE}${path}`, { method: "POST" });
  if (!res.ok)
    throw new Error(`HTTP ${res.status.toString()}: ${res.statusText}`);
  return res.json();
}

async function get(path: string): Promise<unknown> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok)
    throw new Error(`HTTP ${res.status.toString()}: ${res.statusText}`);
  return res.json();
}

/** Start / resume the live simulation engine. */
export async function playSimulation(): Promise<void> {
  await post("/api/simulation/play");
}

/** Pause the live simulation engine. */
export async function pauseSimulation(): Promise<void> {
  await post("/api/simulation/pause");
}

/** Stop the live simulation engine. */
export async function stopSimulation(): Promise<void> {
  await post("/api/simulation/stop");
}

/** Start / resume the dual simulation engine. */
export async function playDualSimulation(): Promise<void> {
  await post("/api/simulation/dual/play");
}

/** Pause the dual simulation engine. */
export async function pauseDualSimulation(): Promise<void> {
  await post("/api/simulation/dual/pause");
}

/** Reset the dual simulation engine. */
export async function resetDualSimulation(): Promise<void> {
  await post("/api/simulation/dual/reset");
}

/** Get current dual simulation status. */
export async function getDualSimulationStatus(): Promise<{
  status: string;
  elapsed: number;
  tick: number;
}> {
  return get("/api/simulation/dual/status") as Promise<{
    status: string;
    elapsed: number;
    tick: number;
  }>;
}

/** Get current simulation lifecycle status. */
export async function getSimulationStatus(): Promise<{
  status: string;
  message?: string;
}> {
  return get("/api/simulation/status") as Promise<{
    status: string;
    message?: string;
  }>;
}

/** Send new configuration to backend. */
export async function updateSimulationConfig(config: {
  intersectionType: string;
  intersectionSize: number;
  laneWidth: number;
  lanesNorth: number;
  lanesSouth: number;
  lanesEast: number;
  lanesWest: number;
  arrivalRate?: number;
  duration?: number;
  randomSeed?: number;
}): Promise<void> {
  const res = await fetch(`${BASE}/api/simulation/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status.toString()}: ${res.statusText}`);
  }
}

/** Reset/stop lockstep dual simulation. */
export async function stopDualSimulation(): Promise<void> {
  await post("/api/simulation/dual/reset");
}
