import type { MetricContext } from "../../metrics/catalog";
import { formatMetric, metricState, METRICS } from "../../metrics/catalog";
import type { SignalDirection } from "../../types/simulation";
import { SERIES, CHART_GRID } from "../../theme/chart";

interface TrafficFlowVisualizerProps {
  signalCtx: MetricContext;
  roundaboutCtx: MetricContext;
  compact?: boolean;
}

const avgQDef = METRICS.find((m) => m.key === "averageQueueLength")!;
const maxQDef = METRICS.find((m) => m.key === "maxQueueLength")!;
const activeAvgQDef = METRICS.find(
  (m) => m.key === "activeAverageQueueLength",
)!;
const stopsPerVehDef = METRICS.find((m) => m.key === "averageStopsPerVehicle")!;
const totalStopsDef = METRICS.find((m) => m.key === "totalStops")!;
const fairnessDef = METRICS.find((m) => m.key === "directionalFairnessIndex")!;
const congestionTimeDef = METRICS.find(
  (m) => m.key === "congestionRecoveryTime",
)!;
const queueStabilityDef = METRICS.find((m) => m.key === "queueStabilityIndex")!;

const DIRECTIONS: SignalDirection[] = ["north", "south", "east", "west"];

export function TrafficFlowVisualizer({
  signalCtx,
  roundaboutCtx,
  compact = false,
}: TrafficFlowVisualizerProps) {
  const sigMetrics = signalCtx.metrics;
  const rndMetrics = roundaboutCtx.metrics;

  const sigQueues = sigMetrics?.currentQueueLengths ?? {
    north: 0,
    south: 0,
    east: 0,
    west: 0,
  };
  const rndQueues = rndMetrics?.currentQueueLengths ?? {
    north: 0,
    south: 0,
    east: 0,
    west: 0,
  };

  const sigFairnessState = metricState(fairnessDef, signalCtx);
  const rndFairnessState = metricState(fairnessDef, roundaboutCtx);
  const sigFairnessVal =
    sigFairnessState.kind === "value" ? sigFairnessState.value : null;
  const rndFairnessVal =
    rndFairnessState.kind === "value" ? rndFairnessState.value : null;

  // Max queue for scaling the approach bars (at least 5 for pleasant scale)
  const maxApproachQueue = Math.max(
    5,
    ...DIRECTIONS.map((d) => Math.max(sigQueues[d], rndQueues[d])),
  );

  return (
    <div
      className={`traffic-flow-analytics-section ${compact ? "compact" : ""}`}
    >
      {/* 4-Way Approach Directional Queue Visualizer */}
      <div className="flow-radar-card">
        <div className="section-subheading">
          <span className="subheading-title">
            Approach Queue Distribution (Real-Time)
          </span>
          <span className="subheading-hint">
            Vehicles queued right now (N, S, E, W)
          </span>
        </div>

        <div className="approach-grid">
          {DIRECTIONS.map((dir) => {
            const sigQ = sigQueues[dir];
            const rndQ = rndQueues[dir];
            const sigWidthNum = Math.min(100, (sigQ / maxApproachQueue) * 100);
            const rndWidthNum = Math.min(100, (rndQ / maxApproachQueue) * 100);

            return (
              <div className="approach-row" key={dir}>
                <span className="approach-label">{dir.toUpperCase()}</span>
                <div className="approach-bars-pair">
                  <div
                    className="approach-bar-track signal"
                    title={`Signal ${dir}: ${String(sigQ)} veh`}
                  >
                    <div
                      className="approach-bar-fill signal"
                      style={{ width: `${String(sigWidthNum)}%` }}
                    />
                    <span className="approach-bar-num">{sigQ}</span>
                  </div>
                  <div
                    className="approach-bar-track roundabout"
                    title={`Roundabout ${dir}: ${String(rndQ)} veh`}
                  >
                    <div
                      className="approach-bar-fill roundabout"
                      style={{ width: `${String(rndWidthNum)}%` }}
                    />
                    <span className="approach-bar-num">{rndQ}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Fairness & Queue Dynamics Grid */}
      <div className="flow-metrics-grid">
        {/* Directional Fairness Arc Gauge */}
        <div className="flow-metric-card fairness-card">
          <div className="card-top">
            <span className="card-title">Directional Fairness</span>
            <span className="card-badge">Jain&apos;s Index (0.25 - 1.00)</span>
          </div>

          <div className="fairness-gauges-row">
            {/* Signal Fairness Dial */}
            <div className="fairness-dial-box">
              <svg viewBox="0 0 100 60" className="gauge-svg">
                <path
                  d="M 15 50 A 35 35 0 0 1 85 50"
                  fill="none"
                  stroke={CHART_GRID}
                  strokeWidth="8"
                  strokeLinecap="round"
                />
                {sigFairnessVal !== null && (
                  <path
                    d="M 15 50 A 35 35 0 0 1 85 50"
                    fill="none"
                    stroke={SERIES.signal}
                    strokeWidth="8"
                    strokeLinecap="round"
                    strokeDasharray="110"
                    strokeDashoffset={
                      110 *
                      (1 -
                        Math.max(
                          0,
                          Math.min(1, (sigFairnessVal - 0.25) / 0.75),
                        ))
                    }
                  />
                )}
              </svg>
              <div className="gauge-reading">
                <span className="gauge-val signal">
                  {sigFairnessVal !== null ? sigFairnessVal.toFixed(2) : "—"}
                </span>
                <span className="gauge-label">Signal</span>
              </div>
            </div>

            {/* Roundabout Fairness Dial */}
            <div className="fairness-dial-box">
              <svg viewBox="0 0 100 60" className="gauge-svg">
                <path
                  d="M 15 50 A 35 35 0 0 1 85 50"
                  fill="none"
                  stroke={CHART_GRID}
                  strokeWidth="8"
                  strokeLinecap="round"
                />
                {rndFairnessVal !== null && (
                  <path
                    d="M 15 50 A 35 35 0 0 1 85 50"
                    fill="none"
                    stroke={SERIES.roundabout}
                    strokeWidth="8"
                    strokeLinecap="round"
                    strokeDasharray="110"
                    strokeDashoffset={
                      110 *
                      (1 -
                        Math.max(
                          0,
                          Math.min(1, (rndFairnessVal - 0.25) / 0.75),
                        ))
                    }
                  />
                )}
              </svg>
              <div className="gauge-reading">
                <span className="gauge-val roundabout">
                  {rndFairnessVal !== null ? rndFairnessVal.toFixed(2) : "—"}
                </span>
                <span className="gauge-label">Roundabout</span>
              </div>
            </div>
          </div>
          <p className="card-note">
            1.00 = equal queued time across the approaches; the floor is 1 ÷ the
            number of approaches with traffic (0.25 with four). Noisy when few
            vehicles have exited.
          </p>
        </div>

        {/* Queue Lengths Summary */}
        <div className="flow-metric-card">
          <div className="card-top">
            <span className="card-title">Queue Parameters</span>
            <span className="card-badge">post-warmup</span>
          </div>

          <div className="queue-summary-list">
            <div className="queue-item">
              <span className="queue-item-label">Avg Queue per Approach:</span>
              <div className="queue-item-vals">
                <span className="val-signal">
                  {formatMetric(avgQDef, signalCtx)}
                </span>
                <span className="val-vs">vs</span>
                <span className="val-roundabout">
                  {formatMetric(avgQDef, roundaboutCtx)}
                </span>
              </div>
            </div>

            <div className="queue-item">
              <span className="queue-item-label">Maximum Queue Observed:</span>
              <div className="queue-item-vals">
                <span className="val-signal">
                  {formatMetric(maxQDef, signalCtx)}
                </span>
                <span className="val-vs">vs</span>
                <span className="val-roundabout">
                  {formatMetric(maxQDef, roundaboutCtx)}
                </span>
              </div>
            </div>

            <div className="queue-item">
              <span className="queue-item-label">
                Avg Total Queue when Queued:
              </span>
              <div className="queue-item-vals">
                <span className="val-signal">
                  {formatMetric(activeAvgQDef, signalCtx)}
                </span>
                <span className="val-vs">vs</span>
                <span className="val-roundabout">
                  {formatMetric(activeAvgQDef, roundaboutCtx)}
                </span>
              </div>
            </div>

            <div className="queue-item">
              <span className="queue-item-label">Queue Stability Index:</span>
              <div className="queue-item-vals">
                <span className="val-signal">
                  {formatMetric(queueStabilityDef, signalCtx)}
                </span>
                <span className="val-vs">vs</span>
                <span className="val-roundabout">
                  {formatMetric(queueStabilityDef, roundaboutCtx)}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Stops & Congestion Recovery */}
        <div className="flow-metric-card">
          <div className="card-top">
            <span className="card-title">Stops &amp; Congestion Time</span>
            <span className="card-badge">Efficiency</span>
          </div>

          <div className="queue-summary-list">
            <div className="queue-item">
              <span className="queue-item-label">
                Stops per Exited Vehicle:
              </span>
              <div className="queue-item-vals">
                <span className="val-signal">
                  {formatMetric(stopsPerVehDef, signalCtx)}
                </span>
                <span className="val-vs">vs</span>
                <span className="val-roundabout">
                  {formatMetric(stopsPerVehDef, roundaboutCtx)}
                </span>
              </div>
            </div>

            <div className="queue-item">
              <span className="queue-item-label">Total Stops Made:</span>
              <div className="queue-item-vals">
                <span className="val-signal">
                  {formatMetric(totalStopsDef, signalCtx)}
                </span>
                <span className="val-vs">vs</span>
                <span className="val-roundabout">
                  {formatMetric(totalStopsDef, roundaboutCtx)}
                </span>
              </div>
            </div>

            <div className="queue-item">
              <span className="queue-item-label">
                Time Congested (&gt;5 veh):
              </span>
              <div className="queue-item-vals">
                <span className="val-signal">
                  {formatMetric(congestionTimeDef, signalCtx)}
                </span>
                <span className="val-vs">vs</span>
                <span className="val-roundabout">
                  {formatMetric(congestionTimeDef, roundaboutCtx)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
