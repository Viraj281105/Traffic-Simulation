/**
 * useWebSocketSnapshot — React hook that manages the WebSocket connection
 * to the live simulation stream and exposes snapshot data + controls.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { SimulationWebSocket } from "../services/websocket";
import { LiveSnapshot, DualSnapshot } from "../types/simulation";
import {
  playSimulation,
  pauseSimulation,
  stopSimulation,
  playDualSimulation,
  pauseDualSimulation,
  resetDualSimulation,
} from "../services/api";
import type { ConnectionStatus } from "../services/websocket";

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
  path: string = "/ws/simulation/live",
): WebSocketSnapshotState {
  const [snapshot, setSnapshot] = useState<LiveSnapshot | DualSnapshot | null>(
    null,
  );
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("disconnected");
  const [isPlaying, setIsPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<SimulationWebSocket | null>(null);

  useEffect(() => {
    const ws = new SimulationWebSocket(
      {
        onSnapshot: (snap: LiveSnapshot | DualSnapshot) => {
          setSnapshot(snap);
          setError(null);
          // Sync play state from snapshot status (either nested or top-level)
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
      path,
    );

    wsRef.current = ws;
    ws.connect();

    return () => {
      ws.disconnect();
    };
  }, [path]);

  const play = useCallback(async () => {
    try {
      setError(null);
      if (path.includes("dual")) {
        await playDualSimulation();
      } else {
        await playSimulation();
      }
      setIsPlaying(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Failed to start simulation: ${msg}`);
    }
  }, [path]);

  const pause = useCallback(async () => {
    try {
      setError(null);
      if (path.includes("dual")) {
        await pauseDualSimulation();
      } else {
        await pauseSimulation();
      }
      setIsPlaying(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Failed to pause simulation: ${msg}`);
    }
  }, [path]);

  const stop = useCallback(async () => {
    try {
      setError(null);
      if (path.includes("dual")) {
        await resetDualSimulation();
      } else {
        await stopSimulation();
      }
      setIsPlaying(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Failed to stop/reset simulation: ${msg}`);
    }
  }, [path]);

  return { snapshot, connectionStatus, isPlaying, error, play, pause, stop };
}
