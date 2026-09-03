import React, { useState, useEffect, useCallback } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import { API_BASE_URL } from "../config";
import "./VolumeAnalysisDashboard.css";

// ── Types ──────────────────────────────────────────────────────────────────

interface SweepRun {
  arrivalRate: number;
  hourlyVolumeVehPerHour: number;
  winner: "signal" | "roundabout" | "tie";
  delayDeltaPercent: number;
  signal: { delay: number; throughput: number; queue: number };
  roundabout: { delay: number; throughput: number; queue: number };
}

interface SweepCurves {
  rates: number[];
  volumesVehPerHour: number[];
  signal: { delays: number[]; throughputs: number[]; queues: number[] };
  roundabout: { delays: number[]; throughputs: number[]; queues: number[] };
  crossoverArrivalRate: number | null;
  crossoverHourlyVolume: number | null;
}

interface SweepSession {
  sessionId: string;
  name: string;
  duration: number;
  randomSeed: number;
  curves: SweepCurves;
  runs: SweepRun[];
}

interface SavedSweep {
  id: string;
  name: string;
  created_at: string;
}

// ── Chart data builder ──────────────────────────────────────────────────────

function buildChartData(session: SweepSession) {
  return session.runs.map((run) => ({
    volume: run.hourlyVolumeVehPerHour,
    rate: run.arrivalRate,
    signalDelay: run.signal.delay,
    roundaboutDelay: run.roundabout.delay,
    signalThroughput: run.signal.throughput,
    roundaboutThroughput: run.roundabout.throughput,
    signalQueue: run.signal.queue,
    roundaboutQueue: run.roundabout.queue,
  }));
}

// ── Custom Tooltip ──────────────────────────────────────────────────────────

const CustomTooltip = ({
  active,
  payload,
  label,
  unit = "",
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: number;
  unit?: string;
}) => {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div
      style={{
        background: "#1a2a3d",
        border: "1px solid #2a3d56",
        borderRadius: 8,
        padding: "8px 12px",
        fontSize: 12,
      }}
    >
      <p style={{ margin: "0 0 4px", color: "#888" }}>Vol: {label} veh/h</p>
      {payload.map((p) => (
        <p key={p.name} style={{ margin: "2px 0", color: p.color }}>
          {p.name}:{" "}
          <strong>
            {p.value.toFixed(2)}
            {unit}
          </strong>
        </p>
      ))}
    </div>
  );
};

// ── Main Component ──────────────────────────────────────────────────────────

