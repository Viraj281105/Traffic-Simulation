import { useId, useState } from "react";
import { useStudyJob } from "../../hooks/useStudyJob";
import { STUDY_JOB_ROUTES } from "../../services/studyJobs";
import { compileScenario } from "../../services/scenarioApi";
import { StudyProgress } from "../ui/StudyProgress";
import { downloadText } from "../../metrics/catalog";
import { ScenarioBuilder } from "./ScenarioBuilder";
import { useScenarioValidation } from "./useScenarioValidation";
import {
  DEFAULT_SCENARIO,
  cloneScenario,
  describeScenario,
  exportScenarioJson,
} from "../../scenario/scenarioModel";
import {
  APPROACHES,
  STRATEGIES,
  STRATEGY_TITLE,
  type ApproachName,
  type ScenarioDocument,
  type Strategy,
} from "../../scenario/scenarioTypes";
import { VEHICLE_CLASSES } from "../../vehicles/vehicleClasses";

type Reading = "lower" | "higher" | "tie" | "inconclusive";

interface Stat {
  mean: number;
  ci: number;
}

interface PairResult {
  meanDifference: number;
  ciLow: number | null;
  ciHigh: number | null;
  reading: Reading;
}

interface SeedSide {
  averageDelay: number | null;
  throughput: number | null;
  averageQueueLength: number | null;
  collisionCount: number | null;
  vehicleTypeBreakdown?: Record<
    string,
    { exited: number; averageDelay: number }
  >;
  approachBreakdown?: Partial<
    Record<
      ApproachName,
      { exited: number; averageDelay: number; averageQueueLength: number }
    >
  >;
}

/** Backend study/control_comparison.run_scenario_comparison. */
export interface ScenarioStudyResult {
  study: "scenario-comparison";
  scenario: ScenarioDocument;
  fingerprint: string;
  controls: Strategy[];
  demandScales: number[];
  seeds: number[];
  duration: number;
  warmupTime: number;
  confidenceLevel: number;
  calibration: { calibrated: boolean; note: string };
  tieTolerance: { absSeconds: number; relative: number };
  collisionCount: Partial<Record<Strategy, number>>;
  compiledConfigs: Partial<Record<Strategy, Record<string, unknown>>>;
  method: { design: string; interval: string; delayComparison: string };
  results: {
    demandScale: number;
    demandVph: number;
    vehicleLimitReached: boolean;
    controls: Partial<Record<Strategy, Partial<Record<string, Stat>>>>;
    delayComparisons: Partial<Record<string, PairResult>>;
  }[];
  perSeed: ({ demandScale: number; seed: number } & Partial<
    Record<Strategy, SeedSide>
  >)[];
}

const SCALES = [0.5, 0.75, 1, 1.25, 1.5];

function stat(s: Stat | undefined, decimals = 1): string {
  if (!s) return "—";
  return `${s.mean.toFixed(decimals)} ± ${s.ci.toFixed(decimals)}`;
}

function reading(p: PairResult | undefined, a: Strategy, b: Strategy): string {
  if (!p) return "—";
  const words: Record<Reading, string> = {
    lower: `${STRATEGY_TITLE[a]} lower`,
    higher: `${STRATEGY_TITLE[b]} lower`,
    tie: "About the same",
    inconclusive: "Inconclusive",
  };
  const ci =
    p.ciLow === null || p.ciHigh === null
      ? ""
      : ` (${p.meanDifference.toFixed(1)} s, ${p.ciLow.toFixed(1)} to ${p.ciHigh.toFixed(1)})`;
  return words[p.reading] + ci;
}

function mean(values: number[]): number | null {
  return values.length
    ? values.reduce((s, v) => s + v, 0) / values.length
    : null;
}

/** Mean over seeds of one per-seed figure, for one strategy and scale. */
function seedMean(
  result: ScenarioStudyResult,
  scale: number,
  strategy: Strategy,
  pick: (side: SeedSide) => number | undefined | null,
): number | null {
  const values = result.perSeed
    .filter((r) => r.demandScale === scale)
    .map((r) => {
      const side = r[strategy];
      return side ? pick(side) : undefined;
    })
    .filter((v): v is number => typeof v === "number");
  return mean(values);
}

function fmt(v: number | null, decimals = 1): string {
  return v === null ? "—" : v.toFixed(decimals);
}

