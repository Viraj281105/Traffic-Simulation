import React, { useState, useMemo } from "react";
import { SlidersHorizontal } from "lucide-react";
import { Loader } from "./ui/Loader";
import { Overlay } from "./ui/Overlay";
import { PageHeader } from "./ui/PageHeader";
import { DEFAULT_CONFIG_VALUES } from "../types/config";
import {
  DEMAND_LEVELS,
  demandLevelFor,
  demandRate,
  demandVph,
} from "../types/demand";

/** Study sizes offered before the first run. Every run keeps the 30 s
 *  warm-up out of the measurement, so runs are long enough to leave
 *  at least 90 s of measured traffic. */
const VALIDATION_PRESETS = [
  {
    id: "quick",
    title: "Quick check",
    seeds: 3,
    duration: 120,
    note: "A first look; too few patterns for firm conclusions.",
  },
  {
    id: "standard",
    title: "Standard",
    seeds: 5,
    duration: 240,
    note: "The size of the published calibrated study.",
  },
  {
    id: "thorough",
    title: "Thorough",
    seeds: 10,
    duration: 300,
    note: "Narrower intervals; takes several minutes.",
  },
] as const;
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
import { SIMILARITY, compare } from "../metrics/plainLanguage";
import { IntegrityCheck } from "./IntegrityCheck";
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

  const level = demandLevelFor(arrivalRate, lanesCount);

  return (
    <div className="uf-page uf-page--wide validation-dashboard">
      <PageHeader
        eyebrow="Research lab"
        title="Statistical validation"
        lead={
          <>
            <p>
              Repeats the comparison over several random traffic patterns (both
              controls get the same pattern each time) and tests whether the
              differences in mean delay, throughput and queue are larger than
              the pattern-to-pattern variation: Welch&apos;s t-test,
              Cohen&apos;s d and Student-t confidence intervals.
            </p>
            <p>
              This study has its own scenario (Study settings). To check a
              comparison you ran in Compare, use “How reliable is this?” on its
              results page.
            </p>
          </>
        }
        actions={
          <>
            <button
              type="button"
              className="uf-btn uf-btn--primary"
              onClick={runValidation}
              disabled={isRunning}
              title="Run the study with the current settings"
            >
              {isRunning ? "Running…" : "Run study"}
            </button>
            <button
              type="button"
              className="uf-btn"
              onClick={() => {
                setShowConfigPanel(true);
              }}
              aria-haspopup="dialog"
            >
              <SlidersHorizontal aria-hidden="true" />
              Study settings
            </button>
            <button
              type="button"
              className="uf-btn"
              onClick={() => {
                setShowMethodologyDrawer(true);
              }}
              aria-haspopup="dialog"
            >
              Method
            </button>
            {result && (
              <button
                type="button"
                className="uf-btn"
                onClick={exportValidationCSV}
              >
                Export CSV
              </button>
            )}
          </>
        }
      />

      <p className="sweep-summary-line">
        {numSeeds.toString()} traffic patterns × {duration.toString()} s,{" "}
        {warmupTime.toFixed(0)} s warm-up excluded,{" "}
        {level ? level.label.toLowerCase() : "custom"} demand (
        {Math.round(arrivalRate * 3600).toLocaleString()} veh/h),{" "}
        {lanesCount === 1 ? "1 lane" : `${lanesCount.toString()} lanes`} per
        approach, {Math.round(confidenceLevel * 100)}% confidence (α = {alpha}).
      </p>

      {/* ── Method drawer ── */}
      {showMethodologyDrawer && (
        <Overlay
          variant="drawer"
          title="Method"
          description="What the test checks, and what it does not."
          closeLabel="Close method"
          onClose={() => {
            setShowMethodologyDrawer(false);
          }}
        >
          <div className="uf-form">
            <section className="uf-form-section">
              <h3 className="uf-form-section__title">
                Null hypothesis H₀: μ<sub>signal</sub> = μ<sub>roundabout</sub>
              </h3>
              <p className="uf-help">
                Any gap is due to which vehicles happened to arrive when. It is
                rejected (the difference is statistically supported) when{" "}
                <strong>p &lt; {alpha}</strong>. Not rejecting it does not show
                the controls are equal.
              </p>
            </section>
            <section className="uf-form-section">
              <h3 className="uf-form-section__title">
                Alternative H₁: μ<sub>signal</sub> ≠ μ<sub>roundabout</sub>
              </h3>
              <p className="uf-help">
                The difference is unlikely to come from arrival randomness
                alone, for this scenario and these patterns. It does not say
                which control is better in general.
              </p>
            </section>
            <section className="uf-form-section">
              <h3 className="uf-form-section__title">
                Effect size (Cohen&apos;s d)
              </h3>
              <p className="uf-help">
                Size of the difference relative to the spread: below 0.2
                negligible, 0.2–0.5 small, 0.5–0.8 medium, above 0.8 large.
              </p>
            </section>
            <section className="uf-form-section">
              <h3 className="uf-form-section__title">Limitations</h3>
              <p className="uf-help">
                The test is unpaired (Welch) although both controls share each
                pattern, three metrics are tested without a multiple-comparison
                correction, and patterns are drawn at random for each study
                (they are listed in the results).
              </p>
            </section>
          </div>
        </Overlay>
      )}

      {/* ── Study settings drawer ── */}
      {showConfigPanel && (
        <Overlay
          variant="drawer"
          wide
          title="Study settings"
          description="Scenario, run length and confidence level for the next study."
          closeLabel="Close study settings"
          onClose={() => {
            setShowConfigPanel(false);
          }}
          footer={
            <>
              <button
                type="button"
                className="uf-btn uf-btn--ghost"
                onClick={resetAdvancedDefaults}
              >
                Reset to defaults
              </button>
              <button
                type="button"
                className="uf-btn uf-btn--primary"
                onClick={runValidation}
                disabled={isRunning}
              >
                {isRunning ? "Running…" : "Run study"}
              </button>
            </>
          }
        >
          <div className="uf-form">
            <fieldset className="uf-form-section">
              <legend className="uf-form-section__title">Demand</legend>
              <div className="uf-choice-list uf-choice-list--grid">
                {DEMAND_LEVELS.map((d) => (
                  <button
                    key={d.id}
                    type="button"
                    className="uf-choice"
                    aria-pressed={level?.id === d.id}
                    onClick={() => {
                      setArrivalRate(demandRate(d, lanesCount));
                    }}
                  >
                    <span className="uf-choice__title">{d.label}</span>
                    <span className="uf-choice__desc">
                      {demandVph(d, lanesCount).toLocaleString()} veh/h ·{" "}
                      {Math.round(d.ratio * 100)}% of capacity
                    </span>
                  </button>
                ))}
              </div>
              <div className="uf-field">
                <span className="uf-label">Arrival process</span>
                <div className="uf-segmented" role="group">
                  <button
                    type="button"
                    aria-pressed={arrivalDistribution === "poisson"}
                    onClick={() => {
                      setArrivalDistribution("poisson");
                    }}
                  >
                    Poisson (random)
                  </button>
                  <button
                    type="button"
                    aria-pressed={arrivalDistribution === "uniform"}
                    onClick={() => {
                      setArrivalDistribution("uniform");
                    }}
                  >
                    Uniform (evenly spaced)
                  </button>
                </div>
              </div>
              <div className="uf-field">
                <span className="uf-label">Lanes per approach</span>
                <div className="uf-segmented" role="group">
                  {([1, 2, 3] as const).map((n) => (
                    <button
                      key={n}
                      type="button"
                      aria-pressed={lanesCount === n}
                      onClick={() => {
                        const kept = demandLevelFor(arrivalRate, lanesCount);
                        setLanesCount(n);
                        if (kept) setArrivalRate(demandRate(kept, n));
                      }}
                    >
                      {n === 1 ? "1 lane" : `${n.toString()} lanes`}
                    </button>
                  ))}
                </div>
                {lanesCount > 1 && (
                  <p className="uf-help">
                    Exploratory: both junctions model every lane, but the
                    roundabout has no lane markings for drivers leaving from an
                    inner ring.
                  </p>
                )}
              </div>
            </fieldset>

            <fieldset className="uf-form-section">
              <legend className="uf-form-section__title">Runs</legend>
              <div className="uf-field-row">
                <label className="uf-field">
                  <span className="uf-label">Traffic patterns (2–30)</span>
                  <input
                    className="uf-input"
                    type="number"
                    min={2}
                    max={30}
                    value={numSeeds}
                    onChange={(e) => {
                      setNumSeeds(Number(e.target.value));
                    }}
                  />
                </label>
                <label className="uf-field">
                  <span className="uf-label">Duration per run (s)</span>
                  <input
                    className="uf-input"
                    type="number"
                    min={60}
                    max={300}
                    step={10}
                    value={duration}
                    onChange={(e) => {
                      setDuration(Number(e.target.value));
                    }}
                  />
                </label>
              </div>
              <label className="uf-field">
                <span className="uf-field-head">
                  <span className="uf-label">Warm-up excluded</span>
                  <output className="uf-value">
                    {warmupTime.toFixed(0)} s
                  </output>
                </span>
                <input
                  type="range"
                  min={0}
                  max={60}
                  step={5}
                  value={warmupTime}
                  onChange={(e) => {
                    setWarmupTime(Number(e.target.value));
                  }}
                  className="uf-range"
                />
              </label>
              <div className="uf-field">
                <span className="uf-label">Time step (Δt)</span>
                <div className="uf-segmented" role="group">
                  {[0.05, 0.1, 0.2].map((dt) => (
                    <button
                      key={dt}
                      type="button"
                      aria-pressed={timeStep === dt}
                      onClick={() => {
                        setTimeStep(dt);
                      }}
                    >
                      {dt.toFixed(2)} s
                    </button>
                  ))}
                </div>
              </div>
              <div className="uf-field">
                <span className="uf-label">Approach length</span>
                <div className="uf-segmented" role="group">
                  {[150, 200, 300].map((len) => (
                    <button
                      key={len}
                      type="button"
                      aria-pressed={approachLength === len}
                      onClick={() => {
                        setApproachLength(len);
                      }}
                    >
                      {len.toString()} m
                    </button>
                  ))}
                </div>
              </div>
            </fieldset>

            <fieldset className="uf-form-section">
              <legend className="uf-form-section__title">Confidence</legend>
              <div className="uf-segmented" role="group">
                {([0.9, 0.95, 0.99] as const).map((c) => (
                  <button
                    key={c}
                    type="button"
                    aria-pressed={confidenceLevel === c}
                    onClick={() => {
                      setConfidenceLevel(c);
                    }}
                  >
                    {Math.round(c * 100)}% (α = {(1 - c).toFixed(2)})
                  </button>
                ))}
              </div>
              <p className="uf-help">
                Sets the Student-t interval width and the significance threshold
                of the next study.
              </p>
            </fieldset>
          </div>
        </Overlay>
      )}

      {error && (
        <div className="uf-callout uf-callout--danger" role="alert">
          <span>
            <strong>The study did not complete.</strong> {error}
          </span>
        </div>
      )}

      {isRunning && (
        <Loader
          layout="fill"
          label={`Running ${numSeeds.toString()} traffic patterns on both controls (${duration.toString()} s each)`}
        />
      )}

      {!result && !isRunning && (
        <div className="uf-empty">
          <p className="uf-empty__title">No study yet</p>
          <p className="uf-empty__text">
            One run is one random traffic pattern. Choose how many patterns to
            repeat the comparison over; more patterns and longer runs give
            narrower intervals but take longer.
          </p>
          <div className="study-presets">
            {VALIDATION_PRESETS.map((p) => (
              <button
                key={p.id}
                type="button"
                className="uf-choice"
                onClick={() => {
                  handleLaunchPreset(p.seeds, p.duration);
                }}
              >
                <span className="uf-choice__title">{p.title}</span>
                <span className="uf-choice__desc">
                  {p.seeds.toString()} patterns × {p.duration.toString()} s.{" "}
                  {p.note}
                </span>
              </button>
            ))}
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
              Charts
            </button>
            <button
              type="button"
              className={`val-tab-btn ${activeTab === "table" ? "active" : ""}`}
              onClick={() => {
                setActiveTab("table");
              }}
            >
              Per-pattern table ({result.numSeeds} trials)
            </button>
            <button
              type="button"
              className={`val-tab-btn ${activeTab === "methodology" ? "active" : ""}`}
              onClick={() => {
                setActiveTab("methodology");
              }}
            >
              How it was tested
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
                              label="Traffic signal"
                              stat={sigStat}
                              color={SIGNAL_COLOR}
                              maxMean={maxMean}
                              ciMargin={ciSig}
                            />
                            <ModernCIBar
                              label="Roundabout"
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
                    <h4>Result for each traffic pattern</h4>
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
                        name="Traffic signal"
                        fill={SIGNAL_COLOR}
                        radius={[4, 4, 0, 0]}
                        animationDuration={400}
                        animationEasing="ease-out"
                      />
                      <Bar
                        dataKey="roundabout"
                        name="Roundabout"
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
                  <h4>Per-pattern results ({result.numSeeds} patterns)</h4>
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
                  Download CSV
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
                                ? "Roundabout"
                                : winner === "signal"
                                  ? "Signal"
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
