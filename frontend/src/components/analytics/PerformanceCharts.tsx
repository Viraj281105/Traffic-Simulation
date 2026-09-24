import { useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  ReferenceLine,
} from "recharts";
import type { ComparisonHistoryPoint } from "../../hooks/useLiveComparisonHistory";
import type { MetricContext } from "../../metrics/catalog";
import { formatMetric, METRICS } from "../../metrics/catalog";

interface PerformanceChartsProps {
  history: ComparisonHistoryPoint[];
  signalCtx: MetricContext;
  roundaboutCtx: MetricContext;
  compact?: boolean;
}

type PerformanceTab =
  | "delays"
  | "queuedTime"
  | "served"
  | "throughputRate"
  | "speed"
  | "reliability";

const SIGNAL_COLOR = "#f59e0b";
const ROUNDABOUT_COLOR = "#06b6d4";

const avgDelayDef = METRICS.find((m) => m.key === "averageDelay")!;
const medDelayDef = METRICS.find((m) => m.key === "medianDelay")!;
const p95DelayDef = METRICS.find((m) => m.key === "p95Delay")!;
const avgWaitDef = METRICS.find((m) => m.key === "averageWaitTime")!;
const servedDef = METRICS.find((m) => m.key === "throughput")!;
const throughputRateDef = METRICS.find((m) => m.key === "throughputRate")!;
const speedDef = METRICS.find((m) => m.key === "averageTravelSpeed")!;
const ptiDef = METRICS.find((m) => m.key === "travelTimeReliability")!;

