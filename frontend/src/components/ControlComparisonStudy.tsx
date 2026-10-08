import { useId, useState } from "react";
import { useStudyJob } from "../hooks/useStudyJob";
import { STUDY_JOB_ROUTES } from "../services/studyJobs";
import { StudyProgress } from "./ui/StudyProgress";
import { downloadText } from "../metrics/catalog";
import { ADAPTIVE_DEFAULTS } from "../types/config";

/** V1.3 three-way study result (backend study/control_comparison.py). */
type Control = "fixed_time" | "adaptive" | "roundabout";
type Reading = "lower" | "higher" | "tie" | "inconclusive";

interface Stat {
  mean: number;
  ci: number;
  ciConfidence: number;
  ciDegreesOfFreedom: number;
}

interface PairResult {
  meanDifference: number;
  ciLow: number | null;
  ciHigh: number | null;
  reading: Reading;
}

interface LevelResult {
  level: string;
  demandVph: number;
  degreeOfSaturation: number;
  vehicleLimitReached: boolean;
  controls: Record<Control, Partial<Record<string, Stat>>>;
  delayComparisons: Partial<Record<string, PairResult>>;
}

export interface ControlComparisonResult {
  controls: Control[];
  lanesPerApproach: number;
  seeds: number[];
  duration: number;
  warmupTime: number;
  confidenceLevel: number;
  adaptiveSettings: Record<string, number>;
  calibration: { calibrated: boolean; note: string };
  tieTolerance: { absSeconds: number; relative: number };
  collisionCount: Record<Control, number>;
  method: { design: string; interval: string; delayComparison: string };
  results: LevelResult[];
}

const CONTROLS: Control[] = ["fixed_time", "adaptive", "roundabout"];
const CONTROL_TITLE: Record<Control, string> = {
  fixed_time: "Fixed-time",
  adaptive: "Adaptive",
  roundabout: "Roundabout",
};
const LEVEL_TITLE: Record<string, string> = {
  light: "Light",
  moderate: "Moderate",
  busy: "Busy",
  near: "Near capacity",
  capacity: "At capacity",
  over: "Over capacity",
};
const PAIRS: { key: string; a: Control; b: Control }[] = [
  { key: "adaptive_vs_fixed_time", a: "adaptive", b: "fixed_time" },
  { key: "adaptive_vs_roundabout", a: "adaptive", b: "roundabout" },
  { key: "fixed_time_vs_roundabout", a: "fixed_time", b: "roundabout" },
];

function stat(s: Stat | undefined, decimals = 1): string {
  if (!s) return "—";
  return `${s.mean.toFixed(decimals)} ± ${s.ci.toFixed(decimals)}`;
}

function readingText(p: PairResult | undefined, a: Control, b: Control) {
  if (!p) return "—";
  const words: Record<Reading, string> = {
    lower: `${CONTROL_TITLE[a]} lower`,
    higher: `${CONTROL_TITLE[b]} lower`,
    tie: "About the same",
    inconclusive: "Inconclusive",
  };
  const ci =
    p.ciLow === null || p.ciHigh === null
      ? ""
      : ` (${p.meanDifference.toFixed(1)} s, ${p.ciLow.toFixed(1)} to ${p.ciHigh.toFixed(1)})`;
  return words[p.reading] + ci;
}

function csvOf(result: ControlComparisonResult): string {
  const rows = [
    [
      "level",
      "demand_vph",
      "control",
      "delay_mean_s",
      "delay_ci_s",
      "wait_mean_s",
      "throughput_mean",
      "queue_mean",
      "max_queue_mean",
      "phase_changes_mean",
      "green_mean_s",
      "green_utilisation_mean",
    ].join(","),
  ];
  for (const level of result.results) {
    for (const c of CONTROLS) {
      const s = level.controls[c];
      const v = (k: string) => (s[k] ? String(s[k].mean) : "");
      rows.push(
        [
          level.level,
          String(level.demandVph),
          c,
          v("averageDelay"),
          s.averageDelay ? String(s.averageDelay.ci) : "",
          v("averageWaitTime"),
          v("throughput"),
          v("averageQueueLength"),
          v("maxQueueLength"),
          v("phaseChanges"),
          v("averageGreenDuration"),
          v("greenUtilisation"),
        ].join(","),
      );
    }
  }
  return rows.join("\n") + "\n";
}

/** Research Lab: fixed-time vs adaptive signal vs roundabout over demand
 *  levels and seeds, with the same traffic for all three. Evidence, not a
 *  verdict: every reading carries its interval, ties and inconclusive
 *  results are reported as such. */
