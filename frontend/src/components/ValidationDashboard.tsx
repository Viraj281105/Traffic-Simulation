import React, { useState } from "react";
import { API_BASE_URL } from "../config";
import "./ValidationDashboard.css";

// ── Types ──────────────────────────────────────────────────────────────────

interface StatResult {
  mean: number;
  std: number;
  min: number;
  max: number;
  ci95: number;
}

interface SeedRun {
  seed: number;
  signal: { delay: number; throughput: number; queue: number };
  roundabout: { delay: number; throughput: number; queue: number };
}

interface ValidationResult {
  numSeeds: number;
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
    delay: { pValue: number | null; significant: boolean; cohensD: number };
    throughput: {
      pValue: number | null;
      significant: boolean;
      cohensD: number;
    };
    queue: { pValue: number | null; significant: boolean; cohensD: number };
  };
  seedRuns: SeedRun[];
}

const METRIC_KEYS = ["delay", "throughput", "queue"] as const;
type MetricKey = (typeof METRIC_KEYS)[number];

const METRIC_LABELS: Record<MetricKey, string> = {
  delay: "Avg Delay (s)",
  throughput: "Throughput (veh)",
  queue: "Avg Queue (veh)",
};

const SIGNAL_COLOR = "#4d96ff";
const ROUND_COLOR = "#2ecc40";

// ── CI Bar Component ────────────────────────────────────────────────────────

