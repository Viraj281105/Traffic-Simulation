import React, { useState, useMemo } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
} from "recharts";
import { API_BASE_URL } from "../config";
import "./ValidationDashboard.css";
import { DEFAULT_CONFIG_VALUES } from "../types/config";
import {
  DEMAND_LEVELS,
  REFERENCE_CAPACITY_VPH,
  demandRate,
  saturationRatio,
} from "../types/demand";
import { SIMILARITY, compare } from "../metrics/plainLanguage";
import { IntegrityCheck } from "./IntegrityCheck";
import { CloseButton } from "./ui/CloseButton";
import { LoaderMark } from "./ui/Loader";
import { SERIES } from "../theme/chart";

// ── Types ──────────────────────────────────────────────────────────────────

interface StatResult {
  mean: number;
  std: number;
  min: number;
  max: number;
  /** Student-t half-width at the run's confidence level. */
  ci?: number;
  /** Student-t half-width at 95 % (always present). */
  ci95: number;
  ciConfidence?: number;
  ciDegreesOfFreedom?: number;
  ciCriticalValue?: number;
}

interface SeedRun {
  seed: number;
  signal: { delay: number; throughput: number; queue: number };
  roundabout: { delay: number; throughput: number; queue: number };
}

interface ValidationResult {
  numSeeds: number;
  /** Level the intervals and significance flags were computed at; alpha is
   *  1 - level. Both come from the backend, which is what ran the test. */
  confidenceLevel?: number;
  alpha?: number;
  calibration?: { calibrated: boolean; note: string };
  vehicleLimitReachedSeeds?: number[];
  signal: {
    delay: StatResult;
    throughput: StatResult;
    queue: StatResult;
  };
  roundabout: {
    delay: StatResult;
    throughput: StatResult;
    queue: StatResult;
  };
  comparison: {
    delay: GroupComparison;
    throughput: GroupComparison;
    queue: GroupComparison;
  };
  seedRuns: SeedRun[];
}

/** Welch's t-test result from the backend (_compare_groups). */
interface GroupComparison {
  pValue: number | null;
  significant: boolean;
  cohensD: number;
  /** Welch-Satterthwaite degrees of freedom (absent for degenerate cases). */
  degreesOfFreedom?: number;
}

const METRIC_KEYS = ["delay", "throughput", "queue"] as const;
type MetricKey = (typeof METRIC_KEYS)[number];

const METRIC_LABELS: Record<MetricKey, string> = {
  delay: "Avg Delay (s)",
  throughput: "Throughput (veh)",
  queue: "Avg Queue (veh)",
};

const METRIC_UNITS: Record<MetricKey, string> = {
  delay: "seconds",
  throughput: "vehicles",
  queue: "vehicles",
};

const SIGNAL_COLOR = "#3b82f6"; // Vibrant blue
const ROUND_COLOR = "#10b981"; // Emerald green

function getCohensDLabel(d: number): {
  label: string;
  color: string;
  bg: string;
} {
  const absD = Math.abs(d);
  if (absD >= 0.8)
    return {
      label: "Large Effect",
      color: SERIES.signal,
      bg: "rgba(245, 158, 11, 0.12)",
    };
  if (absD >= 0.5)
    return {
      label: "Medium Effect",
      color: "#3b82f6",
      bg: "rgba(59, 130, 246, 0.12)",
    };
  if (absD >= 0.2)
    return {
      label: "Small Effect",
      color: "#8b5cf6",
      bg: "rgba(139, 92, 246, 0.12)",
    };
  return {
    label: "Negligible",
    color: "#64748b",
    bg: "rgba(100, 116, 139, 0.12)",
  };
}

// ── Custom Tooltip for Recharts ─────────────────────────────────────────────

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    value: number;
    dataKey: string;
    color: string;
    name: string;
  }>;
  label?: string;
  metric: MetricKey;
}

const CustomChartTooltip: React.FC<CustomTooltipProps> = ({
  active,
  payload,
  label,
  metric,
}) => {
  if (!active || !payload || payload.length < 2) return null;

  const sigVal = payload.find((p) => p.dataKey === "signal")?.value ?? 0;
  const rndVal = payload.find((p) => p.dataKey === "roundabout")?.value ?? 0;
  const delta = rndVal - sigVal;
  const unit = METRIC_UNITS[metric];

  // Which side has the lower delay/queue or the higher throughput: a plain
  // description of this seed, not a judgement of either control.
  const rndWins = metric === "throughput" ? rndVal > sigVal : rndVal < sigVal;

  return (
    <div className="validation-chart-tooltip">
      <div className="tooltip-seed-title">Seed #{label}</div>
      <div className="tooltip-metric-rows">
        <div className="tooltip-row">
          <span className="tooltip-dot" style={{ background: SIGNAL_COLOR }} />
          <span className="tooltip-name">Signal:</span>
          <span className="tooltip-val">
            {sigVal.toFixed(2)} {unit}
          </span>
        </div>
        <div className="tooltip-row">
          <span className="tooltip-dot" style={{ background: ROUND_COLOR }} />
          <span className="tooltip-name">Roundabout:</span>
          <span className="tooltip-val">
            {rndVal.toFixed(2)} {unit}
          </span>
        </div>
      </div>
      <div className="tooltip-delta-footer">
        <span className="tooltip-delta-label">Difference:</span>
        <span className="tooltip-delta-val">
          {delta > 0 ? `+${delta.toFixed(2)}` : delta.toFixed(2)} (
          {metric === "throughput"
            ? rndWins
              ? "more through the roundabout"
              : "more through the signal"
            : rndWins
              ? "lower at the roundabout"
              : "lower at the signal"}
          )
        </span>
      </div>
    </div>
  );
};