export function ControlComparisonStudy() {
  const [lanes, setLanes] = useState(1);
  const [seeds, setSeeds] = useState(5);
  const [duration, setDuration] = useState(300);
  const [result, setResult] = useState<ControlComparisonResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const study = useStudyJob();
  const lanesId = useId();
  const seedsId = useId();
  const durationId = useId();

  const run = () => {
    setRunning(true);
    setError(null);
    study
      .run<ControlComparisonResult>(STUDY_JOB_ROUTES.controlComparison, {
        lanes,
        numSeeds: seeds,
        duration,
      })
      .then((r) => {
        setResult(r);
      })
      .catch((e: unknown) => {
        setError(
          e instanceof Error
            ? `The study could not run (${e.message}).`
            : "The study could not run.",
        );
      })
      .finally(() => {
        setRunning(false);
      });
  };

  return (
    <div className="control-study">
      <div className="control-study__form">
        <label htmlFor={lanesId}>
          Lanes per approach
          <select
            id={lanesId}
            value={lanes}
            disabled={running}
            onChange={(e) => {
              setLanes(Number(e.target.value));
            }}
          >
            <option value={1}>1 (calibrated)</option>
            <option value={2}>2 (exploratory)</option>
            <option value={3}>3 (exploratory)</option>
          </select>
        </label>
        <label htmlFor={seedsId}>
          Seeds per level
          <select
            id={seedsId}
            value={seeds}
            disabled={running}
            onChange={(e) => {
              setSeeds(Number(e.target.value));
            }}
          >
            <option value={3}>3</option>
            <option value={5}>5</option>
            <option value={10}>10</option>
          </select>
        </label>
        <label htmlFor={durationId}>
          Simulated time
          <select
            id={durationId}
            value={duration}
            disabled={running}
            onChange={(e) => {
              setDuration(Number(e.target.value));
            }}
          >
            <option value={300}>5 min</option>
            <option value={600}>10 min</option>
          </select>
        </label>
        <button
          type="button"
          className="guided-primary-btn"
          onClick={run}
          disabled={running}
        >
          Run the three-way study
        </button>
      </div>
      <p className="q-help">
        Six demand levels × {seeds} seeds × 3 controls = {String(6 * seeds * 3)}{" "}
        simulations, adaptive settings at their defaults (min{" "}
        {ADAPTIVE_DEFAULTS.minGreen} s, max {ADAPTIVE_DEFAULTS.maxGreen} s,
        passage {ADAPTIVE_DEFAULTS.extensionStep} s,{" "}
        {ADAPTIVE_DEFAULTS.detectionDistance} m zone).
      </p>

      {running && (
        <StudyProgress
          title="Fixed-time vs adaptive vs roundabout"
          progress={study.progress}
        />
      )}
      {error && (
        <p className="q-note is-caution" role="alert">
          {error}
        </p>
      )}

      {result && !running && (
        <div className="control-study__result">
          <p className="q-note" role="note">
            {result.calibration.note} Seeds {result.seeds.join(", ")};{" "}
            {String(result.duration)} s each, {String(result.warmupTime)} s
            warm-up excluded. Collisions: fixed-time{" "}
            {result.collisionCount.fixed_time}, adaptive{" "}
            {result.collisionCount.adaptive}, roundabout{" "}
            {result.collisionCount.roundabout}.
          </p>
          <div className="multi-run-scroll">
            <table className="plain-table">
              <caption>
                Mean delay per vehicle (s), mean ±{" "}
                {Math.round(result.confidenceLevel * 100)} % interval
              </caption>
              <thead>
                <tr>
                  <th scope="col">Demand</th>
                  {CONTROLS.map((c) => (
                    <th scope="col" key={c}>
                      {CONTROL_TITLE[c]}
                    </th>
                  ))}
                  {PAIRS.map((p) => (
                    <th scope="col" key={p.key}>
                      {CONTROL_TITLE[p.a]} vs {CONTROL_TITLE[p.b]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.results.map((level) => (
                  <tr key={level.level}>
                    <th scope="row">
                      {LEVEL_TITLE[level.level] ?? level.level}
                      <span className="metric-key">
                        {level.demandVph.toLocaleString()} veh/h
                        {level.vehicleLimitReached ? " · limit reached" : ""}
                      </span>
                    </th>
                    {CONTROLS.map((c) => (
                      <td key={c}>{stat(level.controls[c].averageDelay)}</td>
                    ))}
                    {PAIRS.map((p) => (
                      <td key={p.key}>
                        {readingText(level.delayComparisons[p.key], p.a, p.b)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="multi-run-scroll">
            <table className="plain-table">
              <caption>
                Throughput, queue and green time (means over seeds)
              </caption>
              <thead>
                <tr>
                  <th scope="col">Demand</th>
                  <th scope="col">Control</th>
                  <th scope="col">Vehicles served</th>
                  <th scope="col">Mean queue</th>
                  <th scope="col">Phase changes</th>
                  <th scope="col">Mean green (s)</th>
                  <th scope="col">Green used</th>
                </tr>
              </thead>
              <tbody>
                {result.results.flatMap((level) =>
                  CONTROLS.map((c) => {
                    const s = level.controls[c];
                    return (
                      <tr key={`${level.level}-${c}`}>
                        <th scope="row">
                          {LEVEL_TITLE[level.level] ?? level.level}
                        </th>
                        <td>{CONTROL_TITLE[c]}</td>
                        <td>{stat(s.throughput, 0)}</td>
                        <td>{stat(s.averageQueueLength)}</td>
                        <td>
                          {s.phaseChanges ? stat(s.phaseChanges, 0) : "—"}
                        </td>
                        <td>
                          {s.averageGreenDuration
                            ? stat(s.averageGreenDuration)
                            : "—"}
                        </td>
                        <td>
                          {s.greenUtilisation
                            ? `${(s.greenUtilisation.mean * 100).toFixed(0)} %`
                            : "—"}
                        </td>
                      </tr>
                    );
                  }),
                )}
              </tbody>
            </table>
          </div>
          <p className="q-help">
            <strong>Reading the comparison.</strong>{" "}
            {result.method.delayComparison} Tie tolerance:{" "}
            {result.tieTolerance.absSeconds} s or{" "}
            {Math.round(result.tieTolerance.relative * 100)} %.
          </p>
          <div className="next-actions">
            <button
              type="button"
              className="pb-btn pb-secondary"
              onClick={() => {
                downloadText(
                  `control_comparison_${Date.now().toString()}.csv`,
                  csvOf(result),
                  "text/csv;charset=utf-8",
                );
              }}
            >
              Download CSV
            </button>
            <button
              type="button"
              className="pb-btn pb-secondary"
              onClick={() => {
                downloadText(
                  `control_comparison_${Date.now().toString()}.json`,
                  JSON.stringify(result, null, 2),
                  "application/json",
                );
              }}
            >
              Download JSON
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
