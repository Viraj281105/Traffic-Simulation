/**
 * Tests for useWebSocketSnapshot — the hook the dashboard drives itself from.
 *
 * It owns the mapping from stream snapshots to the play/pause state the
 * controls render, switches endpoints between single and dual mode, and turns
 * failed control calls into user-visible errors. None of that was covered.
 */
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const connect = vi.fn();
const disconnect = vi.fn();
let capturedCallbacks: {
  onSnapshot: (s: unknown) => void;
  onStatusChange: (s: string) => void;
  onError: (m: string) => void;
};
let capturedUrl = "";

vi.mock("../services/websocket", () => ({
  SimulationWebSocket: class {
    constructor(callbacks: typeof capturedCallbacks, url: string) {
      capturedCallbacks = callbacks;
      capturedUrl = url;
    }
    connect = connect;
    disconnect = disconnect;
  },
}));

const playSimulation = vi.fn();
const pauseSimulation = vi.fn();
const stopSimulation = vi.fn();
const playDualSimulation = vi.fn();
const pauseDualSimulation = vi.fn();
const stopDualSimulation = vi.fn();

vi.mock("../services/api", () => ({
  playSimulation: async (): Promise<void> => {
    await playSimulation();
  },
  pauseSimulation: async (): Promise<void> => {
    await pauseSimulation();
  },
  stopSimulation: async (): Promise<void> => {
    await stopSimulation();
  },
  playDualSimulation: async (): Promise<void> => {
    await playDualSimulation();
  },
  pauseDualSimulation: async (): Promise<void> => {
    await pauseDualSimulation();
  },
  stopDualSimulation: async (): Promise<void> => {
    await stopDualSimulation();
  },
}));

import { useWebSocketSnapshot } from "../hooks/useWebSocketSnapshot";

beforeEach(() => {
  vi.clearAllMocks();
  playSimulation.mockResolvedValue(undefined);
  pauseSimulation.mockResolvedValue(undefined);
  stopSimulation.mockResolvedValue(undefined);
  playDualSimulation.mockResolvedValue(undefined);
  pauseDualSimulation.mockResolvedValue(undefined);
  stopDualSimulation.mockResolvedValue(undefined);
});

afterEach(() => {
  capturedUrl = "";
});

