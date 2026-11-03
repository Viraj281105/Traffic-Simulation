import type { MetricContext } from "../../metrics/catalog";
import type { RunningMetrics } from "../../types/simulation";
import { formatMetric, metricState, METRICS } from "../../metrics/catalog";
import { SERIES, CHART_GRID } from "../../theme/chart";
import { outsideNetworkText } from "../../metrics/entryModel";

interface CapacityDemandVisualizerProps {
  signalCtx: MetricContext;
  roundaboutCtx: MetricContext;
  compact?: boolean;
}

const satVolDef = METRICS.find((m) => m.key === "criticalSaturationVolume")!;
const utilDef = METRICS.find((m) => m.key === "intersectionUtilization")!;
const idleLossDef = METRICS.find((m) => m.key === "idleOpportunityLoss")!;
const footprintDef = METRICS.find((m) => m.key === "spaceFootprintConsumed")!;
const spawnedDef = METRICS.find((m) => m.key === "totalVehiclesSpawned")!;
const activeDef = METRICS.find((m) => m.key === "activeVehicleCount")!;

// Below this many expected arrivals the admitted share is mostly arrival
// noise (early in a run, 3 admitted of 2.1 expected reads as 143 %).
const MIN_NOMINAL_FOR_SHARE = 20;

/** "62 % of configured demand", or null while it is not meaningful. The
 *  nominal demand is an expectation from the configured rate (metric
 *  contract 7.10a); an entry that stays full suspends further arrivals, so
 *  a share well below 100 % is demand that never got in. */
function admittedShareText(
  m: RunningMetrics | undefined | null,
): string | null {
  const acc = m?.demandAccounting;
  if (!acc || acc.admittedShareOfNominal === null) return null;
  if (acc.nominalDemand < MIN_NOMINAL_FOR_SHARE) return null;
  return `${String(Math.round(acc.admittedShareOfNominal * 100))}% of configured demand`;
}

