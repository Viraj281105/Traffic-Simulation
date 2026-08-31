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
import type { LiveSnapshot, DualSnapshot } from "../types/simulation";
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
  mode: "single" | "dual",
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
    // Reset snapshot state on mode switch
    setSnapshot(null);
    setIsPlaying(false);

    const url =
      mode === "dual"
        ? "ws://localhost:8000/ws/simulation/dual"
        : "ws://localhost:8000/ws/simulation/live";

    const ws = new SimulationWebSocket(
      {
        onSnapshot: (snap) => {
          setSnapshot(snap);
          setError(null);
          // Sync play state from snapshot status
          let status = "";
          if ("signal" in snap) {
            status = (snap as unknown as DualSnapshot).signal.simulationStatus;
          } else {
            status = snap.simulationStatus;
          }

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