describe("useWebSocketSnapshot", () => {
  it("connects to the live endpoint in single mode", () => {
    renderHook(() => useWebSocketSnapshot("single"));

    expect(connect).toHaveBeenCalled();
    expect(capturedUrl).toContain("/ws/simulation/live");
  });

  it("connects to the dual endpoint in dual mode", () => {
    renderHook(() => useWebSocketSnapshot("dual"));

    expect(capturedUrl).toContain("/ws/simulation/dual");
  });

  it("disconnects on unmount so the socket is not leaked", () => {
    const { unmount } = renderHook(() => useWebSocketSnapshot("single"));

    unmount();

    expect(disconnect).toHaveBeenCalled();
  });

  it("reconnects to the other endpoint when the mode changes", () => {
    const initialProps: { mode: "single" | "dual" } = { mode: "single" };
    const { rerender } = renderHook(
      ({ mode }: { mode: "single" | "dual" }) => useWebSocketSnapshot(mode),
      { initialProps },
    );
    expect(capturedUrl).toContain("/ws/simulation/live");

    rerender({ mode: "dual" });

    expect(disconnect).toHaveBeenCalled();
    expect(capturedUrl).toContain("/ws/simulation/dual");
  });

  it("exposes the latest snapshot", () => {
    const { result } = renderHook(() => useWebSocketSnapshot("single"));

    act(() => {
      capturedCallbacks.onSnapshot({ tick: 3, simulationStatus: "running" });
    });

    expect(result.current.snapshot).toEqual({
      tick: 3,
      simulationStatus: "running",
    });
  });

  it("ignores a message that repeats the current simulation state", () => {
    const { result } = renderHook(() => useWebSocketSnapshot("single"));

    act(() => {
      capturedCallbacks.onSnapshot({ tick: 3, simulationStatus: "paused" });
    });
    const first = result.current.snapshot;
    act(() => {
      capturedCallbacks.onSnapshot({ tick: 3, simulationStatus: "paused" });
    });
    expect(result.current.snapshot).toBe(first);

    // A status change at the same tick is new state and does get through.
    act(() => {
      capturedCallbacks.onSnapshot({ tick: 3, simulationStatus: "running" });
    });
    expect(result.current.snapshot).not.toBe(first);
    expect(result.current.isPlaying).toBe(true);
  });

  it("marks the simulation as playing while it is running", () => {
    const { result } = renderHook(() => useWebSocketSnapshot("single"));

    act(() => {
      capturedCallbacks.onSnapshot({ simulationStatus: "running" });
    });

    expect(result.current.isPlaying).toBe(true);
  });

  it("marks the simulation as not playing once it completes", () => {
    const { result } = renderHook(() => useWebSocketSnapshot("single"));

    act(() => {
      capturedCallbacks.onSnapshot({ simulationStatus: "running" });
    });
    act(() => {
      capturedCallbacks.onSnapshot({ simulationStatus: "completed" });
    });

    expect(result.current.isPlaying).toBe(false);
  });

  it("reads the status from the signal side of a dual snapshot", () => {
    const { result } = renderHook(() => useWebSocketSnapshot("dual"));

    act(() => {
      capturedCallbacks.onSnapshot({
        signal: { simulationStatus: "running" },
        roundabout: { simulationStatus: "running" },
      });
    });

    expect(result.current.isPlaying).toBe(true);
  });

  it("clears the stale snapshot when the mode changes", () => {
    const initialProps: { mode: "single" | "dual" } = { mode: "single" };
    const { result, rerender } = renderHook(
      ({ mode }: { mode: "single" | "dual" }) => useWebSocketSnapshot(mode),
      { initialProps },
    );
    act(() => {
      capturedCallbacks.onSnapshot({ simulationStatus: "running" });
    });
    expect(result.current.snapshot).not.toBeNull();

    rerender({ mode: "dual" });

    expect(result.current.snapshot).toBeNull();
    expect(result.current.isPlaying).toBe(false);
  });

  it("tracks connection status changes", () => {
    const { result } = renderHook(() => useWebSocketSnapshot("single"));

    act(() => {
      capturedCallbacks.onStatusChange("connected");
    });

    expect(result.current.connectionStatus).toBe("connected");
  });

  it("surfaces stream errors", () => {
    const { result } = renderHook(() => useWebSocketSnapshot("single"));

    act(() => {
      capturedCallbacks.onError("boom");
    });

    expect(result.current.error).toBe("boom");
  });

  it("clears a previous error once a snapshot arrives", () => {
    const { result } = renderHook(() => useWebSocketSnapshot("single"));

    act(() => {
      capturedCallbacks.onError("boom");
    });
    act(() => {
      capturedCallbacks.onSnapshot({ simulationStatus: "running" });
    });

    expect(result.current.error).toBeNull();
  });

  it("calls the single-mode control endpoints", async () => {
    const { result } = renderHook(() => useWebSocketSnapshot("single"));

    await act(async () => {
      await result.current.play();
    });
    expect(playSimulation).toHaveBeenCalled();
    expect(result.current.isPlaying).toBe(true);

    await act(async () => {
      await result.current.pause();
    });
    expect(pauseSimulation).toHaveBeenCalled();
    expect(result.current.isPlaying).toBe(false);

    await act(async () => {
      await result.current.stop();
    });
    expect(stopSimulation).toHaveBeenCalled();
  });

  it("calls the dual-mode control endpoints", async () => {
    const { result } = renderHook(() => useWebSocketSnapshot("dual"));

    await act(async () => {
      await result.current.play();
    });

    expect(playDualSimulation).toHaveBeenCalled();
    expect(playSimulation).not.toHaveBeenCalled();
  });

  it("reports a failed play instead of silently staying stopped", async () => {
    playSimulation.mockRejectedValue(new Error("HTTP 401: Unauthorized"));
    const { result } = renderHook(() => useWebSocketSnapshot("single"));

    await act(async () => {
      await result.current.play();
    });

    await waitFor(() => {
      expect(result.current.error).toContain("Failed to start simulation");
      expect(result.current.error).toContain("401");
    });
    expect(result.current.isPlaying).toBe(false);
  });

  it("reports a failed pause", async () => {
    pauseSimulation.mockRejectedValue(new Error("network down"));
    const { result } = renderHook(() => useWebSocketSnapshot("single"));

    await act(async () => {
      await result.current.pause();
    });

    expect(result.current.error).toContain("Failed to pause simulation");
  });
});
