import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  ReferenceLine,
} from "recharts";
import type {
  ComparisonHistoryPoint,
  CollisionEventRecord,
} from "../../hooks/useLiveComparisonHistory";
import type { MetricContext } from "../../metrics/catalog";
import { formatMetric, METRICS } from "../../metrics/catalog";

interface SafetyTimelineVisualizerProps {
  history: ComparisonHistoryPoint[];
  collisionEvents: CollisionEventRecord[];
  signalCtx: MetricContext;
  roundaboutCtx: MetricContext;
  compact?: boolean;
}

const minTtcDef = METRICS.find((m) => m.key === "minTTC")!;
const ttcEventsDef = METRICS.find((m) => m.key === "ttcEventCount")!;
const ttcSamplesDef = METRICS.find((m) => m.key === "ttcSampleCount")!;
const minPetDef = METRICS.find((m) => m.key === "minPET")!;
const petEventsDef = METRICS.find((m) => m.key === "petEventCount")!;
const petSamplesDef = METRICS.find((m) => m.key === "petSampleCount")!;

const SIGNAL_COLOR = "#f59e0b";
const ROUNDABOUT_COLOR = "#06b6d4";

export function SafetyTimelineVisualizer({
  history,
  collisionEvents,
  signalCtx,
  roundaboutCtx,
  compact = false,
}: SafetyTimelineVisualizerProps) {
  const sigM = signalCtx.metrics;
  const rndM = roundaboutCtx.metrics;

  const sigCollisions = sigM?.collisionCount ?? 0;
  const rndCollisions = rndM?.collisionCount ?? 0;

  const ttcThreshold =
    sigM?.ttcThresholdSeconds ?? rndM?.ttcThresholdSeconds ?? 1.5;
  const petThreshold = sigM?.petThresholdSeconds ?? 5.0;

  return (
    <div className={`safety-analytics-section ${compact ? "compact" : ""}`}>
      {/* Prominent Collision Counter / Timeline */}
      <div className="collision-highlight-row">
        <div
          className={`collision-card signal ${sigCollisions > 0 ? "has-events" : "zero-events"}`}
        >
          <div className="collision-card-header">
            <span className="control-pill signal">🚦 Fixed-Time Signal</span>
            <span className="collision-type">Distinct Overlaps</span>
          </div>
          <div className="collision-stat-body">
            <span className="collision-count">{sigCollisions}</span>
            <span className="collision-status-text">
              {sigCollisions === 0
                ? "No vehicle overlaps recorded"
                : "Vehicle overlaps recorded (model limit, not a crash forecast)"}
            </span>
          </div>
        </div>

        <div
          className={`collision-card roundabout ${rndCollisions > 0 ? "has-events" : "zero-events"}`}
        >
          <div className="collision-card-header">
            <span className="control-pill roundabout">
              🔄 Modern Roundabout
            </span>
            <span className="collision-type">Distinct Overlaps</span>
          </div>
          <div className="collision-stat-body">
            <span className="collision-count">{rndCollisions}</span>
            <span className="collision-status-text">
              {rndCollisions === 0
                ? "No vehicle overlaps recorded"
                : "Collision events observed"}
            </span>
          </div>
        </div>
      </div>

      {/* Discrete Collision Event Timeline Log */}
      {collisionEvents.length > 0 && !compact && (
        <div className="collision-timeline-log">
          <span className="timeline-title">Event Timeline (Chronological)</span>
          <div className="timeline-chips">
            {collisionEvents.map((evt) => (
              <span key={evt.id} className={`timeline-chip ${evt.control}`}>
                <strong>
                  {evt.control === "signal" ? "🚦 Signal" : "🔄 Roundabout"}
                </strong>{" "}
                at {evt.timeFormatted} (count #{evt.newCount})
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Minimum TTC Trend Chart with Threshold Reference */}
      <div className="ttc-trend-card">
        <div className="ttc-trend-header">
          <div>
            <span className="ttc-title">
              Smallest time-to-collision (TTC) seen so far
            </span>
            <span className="ttc-sub">
              Threshold: {ttcThreshold.toFixed(1)} s (a literature default, not
              validated for this model). A running minimum, so it can only fall
              during a run.
            </span>
          </div>
          <div className="ttc-current-readouts">
            <span className="ttc-readout signal">
              Signal: <strong>{formatMetric(minTtcDef, signalCtx)}</strong>
            </span>
            <span className="ttc-readout roundabout">
              Roundabout:{" "}
              <strong>{formatMetric(minTtcDef, roundaboutCtx)}</strong>
            </span>
          </div>
        </div>

        <div style={{ width: "100%", height: compact ? 180 : 230 }}>
          {history.length === 0 ? (
            <div className="chart-empty-state">
              <p>No TTC observations yet</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={history}
                margin={{ top: 10, right: 20, left: 0, bottom: 0 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(255,255,255,0.08)"
                />
                <XAxis dataKey="timeFormatted" stroke="#8892b0" fontSize={11} />
                <YAxis stroke="#8892b0" fontSize={11} unit=" s" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1e2230",
                    borderColor: "#333c56",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Legend height={32} wrapperStyle={{ top: 0, fontSize: 11 }} />
                <ReferenceLine
                  y={ttcThreshold}
                  stroke="#ef4444"
                  strokeDasharray="4 4"
                  strokeWidth={1.5}
                  label={{
                    value: `Critical Cutoff (${ttcThreshold.toFixed(1)} s)`,
                    fill: "#ef4444",
                    fontSize: 10,
                    position: "insideBottomRight",
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="signalMinTtc"
                  name="Signal Min TTC"
                  stroke={SIGNAL_COLOR}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="roundaboutMinTtc"
                  name="Roundabout Min TTC"
                  stroke={ROUNDABOUT_COLOR}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Low-TTC & PET Surrogate Conflict Metrics Grid */}
      <div className="safety-surrogates-grid">
        <div className="surrogate-metric-card">
          <span className="surrogate-card-title">
            Low-TTC Critical Events (TTC ≤ {ttcThreshold.toFixed(1)} s)
          </span>
          <div className="surrogate-values-row">
            <div className="surrogate-val-group">
              <span className="val-control">Signal:</span>
              <span className="val-strong">
                {formatMetric(ttcEventsDef, signalCtx)}
              </span>
              <span className="val-note">
                / {formatMetric(ttcSamplesDef, signalCtx)} obs
              </span>
            </div>
            <div className="surrogate-val-group">
              <span className="val-control">Roundabout:</span>
              <span className="val-strong">
                {formatMetric(ttcEventsDef, roundaboutCtx)}
              </span>
              <span className="val-note">
                / {formatMetric(ttcSamplesDef, roundaboutCtx)} obs
              </span>
            </div>
          </div>
        </div>

        <div className="surrogate-metric-card">
          <span className="surrogate-card-title">
            Post-Encroachment Time (PET ≤ {petThreshold.toFixed(1)} s)
          </span>
          <div className="surrogate-values-row">
            <div className="surrogate-val-group">
              <span className="val-control">Signal:</span>
              <span className="val-strong">
                {formatMetric(minPetDef, signalCtx)}
              </span>
              <span className="val-note">
                ({formatMetric(petEventsDef, signalCtx)} events /{" "}
                {formatMetric(petSamplesDef, signalCtx)} obs)
              </span>
            </div>
            <div className="surrogate-val-group">
              <span className="val-control">Roundabout:</span>
              <span className="val-na">N/A</span>
              <span className="val-note">Not applicable to roundabouts</span>
            </div>
          </div>
        </div>
      </div>

      {/* Mandatory Surrogate Safety Disclaimer Banner */}
      <div className="safety-disclaimer-banner">
        <span className="disclaimer-icon">ℹ️</span>
        <p className="disclaimer-text">
          <strong>Surrogate Safety Measures Notice:</strong> TTC and PET are
          exploratory research diagnostics, not a safety score, a count of real
          collisions, or a crash probability. Thresholds are literature
          defaults, not validated for this model, and the counts are not a
          validated safety ranking between geometries.
        </p>
      </div>
      <details className="how-measured">
        <summary>How TTC and PET are measured</summary>
        <ul>
          <li>
            <strong>TTC</strong> is sampled on every 0.1 s tick for pairs of
            vehicles on different lanes within 50 m: the time until two vehicles
            would touch if both kept their current speed and heading. Same-lane
            car-following is excluded. &ldquo;Low-TTC events&rdquo; counts
            ticks, so one long close approach counts many times; it is an
            exposure count, not a number of distinct near-misses. The smallest
            TTC is a run-long minimum.
          </li>
          <li>
            <strong>PET</strong> is measured only at the signal&apos;s conflict
            points: the gap between one vehicle leaving a crossing point and a
            different vehicle reaching it. It is not measured for the roundabout
            (shown as N/A, meaning &ldquo;not measured&rdquo;, never &ldquo;no
            conflicts&rdquo;). The default 5 s threshold is generous, so many
            ordinary crossings count.
          </li>
          <li>
            The number of observations depends on how many vehicles share space,
            which differs by layout, so TTC and PET counts are not comparable
            between the signal and the roundabout as risk.
          </li>
          <li>
            &ldquo;Collisions&rdquo; are vehicle-body overlaps in the model,
            counted from the start of the run including warm-up. They show where
            the model reached a limit, not a prediction of real crashes.
          </li>
        </ul>
      </details>
    </div>
  );
}