function CIBar({
  label,
  stat,
  color,
  maxMean,
}: {
  label: string;
  stat: StatResult;
  color: string;
  maxMean: number;
}) {
  const pct = maxMean > 0 ? (stat.mean / maxMean) * 100 : 0;
  const ciWidthPct = maxMean > 0 ? (stat.ci95 / maxMean) * 100 : 0;
  const ciLeft = Math.max(0, pct - ciWidthPct / 2);

  return (
    <div className="ci-row">
      <span className="ci-label">{label}</span>
      <div className="ci-bar-track">
        <div
          className="ci-bar-fill"
          style={{
            width: `${pct.toString()}%`,
            background: color,
            opacity: 0.6,
          }}
        />
        <div
          className="ci-bar-ci"
          style={{
            left: `${ciLeft.toString()}%`,
            width: `${ciWidthPct.toString()}%`,
          }}
        />
      </div>
      <div className="ci-values">
        <span className="ci-mean" style={{ color }}>
          {stat.mean.toFixed(2)}
        </span>
        <span className="ci-range">
          ± {stat.ci95.toFixed(2)} (σ={stat.std.toFixed(2)})
        </span>
      </div>
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────────────────────

export const ValidationDashboard: React.FC = () => {
  const [numSeeds, setNumSeeds] = useState(5);
  const [duration, setDuration] = useState(30);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ValidationResult | null>(null);

  const runValidation = () => {
    setIsRunning(true);
    setError(null);
    fetch(`${API_BASE_URL}/api/v1/study/validate/monte-carlo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ num_seeds: numSeeds, duration }),
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

  const allSignificant = result
    ? METRIC_KEYS.every((k) => result.comparison[k].significant)
    : false;

  const anySignificant = result
    ? METRIC_KEYS.some((k) => result.comparison[k].significant)
    : false;

  return (
    <div className="validation-dashboard">
      {/* ── Trigger panel ─────────────────────────────── */}
      <div className="validation-trigger-panel">
        <h3>🔬 Monte Carlo Statistical Validation</h3>
        <div className="validation-controls">
          <div className="validation-field">
            <label>Seeds (N)</label>
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
          <div className="validation-field">
            <label>Duration / Seed (s)</label>
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
          <button
            className="validation-run-btn"
            onClick={runValidation}
            disabled={isRunning}
          >
            {isRunning ? "⏳ Running…" : "▶ Run Validation"}
          </button>
        </div>
        {error && <div className="validation-error">⚠ {error}</div>}
        {isRunning && (
          <div className="validation-loading">
            <div className="spin-purple" />
            Executing {numSeeds} randomized seeds × {duration}s — computing
            confidence intervals…
          </div>
        )}
      </div>

      {/* ── Results ───────────────────────────────────── */}
      {result && !isRunning && (
        <>
          {/* Verdict */}
          <div
            className={`verdict-card ${
              anySignificant ? "significant" : "not-significant"
            }`}
          >
            <span className="verdict-icon">
              {allSignificant ? "✅" : anySignificant ? "⚠️" : "❌"}
            </span>
            <div className="verdict-text">
              <strong>
                {allSignificant
                  ? "Statistically Significant Difference Across All Metrics"
                  : anySignificant
                    ? "Partial Statistical Significance Detected"
                    : "No Statistically Significant Difference Detected"}
              </strong>
              <span>
                Based on {result.numSeeds} randomized Monte Carlo seeds with 95%
                confidence intervals (α = 0.05). Significance tags:{" "}
                <span className="significance-tags">
                  {METRIC_KEYS.map((k) => (
                    <span
                      key={k}
                      className={`sig-tag ${
                        result.comparison[k].significant ? "yes" : "no"
                      }`}
                    >
                      {METRIC_LABELS[k]}:{" "}
                      {result.comparison[k].significant
                        ? "Significant"
                        : "Not Significant"}
                    </span>
                  ))}
                </span>
              </span>
            </div>
          </div>

          {/* Per-metric CI stat cards */}
          <div className="stats-grid">
            {METRIC_KEYS.map((key) => {
              const sigStat = result.signal[key];
              const rndStat = result.roundabout[key];
              const maxMean = Math.max(
                sigStat.mean + sigStat.ci95,
                rndStat.mean + rndStat.ci95,
                0.01,
              );
              const cmp = result.comparison[key];

              return (
                <div className="stat-card" key={key}>
                  <h4>{METRIC_LABELS[key]}</h4>
                  <div className="ci-comparison">
                    <CIBar
                      label="Fixed-Time Signal"
                      stat={sigStat}
                      color={SIGNAL_COLOR}
                      maxMean={maxMean}
                    />
                    <CIBar
                      label="Roundabout"
                      stat={rndStat}
                      color={ROUND_COLOR}
                      maxMean={maxMean}
                    />
                    <div
                      style={{
                        marginTop: 6,
                        fontSize: 11,
                        color: cmp.significant ? "#ffd93d" : "#555",
                      }}
                    >
                      Cohen's d = {cmp.cohensD.toFixed(3)}
                      {cmp.pValue !== null && (
                        <>
                          {" "}
                          · p ={" "}
                          {cmp.pValue < 0.001
                            ? "<0.001"
                            : cmp.pValue.toFixed(3)}
                        </>
                      )}{" "}
                      ·{" "}
                      <strong
                        style={{ color: cmp.significant ? "#ffd93d" : "#555" }}
                      >
                        {cmp.significant ? "★ Significant" : "Not Significant"}
                      </strong>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Per-seed runs table */}
          {result.seedRuns.length > 0 && (
            <div className="seed-runs-table">
              <h4>Per-Seed Raw Results ({result.numSeeds} seeds)</h4>
              <table>
                <thead>
                  <tr>
                    <th>Seed</th>
                    <th>Sig Delay</th>
                    <th>Rnd Delay</th>
                    <th>Sig Tput</th>
                    <th>Rnd Tput</th>
                    <th>Sig Queue</th>
                    <th>Rnd Queue</th>
                  </tr>
                </thead>
                <tbody>
                  {result.seedRuns.map((run) => (
                    <tr key={run.seed}>
                      <td>{run.seed}</td>
                      <td>{run.signal.delay.toFixed(2)}</td>
                      <td>{run.roundabout.delay.toFixed(2)}</td>
                      <td>{run.signal.throughput.toFixed(1)}</td>
                      <td>{run.roundabout.throughput.toFixed(1)}</td>
                      <td>{run.signal.queue.toFixed(2)}</td>
                      <td>{run.roundabout.queue.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
};
