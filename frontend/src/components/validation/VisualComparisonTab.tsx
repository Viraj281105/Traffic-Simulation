import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CIBar as ModernCIBar } from "./CIBar";
import { SeedChartTooltip as CustomChartTooltip } from "./SeedChartTooltip";
import {
  METRIC_KEYS,
  METRIC_LABELS,
  ROUND_COLOR,
  SIGNAL_COLOR,
  getCohensDLabel,
  seedChartRows,
  type MetricKey,
  type ValidationResult,
} from "./validationModel";

/** One confidence-interval card per metric and the seed-by-seed chart. */
export function VisualComparisonTab({
  result,
  chartMetric,
  setChartMetric,
}: {
  result: ValidationResult;
  chartMetric: MetricKey;
  setChartMetric: (metric: MetricKey) => void;
}) {
  const isMetricSignificant = (key: MetricKey) =>
    result.comparison[key].significant;
  const resultAlpha = result.alpha ?? 0.05;
  const seedChartData = seedChartRows(result, chartMetric);

  return (
    <div className="visual-tab-content">
      {/* 3 Widescreen Metric CI Cards */}
      <div className="stats-grid">
        {METRIC_KEYS.map((key) => {
          const sigStat = result.signal[key];
          const rndStat = result.roundabout[key];
          const maxMean = Math.max(
            sigStat.mean + (sigStat.ci ?? sigStat.ci95),
            rndStat.mean + (rndStat.ci ?? rndStat.ci95),
            0.01,
          );
          const cmp = result.comparison[key];
          const effect = getCohensDLabel(cmp.cohensD);

          // Calculate percentage reduction/gain
          const deltaPct =
            sigStat.mean > 0
              ? ((rndStat.mean - sigStat.mean) / sigStat.mean) * 100
              : 0;

          return (
            <div className="stat-card" key={key}>
              <div className="stat-card-header">
                <div className="stat-title-group">
                  <h4>{METRIC_LABELS[key]}</h4>
                  <span
                    className="validation-delta-pill"
                    title="Roundabout mean relative to signal mean: descriptive, not better or worse"
                  >
                    {deltaPct > 0
                      ? `+${deltaPct.toFixed(1)}%`
                      : `${deltaPct.toFixed(1)}%`}
                  </span>
                </div>
                <span
                  className="effect-badge"
                  style={{
                    color: effect.color,
                    background: effect.bg,
                    borderColor: effect.color,
                  }}
                >
                  {effect.label}
                </span>
              </div>

              {(() => {
                const ciSig = sigStat.ci ?? sigStat.ci95;
                const ciRnd = rndStat.ci ?? rndStat.ci95;
                return (
                  <div className="ci-comparison">
                    <ModernCIBar
                      label="Fixed-Time Signal"
                      stat={sigStat}
                      color={SIGNAL_COLOR}
                      maxMean={maxMean}
                      ciMargin={ciSig}
                    />
                    <ModernCIBar
                      label="Modern Roundabout"
                      stat={rndStat}
                      color={ROUND_COLOR}
                      maxMean={maxMean}
                      ciMargin={ciRnd}
                    />

                    <div className="metric-stats-footer">
                      <div className="stats-footer-left">
                        <span className="stat-badge-chip">
                          Cohen&apos;s d:{" "}
                          <strong>
                            {cmp.cohensD === null
                              ? "—"
                              : cmp.cohensD.toFixed(3)}
                          </strong>
                        </span>
                        {cmp.pValue !== null && (
                          <span className="stat-badge-chip">
                            p-val:{" "}
                            <strong>
                              {cmp.pValue < 0.001
                                ? "<0.001"
                                : cmp.pValue.toFixed(3)}
                            </strong>
                          </span>
                        )}
                        {cmp.degreesOfFreedom !== undefined && (
                          <span
                            className="stat-badge-chip"
                            title="Welch–Satterthwaite degrees of freedom"
                          >
                            df:{" "}
                            <strong>{cmp.degreesOfFreedom.toFixed(1)}</strong>
                          </span>
                        )}
                      </div>
                      <div className="stats-footer-right">
                        <span
                          className={`sig-status-badge ${isMetricSignificant(key) ? "significant" : "not-significant"}`}
                        >
                          {isMetricSignificant(key)
                            ? `Supported (α=${resultAlpha.toString()})`
                            : "Not supported"}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })()}
            </div>
          );
        })}
      </div>

      {/* Seed-by-Seed Interactive Recharts Studio */}
      <div className="seed-chart-container">
        <div className="seed-chart-header">
          <div className="seed-chart-titles">
            <h4>Seed-by-Seed Comparative Distribution</h4>
            <span className="seed-chart-sub">
              Visualizing stochastic jitter across individual randomized seed
              pairs
            </span>
          </div>

          {/* Metric Switcher Pills */}
          <div className="validation-chart-metric-pills">
            {METRIC_KEYS.map((k) => (
              <button
                key={k}
                type="button"
                className={`validation-metric-pill-btn ${chartMetric === k ? "active" : ""}`}
                onClick={() => {
                  setChartMetric(k);
                }}
              >
                {METRIC_LABELS[k]}
              </button>
            ))}
          </div>
        </div>

        <div className="seed-chart-wrapper">
          <ResponsiveContainer width="100%" height={320}>
            <BarChart
              data={seedChartData}
              margin={{ top: 18, right: 24, left: 0, bottom: 6 }}
            >
              <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
              <XAxis
                dataKey="seed"
                tick={{
                  fill: "hsl(var(--muted-foreground))",
                  fontSize: 11,
                }}
                tickLine={{ stroke: "hsl(var(--border))" }}
                axisLine={{ stroke: "hsl(var(--border))" }}
                label={{
                  value: "Seed Index",
                  position: "insideBottom",
                  offset: -4,
                  fill: "hsl(var(--muted-foreground))",
                  fontSize: 11,
                }}
              />
              <YAxis
                tick={{
                  fill: "hsl(var(--muted-foreground))",
                  fontSize: 11,
                }}
                tickLine={{ stroke: "hsl(var(--border))" }}
                axisLine={{ stroke: "hsl(var(--border))" }}
                unit={chartMetric === "delay" ? "s" : ""}
              />
              <Tooltip content={<CustomChartTooltip metric={chartMetric} />} />
              <Legend wrapperStyle={{ paddingBottom: 10, fontSize: 12 }} />
              <ReferenceLine
                y={result.signal[chartMetric].mean}
                stroke={SIGNAL_COLOR}
                strokeDasharray="4 4"
                label={{
                  value: `Signal Mean: ${result.signal[chartMetric].mean.toFixed(1)}`,
                  fill: SIGNAL_COLOR,
                  fontSize: 10,
                  position: "top",
                }}
              />
              <ReferenceLine
                y={result.roundabout[chartMetric].mean}
                stroke={ROUND_COLOR}
                strokeDasharray="4 4"
                label={{
                  value: `Rnd Mean: ${result.roundabout[chartMetric].mean.toFixed(1)}`,
                  fill: ROUND_COLOR,
                  fontSize: 10,
                  position: "top",
                }}
              />
              <Bar
                dataKey="signal"
                name="Fixed-Time Signal"
                fill={SIGNAL_COLOR}
                radius={[4, 4, 0, 0]}
                animationDuration={400}
                animationEasing="ease-out"
              />
              <Bar
                dataKey="roundabout"
                name="Modern Roundabout"
                fill={ROUND_COLOR}
                radius={[4, 4, 0, 0]}
                animationDuration={400}
                animationEasing="ease-out"
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
