import React from "react";
import type { LiveSnapshot, RunningMetrics, SignalDirection } from "../types/simulation";
import type { ConnectionStatus } from "../services/websocket";

interface MetricsSidebarProps {
  snapshot: LiveSnapshot | null;
  connectionStatus: ConnectionStatus;
}

const DIRECTIONS: SignalDirection[] = ["north", "south", "east", "west"];
const DIR_LABEL: Record<SignalDirection, string> = {
  north: "N",
  south: "S",
  east: "E",
  west: "W",
};

function fmt(val: number | undefined, decimals = 1): string {
  if (val === undefined || val === null || isNaN(val)) return "—";
  return val.toFixed(decimals);
}

function metricColor(value: number, low: number, high: number): string {
  if (value <= low) return "#2ecc40";
  if (value >= high) return "#ff4136";
  return "#ffdc00";
}

const CONNECTION_LABELS: Record<ConnectionStatus, { label: string; color: string }> = {
  connected: { label: "● LIVE", color: "#2ecc40" },
  connecting: { label: "◌ CONNECTING", color: "#ffdc00" },
  reconnecting: { label: "↻ RECONNECTING", color: "#ff922b" },
  disconnected: { label: "○ OFFLINE", color: "#888" },
  error: { label: "✕ ERROR", color: "#ff4136" },
};

