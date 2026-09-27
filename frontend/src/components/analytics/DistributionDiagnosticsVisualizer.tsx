import type { MetricContext } from "../../metrics/catalog";
import { formatMetric, METRICS } from "../../metrics/catalog";

interface DistributionDiagnosticsVisualizerProps {
  signalCtx: MetricContext;
  roundaboutCtx: MetricContext;
  compact?: boolean;
}

const minDelayDef = METRICS.find((m) => m.key === "minDelay")!;
const medDelayDef = METRICS.find((m) => m.key === "medianDelay")!;
const avgDelayDef = METRICS.find((m) => m.key === "averageDelay")!;
const p95DelayDef = METRICS.find((m) => m.key === "p95Delay")!;
const maxDelayDef = METRICS.find((m) => m.key === "maxDelay")!;
const delayStdDevDef = METRICS.find((m) => m.key === "delayStdDev")!;
const sviDef = METRICS.find((m) => m.key === "speedVarianceIndex")!;
const queueStdDevDef = METRICS.find((m) => m.key === "queueStdDev")!;
const queueStabilityDef = METRICS.find((m) => m.key === "queueStabilityIndex")!;

export function DistributionDiagnosticsVisualizer({
  signalCtx,
  roundaboutCtx,
  compact = false,
}: DistributionDiagnosticsVisualizerProps) {
  const sigM = signalCtx.metrics;
  const rndM = roundaboutCtx.metrics;

  const sigMax = sigM?.maxDelay ?? 10;
  const rndMax = rndM?.maxDelay ?? 10;
  const maxDelayScale = Math.max(15, sigMax, rndMax);

  return (
    <div
      className={`diagnostics-analytics-section ${compact ? "compact" : ""}`}
    >
      {/* Delay Distribution Range Whisker Visualizer */}
      <div className="diag-card delay-spread-card">
        <div className="diag-card-header">
          <span className="card-title">
            Delay Distribution Spread (Min — Median — P95 — Max)
          </span>
          <span className="card-badge">seconds</span>
        </div>

        <p className="card-explanation">
          Line: smallest to largest driver delay. Box: median to 95th
          percentile. Dot: mean. This is how much individual drivers&apos;
          delays varied within this run.
        </p>
        <div className="whisker-rows-wrapper">
          {/* Signal Whisker */}
          <div className="whisker-row">
            <div className="whisker-meta">
              <span className="control-label signal">🚦 Signal</span>
              <span className="whisker-stats-text">
                Min: {formatMetric(minDelayDef, signalCtx)} | Med:{" "}
                {formatMetric(medDelayDef, signalCtx)} | Avg:{" "}
                {formatMetric(avgDelayDef, signalCtx)} | P95:{" "}
                {formatMetric(p95DelayDef, signalCtx)} | Max:{" "}
                {formatMetric(maxDelayDef, signalCtx)}
              </span>
            </div>
            <div className="whisker-track">
              {sigM && sigM.maxDelay > 0 && (
                <>
                  {/* Range line: min to max */}
                  <div
                    className="whisker-range-line signal"
                    style={{
                      left: `${String((sigM.minDelay / maxDelayScale) * 100)}%`,
                      width: `${String(((sigM.maxDelay - sigM.minDelay) / maxDelayScale) * 100)}%`,
                    }}
                  />
                  {/* Box: median to 95th percentile (not an interquartile range) */}
                  <div
                    className="whisker-iqr-box signal"
                    style={{
                      left: `${String((sigM.medianDelay / maxDelayScale) * 100)}%`,
                      width: `${String(((Math.max(sigM.medianDelay, sigM.p95Delay) - sigM.medianDelay) / maxDelayScale) * 100)}%`,
                    }}
                  />
                  {/* Mean marker */}
                  <div
                    className="whisker-mean-dot signal"
                    title={`Average: ${String(sigM.averageDelay)} s`}
                    style={{
                      left: `${String((sigM.averageDelay / maxDelayScale) * 100)}%`,
                    }}
                  />
                </>
              )}
            </div>
          </div>

          {/* Roundabout Whisker */}
          <div className="whisker-row">
            <div className="whisker-meta">
              <span className="control-label roundabout">🔄 Roundabout</span>
              <span className="whisker-stats-text">
                Min: {formatMetric(minDelayDef, roundaboutCtx)} | Med:{" "}
                {formatMetric(medDelayDef, roundaboutCtx)} | Avg:{" "}
                {formatMetric(avgDelayDef, roundaboutCtx)} | P95:{" "}
                {formatMetric(p95DelayDef, roundaboutCtx)} | Max:{" "}
                {formatMetric(maxDelayDef, roundaboutCtx)}
              </span>
            </div>
            <div className="whisker-track">
              {rndM && rndM.maxDelay > 0 && (
                <>
                  {/* Range line: min to max */}
                  <div
                    className="whisker-range-line roundabout"
                    style={{
                      left: `${String((rndM.minDelay / maxDelayScale) * 100)}%`,
                      width: `${String(((rndM.maxDelay - rndM.minDelay) / maxDelayScale) * 100)}%`,
                    }}
                  />
                  {/* Box: median to 95th percentile (not an interquartile range) */}
                  <div
                    className="whisker-iqr-box roundabout"
                    style={{
                      left: `${String((rndM.medianDelay / maxDelayScale) * 100)}%`,
                      width: `${String(((Math.max(rndM.medianDelay, rndM.p95Delay) - rndM.medianDelay) / maxDelayScale) * 100)}%`,
                    }}
                  />
                  {/* Mean marker */}
                  <div
                    className="whisker-mean-dot roundabout"
                    title={`Average: ${String(rndM.averageDelay)} s`}
                    style={{
                      left: `${String((rndM.averageDelay / maxDelayScale) * 100)}%`,
                    }}
                  />
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Variance & Stability Metrics */}
      <div className="diag-grid">
        <div className="diag-card">
          <div className="diag-card-header">
            <span className="card-title">
              Dispersion &amp; Standard Deviations
            </span>
            <span className="card-badge">sample σ</span>
          </div>
          <div className="dispersion-list">
            <div className="dispersion-item">
              <span className="d-label">Delay Std Dev:</span>
              <span className="d-val signal">
                {formatMetric(delayStdDevDef, signalCtx)}
              </span>
              <span className="d-vs">vs</span>
              <span className="d-val roundabout">
                {formatMetric(delayStdDevDef, roundaboutCtx)}
              </span>
            </div>
            <div className="dispersion-item">
              <span className="d-label">Queue Std Dev:</span>
              <span className="d-val signal">
                {formatMetric(queueStdDevDef, signalCtx)}
              </span>
              <span className="d-vs">vs</span>
              <span className="d-val roundabout">
                {formatMetric(queueStdDevDef, roundaboutCtx)}
              </span>
            </div>
            <div className="dispersion-item">
              <span className="d-label">Queue Stability Index:</span>
              <span className="d-val signal">
                {formatMetric(queueStabilityDef, signalCtx)}
              </span>
              <span className="d-vs">vs</span>
              <span className="d-val roundabout">
                {formatMetric(queueStabilityDef, roundaboutCtx)}
              </span>
            </div>
            <div className="dispersion-item">
              <span className="d-label">Speed Variance Index:</span>
              <span className="d-val signal">
                {formatMetric(sviDef, signalCtx)}
              </span>
              <span className="d-vs">vs</span>
              <span className="d-val roundabout">
                {formatMetric(sviDef, roundaboutCtx)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
