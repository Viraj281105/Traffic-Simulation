import { useEffect, useState } from "react";
import { Activity, GitBranch } from "lucide-react";
import "../copilot/Copilot.css";
import "../discovery/Discovery.css";
import {
  cancelJob,
  getJob,
  getJobResult,
  listJobs,
  startBreakpoints,
  startSuite,
  type BreakpointResult,
  type StressJob,
  type SuiteResult,
} from "../../services/v3/stress";
import { ExperimentsApiError } from "../../services/v3/experiments";

const POLL_MS = 2000;

function message(err: unknown, fallback: string): string {
  return err instanceof ExperimentsApiError ? err.message : fallback;
}

function parseLevels(text: string, factor: string): (number | string)[] {
  const parts = text
    .split(",")
    .map((p) => p.trim())
    .filter(Boolean);
  return factor === "demand_scale" ? parts.map(Number) : parts;
}

/** Stress-test lab (generated stationary extremes, classified failures) and
 *  the strategy breakpoint explorer. */
export function StressLabPage() {
  const [seed, setSeed] = useState(1);
  const [count, setCount] = useState(8);
  const [factor, setFactor] = useState<"demand_scale" | "aggression">(
    "demand_scale",
  );
  const [levels, setLevels] = useState("0.6, 0.8, 1.0, 1.2, 1.4");
  const [jobs, setJobs] = useState<StressJob[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [job, setJob] = useState<StressJob | null>(null);
  const [result, setResult] = useState<SuiteResult | BreakpointResult | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    listJobs()
      .then(setJobs)
      .catch(() => {
        setJobs([]);
      });
  }, [tick]);

  useEffect(() => {
    if (!selected) return;
    let stop = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = () => {
      getJob(selected)
        .then((j) => {
          if (stop) return;
          setJob(j);
          if (j.status === "queued" || j.status === "running") {
            timer = setTimeout(load, POLL_MS);
            return;
          }
          setTick((n) => n + 1);
          if (j.resultAvailable) {
            void getJobResult(selected).then((r) => {
              if (!stop) setResult(r);
            });
          }
        })
        .catch((err: unknown) => {
          setError(message(err, "The job could not be loaded."));
        });
    };
    load();
    return () => {
      stop = true;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [selected]);

  const begin = (start: Promise<StressJob>) => {
    setError(null);
    start
      .then((j) => {
        setResult(null);
        setSelected(j.id);
        setTick((n) => n + 1);
      })
      .catch((err: unknown) => {
        setError(message(err, "The job could not be started."));
      });
  };

  const running = job?.status === "queued" || job?.status === "running";

  return (
    <div className="copilot-page">
      <header className="copilot-header">
        <p className="guided-eyebrow">Plan</p>
        <h1>Stress Lab and Breakpoint Explorer</h1>
        <p>
          Generate reproducible hard scenarios, run the strategies on them and
          see which failures each produces; or sweep one factor to find where
          the strategy with the lowest delay changes. The engine has no
          time-varying demand or incidents, so these are stationary extremes.
        </p>
      </header>

      <section className="copilot-card" aria-labelledby="stress-suite">
        <h2 id="stress-suite">Stress suite</h2>
        <div className="discovery-form">
          <label>
            Generator seed
            <input
              type="number"
              min={0}
              value={seed}
              onChange={(e) => {
                setSeed(Number(e.target.value));
              }}
            />
          </label>
          <label>
            Scenarios (at most 30)
            <input
              type="number"
              min={1}
              max={30}
              value={count}
              onChange={(e) => {
                setCount(Number(e.target.value));
              }}
            />
          </label>
        </div>
        <div className="copilot-actions">
          <button
            type="button"
            className="pb-btn pb-primary"
            disabled={running}
            onClick={() => {
              begin(startSuite({ seed, count, seedsPerRun: 2 }));
            }}
          >
            <Activity size={15} aria-hidden="true" />
            Run stress suite
          </button>
        </div>
      </section>

      <section className="copilot-card" aria-labelledby="stress-bp">
        <h2 id="stress-bp">Breakpoint explorer</h2>
        <div className="discovery-form">
          <label>
            Factor
            <select
              value={factor}
              onChange={(e) => {
                const next = e.target.value as "demand_scale" | "aggression";
                setFactor(next);
                setLevels(
                  next === "demand_scale"
                    ? "0.6, 0.8, 1.0, 1.2, 1.4"
                    : "standard, moderate, high",
                );
              }}
            >
              <option value="demand_scale">Demand scale</option>
              <option value="aggression">Driver aggression</option>
            </select>
          </label>
          <label>
            Levels (comma-separated)
            <input
              type="text"
              value={levels}
              onChange={(e) => {
                setLevels(e.target.value);
              }}
            />
          </label>
        </div>
        <div className="copilot-actions">
          <button
            type="button"
            className="pb-btn pb-primary"
            disabled={running}
            onClick={() => {
              begin(
                startBreakpoints({
                  factor,
                  levels: parseLevels(levels, factor),
                  seedsPerLevel: 3,
                }),
              );
            }}
          >
            <GitBranch size={15} aria-hidden="true" />
            Find breakpoints
          </button>
        </div>
        {error ? (
          <p className="copilot-error" role="alert">
            {error}
          </p>
        ) : null}
      </section>

      {jobs.length ? (
        <section className="copilot-card" aria-labelledby="stress-jobs">
          <h2 id="stress-jobs">Your jobs</h2>
          <ul className="discovery-list">
            {jobs.map((j) => (
              <li key={j.id}>
                <button
                  type="button"
                  className={`uf-link discovery-pick ${j.id === selected ? "is-current" : ""}`}
                  onClick={() => {
                    setResult(null);
                    setSelected(j.id);
                  }}
                >
                  {j.kind} · {j.status} · {j.runs.toString()} runs
                </button>
              </li>
            ))}
          </ul>
          {job && running ? (
            <button
              type="button"
              className="pb-btn pb-secondary"
              onClick={() => {
                void cancelJob(job.id).then(setJob);
              }}
            >
              Cancel
            </button>
          ) : null}
        </section>
      ) : null}

      {result && result.format === "urbanflow-stress-suite" ? (
        <SuiteView result={result} />
      ) : null}
      {result && result.format === "urbanflow-breakpoints" ? (
        <BreakpointView result={result} />
      ) : null}
    </div>
  );
}

function SuiteView({ result }: { result: SuiteResult }) {
  const failures = Object.keys(result.rules);
  return (
    <section className="copilot-card" aria-labelledby="stress-suite-result">
      <h2 id="stress-suite-result">Failures by strategy</h2>
      <p className="copilot-muted">
        {result.generator}, seed {result.seed.toString()}, suite{" "}
        <code>{result.suiteFingerprint}</code>. {result.note}
      </p>
      <div className="comparison-table-wrap">
        <table className="copilot-table">
          <thead>
            <tr>
              <th scope="col">Strategy</th>
              {failures.map((f) => (
                <th key={f} scope="col" title={result.rules[f]}>
                  {f}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.strategies.map((s) => (
              <tr key={s}>
                <th scope="row">{s}</th>
                {failures.map((f) => (
                  <td key={f}>
                    {(result.failureTotals[s]?.[f] ?? 0).toString()}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3>Scenarios</h3>
      <div className="comparison-table-wrap">
        <table className="copilot-table">
          <thead>
            <tr>
              <th scope="col">Scenario</th>
              {result.strategies.map((s) => (
                <th key={s} scope="col">
                  {s}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.scenarios.map((row) => (
              <tr key={row.index}>
                <th scope="row">{row.name}</th>
                {result.strategies.map((s) => {
                  const cell = row.results[s];
                  if (!cell) return <td key={s}>—</td>;
                  if ("skipped" in cell) return <td key={s}>skipped</td>;
                  const names = Object.keys(cell.failures);
                  return (
                    <td key={s}>
                      {cell.meanDelay !== null
                        ? `${cell.meanDelay.toFixed(1)} s`
                        : "—"}
                      {names.length ? ` · ${names.join(", ")}` : ""}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function BreakpointView({ result }: { result: BreakpointResult }) {
  return (
    <section className="copilot-card" aria-labelledby="stress-bp-result">
      <h2 id="stress-bp-result">Where the preference changes</h2>
      {result.tooFewToAssess ? (
        <p className="copilot-warnings">
          Too few conditions to assess: {result.tooFewToAssess.join("; ")}.
        </p>
      ) : null}
      {result.breakpoints.length ? (
        <ul>
          {result.breakpoints.map((b) => (
            <li key={`${String(b.between[0])}-${String(b.between[1])}`}>
              Between {String(b.between[0])} and {String(b.between[1])}:{" "}
              {b.from} → {b.to} (bootstrap confidence {b.confidence.toFixed(2)})
            </li>
          ))}
        </ul>
      ) : (
        <p>No change of the preferred strategy on this grid.</p>
      )}
      <div className="comparison-table-wrap">
        <table className="copilot-table">
          <thead>
            <tr>
              <th scope="col">{result.factor}</th>
              {result.strategies.map((s) => (
                <th key={s} scope="col">
                  {s} mean delay (s)
                </th>
              ))}
              <th scope="col">Lowest delay</th>
            </tr>
          </thead>
          <tbody>
            {result.table.map((row) => (
              <tr key={String(row.level)}>
                <th scope="row">{String(row.level)}</th>
                {result.strategies.map((s) => (
                  <td key={s}>
                    {row.meanDelay[s] != null
                      ? (row.meanDelay[s] ?? 0).toFixed(2)
                      : "—"}
                  </td>
                ))}
                <td>{row.preferred ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="copilot-muted">{result.note}</p>
    </section>
  );
}
