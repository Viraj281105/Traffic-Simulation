import React, { useId, useMemo } from "react";
import type { RunningMetrics } from "../types/simulation";
import type { MetricContext } from "../metrics/catalog";
import type { ScoringWeights } from "../types/scoring";
import {
  DEFAULT_WEIGHTS,
  SCORE_NORMALISATION,
  computeWeightedScore,
  weightedScoreReady,
} from "../types/scoring";
import "./WeightedScoringPanel.css";

interface WeightedScoringPanelProps {
  metricsSignal: RunningMetrics | undefined;
  metricsRoundabout: RunningMetrics | undefined;
  /** Warm-up state of each side. Omitted, the metrics are read as measured
   *  values (saved comparisons carry no timing). */
  signalCtx?: MetricContext;
  roundaboutCtx?: MetricContext;
  weights: ScoringWeights;
  onWeightsChange: (newWeights: ScoringWeights) => void;
}

const PRESETS: Array<{ label: string; weights: ScoringWeights }> = [
  { label: "Balanced", weights: DEFAULT_WEIGHTS },
  {
    label: "Throughput first",
    weights: {
      weightWaitTime: 15,
      weightThroughput: 50,
      weightQueue: 15,
      weightFairness: 10,
      weightStops: 10,
    },
  },
  {
    label: "Delay first",
    weights: {
      weightWaitTime: 50,
      weightThroughput: 15,
      weightQueue: 15,
      weightFairness: 10,
      weightStops: 10,
    },
  },
  {
    label: "Equal weights",
    weights: {
      weightWaitTime: 20,
      weightThroughput: 20,
      weightQueue: 20,
      weightFairness: 20,
      weightStops: 20,
    },
  },
];

const SLIDERS: Array<{
  key: keyof ScoringWeights;
  label: string;
  max: number;
}> = [
  { key: "weightWaitTime", label: "Average queued time", max: 60 },
  { key: "weightThroughput", label: "Throughput rate", max: 60 },
  { key: "weightQueue", label: "Average queue", max: 50 },
  { key: "weightFairness", label: "Directional fairness", max: 50 },
  { key: "weightStops", label: "Stops per vehicle", max: 40 },
];

/**
 * A decision aid, not a result: the user chooses how much each metric
 * matters and sees the resulting 0-100 score for each control. The panel
 * says which score is higher under the chosen weights and by how many
 * points — it does not declare an overall "winner".
 */
export const WeightedScoringPanel: React.FC<WeightedScoringPanelProps> = ({
  metricsSignal,
  metricsRoundabout,
  signalCtx,
  roundaboutCtx,
  weights,
  onWeightsChange,
}) => {
  const idBase = useId();
  const scoreSignal = useMemo(
    () => computeWeightedScore(metricsSignal, weights),
    [metricsSignal, weights],
  );
  const scoreRoundabout = useMemo(
    () => computeWeightedScore(metricsRoundabout, weights),
    [metricsRoundabout, weights],
  );
  const ready =
    weightedScoreReady(
      signalCtx ?? {
        metrics: metricsSignal,
        geometry: "fixed_time_signal",
        inWarmup: false,
      },
    ) &&
    weightedScoreReady(
      roundaboutCtx ?? {
        metrics: metricsRoundabout,
        geometry: "roundabout",
        inWarmup: false,
      },
    );
  const total = SLIDERS.reduce((sum, s) => sum + weights[s.key], 0);
  const share = (v: number) => (total > 0 ? (v / total) * 100 : 0);

  const gap = Math.round((scoreRoundabout - scoreSignal) * 10) / 10;
  const summary =
    total === 0
      ? "Set at least one weight above zero."
      : gap === 0
        ? "Both controls score the same under these weights."
        : `Under these weights the ${gap > 0 ? "roundabout" : "signal"} scores ${Math.abs(gap).toFixed(1)} points higher. This reflects the weights you chose, not a finding about either control.`;

  return (
    <section
      className="weighted-scoring-card"
      aria-labelledby={`${idBase}-title`}
    >
      <div className="scoring-header">
        <div className="scoring-title-group">
          <h3 className="scoring-title" id={`${idBase}-title`}>
            Weighted score (your priorities)
          </h3>
          <p className="scoring-subtitle">
            Combines five normalised metrics with weights you choose. The score
            reflects those weights — it is not an objective ranking.
          </p>
        </div>
        <div className="scoring-presets" role="group" aria-label="Presets">
          {PRESETS.map((p) => (
            <button
              key={p.label}
              type="button"
              className="preset-btn"
              aria-pressed={SLIDERS.every(
                (s) => p.weights[s.key] === weights[s.key],
              )}
              onClick={() => {
                onWeightsChange(p.weights);
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {!ready ? (
        <p className="score-summary" role="status">
          No score yet: the weighted score needs the warm-up to be over and at
          least one vehicle through on each side. Until then every input is a
          placeholder, not a measurement.
        </p>
      ) : (
        <div className="winner-banner" role="status">
          <div className="scores-comparison">
            <div className="score-tag">
              <span className="score-tag-name">Signal</span>
              <span className="score-tag-val">
                {scoreSignal.toFixed(1)} / 100
              </span>
              <span className="score-bar" aria-hidden="true">
                <i style={{ width: `${String(scoreSignal)}%` }} />
              </span>
            </div>
            <div className="score-tag">
              <span className="score-tag-name">Roundabout</span>
              <span className="score-tag-val">
                {scoreRoundabout.toFixed(1)} / 100
              </span>
              <span className="score-bar" aria-hidden="true">
                <i style={{ width: `${String(scoreRoundabout)}%` }} />
              </span>
            </div>
          </div>
          <p className="score-summary">{summary}</p>
        </div>
      )}

      <div className="weights-grid">
        {SLIDERS.map((s) => {
          const id = `${idBase}-${s.key}`;
          return (
            <div className="weight-control" key={s.key}>
              <div className="weight-header">
                <label htmlFor={id}>{s.label}</label>
                <span className="weight-percent">
                  {share(weights[s.key]).toFixed(0)}% of total
                </span>
              </div>
              <input
                id={id}
                type="range"
                min="0"
                max={s.max}
                step="5"
                className="weight-slider"
                value={weights[s.key]}
                aria-valuetext={`weight ${String(weights[s.key])}, ${share(weights[s.key]).toFixed(0)} percent of total`}
                onChange={(e) => {
                  onWeightsChange({
                    ...weights,
                    [s.key]: parseInt(e.target.value, 10),
                  });
                }}
              />
            </div>
          );
        })}
      </div>

      <details className="scoring-method">
        <summary>How the score is computed</summary>
        <p>
          Each metric is mapped onto 0–1, multiplied by its share of the total
          weight, and summed to a 0–100 score:
        </p>
        <ul>
          {SCORE_NORMALISATION.map(([name, rule]) => (
            <li key={name}>
              <strong>{name}:</strong> {rule}
            </li>
          ))}
        </ul>
        <p>
          The caps (60 s, 120 veh/min, 15 vehicles, 5 stops) are fixed reference
          points chosen for this tool, not standards. Both controls receive the
          same arrivals, so the throughput term mostly reflects how much traffic
          there was, and it compresses the other differences. The score ranks
          nothing on its own: it is a way to see how your priorities would tilt
          a comparison, and it is never a substitute for the measurements.
        </p>
      </details>
    </section>
  );
};