// ── Modern CI Visual Bar ───────────────────────────────────────────────────

function ModernCIBar({
  label,
  stat,
  color,
  maxMean,
  ciMargin,
}: {
  label: string;
  stat: StatResult;
  color: string;
  maxMean: number;
  ciMargin?: number;
}) {
  const activeCI = ciMargin !== undefined ? ciMargin : stat.ci95;
  const pct = maxMean > 0 ? Math.min(100, (stat.mean / maxMean) * 100) : 0;
  const ciWidthPct =
    maxMean > 0 ? Math.min(100, (activeCI / maxMean) * 100) : 0;
  const ciLeft = Math.max(0, pct - ciWidthPct / 2);

  return (
    <div className="ci-row">
      <div className="ci-label-group">
        <span className="ci-model-name" style={{ borderLeftColor: color }}>
          {label}
        </span>
        <span className="ci-range-hint">
          Min {stat.min.toFixed(1)} · Max {stat.max.toFixed(1)}
        </span>
      </div>

      <div className="ci-track-container">
        <div className="ci-bar-track">
          <div
            className="ci-bar-fill"
            style={{
              width: `${pct.toString()}%`,
              background: `linear-gradient(90deg, ${color}88, ${color})`,
            }}
          />
          <div
            className="ci-bar-ci"
            style={{
              left: `${ciLeft.toString()}%`,
              width: `${Math.max(4, ciWidthPct).toString()}%`,
            }}
            title={`CI: [${(stat.mean - activeCI).toFixed(2)} – ${(stat.mean + activeCI).toFixed(2)}]`}
          />
        </div>
      </div>

      <div className="ci-values">
        <span className="ci-mean" style={{ color }}>
          {stat.mean.toFixed(2)}
        </span>
        <span className="ci-range">
          ±{activeCI.toFixed(2)}{" "}
          <span className="ci-sigma">(σ={stat.std.toFixed(2)})</span>
        </span>
      </div>
    </div>
  );
}

// ── Main Validation Dashboard Component ─────────────────────────────────────