export function PerformanceCharts({
  history,
  signalCtx,
  roundaboutCtx,
  compact = false,
}: PerformanceChartsProps) {
  const [activeTab, setActiveTab] = useState<PerformanceTab>("delays");

  const inWarmup = signalCtx.inWarmup || roundaboutCtx.inWarmup;

  // Current values (formatted without redundant unit suffix when header badge displays unit)
  const sigAvgDelay = formatMetric(avgDelayDef, signalCtx, false);
  const rndAvgDelay = formatMetric(avgDelayDef, roundaboutCtx, false);

  const sigMedDelay = formatMetric(medDelayDef, signalCtx);
  const rndMedDelay = formatMetric(medDelayDef, roundaboutCtx);

  const sigP95Delay = formatMetric(p95DelayDef, signalCtx);
  const rndP95Delay = formatMetric(p95DelayDef, roundaboutCtx);

  const sigWait = formatMetric(avgWaitDef, signalCtx, false);
  const rndWait = formatMetric(avgWaitDef, roundaboutCtx, false);

  const sigServed = formatMetric(servedDef, signalCtx, false);
  const rndServed = formatMetric(servedDef, roundaboutCtx, false);

  const sigThroughputRate = formatMetric(throughputRateDef, signalCtx, false);
  const rndThroughputRate = formatMetric(throughputRateDef, roundaboutCtx, false);

  const sigSpeed = formatMetric(speedDef, signalCtx, false);
  const rndSpeed = formatMetric(speedDef, roundaboutCtx, false);

  const sigPti = formatMetric(ptiDef, signalCtx, false);
  const rndPti = formatMetric(ptiDef, roundaboutCtx, false);

  const lowSampleSig = signalCtx.metrics?.travelTimeReliabilityLowSampleSize;
  const lowSampleRnd = roundaboutCtx.metrics?.travelTimeReliabilityLowSampleSize;

  return (
    <div className={`performance-analytics-section ${compact ? "compact" : ""}`}>
      {/* Warm-up banner if applicable */}
      {inWarmup && (
        <div className="analytics-warmup-notice" role="status">
          <span className="warmup-pulse-dot" />
          <span>
            <strong>Warm-up active:</strong> Exited vehicle delay &amp; rate metrics accumulate post-warmup (after 30s). Current speed and instantaneous telemetry remain live.
          </span>
        </div>
      )}

      {/* Primary Performance KPIs Grid */}
      <div className="perf-kpi-grid">
        <div
          className={`perf-kpi-card ${activeTab === "delays" ? "active" : ""}`}
          onClick={() => { setActiveTab("delays"); }}
          role="button"
          tabIndex={0}
        >
          <div className="kpi-header">
            <span className="kpi-label">Average Delay</span>
            <span className="kpi-unit">s</span>
          </div>
          <div className="kpi-values-row">
            <span className="kpi-val signal" title="Signal">{sigAvgDelay}</span>
            <span className="kpi-divider">vs</span>
            <span className="kpi-val roundabout" title="Roundabout">{rndAvgDelay}</span>
          </div>
          <div className="kpi-subtext">
            Median: {sigMedDelay} vs {rndMedDelay} · P95: {sigP95Delay} vs {rndP95Delay}
          </div>
        </div>

        <div
          className={`perf-kpi-card ${activeTab === "queuedTime" ? "active" : ""}`}
          onClick={() => { setActiveTab("queuedTime"); }}
          role="button"
          tabIndex={0}
        >
          <div className="kpi-header">
            <span className="kpi-label">Queued Time</span>
            <span className="kpi-unit">s</span>
          </div>
          <div className="kpi-values-row">
            <span className="kpi-val signal" title="Signal">{sigWait}</span>
            <span className="kpi-divider">vs</span>
            <span className="kpi-val roundabout" title="Roundabout">{rndWait}</span>
          </div>
          <div className="kpi-subtext">Mean time spent &lt; 0.5 m/s</div>
        </div>

        <div
          className={`perf-kpi-card ${activeTab === "served" ? "active" : ""}`}
          onClick={() => { setActiveTab("served"); }}
          role="button"
          tabIndex={0}
        >
          <div className="kpi-header">
            <span className="kpi-label">Vehicles Served</span>
            <span className="kpi-unit">veh</span>
          </div>
          <div className="kpi-values-row">
            <span className="kpi-val signal" title="Signal">{sigServed}</span>
            <span className="kpi-divider">vs</span>
            <span className="kpi-val roundabout" title="Roundabout">{rndServed}</span>
          </div>
          <div className="kpi-subtext">Cumulative post-warmup exits</div>
        </div>

        <div
          className={`perf-kpi-card ${activeTab === "throughputRate" ? "active" : ""}`}
          onClick={() => { setActiveTab("throughputRate"); }}
          role="button"
          tabIndex={0}
        >
          <div className="kpi-header">
            <span className="kpi-label">Throughput Rate</span>
            <span className="kpi-unit">veh/min</span>
          </div>
          <div className="kpi-values-row">
            <span className="kpi-val signal" title="Signal">{sigThroughputRate}</span>
            <span className="kpi-divider">vs</span>
            <span className="kpi-val roundabout" title="Roundabout">{rndThroughputRate}</span>
          </div>
          <div className="kpi-subtext">Rolling 60 s exit rate</div>
        </div>

        <div
          className={`perf-kpi-card ${activeTab === "speed" ? "active" : ""}`}
          onClick={() => { setActiveTab("speed"); }}
          role="button"
          tabIndex={0}
        >
          <div className="kpi-header">
            <span className="kpi-label">Mean Speed</span>
            <span className="kpi-unit">m/s</span>
          </div>
          <div className="kpi-values-row">
            <span className="kpi-val signal" title="Signal">{sigSpeed}</span>
            <span className="kpi-divider">vs</span>
            <span className="kpi-val roundabout" title="Roundabout">{rndSpeed}</span>
          </div>
          <div className="kpi-subtext">Current in-network mean</div>
        </div>

        <div
          className={`perf-kpi-card ${activeTab === "reliability" ? "active" : ""}`}
          onClick={() => { setActiveTab("reliability"); }}
          role="button"
          tabIndex={0}
        >
          <div className="kpi-header">
            <span className="kpi-label">Planning Time Index</span>
            <span className="kpi-unit">ratio</span>
          </div>
          <div className="kpi-values-row">
            <span className="kpi-val signal" title="Signal">{sigPti}</span>
            <span className="kpi-divider">vs</span>
            <span className="kpi-val roundabout" title="Roundabout">{rndPti}</span>
          </div>
          <div className="kpi-subtext">
            {lowSampleSig || lowSampleRnd ? (
              <span className="low-sample-warning" title="Fewer than 20 vehicles exited">⚠️ Low sample (n &lt; 20)</span>
            ) : (
              "P95 / Median travel time"
            )}
          </div>
        </div>
      </div>

      {/* Chart Selector Tabs */}
      <div className="chart-tab-bar">
        <button
          type="button"
          className={`chart-tab-btn ${activeTab === "delays" ? "active" : ""}`}
          onClick={() => { setActiveTab("delays"); }}
        >
          📈 Delay Dynamics (Avg, Median, P95)
        </button>
        <button
          type="button"
          className={`chart-tab-btn ${activeTab === "queuedTime" ? "active" : ""}`}
          onClick={() => { setActiveTab("queuedTime"); }}
        >
          ⏱️ Queued Time Trend
        </button>
        <button
          type="button"
          className={`chart-tab-btn ${activeTab === "served" ? "active" : ""}`}
          onClick={() => { setActiveTab("served"); }}
        >
          📊 Cumulative Vehicles Served
        </button>
        <button
          type="button"
          className={`chart-tab-btn ${activeTab === "throughputRate" ? "active" : ""}`}
          onClick={() => { setActiveTab("throughputRate"); }}
        >
          🚀 Throughput Rate
        </button>
        <button
          type="button"
          className={`chart-tab-btn ${activeTab === "speed" ? "active" : ""}`}
          onClick={() => { setActiveTab("speed"); }}
        >
          ⚡ Mean Travel Speed (m/s)
        </button>
        <button
          type="button"
          className={`chart-tab-btn ${activeTab === "reliability" ? "active" : ""}`}
          onClick={() => { setActiveTab("reliability"); }}
        >
          🎯 Planning Time Index (PTI)
        </button>
      </div>

      {/* Chart Canvas Area */}
      <div className="chart-canvas-card">
        {history.length === 0 ? (
          <div className="chart-empty-state">
            <p>Waiting for live stream data points…</p>
            <span className="chart-empty-sub">Time-series history starts plotting as the simulation advances.</span>
          </div>
        ) : (
          <div style={{ width: "100%", height: compact ? 220 : 280 }}>
            {activeTab === "delays" && (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={history} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                  <XAxis dataKey="timeFormatted" stroke="#8892b0" fontSize={11} />
                  <YAxis stroke="#8892b0" fontSize={11} unit=" s" />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#1e2230", borderColor: "#333c56", borderRadius: 8, fontSize: 12 }}
                  />
                  <Legend height={36} wrapperStyle={{ top: 0, fontSize: 11 }} />
                  <Line
                    type="monotone"
                    dataKey="signalAvgDelay"
                    name="Signal Avg Delay"
                    stroke={SIGNAL_COLOR}
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="roundaboutAvgDelay"
                    name="Roundabout Avg Delay"
                    stroke={ROUNDABOUT_COLOR}
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                  {!compact && (
                    <>
                      <Line
                        type="monotone"
                        dataKey="signalMedianDelay"
                        name="Signal Median"
                        stroke={SIGNAL_COLOR}
                        strokeDasharray="4 4"
                        strokeWidth={1.5}
                        dot={false}
                        isAnimationActive={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="roundaboutMedianDelay"
                        name="Roundabout Median"
                        stroke={ROUNDABOUT_COLOR}
                        strokeDasharray="4 4"
                        strokeWidth={1.5}
                        dot={false}
                        isAnimationActive={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="signalP95Delay"
                        name="Signal P95"
                        stroke="#fb7185"
                        strokeWidth={1.2}
                        dot={false}
                        isAnimationActive={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="roundaboutP95Delay"
                        name="Roundabout P95"
                        stroke="#38bdf8"
                        strokeWidth={1.2}
                        dot={false}
                        isAnimationActive={false}
                      />
                    </>
                  )}
                </LineChart>
              </ResponsiveContainer>
            )}

            {activeTab === "queuedTime" && (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={history} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                  <XAxis dataKey="timeFormatted" stroke="#8892b0" fontSize={11} />
                  <YAxis stroke="#8892b0" fontSize={11} unit=" s" />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#1e2230", borderColor: "#333c56", borderRadius: 8, fontSize: 12 }}
                  />
                  <Legend height={36} wrapperStyle={{ top: 0, fontSize: 11 }} />
                  <Line
                    type="monotone"
                    dataKey="signalAvgWait"
                    name="Signal Queued Time"
                    stroke={SIGNAL_COLOR}
                    strokeWidth={2.5}
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="roundaboutAvgWait"
                    name="Roundabout Queued Time"
                    stroke={ROUNDABOUT_COLOR}
                    strokeWidth={2.5}
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}

            {activeTab === "served" && (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={history} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="sigServedGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={SIGNAL_COLOR} stopOpacity={0.4} />
                      <stop offset="95%" stopColor={SIGNAL_COLOR} stopOpacity={0.0} />
                    </linearGradient>
                    <linearGradient id="rndServedGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={ROUNDABOUT_COLOR} stopOpacity={0.4} />
                      <stop offset="95%" stopColor={ROUNDABOUT_COLOR} stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                  <XAxis dataKey="timeFormatted" stroke="#8892b0" fontSize={11} />
                  <YAxis stroke="#8892b0" fontSize={11} unit=" veh" />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#1e2230", borderColor: "#333c56", borderRadius: 8, fontSize: 12 }}
                  />
                  <Legend height={36} wrapperStyle={{ top: 0, fontSize: 11 }} />
                  <Area
                    type="monotone"
                    dataKey="signalThroughput"
                    name="Signal Vehicles Served"
                    stroke={SIGNAL_COLOR}
                    fillOpacity={1}
                    fill="url(#sigServedGrad)"
                    strokeWidth={2}
                    isAnimationActive={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="roundaboutThroughput"
                    name="Roundabout Vehicles Served"
                    stroke={ROUNDABOUT_COLOR}
                    fillOpacity={1}
                    fill="url(#rndServedGrad)"
                    strokeWidth={2}
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}

            {activeTab === "throughputRate" && (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={history} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                  <XAxis dataKey="timeFormatted" stroke="#8892b0" fontSize={11} />
                  <YAxis stroke="#8892b0" fontSize={11} unit=" v/m" />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#1e2230", borderColor: "#333c56", borderRadius: 8, fontSize: 12 }}
                  />
                  <Legend height={36} wrapperStyle={{ top: 0, fontSize: 11 }} />
                  <Line
                    type="monotone"
                    dataKey="signalThroughputRate"
                    name="Signal Rate (veh/min)"
                    stroke={SIGNAL_COLOR}
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="roundaboutThroughputRate"
                    name="Roundabout Rate (veh/min)"
                    stroke={ROUNDABOUT_COLOR}
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}

            {activeTab === "speed" && (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={history} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                  <XAxis dataKey="timeFormatted" stroke="#8892b0" fontSize={11} />
                  <YAxis stroke="#8892b0" fontSize={11} unit=" m/s" domain={[0, "auto"]} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#1e2230", borderColor: "#333c56", borderRadius: 8, fontSize: 12 }}
                  />
                  <Legend height={36} wrapperStyle={{ top: 0, fontSize: 11 }} />
                  <ReferenceLine y={0.5} stroke="#ef4444" strokeDasharray="3 3" label={{ value: "Wait threshold (0.5 m/s)", fill: "#ef4444", fontSize: 10, position: "insideBottomRight" }} />
                  <Line
                    type="monotone"
                    dataKey="signalSpeed"
                    name="Signal Mean Speed (m/s)"
                    stroke={SIGNAL_COLOR}
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="roundaboutSpeed"
                    name="Roundabout Mean Speed (m/s)"
                    stroke={ROUNDABOUT_COLOR}
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}

            {activeTab === "reliability" && (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={history} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                  <XAxis dataKey="timeFormatted" stroke="#8892b0" fontSize={11} />
                  <YAxis stroke="#8892b0" fontSize={11} domain={[0.8, "auto"]} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#1e2230", borderColor: "#333c56", borderRadius: 8, fontSize: 12 }}
                  />
                  <Legend height={36} wrapperStyle={{ top: 0, fontSize: 11 }} />
                  <ReferenceLine y={1.0} stroke="#10b981" strokeDasharray="3 3" label={{ value: "Ideal Reliability (1.00)", fill: "#10b981", fontSize: 10, position: "insideBottomRight" }} />
                  <Line
                    type="monotone"
                    dataKey="signalPti"
                    name="Signal Planning Time Index"
                    stroke={SIGNAL_COLOR}
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="roundaboutPti"
                    name="Roundabout Planning Time Index"
                    stroke={ROUNDABOUT_COLOR}
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
