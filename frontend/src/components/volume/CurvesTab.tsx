import { Car, ChartColumn, ChartSpline, Ruler, Timer } from "lucide-react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CHART_AXIS, CHART_GRID } from "../../theme/chart";
import type { SweepChartRow } from "../volumeSweepModel";
import { SweepTooltip, type XAxisMode } from "./SweepTooltip";

export type MetricView = "all" | "delay" | "throughput" | "queue";

interface CurvesTabProps {
  chartData: SweepChartRow[];
  crossover: number | null;
  metricView: MetricView;
  onMetricViewChange: (view: MetricView) => void;
  xAxisMode: XAxisMode;
  onXAxisModeChange: (mode: XAxisMode) => void;
  showUncertaintyBands: boolean;
  onShowUncertaintyBandsChange: (show: boolean) => void;
  showDeltaTrend: boolean;
  onShowDeltaTrendChange: (show: boolean) => void;
}

/** Studio tab 1: delay, throughput and queue curves against demand, with the
 *  crossover marked and an optional relative-delta chart. */
export function CurvesTab({
  chartData,
  crossover,
  metricView,
  onMetricViewChange,
  xAxisMode,
  onXAxisModeChange,
  showUncertaintyBands,
  onShowUncertaintyBandsChange,
  showDeltaTrend,
  onShowDeltaTrendChange,
}: CurvesTabProps) {
  const xDataKey = xAxisMode === "volume" ? "volume" : "rate";

  return (
    <div className="chart-studio-container">
      {/* Integrated Chart Header Controls */}
      <div className="chart-studio-header">
        <div className="chart-studio-title">
          <h4>
            {metricView === "delay" && "Average Delay vs. Traffic Volume"}
            {metricView === "throughput" && "Throughput vs. Traffic Volume"}
            {metricView === "queue" &&
              "Average Queue Length vs. Traffic Volume"}
            {metricView === "all" &&
              "All Performance Envelopes (Delay · Throughput · Queue)"}
          </h4>
          <p className="chart-studio-subtitle">
            {metricView === "delay" &&
              "Vehicular control delay comparison across demand tiers (HCM 6th Edition)"}
            {metricView === "throughput" &&
              "Total vehicles cleared through intersection per simulation interval"}
            {metricView === "queue" &&
              "Mean standing queue depth per approach lane across volume levels"}
            {metricView === "all" &&
              "Side-by-side telemetry across all operational dimensions"}
          </p>
        </div>

        <div className="chart-studio-controls">
          <div className="volume-chart-metric-pills">
            <button
              type="button"
              className={`volume-metric-pill-btn ${metricView === "delay" ? "active" : ""}`}
              onClick={() => {
                onMetricViewChange("delay");
              }}
            >
              <Timer size={14} aria-hidden="true" className="uf-glyph" /> Delay
            </button>
            <button
              type="button"
              className={`volume-metric-pill-btn ${metricView === "throughput" ? "active" : ""}`}
              onClick={() => {
                onMetricViewChange("throughput");
              }}
            >
              <Car size={14} aria-hidden="true" className="uf-glyph" />{" "}
              Throughput
            </button>
            <button
              type="button"
              className={`volume-metric-pill-btn ${metricView === "queue" ? "active" : ""}`}
              onClick={() => {
                onMetricViewChange("queue");
              }}
            >
              <Ruler size={14} aria-hidden="true" className="uf-glyph" /> Queue
            </button>
            <button
              type="button"
              className={`volume-metric-pill-btn ${metricView === "all" ? "active" : ""}`}
              onClick={() => {
                onMetricViewChange("all");
              }}
            >
              <ChartColumn size={14} aria-hidden="true" className="uf-glyph" />{" "}
              All 3
            </button>
          </div>

          <div className="chart-option-pills">
            <button
              type="button"
              className={`option-pill-btn ${showUncertaintyBands ? "active" : ""}`}
              onClick={() => {
                onShowUncertaintyBandsChange(!showUncertaintyBands);
              }}
              title="Toggle spread bands: how much individual drivers' delays varied within each run (±σ and min–max). This is not uncertainty about the average."
            >
              ± Driver spread
            </button>
            <button
              type="button"
              className={`option-pill-btn ${showDeltaTrend ? "active" : ""}`}
              onClick={() => {
                onShowDeltaTrendChange(!showDeltaTrend);
              }}
              title="Toggle relative percentage delta comparison curve"
            >
              % Delta Trend
            </button>
          </div>

          <div className="chart-axis-pills">
            <button
              type="button"
              className={`axis-pill-btn ${xAxisMode === "volume" ? "active" : ""}`}
              onClick={() => {
                onXAxisModeChange("volume");
              }}
            >
              veh/h
            </button>
            <button
              type="button"
              className={`axis-pill-btn ${xAxisMode === "rate" ? "active" : ""}`}
              onClick={() => {
                onXAxisModeChange("rate");
              }}
            >
              veh/s
            </button>
          </div>
        </div>
      </div>

      {/* Charts Grid */}
      <div className={`charts-grid view-${metricView}`}>
        {/* Delay Chart */}
        {(metricView === "all" || metricView === "delay") && (
          <div className="chart-card">
            {metricView === "all" && (
              <div className="chart-card-mini-header">
                <span className="mini-title">
                  <Timer size={14} aria-hidden="true" className="uf-glyph" />{" "}
                  Control Delay (s)
                </span>
                <span className="mini-unit">s / vehicle</span>
              </div>
            )}
            {chartData.length > 0 ? (
              <ResponsiveContainer
                width="100%"
                height={metricView === "all" ? 280 : 400}
              >
                <LineChart
                  data={chartData}
                  margin={{ top: 16, right: 24, bottom: 12, left: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                  <XAxis
                    dataKey={xDataKey}
                    tick={{
                      fontSize: 12,
                      fill: "hsl(var(--muted-foreground))",
                    }}
                    tickFormatter={(v: number) => v.toString()}
                    label={{
                      value:
                        xAxisMode === "volume"
                          ? "Hourly Volume (veh/h)"
                          : "Arrival Rate (veh/s)",
                      position: "insideBottom",
                      offset: -6,
                      fill: "hsl(var(--muted-foreground))",
                      fontSize: 12,
                    }}
                  />
                  <YAxis
                    tick={{
                      fontSize: 12,
                      fill: "hsl(var(--muted-foreground))",
                    }}
                    label={{
                      value: "Delay (s)",
                      angle: -90,
                      position: "insideLeft",
                      offset: 8,
                      fill: "hsl(var(--muted-foreground))",
                      fontSize: 12,
                    }}
                  />
                  <Tooltip
                    content={<SweepTooltip unit="s" xMode={xAxisMode} />}
                  />
                  <Legend wrapperStyle={{ fontSize: 13, paddingTop: 10 }} />
                  {crossover && xAxisMode === "volume" && (
                    <ReferenceLine
                      x={crossover}
                      stroke="#f59e0b"
                      strokeDasharray="4 3"
                      strokeWidth={2}
                      label={{
                        value: `Crossover (${crossover.toLocaleString()} veh/h)`,
                        position: "top",
                        fill: "#f59e0b",
                        fontSize: 12,
                      }}
                    />
                  )}
                  <Line
                    type="monotone"
                    dataKey="signalDelay"
                    name="Fixed-Time Signal"
                    stroke="#38bdf8"
                    strokeWidth={3}
                    dot={{ r: 5, fill: "#38bdf8" }}
                    activeDot={{
                      r: 8,
                      stroke: "#7dd3fc",
                      strokeWidth: 2,
                    }}
                    animationDuration={450}
                    animationEasing="ease-out"
                  />
                  <Line
                    type="monotone"
                    dataKey="roundaboutDelay"
                    name="Modern Roundabout"
                    stroke="#10b981"
                    strokeWidth={3}
                    dot={{ r: 5, fill: "#10b981" }}
                    activeDot={{
                      r: 8,
                      stroke: "#34d399",
                      strokeWidth: 2,
                    }}
                    animationDuration={450}
                    animationEasing="ease-out"
                  />
                  {showUncertaintyBands && (
                    <>
                      <Line
                        type="monotone"
                        dataKey="signalDelayMax"
                        name="Signal driver spread, upper (max / +σ)"
                        stroke="#38bdf8"
                        strokeDasharray="3 3"
                        strokeOpacity={0.4}
                        strokeWidth={1.5}
                        dot={false}
                        activeDot={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="signalDelayMin"
                        name="Signal driver spread, lower (min / −σ)"
                        stroke="#38bdf8"
                        strokeDasharray="2 2"
                        strokeOpacity={0.3}
                        strokeWidth={1.2}
                        dot={false}
                        activeDot={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="roundaboutDelayMax"
                        name="Roundabout driver spread, upper (max / +σ)"
                        stroke="#10b981"
                        strokeDasharray="3 3"
                        strokeOpacity={0.4}
                        strokeWidth={1.5}
                        dot={false}
                        activeDot={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="roundaboutDelayMin"
                        name="Roundabout driver spread, lower (min / −σ)"
                        stroke="#10b981"
                        strokeDasharray="2 2"
                        strokeOpacity={0.3}
                        strokeWidth={1.2}
                        dot={false}
                        activeDot={false}
                      />
                    </>
                  )}
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="chart-empty">No telemetry data recorded</div>
            )}
          </div>
        )}

        {/* Throughput Chart */}
        {(metricView === "all" || metricView === "throughput") && (
          <div className="chart-card">
            {metricView === "all" && (
              <div className="chart-card-mini-header">
                <span className="mini-title">
                  <Car size={14} aria-hidden="true" className="uf-glyph" />{" "}
                  Throughput
                </span>
                <span className="mini-unit">completed veh</span>
              </div>
            )}
            {chartData.length > 0 ? (
              <ResponsiveContainer
                width="100%"
                height={metricView === "all" ? 280 : 400}
              >
                <LineChart
                  data={chartData}
                  margin={{ top: 16, right: 24, bottom: 12, left: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                  <XAxis
                    dataKey={xDataKey}
                    tick={{
                      fontSize: 12,
                      fill: "hsl(var(--muted-foreground))",
                    }}
                    tickFormatter={(v: number) => v.toString()}
                    label={{
                      value:
                        xAxisMode === "volume"
                          ? "Hourly Volume (veh/h)"
                          : "Arrival Rate (veh/s)",
                      position: "insideBottom",
                      offset: -6,
                      fill: "hsl(var(--muted-foreground))",
                      fontSize: 12,
                    }}
                  />
                  <YAxis
                    tick={{
                      fontSize: 12,
                      fill: "hsl(var(--muted-foreground))",
                    }}
                    label={{
                      value: "Throughput (veh)",
                      angle: -90,
                      position: "insideLeft",
                      offset: 8,
                      fill: "hsl(var(--muted-foreground))",
                      fontSize: 12,
                    }}
                  />
                  <Tooltip
                    content={<SweepTooltip unit=" veh" xMode={xAxisMode} />}
                  />
                  <Legend wrapperStyle={{ fontSize: 13, paddingTop: 10 }} />
                  {crossover && xAxisMode === "volume" && (
                    <ReferenceLine
                      x={crossover}
                      stroke="#f59e0b"
                      strokeDasharray="4 3"
                      strokeWidth={2}
                    />
                  )}
                  <Line
                    type="monotone"
                    dataKey="signalThroughput"
                    name="Fixed-Time Signal"
                    stroke="#38bdf8"
                    strokeWidth={3}
                    dot={{ r: 5, fill: "#38bdf8" }}
                    activeDot={{
                      r: 8,
                      stroke: "#7dd3fc",
                      strokeWidth: 2,
                    }}
                    animationDuration={450}
                    animationEasing="ease-out"
                  />
                  <Line
                    type="monotone"
                    dataKey="roundaboutThroughput"
                    name="Modern Roundabout"
                    stroke="#10b981"
                    strokeWidth={3}
                    dot={{ r: 5, fill: "#10b981" }}
                    activeDot={{
                      r: 8,
                      stroke: "#34d399",
                      strokeWidth: 2,
                    }}
                    animationDuration={450}
                    animationEasing="ease-out"
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="chart-empty">No telemetry data recorded</div>
            )}
          </div>
        )}

        {/* Queue Chart */}
        {(metricView === "all" || metricView === "queue") && (
          <div className="chart-card">
            {metricView === "all" && (
              <div className="chart-card-mini-header">
                <span className="mini-title">
                  <Ruler size={14} aria-hidden="true" className="uf-glyph" />{" "}
                  Queue Length
                </span>
                <span className="mini-unit">avg veh / lane</span>
              </div>
            )}
            {chartData.length > 0 ? (
              <ResponsiveContainer
                width="100%"
                height={metricView === "all" ? 280 : 400}
              >
                <LineChart
                  data={chartData}
                  margin={{ top: 16, right: 24, bottom: 12, left: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                  <XAxis
                    dataKey={xDataKey}
                    tick={{
                      fontSize: 12,
                      fill: "hsl(var(--muted-foreground))",
                    }}
                    tickFormatter={(v: number) => v.toString()}
                    label={{
                      value:
                        xAxisMode === "volume"
                          ? "Hourly Volume (veh/h)"
                          : "Arrival Rate (veh/s)",
                      position: "insideBottom",
                      offset: -6,
                      fill: "hsl(var(--muted-foreground))",
                      fontSize: 12,
                    }}
                  />
                  <YAxis
                    tick={{
                      fontSize: 12,
                      fill: "hsl(var(--muted-foreground))",
                    }}
                    label={{
                      value: "Queue (veh)",
                      angle: -90,
                      position: "insideLeft",
                      offset: 8,
                      fill: "hsl(var(--muted-foreground))",
                      fontSize: 12,
                    }}
                  />
                  <Tooltip
                    content={<SweepTooltip unit=" veh" xMode={xAxisMode} />}
                  />
                  <Legend wrapperStyle={{ fontSize: 13, paddingTop: 10 }} />
                  {crossover && xAxisMode === "volume" && (
                    <ReferenceLine
                      x={crossover}
                      stroke="#f59e0b"
                      strokeDasharray="4 3"
                      strokeWidth={2}
                    />
                  )}
                  <Line
                    type="monotone"
                    dataKey="signalQueue"
                    name="Fixed-Time Signal"
                    stroke="#38bdf8"
                    strokeWidth={3}
                    dot={{ r: 5, fill: "#38bdf8" }}
                    activeDot={{
                      r: 8,
                      stroke: "#7dd3fc",
                      strokeWidth: 2,
                    }}
                    animationDuration={450}
                    animationEasing="ease-out"
                  />
                  <Line
                    type="monotone"
                    dataKey="roundaboutQueue"
                    name="Modern Roundabout"
                    stroke="#10b981"
                    strokeWidth={3}
                    dot={{ r: 5, fill: "#10b981" }}
                    activeDot={{
                      r: 8,
                      stroke: "#34d399",
                      strokeWidth: 2,
                    }}
                    animationDuration={450}
                    animationEasing="ease-out"
                  />
                  {showUncertaintyBands && (
                    <>
                      <Line
                        type="monotone"
                        dataKey="signalQueueMax"
                        name="Signal Peak Queue"
                        stroke="#38bdf8"
                        strokeDasharray="3 3"
                        strokeOpacity={0.45}
                        strokeWidth={1.5}
                        dot={false}
                        activeDot={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="roundaboutQueueMax"
                        name="Roundabout Peak Queue"
                        stroke="#10b981"
                        strokeDasharray="3 3"
                        strokeOpacity={0.45}
                        strokeWidth={1.5}
                        dot={false}
                        activeDot={false}
                      />
                    </>
                  )}
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="chart-empty">No telemetry data recorded</div>
            )}
          </div>
        )}

        {/* Optional Delta Trend Chart */}
        {showDeltaTrend && (
          <div
            className="chart-card chart-card-delta-trend"
            style={{ gridColumn: "1 / -1" }}
          >
            <div className="chart-card-mini-header">
              <span className="mini-title">
                <ChartSpline
                  size={14}
                  aria-hidden="true"
                  className="uf-glyph"
                />{" "}
                Relative Performance Delta (% Difference)
              </span>
              <span className="mini-unit">
                Δ % (Objective Baseline: 0% Parity)
              </span>
            </div>
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart
                  data={chartData}
                  margin={{ top: 16, right: 24, bottom: 12, left: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                  <XAxis
                    dataKey={xDataKey}
                    tick={{
                      fontSize: 12,
                      fill: "hsl(var(--muted-foreground))",
                    }}
                    tickFormatter={(v: number) => v.toString()}
                    label={{
                      value:
                        xAxisMode === "volume"
                          ? "Hourly Volume (veh/h)"
                          : "Arrival Rate (veh/s)",
                      position: "insideBottom",
                      offset: -6,
                      fill: "hsl(var(--muted-foreground))",
                      fontSize: 12,
                    }}
                  />
                  <YAxis
                    tick={{
                      fontSize: 12,
                      fill: "hsl(var(--muted-foreground))",
                    }}
                    label={{
                      value: "Δ % Difference",
                      angle: -90,
                      position: "insideLeft",
                      offset: 8,
                      fill: "hsl(var(--muted-foreground))",
                      fontSize: 12,
                    }}
                  />
                  <Tooltip
                    content={<SweepTooltip unit="%" xMode={xAxisMode} />}
                  />
                  <Legend wrapperStyle={{ fontSize: 13, paddingTop: 10 }} />
                  <ReferenceLine
                    y={0}
                    stroke={CHART_AXIS}
                    strokeDasharray="4 3"
                    strokeWidth={2}
                    label={{
                      value: "Parity (0%)",
                      position: "right",
                      fill: "#94a3b8",
                      fontSize: 11,
                    }}
                  />
                  {crossover && xAxisMode === "volume" && (
                    <ReferenceLine
                      x={crossover}
                      stroke="#f59e0b"
                      strokeDasharray="4 3"
                      strokeWidth={2}
                      label={{
                        value: `Crossover (${crossover.toLocaleString()} veh/h)`,
                        position: "top",
                        fill: "#f59e0b",
                        fontSize: 11,
                      }}
                    />
                  )}
                  <Line
                    type="monotone"
                    dataKey="delayDeltaPercent"
                    name="Delay Δ % (+ = signal lower, − = roundabout lower)"
                    stroke="#8b5cf6"
                    strokeWidth={2.5}
                    dot={{ r: 4, fill: "#8b5cf6" }}
                  />
                  <Line
                    type="monotone"
                    dataKey="queueDeltaPercent"
                    name="Queue Δ % (+ = signal lower, − = roundabout lower)"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    strokeDasharray="4 2"
                    dot={{ r: 3, fill: "#f59e0b" }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="chart-empty">No telemetry data recorded</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
