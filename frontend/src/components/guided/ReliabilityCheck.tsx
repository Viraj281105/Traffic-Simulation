import { useState } from "react";
import type { SimulationConfigValues } from "../../types/config";
import { dashboardPayload } from "../../types/config";
import { runReliabilityCheck } from "../../services/api";
import {
  SIDE_TITLE,
  readReliability,
  type ReliabilityResult,
  type StudyMetric,
} from "../../metrics/plainLanguage";
import { VIEW_ROUTES, followLink } from "../../routing";

const METRIC_TITLES: Record<StudyMetric, string> = {
  delay: "Time lost per driver",
  throughput: "Vehicles through",
  queue: "Average queue",
};

const VERDICT_WORDS = {
  consistent: "Consistent difference",
  "not-consistent": "Not consistent — could be chance",
  "no-gap": "About the same",
} as const;

type State =
  | { kind: "idle" }
  | { kind: "running"; patterns: number }
  | { kind: "done"; result: ReliabilityResult }
  | { kind: "error"; message: string };

/** "How reliable is this?" made runnable: repeats the user's own scenario
 *  over several fresh traffic patterns on the backend (Monte Carlo study,
 *  Welch's t-test) and reads the outcome in plain words, with the
 *  statistics one disclosure away. */
export function ReliabilityCheck({
  config,
}: {
  config: SimulationConfigValues;
}) {
  const [state, setState] = useState<State>({ kind: "idle" });
  const [patterns, setPatterns] = useState(5);

  const run = () => {
    setState({ kind: "running", patterns });
    runReliabilityCheck<ReliabilityResult>(
      dashboardPayload(config, "fixed_time_signal"),
      patterns,
    )
      .then((result) => {
        setState({ kind: "done", result });
      })
      .catch((e: unknown) => {
        setState({
          kind: "error",
          message:
            e instanceof Error
              ? `The check could not run (${e.message}). Is the backend reachable?`
              : "The check could not run. Is the backend reachable?",
        });
      });
  };

  if (state.kind === "running") {
    return (
      <div className="reliability-box" role="status" aria-live="polite">
        <div className="reliability-running">
          <span className="spinner" aria-hidden="true" />
          <span>
            Re-running your junction with {state.patterns} new traffic patterns…
            This usually takes under a minute; busy or long scenarios can take a
            few minutes.
          </span>
        </div>
      </div>
    );
  }

  if (state.kind !== "done") {
    return (
      <div className="reliability-box">
        <p>
          Repeat this exact comparison with several <em>different</em> traffic
          patterns (new random arrivals, same junction and settings) to see
          whether the difference holds up or was down to luck.
        </p>
        <div className="reliability-actions">
          <label className="reliability-patterns">
            Traffic patterns
            <select
              value={patterns}
              onChange={(e) => {
                setPatterns(Number(e.target.value));
              }}
            >
              <option value={5}>5 (recommended)</option>
              <option value={10}>10 (more certain, slower)</option>
            </select>
          </label>
          <button type="button" className="guided-primary-btn" onClick={run}>
            Check reliability
          </button>
        </div>
        {state.kind === "error" && (
          <p className="q-note is-caution" role="alert">
            {state.message}
          </p>
        )}
      </div>
    );
  }

  const { result } = state;
  const readings = (["delay", "throughput", "queue"] as StudyMetric[]).map(
    (m) => readReliability(result, m),
  );
  const main = readings[0];

  return (
    <div className="reliability-box is-done">
      <p className={`reliability-headline verdict-${main.verdict}`}>
        {main.headline}
      </p>
      <p>{main.detail}</p>
      {result.calibration && !result.calibration.calibrated && (
        <p className="q-note is-caution">{result.calibration.note}</p>
      )}
      {result.vehicleLimitReachedSeeds &&
        result.vehicleLimitReachedSeeds.length > 0 && (
          <p className="q-note is-caution">
            Vehicle generation reached its limit in{" "}
            {result.vehicleLimitReachedSeeds.length} of {result.numSeeds}{" "}
            patterns, so those patterns did not receive the scenario&apos;s full
            demand.
          </p>
        )}

      <table className="plain-table">
        <caption className="sr-only">
          Reliability of each measure across {result.numSeeds} traffic patterns
        </caption>
        <thead>
          <tr>
            <th scope="col">Measure</th>
            <th scope="col">Across {result.numSeeds} patterns</th>
            <th scope="col">Lower at</th>
          </tr>
        </thead>
        <tbody>
          {readings.map((reading) => (
            <tr key={reading.metric}>
              <th scope="row">{METRIC_TITLES[reading.metric]}</th>
              <td>{VERDICT_WORDS[reading.verdict]}</td>
              <td>
                signal {reading.tally.signal} · roundabout{" "}
                {reading.tally.roundabout}
                {reading.tally.tie > 0
                  ? ` · tied ${String(reading.tally.tie)}`
                  : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <details className="how-measured">
        <summary>Show the statistics</summary>
        <p>
          Each pattern ran both controls for {result.duration.toFixed(0)} s of
          simulated time on the same arrivals. “Consistent” means Welch’s
          two-sample t-test found the difference significant at the 5% level;
          the ± intervals are 95% Student-t intervals (used because only a few
          patterns are run); the size word is Cohen’s d (below 0.2 negligible,
          0.2 small, 0.5 medium, 0.8 large). The patterns are new ones, not the
          run you watched.
        </p>
        <div className="multi-run-scroll">
          <table className="plain-table mono-cells">
            <thead>
              <tr>
                <th scope="col">Measure</th>
                <th scope="col">{SIDE_TITLE.signal} mean ± 95% CI</th>
                <th scope="col">{SIDE_TITLE.roundabout} mean ± 95% CI</th>
                <th scope="col">p-value</th>
                <th scope="col">Cohen’s d</th>
                <th scope="col">df</th>
              </tr>
            </thead>
            <tbody>
              {readings.map(({ metric }) => {
                const s = result.signal[metric];
                const r = result.roundabout[metric];
                const c = result.comparison[metric];
                return (
                  <tr key={metric}>
                    <th scope="row">{METRIC_TITLES[metric]}</th>
                    <td>
                      {s.mean.toFixed(2)} ± {s.ci95.toFixed(2)}
                    </td>
                    <td>
                      {r.mean.toFixed(2)} ± {r.ci95.toFixed(2)}
                    </td>
                    <td>
                      {c.pValue === null
                        ? "—"
                        : c.pValue < 0.001
                          ? "< 0.001"
                          : c.pValue.toFixed(3)}
                    </td>
                    <td>{c.cohensD.toFixed(2)}</td>
                    <td>
                      {c.degreesOfFreedom === undefined
                        ? "—"
                        : c.degreesOfFreedom.toFixed(1)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="multi-run-scroll">
          <table className="plain-table mono-cells">
            <caption>Each traffic pattern (seed)</caption>
            <thead>
              <tr>
                <th scope="col">Pattern</th>
                <th scope="col">Signal delay (s)</th>
                <th scope="col">Roundabout delay (s)</th>
                <th scope="col">Signal through</th>
                <th scope="col">Roundabout through</th>
              </tr>
            </thead>
            <tbody>
              {result.seedRuns.map((run) => (
                <tr key={run.seed}>
                  <th scope="row">#{run.seed}</th>
                  <td>{run.signal.delay.toFixed(1)}</td>
                  <td>{run.roundabout.delay.toFixed(1)}</td>
                  <td>{run.signal.throughput.toFixed(0)}</td>
                  <td>{run.roundabout.throughput.toFixed(0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>
          For configurable studies (confidence level, time step, arrival
          pattern), use{" "}
          <a
            href={VIEW_ROUTES.validation}
            onClick={(e) => {
              followLink(e, VIEW_ROUTES.validation);
            }}
          >
            Statistical validation in the Research lab
          </a>
          .
        </p>
      </details>

      <button
        type="button"
        className="guided-link-btn small"
        onClick={() => {
          setState({ kind: "idle" });
        }}
      >
        Run the check again
      </button>
    </div>
  );
}
