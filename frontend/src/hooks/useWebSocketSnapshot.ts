/**
 * useWebSocketSnapshot — React hook that manages the WebSocket connection
 * to the live simulation stream and exposes snapshot data + controls.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { SimulationWebSocket } from "../services/websocket";
import {
  playSimulation,
  pauseSimulation,
  stopSimulation,
} from "../services/api";
import type { LiveSnapshot } from "../types/simulation";
import type { ConnectionStatus } from "../services/websocket";

export interface WebSocketSnapshotState {
  snapshot: LiveSnapshot | null;
  connectionStatus: ConnectionStatus;
  isPlaying: boolean;
  error: string | null;
  play: () => Promise<void>;
  pause: () => Promise<void>;
  stop: () => Promise<void>;
}

export function useWebSocketSnapshot(): WebSocketSnapshotState {
  const [snapshot, setSnapshot] = useState<LiveSnapshot | null>(null);
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("disconnected");
  const [isPlaying, setIsPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<SimulationWebSocket | null>(null);

  useEffect(() => {
    const ws = new SimulationWebSocket({
      onSnapshot: (snap) => {
        setSnapshot(snap);
        setError(null);
        // Sync play state from snapshot status
        if (
          snap.simulationStatus === "running" ||
          snap.simulationStatus === "initializing"
        ) {
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
    });

    wsRef.current = ws;
    ws.connect();

    return () => {
      ws.disconnect();
    };
  }, []);

  const play = useCallback(async () => {
    try {
      setError(null);
      await playSimulation();
      setIsPlaying(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Failed to start simulation: ${msg}`);
    }
  }, []);

  const pause = useCallback(async () => {
    try {
      setError(null);
      await pauseSimulation();
      setIsPlaying(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Failed to pause simulation: ${msg}`);
    }
  }, []);

  const stop = useCallback(async () => {
    try {
      setError(null);
      await stopSimulation();
      setIsPlaying(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Failed to stop simulation: ${msg}`);
    }
  }, []);

  return { snapshot, connectionStatus, isPlaying, error, play, pause, stop };
}
