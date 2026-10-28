import { API_BASE_URL } from "../config";
import { ensureLiveSession } from "./liveSession";
import type {
  ControlResponse,
  SimulationStatusResponse,
  SingleVehicleResponse,
} from "../types/simulation";

/** The legacy single-vehicle polling API (backend live/router.py,
 *  /api/simulation/status · start · stop · reset · single-vehicle). Sent
 *  without the user's token, as it always has been; each call's error text is
 *  part of what the polling view shows. */
const API_BASE = `${API_BASE_URL}/api/simulation`;

/** fetch for the live API, sent inside the browser's backend session so it
 *  cannot start a competing one (see liveSession.ts). */
async function liveFetch(url: string, init?: RequestInit): Promise<Response> {
  await ensureLiveSession();
  return fetch(url, init);
}

export async function getSingleVehicle(): Promise<SingleVehicleResponse> {
  const response = await liveFetch(`${API_BASE}/single-vehicle`);
  if (!response.ok) {
    throw new Error(
      `HTTP ${response.status.toString()}: ${response.statusText}`,
    );
  }
  return (await response.json()) as SingleVehicleResponse;
}

async function control(
  action: "start" | "stop" | "reset",
): Promise<ControlResponse> {
  const response = await liveFetch(`${API_BASE}/${action}`, { method: "POST" });
  if (!response.ok) {
    throw new Error(
      `Failed to ${action} simulation: HTTP ${response.status.toString()}`,
    );
  }
  return (await response.json()) as ControlResponse;
}

export const startSingleVehicle = () => control("start");
export const stopSingleVehicle = () => control("stop");
export const resetSingleVehicle = () => control("reset");

export async function getSingleVehicleStatus(): Promise<SimulationStatusResponse> {
  const response = await liveFetch(`${API_BASE}/status`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status.toString()}`);
  }
  return (await response.json()) as SimulationStatusResponse;
}