export const MetricsSidebar: React.FC<MetricsSidebarProps> = ({
  snapshot,
  connectionStatus,
}) => {
  const m: RunningMetrics | undefined = snapshot?.metrics;
  const vc = snapshot?.vehicleCounts;
  const conn = CONNECTION_LABELS[connectionStatus];

  const maxQ = Math.max(
    ...DIRECTIONS.map((d) => m?.currentQueueLengths?.[d] ?? 0),
    1,
  );

  return (
    <aside className="metrics-sidebar">
      {/* Header */}
      <div className="sidebar-header">
        <h2 className="sidebar-title">Live Metrics</h2>
        <span className="conn-badge" style={{ color: conn.color }}>
          {conn.label}
        </span>
      </div>

      {/* Controller type */}
      {snapshot?.controller && (
        <div className="controller-chip">
          {snapshot.controller.type === "fixed_time_signal"
            ? "🚦 Fixed-Time Signal"
            : "🔄 Roundabout"}
        </div>
      )}

      {/* Vehicle state breakdown */}
      <section className="sidebar-section">
        <h3 className="section-title">Vehicles</h3>
        <div className="vehicle-chips">
          <VehicleChip label="Active" value={vc?.active} color="#4d96ff" />
          <VehicleChip label="Approaching" value={vc?.approaching} color="#20c997" />
          <VehicleChip label="Waiting" value={vc?.waiting} color="#ff6b6b" />
          <VehicleChip label="Crossing" value={vc?.crossing} color="#ffd93d" />
          {(vc?.inRoundabout ?? 0) > 0 && (
            <VehicleChip label="In Ring" value={vc?.inRoundabout} color="#cc5de8" />
          )}
          <VehicleChip label="Exited" value={vc?.exited} color="#888" />
        </div>
      </section>

      {/* Queue lengths */}
      <section className="sidebar-section">
        <h3 className="section-title">Queue Lengths</h3>
        <div className="queue-bars">
          {DIRECTIONS.map((dir) => {
            const q = m?.currentQueueLengths?.[dir] ?? 0;
            const pct = Math.min((q / maxQ) * 100, 100);
            const color = metricColor(q, 3, 8);
            return (
              <div key={dir} className="queue-row">
                <span className="queue-dir">{DIR_LABEL[dir]}</span>
                <div className="queue-bar-track">
                  <div
                    className="queue-bar-fill"
                    style={{ width: `${pct}%`, background: color }}
                  />
                </div>
                <span className="queue-val">{q}</span>
              </div>
            );
          })}
        </div>
      </section>

      {/* Key metrics */}
      <section className="sidebar-section">
        <h3 className="section-title">Performance</h3>
        <div className="metric-rows">
          <MetricRow
            label="Avg Wait Time"
            value={`${fmt(m?.averageWaitTime)}s`}
            color={metricColor(m?.averageWaitTime ?? 0, 15, 40)}
          />
          <MetricRow
            label="Throughput"
            value={`${fmt(m?.throughput, 0)} veh`}
            color="#4d96ff"
          />
          <MetricRow
            label="Throughput Rate"
            value={`${fmt(m?.throughputRate)} /min`}
            color="#20c997"
          />
          <MetricRow
            label="Max Queue"
            value={`${fmt(m?.maxQueueLength, 0)} veh`}
            color={metricColor(m?.maxQueueLength ?? 0, 5, 12)}
          />
          <MetricRow
            label="Avg Stops/Veh"
            value={fmt(m?.averageStopsPerVehicle)}
            color={metricColor(m?.averageStopsPerVehicle ?? 0, 1, 3)}
          />
          <MetricRow
            label="Speed Variance"
            value={fmt(m?.speedVarianceIndex)}
            color={metricColor(m?.speedVarianceIndex ?? 0, 0.3, 0.7)}
          />
          <MetricRow
            label="Travel Reliability"
            value={fmt(m?.travelTimeReliability)}
            color={metricColor(m?.travelTimeReliability ?? 0, 1.2, 2.0)}
          />
          <MetricRow
            label="Fairness Index"
            value={fmt(m?.directionalFairnessIndex)}
            color={metricColor(1 - (m?.directionalFairnessIndex ?? 1), 0, 0.2)}
          />
          <MetricRow
            label="Idle Loss"
            value={fmt(m?.idleOpportunityLoss)}
            color={metricColor(m?.idleOpportunityLoss ?? 0, 0.05, 0.2)}
          />
          <MetricRow
            label="Total Spawned"
            value={`${fmt(m?.totalVehiclesSpawned, 0)}`}
            color="#888"
          />
        </div>
      </section>

      {/* Signal phase info */}
      {snapshot?.controller?.type === "fixed_time_signal" && (
        <section className="sidebar-section">
          <h3 className="section-title">Signal Phase</h3>
          <div className="phase-info">
            <span className="phase-name">
              {snapshot.controller.currentPhase?.replace(/_/g, " ").toUpperCase()}
            </span>
            <span className="phase-timer">
              {fmt(snapshot.controller.phaseTimeRemaining)}s left
            </span>
          </div>
          <div className="signal-heads">
            {snapshot.controller.signals.map((sig) => (
              <div key={sig.direction} className="signal-head-item">
                <div
                  className="signal-dot"
                  style={{
                    background: sig.color === "green"
                      ? "#2ecc40"
                      : sig.color === "yellow"
                        ? "#ffdc00"
                        : "#ff4136",
                    boxShadow: `0 0 8px ${sig.color === "green" ? "#2ecc40" : sig.color === "yellow" ? "#ffdc00" : "#ff4136"}`,
                  }}
                />
                <span>{DIR_LABEL[sig.direction as SignalDirection]}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Roundabout info */}
      {snapshot?.controller?.type === "roundabout" && (
        <section className="sidebar-section">
          <h3 className="section-title">Roundabout</h3>
          <div className="metric-rows">
            <MetricRow
              label="Circulating"
              value={`${snapshot.controller.circulatingCount} veh`}
              color="#cc5de8"
            />
            <MetricRow
              label="Yielding"
              value={`${snapshot.controller.yieldingCount} veh`}
              color="#ff922b"
            />
            <MetricRow
              label="Gap Acceptance"
              value={`${fmt(snapshot.controller.gapAcceptance)}s`}
              color="#4d96ff"
            />
          </div>
        </section>
      )}
    </aside>
  );
};

// ── Sub-components ────────────────────────────────────────────────────────────

function VehicleChip({
  label,
  value,
  color,
}: {
  label: string;
  value: number | undefined;
  color: string;
}) {
  return (
    <div className="vehicle-chip" style={{ borderColor: color }}>
      <span className="chip-count" style={{ color }}>
        {value ?? 0}
      </span>
      <span className="chip-label">{label}</span>
    </div>
  );
}

function MetricRow({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="metric-row">
      <span className="metric-label">{label}</span>
      <span className="metric-value" style={{ color }}>
        {value}
      </span>
    </div>
  );
}