export function CapacityDemandVisualizer({
  signalCtx,
  roundaboutCtx,
  compact = false,
}: CapacityDemandVisualizerProps) {
  const sigM = signalCtx.metrics;
  const rndM = roundaboutCtx.metrics;

  const sigSpawned = sigM?.totalVehiclesSpawned ?? 0;
  const rndSpawned = rndM?.totalVehiclesSpawned ?? 0;

  // Vehicles served after warm-up, shown as a count only.
  const sigThroughput = signalCtx.inWarmup ? 0 : (sigM?.throughput ?? 0);
  const rndThroughput = roundaboutCtx.inWarmup ? 0 : (rndM?.throughput ?? 0);

  const sigShare = admittedShareText(sigM);
  const rndShare = admittedShareText(rndM);
  const sigOutside = outsideNetworkText(sigM);
  const rndOutside = outsideNetworkText(rndM);

  const sigActive = sigM?.activeVehicleCount ?? 0;
  const rndActive = rndM?.activeVehicleCount ?? 0;

  // Share of admitted vehicles that have exited, over ONE window (the whole
  // run, warm-up included). Exited vehicles are never removed from the pool,
  // so exited = admitted - still in the network, and the two segments below
  // add up to 100 %. (Dividing post-warm-up exits by all-time spawns would mix
  // two windows and understate the served share.)
  const sigExited = Math.max(0, sigSpawned - sigActive);
  const rndExited = Math.max(0, rndSpawned - rndActive);
  const sigServedRate = sigSpawned > 0 ? (sigExited / sigSpawned) * 100 : 0;
  const rndServedRate = rndSpawned > 0 ? (rndExited / rndSpawned) * 100 : 0;

  const sigActivePct =
    sigSpawned > 0
      ? Math.min(100 - sigServedRate, (sigActive / sigSpawned) * 100)
      : 0;
  const rndActivePct =
    rndSpawned > 0
      ? Math.min(100 - rndServedRate, (rndActive / rndSpawned) * 100)
      : 0;

  const sigUtilState = metricState(utilDef, signalCtx);
  const rndUtilState = metricState(utilDef, roundaboutCtx);
  const sigUtilVal = sigUtilState.kind === "value" ? sigUtilState.value : null;
  const rndUtilVal = rndUtilState.kind === "value" ? rndUtilState.value : null;

  const sigIdleState = metricState(idleLossDef, signalCtx);
  const sigIdleVal = sigIdleState.kind === "value" ? sigIdleState.value : null;

  return (
    <div className={`capacity-analytics-section ${compact ? "compact" : ""}`}>
      {/* Demand vs. Served Balance Card */}
      <div className="capacity-card demand-balance-card">
        <div className="capacity-card-header">
          <span className="card-title">Demand vs. Served Balance</span>
          <span className="card-subtitle">
            Vehicles admitted vs. exited, over the whole run (warm-up included)
          </span>
        </div>

        <div className="demand-bars-pair">
          {/* Signal Balance */}
          <div className="demand-bar-row">
            <div className="demand-row-meta">
              <span className="control-label signal">
                <span className="series-dot is-signal" aria-hidden="true" />{" "}
                Fixed-Time Signal
              </span>
              <span className="rate-badge">
                {`${sigServedRate.toFixed(1)}% exited`}
              </span>
            </div>
            <div
              className="balance-track"
              title={`Exited (whole run): ${String(sigExited)}, still in network: ${String(sigActive)}, admitted: ${String(sigSpawned)}. Vehicles served after warm-up: ${String(sigThroughput)}`}
            >
              <div
                className="balance-fill served signal"
                style={{ width: `${String(sigServedRate)}%` }}
              />
              <div
                className="balance-fill active signal"
                style={{ width: `${String(sigActivePct)}%` }}
              />
            </div>
            <div className="balance-numbers">
              <span>{String(sigExited)} exited (whole run)</span>
              <span>{formatMetric(activeDef, signalCtx)} in network</span>
              <span>{formatMetric(spawnedDef, signalCtx)} admitted</span>
              {sigShare && <span>{sigShare}</span>}
              {sigOutside && <span>{sigOutside}</span>}
            </div>
          </div>

          {/* Roundabout Balance */}
          <div className="demand-bar-row">
            <div className="demand-row-meta">
              <span className="control-label roundabout">
                <span className="series-dot is-roundabout" aria-hidden="true" />{" "}
                Modern Roundabout
              </span>
              <span className="rate-badge">
                {`${rndServedRate.toFixed(1)}% exited`}
              </span>
            </div>
            <div
              className="balance-track"
              title={`Exited (whole run): ${String(rndExited)}, still in network: ${String(rndActive)}, admitted: ${String(rndSpawned)}. Vehicles served after warm-up: ${String(rndThroughput)}`}
            >
              <div
                className="balance-fill served roundabout"
                style={{ width: `${String(rndServedRate)}%` }}
              />
              <div
                className="balance-fill active roundabout"
                style={{ width: `${String(rndActivePct)}%` }}
              />
            </div>
            <div className="balance-numbers">
              <span>{String(rndExited)} exited (whole run)</span>
              <span>{formatMetric(activeDef, roundaboutCtx)} in network</span>
              <span>{formatMetric(spawnedDef, roundaboutCtx)} admitted</span>
              {rndShare && <span>{rndShare}</span>}
              {rndOutside && <span>{rndOutside}</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Utilization & Capacity Grid */}
      <div className="capacity-grid">
        {/* Service Utilization Dial */}
        <div className="capacity-card util-card">
          <div className="capacity-card-header">
            <span className="card-title">Time with traffic moving</span>
            <span className="card-badge">% moving share</span>
          </div>

          <div className="util-rings-row">
            <div className="util-ring-box">
              <svg viewBox="0 0 80 80" className="radial-ring-svg">
                <circle
                  cx="40"
                  cy="40"
                  r="32"
                  fill="none"
                  stroke={CHART_GRID}
                  strokeWidth="7"
                />
                {sigUtilVal !== null && (
                  <circle
                    cx="40"
                    cy="40"
                    r="32"
                    fill="none"
                    stroke={SERIES.signal}
                    strokeWidth="7"
                    strokeDasharray={201}
                    strokeDashoffset={201 * (1 - sigUtilVal / 100)}
                    strokeLinecap="round"
                    transform="rotate(-90 40 40)"
                  />
                )}
              </svg>
              <div className="ring-reading">
                <span className="ring-val signal">
                  {sigUtilVal !== null ? `${sigUtilVal.toFixed(1)}%` : "—"}
                </span>
                <span className="ring-label">Signal</span>
              </div>
            </div>

            <div className="util-ring-box">
              <svg viewBox="0 0 80 80" className="radial-ring-svg">
                <circle
                  cx="40"
                  cy="40"
                  r="32"
                  fill="none"
                  stroke={CHART_GRID}
                  strokeWidth="7"
                />
                {rndUtilVal !== null && (
                  <circle
                    cx="40"
                    cy="40"
                    r="32"
                    fill="none"
                    stroke={SERIES.roundabout}
                    strokeWidth="7"
                    strokeDasharray={201}
                    strokeDashoffset={201 * (1 - rndUtilVal / 100)}
                    strokeLinecap="round"
                    transform="rotate(-90 40 40)"
                  />
                )}
              </svg>
              <div className="ring-reading">
                <span className="ring-val roundabout">
                  {rndUtilVal !== null ? `${rndUtilVal.toFixed(1)}%` : "—"}
                </span>
                <span className="ring-label">Roundabout</span>
              </div>
            </div>
          </div>
          <p className="util-subtext">
            Share of ticks with vehicles present where their mean speed exceeded
            0.5 m/s. Not the share of capacity used; near 100 % whenever traffic
            keeps moving.
          </p>
        </div>

        {/* Critical Saturation Volume */}
        <div className="capacity-card">
          <div className="capacity-card-header">
            <span className="card-title">Served-rate estimate</span>
            <span className="card-badge">veh/s</span>
          </div>
          <div className="stat-comparison-block">
            <div className="stat-row">
              <span className="stat-name">Signal:</span>
              <span className="stat-val signal">
                {formatMetric(satVolDef, signalCtx)}
              </span>
            </div>
            <div className="stat-row">
              <span className="stat-name">Roundabout:</span>
              <span className="stat-val roundabout">
                {formatMetric(satVolDef, roundaboutCtx)}
              </span>
            </div>
          </div>
          <p className="card-explanation">
            Backend estimate from throughput and the configured arrival rate. It
            cannot exceed the demand you configured, so it is not a measured
            capacity.
          </p>
        </div>

        {/* Idle Green Opportunity Loss (Signal Only) */}
        <div className="capacity-card">
          <div className="capacity-card-header">
            <span className="card-title">Idle Green Loss</span>
            <span className="card-badge tag-signal-only">Signal Only</span>
          </div>
          <div className="idle-loss-body">
            <div className="idle-val-box">
              <span className="idle-pct-num">
                {sigIdleVal !== null ? `${sigIdleVal.toFixed(1)}%` : "—"}
              </span>
              <span className="idle-desc">wasted green phase time</span>
            </div>
            <div className="idle-progress-track">
              <div
                className="idle-progress-fill"
                style={{ width: `${String(Math.min(100, sigIdleVal ?? 0))}%` }}
              />
            </div>
          </div>
          <p className="card-explanation">
            Ticks where red approach had a queue while green approach was
            completely empty.
          </p>
        </div>

        {/* Footprint Comparison */}
        <div className="capacity-card">
          <div className="capacity-card-header">
            <span className="card-title">Junction Footprint</span>
            <span className="card-badge">m²</span>
          </div>
          <div className="stat-comparison-block">
            <div className="stat-row">
              <span className="stat-name">Signal:</span>
              <span className="stat-val signal">
                {formatMetric(footprintDef, signalCtx)}
              </span>
            </div>
            <div className="stat-row">
              <span className="stat-name">Roundabout:</span>
              <span className="stat-val roundabout">
                {formatMetric(footprintDef, roundaboutCtx)}
              </span>
            </div>
          </div>
          <p className="card-explanation">
            Area from the configured geometry, defined differently per layout:
            crossing box (signal) versus outer circle including the central
            island (roundabout). Design context, not a like-for-like land-take
            comparison.
          </p>
        </div>
      </div>
    </div>
  );
}
