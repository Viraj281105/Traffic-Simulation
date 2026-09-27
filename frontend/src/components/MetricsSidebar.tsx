import React from "react";
import type {
  LiveSnapshot,
  SignalDirection,
  VehicleCounts,
} from "../types/simulation";
import type { ConnectionStatus } from "../services/websocket";
import {
  downloadText,
  isInWarmup,
  singleRunCsv,
  type Geometry,
  type MetricContext,
} from "../metrics/catalog";
import { MetricSections } from "./MetricSections";

interface MetricsSidebarProps {
  snapshot: LiveSnapshot | null;
  connectionStatus: ConnectionStatus;
  /** Geometry of the view, used before any snapshot has arrived. */
  geometry: Geometry;
  /** Set when the metrics come from a saved run rather than the live stream. */
  replayName?: string | null;
}

const DIRECTIONS: SignalDirection[] = ["north", "south", "east", "west"];
const DIR_LABEL: Record<SignalDirection, string> = {
  north: "N",
  south: "S",
  east: "E",
  west: "W",
};

const CONNECTION_LABELS: Record<
  ConnectionStatus,
  { label: string; tone: "ok" | "warn" | "bad" | "idle" }
> = {
  connected: { label: "Live", tone: "ok" },
  connecting: { label: "Connecting", tone: "warn" },
  reconnecting: { label: "Reconnecting", tone: "warn" },
  disconnected: { label: "Offline", tone: "idle" },
  error: { label: "Connection error", tone: "bad" },
};

export function ConnectionBadge({ status }: { status: ConnectionStatus }) {
  const c = CONNECTION_LABELS[status];
  return (
    <span className={`conn-badge tone-${c.tone}`} role="status">
      <span className="conn-dot" aria-hidden="true" />
      {c.label}
    </span>
  );
}

/** Explains why post-warm-up metrics are still empty. */
export function WarmupNotice({ snapshot }: { snapshot: LiveSnapshot | null }) {
  const live = snapshot as Partial<LiveSnapshot> | null;
  if (!snapshot || live?.timestamp === undefined) return null;
  if (snapshot.warmupTime === undefined) return null;
  if (!isInWarmup(snapshot.timestamp, snapshot.warmupTime)) return null;
  const remaining = Math.max(0, snapshot.warmupTime - snapshot.timestamp);
  return (
    <p className="warmup-notice" role="status">
      Warm-up: most metrics start at {snapshot.warmupTime.toFixed(0)} s of
      simulated time ({remaining.toFixed(0)} s to go).
    </p>
  );
}

