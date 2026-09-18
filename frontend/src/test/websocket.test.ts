/**
 * Tests for SimulationWebSocket — the live stream client.
 *
 * This is the frontend's most failure-prone surface: it owns reconnection,
 * backoff and connection state for the whole dashboard, and it had no tests at
 * all. A regression here shows up as a demo that silently stops updating, which
 * is exactly the failure a reviewer would notice first.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  SimulationWebSocket,
  type ConnectionStatus,
  type WebSocketCallbacks,
} from "../services/websocket";

/** `Array.prototype.at` needs a newer lib target than this project sets. */
function last<T>(items: T[]): T | undefined {
  return items[items.length - 1];
}

/** Minimal WebSocket double with manual control over lifecycle events. */
class FakeWebSocket {
  static instances: FakeWebSocket[] = [];

  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: (() => void) | null = null;

  closed = false;
  closeCode: number | undefined;
  closeReason: string | undefined;

  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }

  close(code?: number, reason?: string): void {
    this.closed = true;
    this.closeCode = code;
    this.closeReason = reason;
  }

  // ── test helpers ────────────────────────────────────────────────────
  open(): void {
    if (this.onopen) {
      this.onopen();
    }
  }

  emit(data: unknown): void {
    if (this.onmessage) {
      this.onmessage({ data: JSON.stringify(data) } as MessageEvent);
    }
  }

  emitRaw(data: string): void {
    if (this.onmessage) {
      this.onmessage({ data } as MessageEvent);
    }
  }

  drop(code = 1006): void {
    if (this.onclose) {
      this.onclose({ code } as CloseEvent);
    }
  }

  fail(): void {
    if (this.onerror) {
      this.onerror();
    }
  }

  static latest(): FakeWebSocket {
    const ws = last(FakeWebSocket.instances);
    if (!ws) throw new Error("no WebSocket was constructed");
    return ws;
  }
}

