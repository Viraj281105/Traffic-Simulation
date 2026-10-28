import { useEffect, useState, type RefObject } from "react";
import type { SimClock } from "./clock";
import {
  seriesAt,
  windowLength,
  type SceneData,
  type StrategyId,
} from "./sceneData";

export interface Hud {
  /** Simulated seconds into the full run. */
  clock: number;
  /** Vehicles on the network in the nearest recorded frame. */
  vehicles: number;
  queued: number;
  departed: number;
}

/** Live readout of the replay, sampled a few times a second from the same
 *  recorded frames the canvas draws. */
export function useHud(
  data: SceneData | null,
  strategy: StrategyId,
  clock: RefObject<SimClock>,
  everyMs = 250,
): Hud {
  const [hud, setHud] = useState<Hud>({
    clock: 0,
    vehicles: 0,
    queued: 0,
    departed: 0,
  });
  useEffect(() => {
    if (!data) return;
    const run = data.runs[strategy];
    const read = () => {
      const len = windowLength(data);
      const local = ((clock.current.t % len) + len) % len;
      const sim = data.provenance.window[0] + local;
      const idx = Math.min(
        run.frames.length - 1,
        Math.round(local / data.provenance.frameSeconds),
      );
      const s = seriesAt(run, sim);
      setHud({
        clock: sim,
        vehicles: run.frames[idx]?.v.length ?? 0,
        queued: s.queued,
        departed: s.departed,
      });
    };
    read();
    const id = window.setInterval(() => {
      if (!document.hidden) read();
    }, everyMs);
    return () => {
      window.clearInterval(id);
    };
  }, [data, strategy, clock, everyMs]);
  return hud;
}
