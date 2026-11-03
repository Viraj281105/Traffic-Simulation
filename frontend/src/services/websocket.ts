/**
 * WebSocket client for the live simulation stream.
 * Connects to ws://localhost:8000/ws/simulation/live
 * Handles reconnection with exponential backoff.
 * Pure TypeScript — zero React imports.
 */
import type {
  ComparisonSnapshot,
  LiveSnapshot,
  DualSnapshot,
} from "../types/simulation";
import { WS_BASE_URL } from "../config";

const BACKOFF_DELAYS_MS = [1000, 2000, 4000, 8000, 16000, 30000];

export type ConnectionStatus =
  "disconnected" | "connecting" | "connected" | "reconnecting" | "error";

export interface WebSocketCallbacks {
  onSnapshot: (
    snapshot: LiveSnapshot | DualSnapshot | ComparisonSnapshot,
  ) => void;
  onStatusChange: (status: ConnectionStatus) => void;
  onError: (error: string) => void;
}

export class SimulationWebSocket {
  private ws: WebSocket | null = null;
  private callbacks: WebSocketCallbacks;
  private retryCount = 0;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = true;
  private status: ConnectionStatus = "disconnected";
  private url: string;

  constructor(
    callbacks: WebSocketCallbacks,
    url: string = `${WS_BASE_URL}/ws/simulation/live`,
  ) {
    this.callbacks = callbacks;
    this.url = url;
  }

  connect(): void {
    this.shouldReconnect = true;
    this.retryCount = 0;
    this._clearRetry();
    this._connect();
  }

  private _clearRetry(): void {
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
  }

  /** Close a socket that is being replaced or dropped without letting its
   *  handlers act: a late "close" from it would otherwise null the current
   *  socket and schedule a second reconnect. */
  private static _retire(ws: WebSocket, code?: number, reason?: string): void {
    ws.onopen = null;
    ws.onmessage = null;
    ws.onerror = null;
    ws.onclose = null;
    ws.close(code, reason);
  }

  disconnect(): void {
    this.shouldReconnect = false;
    this._clearRetry();
    if (this.ws) {
      // Detach first: closing a socket that is still connecting fires
      // "error", which would surface a spurious connection error for what
      // is an intentional disconnect (view change, unmount).
      SimulationWebSocket._retire(this.ws, 1000, "Client disconnect");
      this.ws = null;
    }
    this._setStatus("disconnected");
  }

  getStatus(): ConnectionStatus {
    return this.status;
  }

  private _connect(): void {
    if (this.ws) {
      SimulationWebSocket._retire(this.ws);
      this.ws = null;
    }

    this._setStatus(this.retryCount === 0 ? "connecting" : "reconnecting");

    let socket: WebSocket;
    try {
      socket = new WebSocket(this.url);
    } catch {
      this._scheduleReconnect();
      return;
    }
    this.ws = socket;

    socket.onopen = () => {
      this.retryCount = 0;
      this._setStatus("connected");
    };

    socket.onmessage = (event: MessageEvent) => {
      try {
        const snapshot = JSON.parse(event.data as string) as
          LiveSnapshot | DualSnapshot | ComparisonSnapshot;
        this.callbacks.onSnapshot(snapshot);
      } catch {
        this.callbacks.onError("Failed to parse snapshot JSON");
      }
    };

    socket.onclose = (event: CloseEvent) => {
      if (this.ws !== socket) return; // a socket already replaced
      this.ws = null;
      if (!this.shouldReconnect) return;
      if (event.code === 1000) return; // clean close
      this._setStatus("reconnecting");
      this._scheduleReconnect();
    };

    socket.onerror = () => {
      if (this.ws !== socket) return;
      this.callbacks.onError("WebSocket connection error");
      this._setStatus("error");
    };
  }

  private _scheduleReconnect(): void {
    if (!this.shouldReconnect) return;
    const delay =
      BACKOFF_DELAYS_MS[
        Math.min(this.retryCount, BACKOFF_DELAYS_MS.length - 1)
      ];
    this.retryCount++;
    this._clearRetry();
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      this._connect();
    }, delay);
  }

  private _setStatus(status: ConnectionStatus): void {
    this.status = status;
    this.callbacks.onStatusChange(status);
  }
}