function summaryCsv(result: ScenarioStudyResult): string {
  const rows = [
    "demand_scale,demand_vph,strategy,delay_mean_s,delay_ci_s,throughput_mean,queue_mean,collisions_total",
  ];
  for (const level of result.results) {
    for (const s of result.controls) {
      const st = level.controls[s] ?? {};
      rows.push(
        [
          level.demandScale,
          level.demandVph,
          s,
          st.averageDelay?.mean ?? "",
          st.averageDelay?.ci ?? "",
          st.throughput?.mean ?? "",
          st.averageQueueLength?.mean ?? "",
          result.collisionCount[s] ?? "",
        ].join(","),
      );
    }
  }
  rows.push("");
  rows.push("demand_scale,seed,strategy,approach,exited,delay_s,mean_queue");
  for (const r of result.perSeed) {
    for (const s of result.controls) {
      const side = r[s];
      for (const a of APPROACHES) {
        const ab = side?.approachBreakdown?.[a];
        if (!ab) continue;
        rows.push(
          [
            r.demandScale,
            r.seed,
            s,
            a,
            ab.exited,
            ab.averageDelay,
            ab.averageQueueLength,
          ].join(","),
        );
      }
    }
  }
  return rows.join("\n") + "\n";
}

/**
 * Research Lab: a user's own scenario, run under each chosen control over
 * several seeds. Every control is compiled from the same scenario document,
 * so only the control differs — the exact configurations are shown and
 * exported with the result.
 */
