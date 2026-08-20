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
