/**
 * The landing page's simulation data.
 *
 * Everything the scene shows was recorded from the real engine by
 * scripts/record_landing_scene.py (one seed, 520 vehicles per hour on every
 * arm, one run per control strategy). The file is a separate chunk, fetched
 * after the first paint, and the page replays its frames: nothing is
 * simulated or estimated in the browser.
 */
import { useEffect, useState } from "react";

export const STRATEGY_IDS = [
  "fixed_time",
  "adaptive",
  "roundabout",
  "metered_entry_roundabout",
] as const;
export type StrategyId = (typeof STRATEGY_IDS)[number];

/** id, x (m), y (m), heading (compass degrees), speed (m/s), vehicle type */
export type VehicleRow = [number, number, number, number, number, string];

export interface ControlState {
  signals?: { direction: string; color: string }[];
  metering?: { arms: { direction: string; color: string }[] };
}

export interface Frame {
  t: number;
  v: VehicleRow[];
  c: ControlState;
}

export interface Run {
  label: string;
  geometry: { innerRadius?: number; outerRadius?: number };
  frames: Frame[];
  /** [second, vehicles queued, vehicles that have left the network] */
  series: [number, number, number][];
  metrics: Record<string, number | null>;
}

export interface SceneData {
  provenance: {
    gitCommit: string;
    seed: number;
    durationSeconds: number;
    warmupSeconds: number;
    vehiclesPerHourPerArm: number;
    frameSeconds: number;
    window: [number, number];
  };
  runs: Record<StrategyId, Run>;
}

export interface DrawVehicle {
  id: number;
  x: number;
  y: number;
  heading: number;
  speed: number;
  type: string;
  alpha: number;
}

let pending: Promise<SceneData> | null = null;

export function loadScene(): Promise<SceneData> {
  pending ??= import("../data/scene.json").then(
    (m) => m.default as unknown as SceneData,
  );
  return pending;
}

/** The scene data once it has loaded; null until then. */
export function useScene(): SceneData | null {
  const [data, setData] = useState<SceneData | null>(null);
  useEffect(() => {
    let live = true;
    void loadScene().then((d) => {
      if (live) setData(d);
    });
    return () => {
      live = false;
    };
  }, []);
  return data;
}

const rowCache = new WeakMap<Frame, Map<number, VehicleRow>>();

function rowsById(frame: Frame): Map<number, VehicleRow> {
  let rows = rowCache.get(frame);
  if (!rows) {
    rows = new Map(frame.v.map((row) => [row[0], row]));
    rowCache.set(frame, rows);
  }
  return rows;
}

function turn(from: number, to: number, k: number): number {
  const d = ((((to - from) % 360) + 540) % 360) - 180;
  return from + d * k;
}

/** Length of the replayed stretch, in simulated seconds. */
export function windowLength(data: SceneData): number {
  return data.provenance.window[1] - data.provenance.window[0];
}

/** Vehicles at `t` seconds into the replayed window (looping), blended
 *  between the two recorded frames either side of it. */
export function sampleRun(
  run: Run,
  data: SceneData,
  t: number,
): { vehicles: DrawVehicle[]; control: ControlState; clock: number } {
  const len = windowLength(data);
  const local = ((t % len) + len) % len;
  const step = data.provenance.frameSeconds;
  const last = run.frames.length - 1;
  const raw = local / step;
  const i = Math.min(last - 1, Math.floor(raw));
  const k = Math.min(1, raw - i);
  const clock = data.provenance.window[0] + local;
  if (run.frames.length < 2) return { vehicles: [], control: {}, clock };
  const a = run.frames[i];
  const b = run.frames[i + 1];
  // Fade the whole scene across the loop seam so vehicles do not pop.
  const seam = Math.min(1, local / 0.8, (len - local) / 0.8);
  const before = rowsById(a);
  const after = rowsById(b);
  const vehicles: DrawVehicle[] = [];
  for (const [id, to] of after) {
    const from = before.get(id);
    if (from) {
      vehicles.push({
        id,
        x: from[1] + (to[1] - from[1]) * k,
        y: from[2] + (to[2] - from[2]) * k,
        heading: turn(from[3], to[3], k),
        speed: from[4] + (to[4] - from[4]) * k,
        type: to[5],
        alpha: seam,
      });
    } else {
      vehicles.push({
        id,
        x: to[1],
        y: to[2],
        heading: to[3],
        speed: to[4],
        type: to[5],
        alpha: seam * k,
      });
    }
  }
  return { vehicles, control: k < 0.5 ? a.c : b.c, clock };
}

/** Queue and cumulative departures at a simulated second of the full run. */
export function seriesAt(
  run: Run,
  second: number,
): { queued: number; departed: number } {
  if (run.series.length === 0) return { queued: 0, departed: 0 };
  const row =
    run.series[
      Math.max(0, Math.min(run.series.length - 1, Math.round(second)))
    ];
  return { queued: row[1], departed: row[2] };
}

export function formatClock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)
    .toString()
    .padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`;
}
