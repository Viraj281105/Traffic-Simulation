import { useCallback, useEffect, useRef, useState } from "react";
import { SimulationWebSocket } from "../services/websocket";
import type {
  ComparisonSnapshot,
  LiveSnapshot,
  DualSnapshot,
} from "../types/simulation";
import {
  playSimulation,
  pauseSimulation,
  stopSimulation,
  playDualSimulation,
  pauseDualSimulation,
  stopDualSimulation,
  playComparison,
  pauseComparison,
  resetComparison,
} from "../services/api";
import type { ConnectionStatus } from "../services/websocket";
import { WS_BASE_URL } from "../config";
import { whenLiveSessionReady } from "../services/liveSession";

/** Which live stream to follow: the single simulation, the legacy
 *  signal-vs-roundabout pair, or the comparison of chosen strategies. */
export type StreamMode = "single" | "dual" | "comparison";

const STREAM_PATH: Record<StreamMode, string> = {
  single: "/ws/simulation/live",
  dual: "/ws/simulation/dual",
  comparison: "/ws/simulation/comparison",
};

const CONTROLS: Record<
  StreamMode,
  {
    play: () => Promise<void>;
    pause: () => Promise<void>;
    stop: () => Promise<void>;
  }
> = {
  single: {
    play: playSimulation,
    pause: pauseSimulation,
    stop: stopSimulation,
  },
  dual: {
    play: playDualSimulation,
    pause: pauseDualSimulation,
    stop: stopDualSimulation,
  },
  comparison: {
    play: playComparison,
    pause: pauseComparison,
    stop: resetComparison,
  },
};

export interface WebSocketSnapshotState {
  snapshot: LiveSnapshot | DualSnapshot | ComparisonSnapshot | null;
  connectionStatus: ConnectionStatus;
  isPlaying: boolean;
  error: string | null;
  play: () => Promise<void>;
  pause: () => Promise<void>;
  stop: () => Promise<void>;
}

export function useWebSocketSnapshot(mode: StreamMode): WebSocketSnapshotState {
  const [snapshot, setSnapshot] = useState<
    LiveSnapshot | DualSnapshot | ComparisonSnapshot | null
  >(null);
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
    const url = `${WS_BASE_URL}${STREAM_PATH[mode]}`;

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
          const status = streamStatus(snap);

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
    // Open the stream inside the same backend session as the REST calls
    // (see liveSession.ts); a socket opened first is bound to another one.
    const cancelConnect = whenLiveSessionReady(() => {
      ws.connect();
    });

    return () => {
      cancelConnect();
      ws.disconnect();
    };
  }, [mode]);

  const play = useCallback(async () => {
    try {
      setError(null);
      await CONTROLS[mode].play();
      setIsPlaying(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Failed to start simulation: ${msg}`);
    }
  }, [mode]);

  const pause = useCallback(async () => {
    try {
      setError(null);
      await CONTROLS[mode].pause();
      setIsPlaying(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Failed to pause simulation: ${msg}`);
    }
  }, [mode]);

  const stop = useCallback(async () => {
    try {
      setError(null);
      await CONTROLS[mode].stop();
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
function snapshotKey(
  snap: LiveSnapshot | DualSnapshot | ComparisonSnapshot,
): string {
  const one = (s: LiveSnapshot) =>
    [s.simulationId, s.configId, s.tick, s.timestamp, s.simulationStatus].join(
      "|",
    );
  if ("runs" in snap) {
    return snap.runs.map((r) => `${r.strategy}:${one(r.snapshot)}`).join("#");
  }
  return "signal" in snap
    ? `${one(snap.signal)}#${one(snap.roundabout)}`
    : one(snap);
}

/** The lead run's status: every run of a lockstep stream shares it. */
function streamStatus(
  snap: LiveSnapshot | DualSnapshot | ComparisonSnapshot,
): string | undefined {
  if ("runs" in snap) return snap.runs[0]?.snapshot.simulationStatus;
  return "signal" in snap
    ? snap.signal.simulationStatus
    : snap.simulationStatus;
}