export const VolumeAnalysisDashboard: React.FC = () => {
  const [savedSweeps, setSavedSweeps] = useState<SavedSweep[]>([]);
  const [activeSession, setActiveSession] = useState<SweepSession | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Sweep config form state
  const [sweepDuration, setSweepDuration] = useState(60);
  const [randomSeed, setRandomSeed] = useState(42);

  const [isRunning, setIsRunning] = useState(false);
  const [sweepError, setSweepError] = useState<string | null>(null);
  const [loadingSession, setLoadingSession] = useState(false);

  // Fetch saved sweep list
  const fetchSweeps = useCallback(() => {
    fetch(`${API_BASE_URL}/api/v1/study/sweeps`)
      .then((r) => r.json())
      .then((data: SavedSweep[]) => {
        setSavedSweeps(data);
      })
      .catch(() => {
        setSavedSweeps([]);
      });
  }, []);

  useEffect(() => {
    fetchSweeps();
  }, [fetchSweeps]);

  // Load a specific sweep session
  const loadSweep = (id: string) => {
    setSelectedId(id);
    setLoadingSession(true);
    fetch(`${API_BASE_URL}/api/v1/study/sweeps/${id}`)
      .then((r) => r.json())
      .then((data: SweepSession) => {
        setActiveSession(data);
        setLoadingSession(false);
      })
      .catch(() => {
        setLoadingSession(false);
        setSweepError("Failed to load sweep results.");
      });
  };

  // Trigger new sweep via API
  const runSweep = () => {
    setIsRunning(true);
    setSweepError(null);
    fetch(`${API_BASE_URL}/api/v1/study/sweeps/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        duration: sweepDuration,
        random_seed: randomSeed,
        time_step: 0.1,
      }),
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status.toString()}`);
        return r.json() as Promise<SweepSession>;
      })
      .then((data) => {
        setActiveSession(data);
        setSelectedId(data.sessionId);
        setIsRunning(false);
        fetchSweeps();
      })
      .catch((e: unknown) => {
        setSweepError(e instanceof Error ? e.message : "Sweep failed");
        setIsRunning(false);
      });
  };

  const chartData = activeSession ? buildChartData(activeSession) : [];
  const crossover = activeSession?.curves.crossoverHourlyVolume ?? null;

  return (
    <div className="volume-dashboard">
      {/* ── Trigger Panel ─────────────────────────────── */}
      <div className="sweep-trigger-panel">
        <h3>📊 Run Volume Sweep Experiment</h3>
        <div className="sweep-controls">
          <div className="sweep-field">
            <label>Duration (s)</label>
            <input
              type="number"
              min={10}
              max={600}
              step={10}
              value={sweepDuration}
              onChange={(e) => {
                setSweepDuration(Number(e.target.value));
              }}
            />
          </div>
          <div className="sweep-field">
            <label>Random Seed</label>
            <input
              type="number"
              min={1}
              value={randomSeed}
              onChange={(e) => {
                setRandomSeed(Number(e.target.value));
              }}
            />
          </div>
          <div className="sweep-field" style={{ opacity: 0.5 }}>
            <label>Rates Evaluated</label>
            <input type="number" value={8} disabled readOnly />
          </div>
          <button
            className="sweep-run-btn"
            onClick={runSweep}
            disabled={isRunning}
          >
            {isRunning ? "⏳ Running..." : "▶ Run Sweep"}
          </button>
        </div>
        {sweepError && <div className="sweep-error">⚠ {sweepError}</div>}
        {isRunning && (
          <div className="sweep-loading">
            <div className="spin" />
            Running 8 arrival rates — this may take 10–60s…
          </div>
        )}
      </div>

      {/* ── Saved Sweeps ──────────────────────────────── */}
      {savedSweeps.length > 0 && (
        <div className="saved-sweeps-panel">
          <h3>📁 Saved Sweeps</h3>
          <div className="sweep-list">
            {savedSweeps.map((s) => (
              <div
                key={s.id}
                className={`sweep-list-item ${selectedId === s.id ? "active" : ""}`}
                onClick={() => {
                  loadSweep(s.id);
                }}
              >
                <span className="sweep-name">{s.name}</span>
                <span className="sweep-meta">
                  {new Date(s.created_at).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Loading ───────────────────────────────────── */}
      {loadingSession && (
        <div className="sweep-loading">
          <div className="spin" />
          Loading sweep results…
        </div>
      )}

      {/* ── Results ───────────────────────────────────── */}
      {activeSession && !loadingSession && (
        <>
          {/* Crossover badge */}
          {crossover ? (
            <div className="crossover-badge">
              <span className="crossover-icon">⭐</span>
              <div className="crossover-text">
                <strong>
                  Critical Saturation Crossover: {crossover.toLocaleString()}{" "}
                  veh/h
                </strong>
                <br />
                <span>
                  Below this volume: Roundabout outperforms Signal (lower
                  delay). Above this volume: Signal provides better queue
                  stability and fairness.
                </span>
              </div>
            </div>
          ) : (
            <div
              className="crossover-badge"
              style={{
                borderColor: "rgba(136,136,136,0.2)",
                background: "rgba(136,136,136,0.05)",
              }}
            >
              <span className="crossover-icon">ℹ</span>
              <div className="crossover-text">
                <span>
                  No crossover point detected within the evaluated volume range.
                  Roundabout maintained advantage across all tested rates.
                </span>
              </div>
            </div>
          )}

          {/* Charts row */}
          <div className="charts-row">
            {/* Delay Chart */}
            <div className="chart-card">
              <h4>Average Delay vs. Traffic Volume</h4>
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart
                    data={chartData}
                    margin={{ top: 4, right: 8, bottom: 4, left: 0 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="rgba(255,255,255,0.06)"
                    />
                    <XAxis
                      dataKey="volume"
                      tick={{ fontSize: 10, fill: "#666" }}
                      tickFormatter={(v: number) => v.toString()}
                      label={{
                        value: "veh/h",
                        position: "insideBottom",
                        offset: -2,
                        fill: "#555",
                        fontSize: 10,
                      }}
                    />
                    <YAxis tick={{ fontSize: 10, fill: "#666" }} />
                    <Tooltip content={<CustomTooltip unit="s" />} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    {crossover && (
                      <ReferenceLine
                        x={crossover}
                        stroke="#ffd93d"
                        strokeDasharray="4 2"
                        label={{
                          value: "Crossover",
                          position: "top",
                          fill: "#ffd93d",
                          fontSize: 10,
                        }}
                      />
                    )}
                    <Line
                      type="monotone"
                      dataKey="signalDelay"
                      name="Signal"
                      stroke="#4d96ff"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="roundaboutDelay"
                      name="Roundabout"
                      stroke="#2ecc40"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="chart-empty">No data yet</div>
              )}
            </div>

            {/* Throughput Chart */}
            <div className="chart-card">
              <h4>Throughput vs. Traffic Volume</h4>
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart
                    data={chartData}
                    margin={{ top: 4, right: 8, bottom: 4, left: 0 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="rgba(255,255,255,0.06)"
                    />
                    <XAxis
                      dataKey="volume"
                      tick={{ fontSize: 10, fill: "#666" }}
                      label={{
                        value: "veh/h",
                        position: "insideBottom",
                        offset: -2,
                        fill: "#555",
                        fontSize: 10,
                      }}
                    />
                    <YAxis tick={{ fontSize: 10, fill: "#666" }} />
                    <Tooltip content={<CustomTooltip unit=" veh" />} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    {crossover && (
                      <ReferenceLine
                        x={crossover}
                        stroke="#ffd93d"
                        strokeDasharray="4 2"
                      />
                    )}
                    <Line
                      type="monotone"
                      dataKey="signalThroughput"
                      name="Signal"
                      stroke="#4d96ff"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="roundaboutThroughput"
                      name="Roundabout"
                      stroke="#2ecc40"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="chart-empty">No data yet</div>
              )}
            </div>

            {/* Queue Chart */}
            <div className="chart-card">
              <h4>Average Queue Length vs. Traffic Volume</h4>
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart
                    data={chartData}
                    margin={{ top: 4, right: 8, bottom: 4, left: 0 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="rgba(255,255,255,0.06)"
                    />
                    <XAxis
                      dataKey="volume"
                      tick={{ fontSize: 10, fill: "#666" }}
                      label={{
                        value: "veh/h",
                        position: "insideBottom",
                        offset: -2,
                        fill: "#555",
                        fontSize: 10,
                      }}
                    />
                    <YAxis tick={{ fontSize: 10, fill: "#666" }} />
                    <Tooltip content={<CustomTooltip unit=" veh" />} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    {crossover && (
                      <ReferenceLine
                        x={crossover}
                        stroke="#ffd93d"
                        strokeDasharray="4 2"
                      />
                    )}
                    <Line
                      type="monotone"
                      dataKey="signalQueue"
                      name="Signal"
                      stroke="#4d96ff"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="roundaboutQueue"
                      name="Roundabout"
                      stroke="#2ecc40"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="chart-empty">No data yet</div>
              )}
            </div>
          </div>

          {/* Summary table */}
          <div className="sweep-summary-table">
            <h4>Volume Sweep Results: {activeSession.name}</h4>
            <table>
              <thead>
                <tr>
                  <th>Rate (veh/s)</th>
                  <th>Vol (veh/h)</th>
                  <th>Sig Delay (s)</th>
                  <th>Rnd Delay (s)</th>
                  <th>Sig Tput</th>
                  <th>Rnd Tput</th>
                  <th>Sig Queue</th>
                  <th>Rnd Queue</th>
                  <th>Winner</th>
                  <th>Δ Delay</th>
                </tr>
              </thead>
              <tbody>
                {activeSession.runs.map((run) => (
                  <tr key={run.arrivalRate}>
                    <td>{run.arrivalRate.toFixed(2)}</td>
                    <td>{run.hourlyVolumeVehPerHour.toLocaleString()}</td>
                    <td>{run.signal.delay.toFixed(2)}</td>
                    <td>{run.roundabout.delay.toFixed(2)}</td>
                    <td>{run.signal.throughput}</td>
                    <td>{run.roundabout.throughput}</td>
                    <td>{run.signal.queue.toFixed(1)}</td>
                    <td>{run.roundabout.queue.toFixed(1)}</td>
                    <td>
                      <span
                        className={
                          run.winner === "roundabout"
                            ? "winner-roundabout"
                            : run.winner === "signal"
                              ? "winner-signal"
                              : "winner-tie"
                        }
                      >
                        {run.winner === "roundabout"
                          ? "🔄 Roundabout"
                          : run.winner === "signal"
                            ? "🚦 Signal"
                            : "— Tie"}
                      </span>
                    </td>
                    <td
                      style={{
                        color:
                          run.delayDeltaPercent > 0
                            ? "#2ecc40"
                            : run.delayDeltaPercent < 0
                              ? "#ff6b6b"
                              : "#888",
                      }}
                    >
                      {run.delayDeltaPercent > 0 ? "+" : ""}
                      {run.delayDeltaPercent.toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
};