export function VehicleCountChips({
  counts,
  geometry,
}: {
  counts: VehicleCounts | undefined;
  geometry: Geometry;
}) {
  const inJunction =
    geometry === "roundabout"
      ? (counts?.inRoundabout ?? 0) + (counts?.crossing ?? 0)
      : (counts?.crossing ?? 0);
  const chips: Array<[string, number | undefined, string]> = [
    ["In network", counts?.active, "var(--accent-blue)"],
    ["Approaching", counts?.approaching, "var(--accent-teal)"],
    ["Waiting", counts?.waiting, "var(--accent-red)"],
    [
      geometry === "roundabout" ? "In ring" : "Crossing",
      counts ? inJunction : undefined,
      "var(--accent-yellow)",
    ],
    ["Exited", counts?.exited, "var(--text-secondary)"],
  ];
  return (
    <dl className="vehicle-chips">
      {chips.map(([label, value, color]) => (
        <div
          className="vehicle-chip"
          style={{ borderColor: color }}
          key={label}
        >
          <dt className="chip-label">{label}</dt>
          <dd className="chip-count" style={{ color }}>
            {value ?? "—"}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function ControllerState({ snapshot }: { snapshot: LiveSnapshot }) {
  const c = snapshot.controller;
  if (c.type === "fixed_time_signal") {
    return (
      <p className="controller-state">
        Phase <strong>{c.currentPhase.replace(/_/g, " ")}</strong> ·{" "}
        {c.phaseTimeRemaining.toFixed(1)} s left · cycle {c.cycleNumber}
      </p>
    );
  }
  return (
    <p className="controller-state">
      <strong>{c.circulatingCount}</strong> circulating ·{" "}
      <strong>{c.yieldingCount}</strong> yielding · critical gap{" "}
      {c.gapAcceptance.toFixed(1)} s
    </p>
  );
}

export const MetricsSidebar: React.FC<MetricsSidebarProps> = ({
  snapshot,
  connectionStatus,
  geometry,
  replayName = null,
}) => {
  const m = snapshot?.metrics;
  // Saved-run snapshots carry metrics only (no controller, time or counts).
  const partial = snapshot as Partial<LiveSnapshot> | null;
  const ctx: MetricContext = {
    metrics: m,
    geometry: partial?.controller?.type ?? geometry,
    inWarmup: isInWarmup(partial?.timestamp, partial?.warmupTime),
  };
  const maxQ = Math.max(
    1,
    ...DIRECTIONS.map((d) => m?.currentQueueLengths[d] ?? 0),
  );
  const title = geometry === "roundabout" ? "Roundabout" : "Fixed-time signal";

  const handleDownload = () => {
    const header = [
      `${title} ${replayName ? `saved run: ${replayName}` : "live run"}`,
      partial?.timestamp !== undefined
        ? `Simulated time: ${partial.timestamp.toFixed(1)} s`
        : "",
      partial?.warmupTime !== undefined
        ? `Warm-up excluded: ${partial.warmupTime.toFixed(0)} s`
        : "",
    ].filter(Boolean);
    downloadText(
      `${geometry}_metrics_${Date.now().toString()}.csv`,
      singleRunCsv(ctx, header),
      "text/csv;charset=utf-8",
    );
  };

  return (
    <aside className="metrics-sidebar" aria-labelledby="metrics-sidebar-title">
      <div className="sidebar-header">
        <h2 className="sidebar-title" id="metrics-sidebar-title">
          {replayName ? "Saved run" : "Live metrics"}
        </h2>
        {!replayName && <ConnectionBadge status={connectionStatus} />}
      </div>

      {replayName && <p className="replay-note">{replayName}</p>}
      <WarmupNotice snapshot={snapshot} />

      {partial?.vehicleCounts !== undefined && snapshot && (
        <section className="sidebar-section" aria-label="Vehicles now">
          <h3 className="section-title">Vehicles now</h3>
          <VehicleCountChips
            counts={snapshot.vehicleCounts}
            geometry={geometry}
          />
          {/* Saved-run snapshots carry no controller state. */}
          {partial.controller !== undefined && (
            <ControllerState snapshot={snapshot} />
          )}
        </section>
      )}

      {m?.currentQueueLengths && !replayName && (
        <section className="sidebar-section" aria-label="Queues now">
          <h3 className="section-title">Queues now</h3>
          <div className="queue-bars">
            {DIRECTIONS.map((dir) => {
              const q = m.currentQueueLengths[dir];
              return (
                <div key={dir} className="queue-row">
                  <span className="queue-dir">{DIR_LABEL[dir]}</span>
                  <div className="queue-bar-track" aria-hidden="true">
                    <div
                      className="queue-bar-fill"
                      style={{ width: `${String((q / maxQ) * 100)}%` }}
                    />
                  </div>
                  <span className="queue-val">
                    {q} <span className="sr-only">vehicles</span>
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {m ? (
        <MetricSections ctx={ctx} />
      ) : (
        <p className="sidebar-empty">
          Metrics appear once the simulation stream connects. Press Play to
          start a run.
        </p>
      )}

      {m && (
        <div className="sidebar-actions">
          <button
            type="button"
            className="pb-btn pb-secondary"
            onClick={handleDownload}
          >
            Download all metrics (CSV)
          </button>
        </div>
      )}
    </aside>
  );
};