export const ValidationDashboard: React.FC = () => {
  const [numSeeds, setNumSeeds] = useState(5);
  const [duration, setDuration] = useState(240);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [activeTab, setActiveTab] = useState<
    "visual" | "table" | "methodology"
  >("visual");
  const [chartMetric, setChartMetric] = useState<MetricKey>("delay");
  const [showMethodologyDrawer, setShowMethodologyDrawer] = useState(false);
  const [showConfigPanel, setShowConfigPanel] = useState(false);

  // Advanced Configuration Parameters
  const [arrivalRate, setArrivalRate] = useState(
    DEFAULT_CONFIG_VALUES.arrivalRate,
  );
  const [arrivalDistribution, setArrivalDistribution] = useState<
    "poisson" | "uniform"
  >("poisson");
  const [warmupTime, setWarmupTime] = useState(30.0);
  const [timeStep, setTimeStep] = useState(0.1);
  const [approachLength, setApproachLength] = useState(200.0);
  const [confidenceLevel, setConfidenceLevel] = useState<0.9 | 0.95 | 0.99>(
    0.95,
  );

  const alpha = useMemo(() => {
    return Number((1 - confidenceLevel).toFixed(2));
  }, [confidenceLevel]);

  // Level and alpha of the result on screen (what the backend actually ran),
  // as opposed to `confidenceLevel`, which is the setting for the next run.
  const [lanesCount, setLanesCount] = useState<1 | 2 | 3>(1);

  const resetAdvancedDefaults = () => {
    setLanesCount(1);
    setArrivalRate(DEFAULT_CONFIG_VALUES.arrivalRate);
    setArrivalDistribution("poisson");
    setWarmupTime(30.0);
    setNumSeeds(5);
    setDuration(240);
    setTimeStep(0.1);
    setApproachLength(200.0);
    setConfidenceLevel(0.95);
  };

  const runValidation = () => {
    setIsRunning(true);
    setError(null);
    setShowConfigPanel(false);

    const customConfig = {
      simulation: {
        timeStep,
        duration,
        warmupTime,
      },
      roads: {
        approachLength,
        laneWidth: 3.5,
        lanesPerApproach: {
          north: lanesCount,
          south: lanesCount,
          east: lanesCount,
          west: lanesCount,
        },
      },
      traffic: {
        arrivalRate,
        arrivalDistribution,
      },
    };

    fetch(`${API_BASE_URL}/api/v1/study/validate/monte-carlo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        numSeeds,
        num_seeds: numSeeds,
        duration,
        confidenceLevel,
        customConfig,
      }),
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status.toString()}`);
        return r.json() as Promise<ValidationResult>;
      })
      .then((data) => {
        setResult(data);
        setIsRunning(false);
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Validation failed");
        setIsRunning(false);
      });
  };

  const handleLaunchPreset = (seeds: number, dur: number) => {
    setNumSeeds(seeds);
    setDuration(dur);
    setIsRunning(true);
    setError(null);
    setShowConfigPanel(false);

    const customConfig = {
      simulation: {
        timeStep,
        duration: dur,
        warmupTime,
      },
      roads: {
        approachLength,
        laneWidth: 3.5,
        lanesPerApproach: {
          north: lanesCount,
          south: lanesCount,
          east: lanesCount,
          west: lanesCount,
        },
      },
      traffic: {
        arrivalRate,
        arrivalDistribution,
      },
    };

    fetch(`${API_BASE_URL}/api/v1/study/validate/monte-carlo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        numSeeds: seeds,
        num_seeds: seeds,
        duration: dur,
        confidenceLevel,
        customConfig,
      }),
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status.toString()}`);
        return r.json() as Promise<ValidationResult>;
      })
      .then((data) => {
        setResult(data);
        setIsRunning(false);
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Validation failed");
        setIsRunning(false);
      });
  };

  const exportValidationCSV = () => {
    if (!result) return;
    const headers = [
      "Seed",
      "Signal Delay (s)",
      "Roundabout Delay (s)",
      "Delta Delay (s)",
      "Signal Throughput (veh)",
      "Roundabout Throughput (veh)",
      "Signal Queue (veh)",
      "Roundabout Queue (veh)",
      "Lower delay",
    ];

    const rows = result.seedRuns.map((r) => [
      r.seed.toString(),
      r.signal.delay.toFixed(2),
      r.roundabout.delay.toFixed(2),
      (r.roundabout.delay - r.signal.delay).toFixed(2),
      r.signal.throughput.toFixed(1),
      r.roundabout.throughput.toFixed(1),
      r.signal.queue.toFixed(2),
      r.roundabout.queue.toFixed(2),
      (() => {
        const c = compare(r.signal.delay, r.roundabout.delay, SIMILARITY.delay);
        return c?.lower === "roundabout"
          ? "Roundabout"
          : c?.lower === "signal"
            ? "Signal"
            : "About the same";
      })(),
    ]);

    const csvContent =
      "data:text/csv;charset=utf-8," +
      [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute(
      "download",
      `monte_carlo_validation_n${result.numSeeds.toString()}_${duration.toString()}s.csv`,
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // The backend's flag, computed at the run's own alpha, is the only source of
  // significance on screen (no second, locally chosen threshold).
  const isMetricSignificant = (key: MetricKey) =>
    result ? result.comparison[key].significant : false;

  const allSignificant = result
    ? METRIC_KEYS.every((k) => isMetricSignificant(k))
    : false;

  const anySignificant = result
    ? METRIC_KEYS.some((k) => isMetricSignificant(k))
    : false;

  const resultAlpha = result?.alpha ?? 0.05;
  const resultLevelPct = Math.round((result?.confidenceLevel ?? 0.95) * 100);

  // Seeds by which control had the lower delay, using the app-wide "about the
  // same" rule (plainLanguage SIMILARITY.delay = backend study/tolerances.py)
  // so a fraction of a second is never counted as one control "winning".
  const roundaboutWinStats = useMemo(() => {
    const tally = { roundabout: 0, signal: 0, same: 0, total: 0 };
    if (!result) return tally;
    for (const r of result.seedRuns) {
      const c = compare(r.signal.delay, r.roundabout.delay, SIMILARITY.delay);
      tally.total += 1;
      if (c?.lower === "roundabout") tally.roundabout += 1;
      else if (c?.lower === "signal") tally.signal += 1;
      else tally.same += 1;
    }
    return tally;
  }, [result]);

  // Transform seed runs for Recharts bar chart
  const seedChartData = useMemo(() => {
    if (!result) return [];
    return result.seedRuns.map((r) => ({
      seed: r.seed.toString(),
      signal: Number(r.signal[chartMetric].toFixed(2)),
      roundabout: Number(r.roundabout[chartMetric].toFixed(2)),
      delta: Number(
        (r.roundabout[chartMetric] - r.signal[chartMetric]).toFixed(2),
      ),
    }));
  }, [result, chartMetric]);

  return (
    <div className="validation-dashboard">
      {/* ── Top Executive Header Row ────────────────────────────── */}
      <div className="validation-header-row">
        <div className="header-title-group">
          <div className="header-badge-row">
            <h2>🔬 Statistical Validation Studio</h2>
            <span className="header-mini-chip">Monte Carlo Engine</span>
            <span className="header-confidence-chip">
              Next run: {Math.round(confidenceLevel * 100)}% confidence (α ={" "}
              {alpha})
            </span>
          </div>
          <p className="header-subtitle">
            Stochastic paired-seed simulation evaluating Fixed-Time Signal vs.
            Modern Roundabout under identical randomized traffic arrivals using
            Welch’s two-sample t-test and Cohen’s d effect sizes.
          </p>
          <p className="header-subtitle">
            This study uses its own configurable scenario (set under Advanced
            Config). To check a comparison you ran in Compare, use “How reliable
            is this?” on its results page — it repeats that exact scenario.
          </p>
        </div>

        <div className="header-actions">
          {/* Inline Seeds & Duration selector in the same line as heading */}
          <div className="header-inline-controls">
            <div className="inline-param">
              <label htmlFor="validation-seeds">Seeds</label>
              <input
                id="validation-seeds"
                type="number"
                min={2}
                max={30}
                value={numSeeds}
                onChange={(e) => {
                  setNumSeeds(Number(e.target.value));
                }}
                title="Seeds (N): 2–30"
              />
            </div>
            <div className="inline-param">
              <label htmlFor="validation-duration">Duration</label>
              <div className="inline-unit-wrap">
                <input
                  id="validation-duration"
                  type="number"
                  min={10}
                  max={300}
                  step={10}
                  value={duration}
                  onChange={(e) => {
                    setDuration(Number(e.target.value));
                  }}
                  title="Duration per seed in seconds (10–300s)"
                />
                <span>s</span>
              </div>
            </div>
            <button
              type="button"
              className="header-run-btn"
              onClick={runValidation}
              disabled={isRunning}
              title="Execute Monte Carlo validation"
            >
              {isRunning ? "⏳ Running…" : "▶ Run"}
            </button>
          </div>

          {/* Config Settings Button named strictly 'Advanced Config' */}
          <button
            type="button"
            className={`header-tool-btn ${showConfigPanel ? "active" : ""}`}
            onClick={() => {
              setShowConfigPanel((v) => !v);
            }}
            title="Configure advanced simulation and statistical parameters"
          >
            ⚙️ Advanced Config
          </button>

          {/* Theory / Methodology Button */}
          <button
            type="button"
            className={`header-tool-btn ${showMethodologyDrawer ? "active" : ""}`}
            onClick={() => {
              setShowMethodologyDrawer((v) => !v);
            }}
            title="Toggle statistical hypothesis & methodology reference"
          >
            📐 {showMethodologyDrawer ? "Hide Theory" : "Theory & Methodology"}
          </button>

          {result && (
            <button
              type="button"
              className="export-csv-btn"
              onClick={exportValidationCSV}
              title="Download stochastic seed dataset as CSV"
            >
              📥 Export CSV
            </button>
          )}
        </div>
      </div>

      {/* ── Collapsible Methodology Drawer ─────────────────────────── */}
      {showMethodologyDrawer && (
        <div className="methodology-drawer">
          <div className="methodology-drawer-header">
            <h4>📐 Statistical Hypothesis & Testing Framework</h4>
            <span className="drawer-sub">
              Mathematical criteria for formal validation
            </span>
          </div>
          <div className="methodology-drawer-grid">
            <div className="methodology-card">
              <span className="method-tag null">H₀ Null Hypothesis</span>
              <h5>
                μ<sub>signal</sub> = μ<sub>roundabout</sub>
              </h5>
              <p>
                Assumes any gap is due to which vehicles happened to arrive
                when. Rejected (the difference is statistically supported) when{" "}
                <strong>p &lt; {alpha}</strong>. Not rejecting it does not show
                the controls are equal.
              </p>
            </div>

            <div className="methodology-card">
              <span className="method-tag alt">H₁ Alternative Hypothesis</span>
              <h5>
                μ<sub>signal</sub> ≠ μ<sub>roundabout</sub>
              </h5>
              <p>
                Means the difference is unlikely to be explained by arrival
                randomness alone, for this scenario and these seeds. It does not
                say which control is better, or that the result holds elsewhere.
              </p>
            </div>

            <div className="methodology-card">
              <span className="method-tag effect">
                Cohen&apos;s d Effect Size
              </span>
              <div className="effect-scale-grid">
                <span className="scale-pill neg">&lt;0.2 Negligible</span>
                <span className="scale-pill sm">0.2–0.5 Small</span>
                <span className="scale-pill med">0.5–0.8 Medium</span>
                <span className="scale-pill lg">&gt;0.8 Large</span>
              </div>
              <p className="effect-note">
                Quantifies practical real-world magnitude beyond statistical
                p-value.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── Rich Advanced Configuration Drawer ─────────────────────── */}
      {showConfigPanel && (
        <div className="validation-advanced-drawer">
          <div className="advanced-drawer-header">
            <div className="advanced-title-group">
              <h4>⚙️ Advanced Stochastic Simulation & Statistical Config</h4>
              <span className="drawer-sub">
                Fine-tune traffic Poisson generation, physical discretization,
                warmup periods, and statistical rigor
              </span>
            </div>
            <CloseButton
              label="Close settings drawer"
              onClick={() => {
                setShowConfigPanel(false);
              }}
            />
          </div>

          <div className="advanced-config-grid">
            {/* Section 1: Traffic Demand & Arrival Dynamics */}
            <div className="advanced-card">
              <div className="adv-card-header">
                <span className="adv-icon">🚗</span>
                <div>
                  <h5>Traffic Demand & Flow Dynamics</h5>
                  <span className="adv-sub">
                    Arrival intensity and headway distribution
                  </span>
                </div>
              </div>

              <div className="adv-field">
                <div className="adv-label-row">
                  <label>Arrival Rate (λ)</label>
                  <span className="adv-val-pill">
                    {arrivalRate.toFixed(2)} veh/s (
                    {Math.round(arrivalRate * 3600)} veh/h,{" "}
                    {Math.round(saturationRatio(arrivalRate, lanesCount) * 100)}
                    % of capacity)
                  </span>
                </div>
                <div className="adv-slider-wrap">
                  <input
                    type="range"
                    min={0.05}
                    max={
                      Math.ceil(
                        (1.5 * REFERENCE_CAPACITY_VPH[lanesCount]) / 36,
                      ) / 100
                    }
                    step={0.01}
                    value={arrivalRate}
                    onChange={(e) => {
                      setArrivalRate(Number(e.target.value));
                    }}
                  />
                  <div className="adv-slider-labels">
                    {[DEMAND_LEVELS[0], DEMAND_LEVELS[2], DEMAND_LEVELS[5]].map(
                      (d) => (
                        <span key={d.id}>
                          {demandRate(d, lanesCount).toFixed(2)} ({d.label})
                        </span>
                      ),
                    )}
                  </div>
                </div>
              </div>

              <div className="adv-field">
                <label>Arrival Pattern</label>
                <div className="adv-pill-group">
                  <button
                    type="button"
                    className={`adv-pill-btn ${arrivalDistribution === "poisson" ? "active" : ""}`}
                    onClick={() => {
                      setArrivalDistribution("poisson");
                    }}
                  >
                    🎲 Poisson (Stochastic Jitter)
                  </button>
                  <button
                    type="button"
                    className={`adv-pill-btn ${arrivalDistribution === "uniform" ? "active" : ""}`}
                    onClick={() => {
                      setArrivalDistribution("uniform");
                    }}
                  >
                    ⏱️ Uniform (Constant Headway)
                  </button>
                </div>
              </div>
            </div>

            {/* Section 2: Physical Discretization & Boundaries */}
            <div className="advanced-card">
              <div className="adv-card-header">
                <span className="adv-icon">⏱️</span>
                <div>
                  <h5>Simulation Physics & Boundaries</h5>
                  <span className="adv-sub">
                    Integration step, warmup time, and road extent
                  </span>
                </div>
              </div>

              <div className="adv-field">
                <div className="adv-label-row">
                  <label>Warmup Time (t_warm)</label>
                  <span className="adv-val-pill">{warmupTime.toFixed(1)}s</span>
                </div>
                <input
                  type="number"
                  min={0}
                  max={60}
                  step={5}
                  value={warmupTime}
                  onChange={(e) => {
                    setWarmupTime(Number(e.target.value));
                  }}
                  title="Warmup time in seconds"
                />
                <span className="adv-hint">
                  Clears initial startup transients before metrics recording
                  begins.
                </span>
              </div>

              <div className="adv-field">
                <label>Integration Step (Δt)</label>
                <div className="adv-pill-group">
                  <button
                    type="button"
                    className={`adv-pill-btn ${timeStep === 0.05 ? "active" : ""}`}
                    onClick={() => {
                      setTimeStep(0.05);
                    }}
                  >
                    0.05s (High Precision)
                  </button>
                  <button
                    type="button"
                    className={`adv-pill-btn ${timeStep === 0.1 ? "active" : ""}`}
                    onClick={() => {
                      setTimeStep(0.1);
                    }}
                  >
                    0.10s (Standard)
                  </button>
                  <button
                    type="button"
                    className={`adv-pill-btn ${timeStep === 0.2 ? "active" : ""}`}
                    onClick={() => {
                      setTimeStep(0.2);
                    }}
                  >
                    0.20s (Fast)
                  </button>
                </div>
              </div>

              <div className="adv-field">
                <label>Approach Road Length</label>
                <div className="adv-pill-group">
                  <button
                    type="button"
                    className={`adv-pill-btn ${approachLength === 150 ? "active" : ""}`}
                    onClick={() => {
                      setApproachLength(150);
                    }}
                  >
                    150m (Compact)
                  </button>
                  <button
                    type="button"
                    className={`adv-pill-btn ${approachLength === 200 ? "active" : ""}`}
                    onClick={() => {
                      setApproachLength(200);
                    }}
                  >
                    200m (Standard)
                  </button>
                  <button
                    type="button"
                    className={`adv-pill-btn ${approachLength === 300 ? "active" : ""}`}
                    onClick={() => {
                      setApproachLength(300);
                    }}
                  >
                    300m (Extended)
                  </button>
                </div>
              </div>
            </div>

            {/* Section 3: Statistical Rigor & Hypothesis Testing */}
            <div className="advanced-card">
              <div className="adv-card-header">
                <span className="adv-icon">📐</span>
                <div>
                  <h5>Statistical Rigor & Confidence</h5>
                  <span className="adv-sub">
                    Applies to the next run: interval width (Student-t) and the
                    significance threshold
                  </span>
                </div>
              </div>

              <div className="adv-field">
                <label>Lanes per approach</label>
                <div className="adv-pill-group">
                  {([1, 2, 3] as const).map((n) => (
                    <button
                      key={n}
                      type="button"
                      className={`adv-pill-btn ${lanesCount === n ? "active" : ""}`}
                      onClick={() => {
                        setLanesCount(n);
                      }}
                    >
                      {n === 1
                        ? "1 lane (calibrated comparison)"
                        : `${String(n)} lanes (exploratory)`}
                    </button>
                  ))}
                </div>
                <span className="adv-sub">
                  With more than one lane both junctions model every lane, but
                  drivers leaving the roundabout from an inner ring cross the
                  outer one without lane markings, so results are exploratory
                  and not the calibrated baseline.
                </span>
              </div>

              <div className="adv-field">
                <label>Confidence Level (1 - α)</label>
                <div className="adv-pill-group">
                  <button
                    type="button"
                    className={`adv-pill-btn ${confidenceLevel === 0.9 ? "active" : ""}`}
                    onClick={() => {
                      setConfidenceLevel(0.9);
                    }}
                  >
                    90% (α = 0.10)
                  </button>
                  <button
                    type="button"
                    className={`adv-pill-btn ${confidenceLevel === 0.95 ? "active" : ""}`}
                    onClick={() => {
                      setConfidenceLevel(0.95);
                    }}
                  >
                    95% (α = 0.05)
                  </button>
                  <button
                    type="button"
                    className={`adv-pill-btn ${confidenceLevel === 0.99 ? "active" : ""}`}
                    onClick={() => {
                      setConfidenceLevel(0.99);
                    }}
                  >
                    99% (α = 0.01)
                  </button>
                </div>
              </div>

              <div className="adv-field">
                <label>Seeds (N) & Duration / Seed (s)</label>
                <div className="adv-two-inputs">
                  <div>
                    <span className="input-mini-label">Seeds (2–30):</span>
                    <input
                      type="number"
                      min={2}
                      max={30}
                      value={numSeeds}
                      onChange={(e) => {
                        setNumSeeds(Number(e.target.value));
                      }}
                    />
                  </div>
                  <div>
                    <span className="input-mini-label">
                      Duration (10–300s):
                    </span>
                    <input
                      type="number"
                      min={10}
                      max={300}
                      step={10}
                      value={duration}
                      onChange={(e) => {
                        setDuration(Number(e.target.value));
                      }}
                    />
                  </div>
                </div>
              </div>

              <div className="adv-summary-box">
                <span>
                  ⚡ <strong>{numSeeds}</strong> seed pairs ×{" "}
                  <strong>{duration}s</strong> duration ={" "}
                  <strong>{numSeeds * 2}</strong> synchronized simulation
                  trials.
                </span>
              </div>
            </div>
          </div>

          <div className="advanced-drawer-footer">
            <div className="adv-foot-summary">
              <span>Active Config:</span>
              <span className="foot-chip">
                {arrivalDistribution === "poisson"
                  ? "🎲 Poisson"
                  : "⏱️ Uniform"}
              </span>
              <span className="foot-chip">λ = {arrivalRate} veh/s</span>
              <span className="foot-chip">
                {Math.round(confidenceLevel * 100)}% CI
              </span>
              <span className="foot-chip">Δt = {timeStep}s</span>
              <span className="foot-chip">{approachLength}m roads</span>
            </div>

            <div className="adv-foot-actions">
              <button
                type="button"
                className="adv-reset-btn"
                onClick={resetAdvancedDefaults}
                title="Reset advanced configuration to default values"
              >
                ↺ Reset Defaults
              </button>
              <button
                type="button"
                className="adv-close-btn"
                onClick={() => {
                  setShowConfigPanel(false);
                }}
              >
                ✕ Close
              </button>
              <button
                type="button"
                className="adv-apply-btn"
                onClick={runValidation}
                disabled={isRunning}
              >
                {isRunning
                  ? "⏳ Executing Trials…"
                  : "▶ Apply & Run Validation"}
              </button>
            </div>
          </div>
        </div>
      )}

      {error && <div className="validation-error">⚠ {error}</div>}

      {isRunning && (
        <div className="validation-loading">
          <LoaderMark />
          <span>
            Simulating {numSeeds} randomized seed pairs × {duration}s —
            computing two-sample Welch statistics…
          </span>
        </div>
      )}

      {/* ── Empty State: Interactive Pre-Flight Launchpad ────────── */}
      {!result && !isRunning && (
        <div className="validation-empty-card">
          <div className="empty-icon-halo">🔬</div>
          <h3>Stochastic Validation Engine Ready</h3>
          <p className="empty-desc">
            A single run reflects one random arrival sequence. Monte Carlo
            validation repeats the comparison over several seeds (both controls
            share each seed) and tests whether the differences in mean delay,
            throughput and queue are statistically significant, with 95%
            confidence intervals.
          </p>

          <div className="preflight-grid">
            <button
              type="button"
              className="preflight-card"
              onClick={() => {
                handleLaunchPreset(3, 120);
              }}
            >
              <div className="preflight-header">
                <span className="preflight-badge quick">⚡ Quick Check</span>
                <span className="preflight-time">~15s</span>
              </div>
              <h4>3 Seeds × 120 Seconds</h4>
              <p>
                A fast look at seed-to-seed variation. Too few seeds for strong
                conclusions.
              </p>
              <span className="preflight-cta">Launch Quick Check →</span>
            </button>

            <button
              type="button"
              className="preflight-card featured"
              onClick={() => {
                handleLaunchPreset(5, 240);
              }}
            >
              <div className="preflight-header">
                <span className="preflight-badge standard">🧪 Recommended</span>
                <span className="preflight-time">~40s</span>
              </div>
              <h4>5 Seeds × 240 Seconds</h4>
              <p>
                A reasonable default: enough seeds for a first Welch t-test,
                still quick to run.
              </p>
              <span className="preflight-cta">Launch Standard Rigor →</span>
            </button>

            <button
              type="button"
              className="preflight-card"
              onClick={() => {
                handleLaunchPreset(10, 300);
              }}
            >
              <div className="preflight-header">
                <span className="preflight-badge rigor">🔬 High Rigor</span>
                <span className="preflight-time">~2 min</span>
              </div>
              <h4>10 Seeds × 300 Seconds</h4>
              <p>
                More seeds and longer runs give narrower confidence intervals;
                slower to run.
              </p>
              <span className="preflight-cta">Launch High Rigor →</span>
            </button>
          </div>
        </div>
      )}

      {/* ── Validation Results View ──────────────────────────────── */}
      {result && !isRunning && (
        <>
          {/* Executive Verdict Banner */}
          <div
            className={`verdict-card ${
              allSignificant
                ? "all-sig"
                : anySignificant
                  ? "partial-sig"
                  : "non-sig"
            }`}
          >
            <div className="verdict-icon-box">
              {allSignificant ? "✅" : anySignificant ? "⚖️" : "❌"}
            </div>
            <div className="verdict-content">
              <div className="verdict-headline">
                <h4>
                  {allSignificant
                    ? `Difference statistically supported on all three metrics at α = ${resultAlpha.toString()}`
                    : anySignificant
                      ? `Difference statistically supported on some metrics at α = ${resultAlpha.toString()}`
                      : `No statistically supported difference at α = ${resultAlpha.toString()}`}
                </h4>
                <span className="win-rate-pill">
                  Lower delay by seed: roundabout{" "}
                  {roundaboutWinStats.roundabout}, signal{" "}
                  {roundaboutWinStats.signal}, about the same{" "}
                  {roundaboutWinStats.same} (of {roundaboutWinStats.total})
                </span>
              </div>

              <div className="verdict-meta-row">
                <span className="verdict-detail">
                  Based on{" "}
                  <strong>
                    {result.numSeeds} randomized Monte Carlo trials
                  </strong>{" "}
                  (Duration: {duration}s / seed) with {resultLevelPct}%
                  Student-t confidence intervals. Three metrics are tested
                  separately with no correction for that, and a result that is
                  not supported means the study cannot distinguish the controls,
                  not that they are equal.
                </span>

                <div className="significance-tag-row">
                  {METRIC_KEYS.map((k) => (
                    <span
                      key={k}
                      className={`sig-pill ${result.comparison[k].significant ? "active" : "inactive"}`}
                    >
                      {METRIC_LABELS[k]}:{" "}
                      {result.comparison[k].significant
                        ? `Supported (p<${resultAlpha.toString()})`
                        : "Not supported"}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {result.calibration && !result.calibration.calibrated && (
            <p className="validation-banner is-exploratory" role="note">
              <strong>Exploratory, not calibrated.</strong>{" "}
              {result.calibration.note}
            </p>
          )}
          {result.vehicleLimitReachedSeeds &&
            result.vehicleLimitReachedSeeds.length > 0 && (
              <p className="validation-banner is-exploratory" role="note">
                <strong>Demand was cut off.</strong> Vehicle generation reached
                its per-run limit in {result.vehicleLimitReachedSeeds.length} of{" "}
                {result.numSeeds} seeds, so those seeds did not receive their
                full demand.
              </p>
            )}
          {/* Studio Tab Bar */}
          <div className="validation-tab-bar">
            <button
              type="button"
              className={`val-tab-btn ${activeTab === "visual" ? "active" : ""}`}
              onClick={() => {
                setActiveTab("visual");
              }}
            >
              📊 Visual Comparison & Charts
            </button>
            <button
              type="button"
              className={`val-tab-btn ${activeTab === "table" ? "active" : ""}`}
              onClick={() => {
                setActiveTab("table");
              }}
            >
              📋 Per-Seed Raw Table ({result.numSeeds} trials)
            </button>
            <button
              type="button"
              className={`val-tab-btn ${activeTab === "methodology" ? "active" : ""}`}
              onClick={() => {
                setActiveTab("methodology");
              }}
            >
              📐 Statistical Method
            </button>
          </div>

          {/* Tab 1: Visual Comparison & Interactive Charts */}
          {activeTab === "visual" && (
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
                            className="delta-pill"
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
                                  <strong>{cmp.cohensD.toFixed(3)}</strong>
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
                                    <strong>
                                      {cmp.degreesOfFreedom.toFixed(1)}
                                    </strong>
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
                      Visualizing stochastic jitter across individual randomized
                      seed pairs
                    </span>
                  </div>

                  {/* Metric Switcher Pills */}
                  <div className="chart-metric-pills">
                    {METRIC_KEYS.map((k) => (
                      <button
                        key={k}
                        type="button"
                        className={`metric-pill-btn ${chartMetric === k ? "active" : ""}`}
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
                      <Tooltip
                        content={<CustomChartTooltip metric={chartMetric} />}
                      />
                      <Legend
                        wrapperStyle={{ paddingBottom: 10, fontSize: 12 }}
                      />
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
          )}

          {/* Tab 2: Raw Seed Runs Table */}
          {activeTab === "table" && (
            <div className="seed-runs-table-wrapper">
              <div className="runs-table-header">
                <div className="table-header-titles">
                  <h4>
                    Synchronized Raw Trials Dataset ({result.numSeeds} Seeds)
                  </h4>
                  <span className="table-meta-hint">
                    Paired trials executed with identical Poisson vehicle spawn
                    seeds
                  </span>
                </div>
                <button
                  type="button"
                  className="table-export-btn"
                  onClick={exportValidationCSV}
                >
                  📥 Download CSV
                </button>
              </div>

              <div className="table-scroll-container">
                <table>
                  <thead>
                    <tr>
                      <th>Seed #</th>
                      <th>Signal Delay</th>
                      <th>Rnd Delay</th>
                      <th>Δ Delay (s)</th>
                      <th>Signal Tput</th>
                      <th>Rnd Tput</th>
                      <th>Signal Queue</th>
                      <th>Rnd Queue</th>
                      <th title="Lower mean delay for this seed">
                        Lower delay
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.seedRuns.map((run) => {
                      const deltaDelay =
                        run.roundabout.delay - run.signal.delay;
                      const cmp = compare(
                        run.signal.delay,
                        run.roundabout.delay,
                        SIMILARITY.delay,
                      );
                      const winner = cmp?.lower ?? "tie";

                      return (
                        <tr key={run.seed}>
                          <td>
                            <strong className="seed-id-cell">
                              #{run.seed}
                            </strong>
                          </td>
                          <td>{run.signal.delay.toFixed(2)}s</td>
                          <td>{run.roundabout.delay.toFixed(2)}s</td>
                          <td
                            style={{
                              fontWeight: 700,
                            }}
                          >
                            {deltaDelay < 0 ? "" : "+"}
                            {deltaDelay.toFixed(2)}s
                          </td>
                          <td>{run.signal.throughput.toFixed(1)}</td>
                          <td>{run.roundabout.throughput.toFixed(1)}</td>
                          <td>{run.signal.queue.toFixed(2)}</td>
                          <td>{run.roundabout.queue.toFixed(2)}</td>
                          <td>
                            <span
                              className={
                                winner === "roundabout"
                                  ? "seed-winner-rnd"
                                  : "seed-winner-sig"
                              }
                            >
                              {winner === "roundabout"
                                ? "🔄 Roundabout"
                                : winner === "signal"
                                  ? "🚦 Signal"
                                  : "About the same"}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Tab 3: Detailed Methodology & Mathematical Proofs */}
          {activeTab === "methodology" && (
            <div className="methodology-full-view">
              <div className="methodology-proof-grid">
                <div className="proof-card">
                  <h4>
                    1. Statistical Significance (Welch&apos;s Two-Sample Test)
                  </h4>
                  <p>
                    Evaluates whether the difference between sample means μ₁ and
                    μ₂ exceeds what would be expected from chance alone under
                    unequal variances (σ₁² ≠ σ₂²):
                  </p>
                  <div className="math-box">
                    t = (X̄₁ - X̄₂) / √(s₁²/N₁ + s₂²/N₂)
                  </div>
                  <p className="proof-sub">
                    Significance criterion:{" "}
                    <strong>p &lt; {resultAlpha}</strong> (rejects H₀ at the{" "}
                    {resultLevelPct}% level the run used). The test is unpaired
                    even though both controls share seeds, which is the
                    conservative choice.
                  </p>
                </div>

                <div className="proof-card">
                  <h4>2. Practical Magnitude (Cohen&apos;s d Effect Size)</h4>
                  <p>
                    Standardized metric indicating the real-world operational
                    separation between the two traffic intersections independent
                    of sample size N:
                  </p>
                  <div className="math-box">d = (X̄₁ - X̄₂) / s_pooled</div>
                  <div className="effect-scale-pills">
                    <span className="scale-pill neg">&lt;0.2 Negligible</span>
                    <span className="scale-pill sm">0.2–0.5 Small</span>
                    <span className="scale-pill med">0.5–0.8 Medium</span>
                    <span className="scale-pill lg">&gt;0.8 Large Effect</span>
                  </div>
                </div>

                <div className="proof-card">
                  <h4>3. Confidence intervals (Student-t)</h4>
                  <p>
                    A range around each mean that should contain the long-run
                    mean in the stated share of repeated studies. The
                    t-distribution is used because only a few seeds are run (at
                    N = 5 the 95% multiplier is 2.776, not 1.96):
                  </p>
                  <div className="math-box">CI = X̄ ± t(N−1) × (s / √N)</div>
                  <p className="proof-sub">
                    Non-overlapping intervals are consistent with a real
                    difference; the Welch test above is the formal check.
                  </p>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      <IntegrityCheck />
    </div>
  );
};