export function ScenarioStudy() {
  const [scenario, setScenario] = useState<ScenarioDocument>(() =>
    cloneScenario(DEFAULT_SCENARIO),
  );
  const [strategies, setStrategies] = useState<Strategy[]>([...STRATEGIES]);
  const [seeds, setSeeds] = useState(5);
  const [scales, setScales] = useState<number[]>([1]);
  const [result, setResult] = useState<ScenarioStudyResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [inspect, setInspect] = useState<{
    strategy: Strategy;
    text: string;
  } | null>(null);
  const study = useStudyJob();
  const seedsId = useId();
  const validation = useScenarioValidation(scenario, strategies);
  const valid = validation.status === "done" && validation.result.valid;
  const runs = strategies.length * seeds * scales.length;

  const toggleStrategy = (s: Strategy) => {
    setStrategies((prev) =>
      prev.includes(s)
        ? prev.filter((x) => x !== s)
        : STRATEGIES.filter((x) => x === s || prev.includes(x)),
    );
  };
  const toggleScale = (v: number) => {
    setScales((prev) =>
      prev.includes(v)
        ? prev.filter((x) => x !== v)
        : [...prev, v].sort((a, b) => a - b),
    );
  };

  const run = () => {
    setRunning(true);
    setError(null);
    study
      .run<ScenarioStudyResult>(STUDY_JOB_ROUTES.controlComparison, {
        scenario,
        strategies,
        numSeeds: seeds,
        demandScales: scales,
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

  const showConfig = (strategy: Strategy) => {
    compileScenario(scenario, strategy)
      .then((r) => {
        setInspect({ strategy, text: JSON.stringify(r.config, null, 2) });
      })
      .catch(() => {
        setInspect({
          strategy,
          text: "Could not compile — check the scenario panel for problems.",
        });
      });
  };

  const pairs = strategies.flatMap((a, i) =>
    strategies.slice(i + 1).map((b) => ({ a, b, key: `${a}_vs_${b}` })),
  );

  return (
    <div className="scenario-study">
      <ScenarioBuilder
        value={scenario}
        onChange={setScenario}
        strategies={strategies}
        validation={validation}
        junctionNote="In a study every chosen control runs on this junction; the type chosen here only sets the default view."
      />

      <div className="control-study__form">
        <fieldset className="sb-inline">
          <legend className="sb-field-label">Controls to compare</legend>
          {STRATEGIES.map((s) => (
            <label key={s} className="sb-check">
              <input
                type="checkbox"
                checked={strategies.includes(s)}
                disabled={
                  running || (strategies.includes(s) && strategies.length <= 2)
                }
                onChange={() => {
                  toggleStrategy(s);
                }}
              />
              {STRATEGY_TITLE[s]}
            </label>
          ))}
        </fieldset>
        <label htmlFor={seedsId}>
          Seeds
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
        <fieldset className="sb-inline">
          <legend className="sb-field-label">Demand (× the scenario’s)</legend>
          {SCALES.map((v) => (
            <button
              key={v}
              type="button"
              className={`chip${scales.includes(v) ? " is-active" : ""}`}
              aria-pressed={scales.includes(v)}
              disabled={running || (scales.includes(v) && scales.length === 1)}
              onClick={() => {
                toggleScale(v);
              }}
            >
              ×{v}
            </button>
          ))}
        </fieldset>
        <button
          type="button"
          className="guided-primary-btn"
          onClick={run}
          disabled={running || !valid}
        >
          Run the study ({runs} simulations)
        </button>
      </div>
      <p className="q-help">
        Seeds start at the scenario’s own seed ({scenario.simulation.seed}).
        Each seed runs once under every control with the same arrivals.{" "}
        <span className="sb-inline">
          Inspect the exact configuration:{" "}
          {strategies.map((s) => (
            <button
              key={s}
              type="button"
              className="link-btn"
              disabled={!valid}
              onClick={() => {
                showConfig(s);
              }}
            >
              {STRATEGY_TITLE[s]}
            </button>
          ))}
        </span>
      </p>
      {inspect && (
        <details open className="sb-card">
          <summary>
            Engine configuration — {STRATEGY_TITLE[inspect.strategy]}
          </summary>
          <pre className="config-json">{inspect.text}</pre>
        </details>
      )}

      {running && (
        <StudyProgress
          title={`${scenario.name}: ${strategies.map((s) => STRATEGY_TITLE[s]).join(" vs ")}`}
          progress={study.progress}
        />
      )}
      {error && (
        <p className="q-note is-caution" role="alert">
          {error}
        </p>
      )}
      {result && !running && (
        <ScenarioStudyResultView result={result} pairs={pairs} />
      )}
    </div>
  );
}

function ScenarioStudyResultView({
  result,
  pairs,
}: {
  result: ScenarioStudyResult;
  pairs: { a: Strategy; b: Strategy; key: string }[];
}) {
  const controls = result.controls;
  const shownPairs = pairs.filter(
    (p) => controls.includes(p.a) && controls.includes(p.b),
  );
  const firstScale = result.demandScales.includes(1)
    ? 1
    : result.demandScales[0];
  const classes = VEHICLE_CLASSES.filter((c) =>
    result.perSeed.some((r) =>
      controls.some(
        (s) => (r[s]?.vehicleTypeBreakdown?.[c.id]?.exited ?? 0) > 0,
      ),
    ),
  );
  return (
    <div className="control-study__result">
      <div className="sb-card scenario-id">
        <p className="sb-status-title">
          {result.scenario.name}{" "}
          <span className="metric-key">scenario {result.fingerprint}</span>
        </p>
        <p className="sb-small">{describeScenario(result.scenario)}</p>
        <p className="sb-small">
          {controls.map((s) => STRATEGY_TITLE[s]).join(" · ")}; seeds{" "}
          {result.seeds.join(", ")}; {result.duration} s each,{" "}
          {result.warmupTime} s warm-up excluded. Collisions:{" "}
          {controls
            .map(
              (s) =>
                `${STRATEGY_TITLE[s]} ${String(result.collisionCount[s] ?? 0)}`,
            )
            .join(", ")}
          .
        </p>
        <p className="q-note" role="note">
          {result.calibration.note} {result.method.design}
        </p>
      </div>

      <div className="multi-run-scroll">
        <table className="plain-table">
          <caption>
            Mean delay per vehicle (s), mean ±{" "}
            {Math.round(result.confidenceLevel * 100)} % interval
          </caption>
          <thead>
            <tr>
              <th scope="col">Demand</th>
              {controls.map((s) => (
                <th scope="col" key={s}>
                  {STRATEGY_TITLE[s]}
                </th>
              ))}
              {shownPairs.map((p) => (
                <th scope="col" key={p.key}>
                  {STRATEGY_TITLE[p.a]} vs {STRATEGY_TITLE[p.b]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.results.map((level) => (
              <tr key={level.demandScale}>
                <th scope="row">
                  ×{level.demandScale}
                  <span className="metric-key">
                    {level.demandVph.toLocaleString()} veh/h
                    {level.vehicleLimitReached ? " · limit reached" : ""}
                  </span>
                </th>
                {controls.map((s) => (
                  <td key={s}>{stat(level.controls[s]?.averageDelay)}</td>
                ))}
                {shownPairs.map((p) => (
                  <td key={p.key}>
                    {reading(level.delayComparisons[p.key], p.a, p.b)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="multi-run-scroll">
        <table className="plain-table">
          <caption>Throughput and queue (means over seeds)</caption>
          <thead>
            <tr>
              <th scope="col">Demand</th>
              <th scope="col">Control</th>
              <th scope="col">Vehicles served</th>
              <th scope="col">Mean queue</th>
              <th scope="col">Max queue</th>
            </tr>
          </thead>
          <tbody>
            {result.results.flatMap((level) =>
              controls.map((s) => {
                const st = level.controls[s] ?? {};
                return (
                  <tr key={`${String(level.demandScale)}-${s}`}>
                    <th scope="row">×{level.demandScale}</th>
                    <td>{STRATEGY_TITLE[s]}</td>
                    <td>{stat(st.throughput, 0)}</td>
                    <td>{stat(st.averageQueueLength)}</td>
                    <td>{stat(st.maxQueueLength, 0)}</td>
                  </tr>
                );
              }),
            )}
          </tbody>
        </table>
      </div>

      <div className="multi-run-scroll">
        <table className="plain-table">
          <caption>
            By approach at ×{firstScale} demand — mean delay (s) / mean queue,
            averaged over seeds
          </caption>
          <thead>
            <tr>
              <th scope="col">Approach</th>
              <th scope="col">Offered (veh/h)</th>
              {controls.map((s) => (
                <th scope="col" key={s}>
                  {STRATEGY_TITLE[s]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {APPROACHES.filter(
              (a) => result.scenario.approaches[a] != null,
            ).map((a) => (
              <tr key={a}>
                <th scope="row">{a}</th>
                <td>
                  {Math.round(
                    (result.scenario.approaches[a]?.vehiclesPerHour ?? 0) *
                      firstScale,
                  )}
                </td>
                {controls.map((s) => (
                  <td key={s}>
                    {fmt(
                      seedMean(
                        result,
                        firstScale,
                        s,
                        (side) => side.approachBreakdown?.[a]?.averageDelay,
                      ),
                    )}{" "}
                    /{" "}
                    {fmt(
                      seedMean(
                        result,
                        firstScale,
                        s,
                        (side) =>
                          side.approachBreakdown?.[a]?.averageQueueLength,
                      ),
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {classes.length > 0 && (
        <div className="multi-run-scroll">
          <table className="plain-table">
            <caption>
              By vehicle class at ×{firstScale} demand — mean delay (s),
              averaged over seeds
            </caption>
            <thead>
              <tr>
                <th scope="col">Class</th>
                {controls.map((s) => (
                  <th scope="col" key={s}>
                    {STRATEGY_TITLE[s]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {classes.map((c) => (
                <tr key={c.id}>
                  <th scope="row">{c.label}</th>
                  {controls.map((s) => (
                    <td key={s}>
                      {fmt(
                        seedMean(
                          result,
                          firstScale,
                          s,
                          (side) =>
                            side.vehicleTypeBreakdown?.[c.id]?.averageDelay,
                        ),
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="q-help">
        <strong>Reading the comparison.</strong> {result.method.delayComparison}{" "}
        Tie tolerance: {result.tieTolerance.absSeconds} s or{" "}
        {Math.round(result.tieTolerance.relative * 100)} %.
      </p>
      <div className="next-actions">
        <button
          type="button"
          className="pb-btn pb-secondary"
          onClick={() => {
            downloadText(
              `scenario_study_${result.fingerprint}.csv`,
              summaryCsv(result),
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
              `scenario_study_${result.fingerprint}.json`,
              JSON.stringify(result, null, 2),
              "application/json",
            );
          }}
        >
          Download JSON (with exact configurations)
        </button>
        <button
          type="button"
          className="pb-btn pb-secondary"
          onClick={() => {
            downloadText(
              `scenario_${result.fingerprint}.urbanflow.json`,
              exportScenarioJson(result.scenario),
              "application/json",
            );
          }}
        >
          Download the scenario
        </button>
      </div>
    </div>
  );
}