function makeCallbacks() {
  const snapshots: unknown[] = [];
  const statuses: ConnectionStatus[] = [];
  const errors: string[] = [];
  const callbacks: WebSocketCallbacks = {
    onSnapshot: (s) => {
      snapshots.push(s);
    },
    onStatusChange: (s) => {
      statuses.push(s);
    },
    onError: (e) => {
      errors.push(e);
    },
  };
  return { callbacks, snapshots, statuses, errors };
}

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("SimulationWebSocket", () => {
  it("connects to the url it was given", () => {
    const { callbacks } = makeCallbacks();
    new SimulationWebSocket(
      callbacks,
      "ws://test/ws/simulation/live",
    ).connect();

    expect(FakeWebSocket.latest().url).toBe("ws://test/ws/simulation/live");
  });

  it("reports connecting then connected", () => {
    const { callbacks, statuses } = makeCallbacks();
    const client = new SimulationWebSocket(callbacks, "ws://test");

    client.connect();
    expect(statuses).toContain("connecting");

    FakeWebSocket.latest().open();
    expect(last(statuses)).toBe("connected");
    expect(client.getStatus()).toBe("connected");
  });

  it("forwards parsed snapshots to the consumer", () => {
    const { callbacks, snapshots } = makeCallbacks();
    new SimulationWebSocket(callbacks, "ws://test").connect();
    FakeWebSocket.latest().open();

    FakeWebSocket.latest().emit({ tick: 7, simulationStatus: "running" });

    expect(snapshots).toEqual([{ tick: 7, simulationStatus: "running" }]);
  });

  it("reports a parse failure instead of throwing", () => {
    const { callbacks, errors, snapshots } = makeCallbacks();
    new SimulationWebSocket(callbacks, "ws://test").connect();
    FakeWebSocket.latest().open();

    expect(() => {
      FakeWebSocket.latest().emitRaw("not json{");
    }).not.toThrow();
    expect(errors).toContain("Failed to parse snapshot JSON");
    expect(snapshots).toHaveLength(0);
  });

  it("surfaces socket errors", () => {
    const { callbacks, errors, statuses } = makeCallbacks();
    new SimulationWebSocket(callbacks, "ws://test").connect();

    FakeWebSocket.latest().fail();

    expect(errors).toContain("WebSocket connection error");
    expect(last(statuses)).toBe("error");
  });

  it("reconnects after an unclean close", () => {
    const { callbacks, statuses } = makeCallbacks();
    new SimulationWebSocket(callbacks, "ws://test").connect();
    FakeWebSocket.latest().open();
    expect(FakeWebSocket.instances).toHaveLength(1);

    FakeWebSocket.latest().drop(1006);
    expect(last(statuses)).toBe("reconnecting");

    vi.advanceTimersByTime(1000);
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it("does not reconnect after a clean close", () => {
    const { callbacks } = makeCallbacks();
    new SimulationWebSocket(callbacks, "ws://test").connect();
    FakeWebSocket.latest().open();

    FakeWebSocket.latest().drop(1000);
    vi.advanceTimersByTime(60_000);

    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it("backs off exponentially across successive failures", () => {
    const { callbacks } = makeCallbacks();
    new SimulationWebSocket(callbacks, "ws://test").connect();

    // 1st retry after 1s
    FakeWebSocket.latest().drop();
    vi.advanceTimersByTime(999);
    expect(FakeWebSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(2);

    // 2nd retry after 2s
    FakeWebSocket.latest().drop();
    vi.advanceTimersByTime(1999);
    expect(FakeWebSocket.instances).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(3);

    // 3rd retry after 4s
    FakeWebSocket.latest().drop();
    vi.advanceTimersByTime(4000);
    expect(FakeWebSocket.instances).toHaveLength(4);
  });

  it("resets backoff once a connection succeeds", () => {
    const { callbacks } = makeCallbacks();
    new SimulationWebSocket(callbacks, "ws://test").connect();

    FakeWebSocket.latest().drop();
    vi.advanceTimersByTime(1000);
    FakeWebSocket.latest().drop();
    vi.advanceTimersByTime(2000);
    expect(FakeWebSocket.instances).toHaveLength(3);

    // A successful open must return the delay to the start of the ladder.
    FakeWebSocket.latest().open();
    FakeWebSocket.latest().drop();
    vi.advanceTimersByTime(1000);
    expect(FakeWebSocket.instances).toHaveLength(4);
  });

  it("stops reconnecting once disconnected", () => {
    const { callbacks, statuses } = makeCallbacks();
    const client = new SimulationWebSocket(callbacks, "ws://test");
    client.connect();
    FakeWebSocket.latest().open();

    client.disconnect();

    expect(last(statuses)).toBe("disconnected");
    vi.advanceTimersByTime(60_000);
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it("cancels a pending reconnect on disconnect", () => {
    const { callbacks } = makeCallbacks();
    const client = new SimulationWebSocket(callbacks, "ws://test");
    client.connect();

    FakeWebSocket.latest().drop();
    client.disconnect();
    vi.advanceTimersByTime(60_000);

    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it("closes the underlying socket cleanly on disconnect", () => {
    const { callbacks } = makeCallbacks();
    const client = new SimulationWebSocket(callbacks, "ws://test");
    client.connect();
    const socket = FakeWebSocket.latest();
    socket.open();

    client.disconnect();

    expect(socket.closed).toBe(true);
    expect(socket.closeCode).toBe(1000);
  });

  it("keeps streaming snapshots after a reconnect", () => {
    const { callbacks, snapshots } = makeCallbacks();
    new SimulationWebSocket(callbacks, "ws://test").connect();
    FakeWebSocket.latest().open();
    FakeWebSocket.latest().emit({ tick: 1 });

    FakeWebSocket.latest().drop();
    vi.advanceTimersByTime(1000);
    FakeWebSocket.latest().open();
    FakeWebSocket.latest().emit({ tick: 2 });

    expect(snapshots).toEqual([{ tick: 1 }, { tick: 2 }]);
  });
});
