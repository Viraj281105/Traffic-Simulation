import { useEffect, useState, type CSSProperties } from "react";
import {
  Activity,
  AlertOctagon,
  GitBranch,
  Layers,
  Route,
  ShieldCheck,
  SkipForward,
  Waypoints,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
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
import { failureSums } from "./stressStats";
import { ExperimentsApiError } from "../../services/v3/experiments";
import { CHART_AXIS, CHART_GRID, TOOLTIP_STYLE } from "../../theme/chart";
import {
  ChartFrame,
  EmptyHint,
  PageHero,
  Panel,
  Pill,
  Skeleton,
  StatGrid,
  StatTile,
  type Tone,
} from "../dashboard/Dashboard";
import { first, prettyName, seriesColour } from "../dashboard/format";

const POLL_MS = 2000;

const STATUS_TONE: Record<StressJob["status"], Tone> = {
  queued: "info",
  running: "info",
  completed: "good",
  failed: "bad",
  cancelled: "warn",
};

const FAILURE_COLOURS = [
  "var(--color-danger)",
  "var(--color-orange)",
  "var(--color-warning)",
  "var(--series-roundabout)",
  "var(--color-accent)",
  "var(--series-neutral)",
];

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
  const jobTotals = {
    completed: jobs.filter((j) => j.status === "completed").length,
    runs: jobs.reduce((a, j) => a + j.runs, 0),
  };

  return (
    <div className="dash-page copilot-page">
      <PageHero
        title="Stress Lab and Breakpoint Explorer"
        aside={
          jobs.length ? (
            <div className="stress-hero-stats">
              <span>
                <strong>{jobs.length.toString()}</strong> jobs
              </span>
              <span>
                <strong>{jobTotals.completed.toString()}</strong> completed
              </span>
              <span>
                <strong>{jobTotals.runs.toLocaleString()}</strong> runs
              </span>
            </div>
          ) : null
        }
      >
        Generate reproducible hard scenarios, run the strategies on them and see
        which failures each produces; or sweep one factor to find where the
        strategy with the lowest delay changes. The engine has no time-varying
        demand or incidents, so these are stationary extremes.
      </PageHero>

      <div className="dash-grid-2">
        <Panel
          id="stress-suite"
          title="Stress suite"
          subtitle="A seeded generator builds hard scenarios; every strategy runs each one and failures are classified by rule."
        >
          <div className="dash-form discovery-form">
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
        </Panel>

        <section className="dash-panel" aria-labelledby="stress-bp">
          <div className="dash-panel__head">
            <div>
              <h2 id="stress-bp">Breakpoint explorer</h2>
              <p className="dash-panel__sub">
                Sweep one factor and see where the lowest-delay strategy
                changes.
              </p>
            </div>
          </div>
          <div className="dash-form discovery-form">
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
      </div>

      <Panel
        id="stress-jobs"
        title="Your jobs"
        actions={
          job && running ? (
            <button
              type="button"
              className="pb-btn pb-secondary"
              onClick={() => {
                void cancelJob(job.id).then(setJob);
              }}
            >
              Cancel
            </button>
          ) : null
        }
      >
        {jobs.length ? (
          <ul className="dash-items discovery-list">
            {jobs.map((j) => (
              <li key={j.id}>
                <button
                  type="button"
                  className={`dash-item discovery-pick ${j.id === selected ? "is-current" : ""}`}
                  aria-pressed={j.id === selected}
                  onClick={() => {
                    setResult(null);
                    setSelected(j.id);
                  }}
                >
                  <span className="dash-item__name">
                    {j.kind === "suite" ? "Stress suite" : "Breakpoints"}
                  </span>
                  <Pill tone={STATUS_TONE[j.status]}>{j.status}</Pill>
                  <span className="dash-item__meta">
                    {j.runs.toString()} runs ·{" "}
                    {new Date(j.createdAt).toLocaleString()}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyHint icon={<Waypoints size={22} />} title="No jobs yet">
            Run a stress suite or a breakpoint sweep above. Results appear here
            as charts and tables.
          </EmptyHint>
        )}
        {job && running ? (
          <div role="status" aria-label="Job running" className="stress-wait">
            <Skeleton lines={3} />
          </div>
        ) : null}
        {job?.error ? (
          <p className="copilot-error" role="alert">
            {job.error}
          </p>
        ) : null}
      </Panel>

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
  const sums = failureSums(result);
  const totalFailures = Object.values(sums).reduce((a, b) => a + b, 0);
  const robust = [...result.strategies].sort(
    (a, b) => (sums[a] ?? 0) - (sums[b] ?? 0),
  )[0];
  const skipped = result.scenarios.reduce(
    (n, s) =>
      n + Object.values(s.results).filter((c) => c && "skipped" in c).length,
    0,
  );
  const delays = result.scenarios.flatMap((s) =>
    Object.values(s.results).flatMap((c) =>
      c && !("skipped" in c) && c.meanDelay !== null ? [c.meanDelay] : [],
    ),
  );
  const maxDelay = Math.max(1, ...delays);
  const worst = first(
    result.scenarios
      .flatMap((s) =>
        Object.entries(s.results).flatMap(([strategy, c]) =>
          c && !("skipped" in c) && c.meanDelay !== null
            ? [{ name: s.name, strategy, delay: c.meanDelay }]
            : [],
        ),
      )
      .sort((a, b) => b.delay - a.delay),
  );

  const stacked = result.strategies.map((s) => ({
    strategy: prettyName(s),
    ...Object.fromEntries(
      failures.map((f) => [f, result.failureTotals[s]?.[f] ?? 0]),
    ),
  }));

  return (
    <section className="dash-panel" aria-labelledby="stress-suite-result">
      <div className="dash-panel__head">
        <div>
          <h2 id="stress-suite-result">Failures by strategy</h2>
          <p className="dash-panel__sub">
            {result.generator}, seed {result.seed.toString()}, suite{" "}
            <code>{result.suiteFingerprint}</code>. {result.note}
          </p>
        </div>
      </div>

      <StatGrid>
        <StatTile
          label="Scenarios"
          icon={<Layers size={16} />}
          value={result.scenarios.length.toString()}
          hint={`${result.strategies.length.toString()} strategies each`}
        />
        <StatTile
          label="Failures found"
          icon={<AlertOctagon size={16} />}
          tone={totalFailures ? "bad" : "good"}
          value={totalFailures.toString()}
          hint={`${failures.length.toString()} failure rule${failures.length === 1 ? "" : "s"} checked`}
        />
        <StatTile
          label="Fewest failures"
          icon={<ShieldCheck size={16} />}
          tone="good"
          value={robust ? prettyName(robust) : "—"}
          hint={
            robust ? `${(sums[robust] ?? 0).toString()} failures` : undefined
          }
          tip="The strategy with the lowest failure total on this suite. Not a ranking of overall quality."
        />
        <StatTile
          label="Highest mean delay"
          icon={<Route size={16} />}
          tone="warn"
          value={worst ? worst.delay.toFixed(1) : "—"}
          unit={worst ? "s" : undefined}
          hint={
            worst ? `${worst.name}, ${prettyName(worst.strategy)}` : undefined
          }
        />
        {skipped ? (
          <StatTile
            label="Skipped cells"
            icon={<SkipForward size={16} />}
            value={skipped.toString()}
            hint="Not applicable to that scenario"
          />
        ) : null}
      </StatGrid>

      <h3>Failure mix</h3>
      <ChartFrame
        label={`Failures per strategy: ${result.strategies.map((s) => `${prettyName(s)} ${(sums[s] ?? 0).toString()}`).join(", ")}`}
        height={Math.max(180, result.strategies.length * 52 + 70)}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={stacked}
            layout="vertical"
            margin={{ top: 4, right: 20, left: 8, bottom: 0 }}
          >
            <CartesianGrid
              strokeDasharray="3 4"
              stroke={CHART_GRID}
              horizontal={false}
            />
            <XAxis
              type="number"
              allowDecimals={false}
              stroke={CHART_AXIS}
              fontSize={11}
            />
            <YAxis
              type="category"
              dataKey="strategy"
              stroke={CHART_AXIS}
              fontSize={11}
              width={120}
              tickLine={false}
            />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              cursor={{ fill: "var(--color-accent-soft)" }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {failures.map((f, i) => (
              <Bar
                key={f}
                dataKey={f}
                stackId="f"
                fill={FAILURE_COLOURS[i % FAILURE_COLOURS.length]}
                barSize={24}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </ChartFrame>

      <div className="dash-table-wrap">
        <table className="dash-table copilot-table">
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
      <ul className="dash-legend stress-rules">
        {failures.map((f, i) => (
          <li key={f}>
            <i
              style={{
                background: FAILURE_COLOURS[i % FAILURE_COLOURS.length],
              }}
            />
            <strong>{f}</strong>: {result.rules[f]}
          </li>
        ))}
      </ul>

      <h3>Scenarios</h3>
      <p className="copilot-muted">
        Mean delay per scenario and strategy; darker cells have higher delay.
        Failure rules that fired are listed in the cell.
      </p>
      <div className="dash-table-wrap">
        <table className="dash-table copilot-table">
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
                {result.strategies.map((s, i) => {
                  const cell = row.results[s];
                  if (!cell) return <td key={s}>—</td>;
                  if ("skipped" in cell) return <td key={s}>skipped</td>;
                  const names = Object.keys(cell.failures);
                  const heat =
                    cell.meanDelay !== null ? cell.meanDelay / maxDelay : 0;
                  return (
                    <td
                      key={s}
                      className="stress-heat-cell"
                      style={
                        {
                          "--heat": heat.toFixed(3),
                          "--heat-colour": seriesColour(s, i),
                        } as CSSProperties
                      }
                    >
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
  const data = result.table.map((row) => ({
    level: String(row.level),
    ...Object.fromEntries(
      result.strategies.map((s) => [s, row.meanDelay[s] ?? null]),
    ),
  }));
  const share = result.table.map((row) => ({
    level: String(row.level),
    ...Object.fromEntries(
      result.strategies.map((s) => [
        s,
        Math.round((row.preferenceShare[s] ?? 0) * 100),
      ]),
    ),
  }));
  const weakest = result.breakpoints.reduce<number | null>(
    (m, b) => (m === null || b.confidence < m ? b.confidence : m),
    null,
  );
  const bestAtEnds = [
    result.table[0]?.preferred,
    result.table[result.table.length - 1]?.preferred,
  ];

  return (
    <section className="dash-panel" aria-labelledby="stress-bp-result">
      <div className="dash-panel__head">
        <div>
          <h2 id="stress-bp-result">Where the preference changes</h2>
          <p className="dash-panel__sub">
            Factor: <strong>{prettyName(result.factor)}</strong>, with{" "}
            {result.seedsPerLevel.toString()} seeds per level.
          </p>
        </div>
      </div>

      <StatGrid>
        <StatTile
          label="Levels swept"
          icon={<Layers size={16} />}
          value={result.table.length.toString()}
          hint={`${result.strategies.length.toString()} strategies compared`}
        />
        <StatTile
          label="Breakpoints"
          icon={<GitBranch size={16} />}
          tone={result.breakpoints.length ? "warn" : "good"}
          value={result.breakpoints.length.toString()}
          hint={
            result.breakpoints.length
              ? "Places the lowest-delay strategy changes"
              : "Preferred strategy never changes"
          }
        />
        <StatTile
          label="Lowest confidence"
          icon={<ShieldCheck size={16} />}
          value={weakest !== null ? weakest.toFixed(2) : "—"}
          hint="Bootstrap confidence of the weakest breakpoint"
          tip="How often a bootstrap resample of the seeds reproduces the change."
        />
        <StatTile
          label="Preferred at the ends"
          icon={<Route size={16} />}
          value={
            bestAtEnds[0] && bestAtEnds[1]
              ? `${prettyName(bestAtEnds[0])} → ${prettyName(bestAtEnds[1])}`
              : "—"
          }
          hint="Lowest delay at first and last level"
        />
      </StatGrid>

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

      <div className="dash-grid-2 discovery-charts">
        <div>
          <h4 className="discovery-chart-title">Mean delay by level (s)</h4>
          <ChartFrame
            label={`Mean delay of ${result.strategies.map(prettyName).join(", ")} across ${result.table.length.toString()} levels of ${result.factor}`}
            height={260}
          >
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={data}
                margin={{ top: 10, right: 20, left: 0, bottom: 0 }}
              >
                <CartesianGrid
                  strokeDasharray="3 4"
                  stroke={CHART_GRID}
                  vertical={false}
                />
                <XAxis dataKey="level" stroke={CHART_AXIS} fontSize={11} />
                <YAxis stroke={CHART_AXIS} fontSize={11} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {result.breakpoints.map((b) => (
                  <ReferenceLine
                    key={`${String(b.between[0])}-${String(b.between[1])}`}
                    x={String(b.between[1])}
                    stroke="var(--color-warning)"
                    strokeDasharray="4 4"
                    label={{
                      value: "change",
                      fill: "var(--color-warning)",
                      fontSize: 11,
                      position: "top",
                    }}
                  />
                ))}
                {result.strategies.map((s, i) => (
                  <Line
                    key={s}
                    type="monotone"
                    dataKey={s}
                    name={prettyName(s)}
                    stroke={seriesColour(s, i)}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </ChartFrame>
        </div>
        <div>
          <h4 className="discovery-chart-title">
            Share of seeds where each strategy has the lowest delay (%)
          </h4>
          <ChartFrame
            label="Share of seeds where each strategy had the lowest delay, by level"
            height={260}
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={share}
                margin={{ top: 10, right: 20, left: 0, bottom: 0 }}
              >
                <CartesianGrid
                  strokeDasharray="3 4"
                  stroke={CHART_GRID}
                  vertical={false}
                />
                <XAxis dataKey="level" stroke={CHART_AXIS} fontSize={11} />
                <YAxis
                  stroke={CHART_AXIS}
                  fontSize={11}
                  domain={[0, 100]}
                  unit="%"
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  cursor={{ fill: "var(--color-accent-soft)" }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {result.strategies.map((s, i) => (
                  <Bar
                    key={s}
                    dataKey={s}
                    name={prettyName(s)}
                    stackId="share"
                    fill={seriesColour(s, i)}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </ChartFrame>
        </div>
      </div>

      <div className="dash-table-wrap">
        <table className="dash-table copilot-table">
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
                  <td
                    key={s}
                    className={row.preferred === s ? "is-best" : undefined}
                  >
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
