import { useCallback, useEffect, useRef, useState } from "react";
import { SimulationWebSocket } from "../services/websocket";
import { LiveSnapshot, DualSnapshot } from "../types/simulation";
import {
  playSimulation,
  pauseSimulation,
  stopSimulation,
  playDualSimulation,
  pauseDualSimulation,
  stopDualSimulation,
} from "../services/api";
import type { ConnectionStatus } from "../services/websocket";
import { WS_BASE_URL } from "../config";

export interface WebSocketSnapshotState {
  snapshot: LiveSnapshot | DualSnapshot | null;
  connectionStatus: ConnectionStatus;
  isPlaying: boolean;
  error: string | null;
  play: () => Promise<void>;
  pause: () => Promise<void>;
  stop: () => Promise<void>;
}

export function useWebSocketSnapshot(
  mode: "single" | "dual",
): WebSocketSnapshotState {
  const [snapshot, setSnapshot] = useState<LiveSnapshot | DualSnapshot | null>(
    null,
  );
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("disconnected");
  const [isPlaying, setIsPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [prevMode, setPrevMode] = useState(mode);
  const wsRef = useRef<SimulationWebSocket | null>(null);

  if (mode !== prevMode) {
    setPrevMode(mode);
    setSnapshot(null);
    setIsPlaying(false);
  }

  useEffect(() => {
    const url =
      mode === "dual"
        ? `${WS_BASE_URL}/ws/simulation/dual`
        : `${WS_BASE_URL}/ws/simulation/live`;

    // The backend streams at ~10 Hz regardless of whether the simulation has
    // advanced: while idle/paused, and whenever its send loop outpaces the
    // simulation thread, consecutive messages describe the same tick. Such a
    // message carries no new state, so re-publishing it would only re-render
    // the whole dashboard (and every page, since this stream stays open).
    let lastKey: string | null = null;

    const ws = new SimulationWebSocket(
      {
        onSnapshot: (snap) => {
          const key = snapshotKey(snap);
          if (key !== lastKey) {
            lastKey = key;
            setSnapshot(snap);
          }
          setError(null);
          const status =
            "signal" in snap
              ? snap.signal.simulationStatus
              : snap.simulationStatus;

          if (status === "running" || status === "initializing") {
            setIsPlaying(true);
          } else {
            setIsPlaying(false);
          }
        },
        onStatusChange: (status) => {
          setConnectionStatus(status);
        },
        onError: (msg) => {
          setError(msg);
        },
      },
      url,
    );

    wsRef.current = ws;
    ws.connect();

    return () => {
      ws.disconnect();
    };
  }, [mode]);

  const play = useCallback(async () => {
    try {
      setError(null);
      if (mode === "dual") {
        await playDualSimulation();
      } else {
        await playSimulation();
      }
      setIsPlaying(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Failed to start simulation: ${msg}`);
    }
  }, [mode]);

  const pause = useCallback(async () => {
    try {
      setError(null);
      if (mode === "dual") {
        await pauseDualSimulation();
      } else {
        await pauseSimulation();
      }
      setIsPlaying(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Failed to pause simulation: ${msg}`);
    }
  }, [mode]);

  const stop = useCallback(async () => {
    try {
      setError(null);
      if (mode === "dual") {
        await stopDualSimulation();
      } else {
        await stopSimulation();
      }
      setIsPlaying(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Failed to stop/reset simulation: ${msg}`);
    }
  }, [mode]);

  return { snapshot, connectionStatus, isPlaying, error, play, pause, stop };
}

/** Identity of the simulation state a snapshot describes. Two snapshots with
 *  the same run, tick, timestamp and status describe the same engine state. */
function snapshotKey(snap: LiveSnapshot | DualSnapshot): string {
  const one = (s: LiveSnapshot) =>
    [s.simulationId, s.configId, s.tick, s.timestamp, s.simulationStatus].join(
      "|",
    );
  return "signal" in snap
    ? `${one(snap.signal)}#${one(snap.roundabout)}`
    : one(snap);
}
