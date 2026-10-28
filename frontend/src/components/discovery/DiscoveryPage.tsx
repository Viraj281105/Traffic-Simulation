import { useEffect, useState, type CSSProperties } from "react";
import {
  Download,
  FlaskConical,
  Gauge,
  Layers,
  Radar,
  ShieldAlert,
  Square,
  Target,
  Timer,
  TriangleAlert,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import "../copilot/Copilot.css";
import "./Discovery.css";
import {
  cancelSearch,
  downloadSearchPackage,
  estimate,
  getSearch,
  getSearchResult,
  listSearches,
  startSearch,
  type ObjectiveRow,
  type SearchResult,
  type SearchSpec,
  type SearchStatus,
} from "../../services/v3/discovery";
import { ExperimentsApiError, saveBlob } from "../../services/v3/experiments";
import { CHART_AXIS, CHART_GRID, TOOLTIP_STYLE } from "../../theme/chart";
import {
  ChartFrame,
  EmptyHint,
  Meter,
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

const DEFAULT_SPEC: SearchSpec = {
  name: "Discovery search",
  regime: {
    name: "Declared regime",
    vehiclesPerHour: 700,
    unevenDemand: true,
    lanesPerArm: 1,
    aggression: "high",
    mix: "default",
    duration: 150,
    warmup: 30,
  },
  budget: {
    population: 10,
    generations: 6,
    tuningSeeds: 2,
    selectionSeeds: 3,
    heldOutSeeds: 10,
    paretoCap: 6,
    shortlist: 3,
    unseenGrid: true,
  },
  seed: 1,
};

const STATUS_TONE: Record<SearchStatus["status"], Tone> = {
  queued: "info",
  running: "info",
  completed: "good",
  failed: "bad",
  cancelled: "warn",
};

function fmt(value: number | null | undefined, digits = 2): string {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toFixed(digits)
    : "—";
}

function objective(row: ObjectiveRow, key: string): number | null {
  const v = row?.[key];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function objectiveCells(row: ObjectiveRow) {
  return (
    <>
      <td>{fmt(row?.averageDelay)}</td>
      <td>{fmt(row?.throughput, 1)}</td>
      <td>{fmt(row?.maxQueueLength, 1)}</td>
      <td>{fmt(row?.nearMissesPer1000, 1)}</td>
    </>
  );
}

function describeGenome(genome: Record<string, unknown>): string {
  return Object.entries(genome)
    .map(
      ([k, v]) =>
        `${k}=${typeof v === "number" || typeof v === "string" || typeof v === "boolean" ? String(v) : "…"}`,
    )
    .join(", ");
}

function message(err: unknown, fallback: string): string {
  return err instanceof ExperimentsApiError ? err.message : fallback;
}

function shortId(id: string): string {
  return id.slice(0, 8);
}

/** The Control Strategy Discovery Lab: a bounded evolutionary search for one
 *  declared regime, judged against the unchanged baselines on held-out seeds. */
export function DiscoveryPage() {
  const [spec, setSpec] = useState<SearchSpec>(DEFAULT_SPEC);
  const [cost, setCost] = useState<{
    runs: number;
    simulatedSeconds: number;
  } | null>(null);
  const [searches, setSearches] = useState<SearchStatus[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [status, setStatus] = useState<SearchStatus | null>(null);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    estimate(spec)
      .then(setCost)
      .catch(() => {
        setCost(null);
      });
  }, [spec]);

  useEffect(() => {
    listSearches()
      .then(setSearches)
      .catch(() => {
        setSearches([]);
      });
  }, [tick]);

  useEffect(() => {
    if (!selected) return;
    let stop = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = () => {
      getSearch(selected)
        .then((s) => {
          if (stop) return;
          setStatus(s);
          if (s.status === "queued" || s.status === "running") {
            timer = setTimeout(load, POLL_MS);
            return;
          }
          setTick((n) => n + 1);
          if (s.resultAvailable) {
            void getSearchResult(selected).then((r) => {
              if (!stop) setResult(r);
            });
          }
        })
        .catch((err: unknown) => {
          setError(message(err, "The search could not be loaded."));
        });
    };
    load();
    return () => {
      stop = true;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [selected]);

  const regime = (patch: Partial<SearchSpec["regime"]>) => {
    setSpec((s) => ({ ...s, regime: { ...s.regime, ...patch } }));
  };
  const budget = (patch: Partial<SearchSpec["budget"]>) => {
    setSpec((s) => ({ ...s, budget: { ...s.budget, ...patch } }));
  };

  const start = () => {
    setBusy(true);
    setError(null);
    startSearch(spec)
      .then((s) => {
        setResult(null);
        setSelected(s.id);
        setTick((n) => n + 1);
      })
      .catch((err: unknown) => {
        setError(message(err, "The search could not be started."));
      })
      .finally(() => {
        setBusy(false);
      });
  };

  const running = status?.status === "queued" || status?.status === "running";
  const candidatesPerSearch = spec.budget.population * spec.budget.generations;

  return (
    <div className="dash-page copilot-page">
      <PageHero title="Control Strategy Discovery Lab">
        A bounded multi-objective evolutionary search over the parameters of the
        registered control strategies, for one traffic regime you declare.
        Candidates are compared with the unchanged fixed-time, adaptive and
        roundabout baselines on held-out seeds the search never saw. It is not a
        learned model, and its results apply to this simulator only.
      </PageHero>

      <Panel
        id="disc-regime"
        title="Regime and budget"
        subtitle="Declare the traffic conditions, then size the search. The cost is reserved up front and unused runs are refunded."
      >
        <div className="dash-form discovery-form">
          <label>
            Vehicles per hour per arm
            <input
              type="number"
              min={100}
              max={1200}
              value={spec.regime.vehiclesPerHour}
              onChange={(e) => {
                regime({ vehiclesPerHour: Number(e.target.value) });
              }}
            />
          </label>
          <label>
            Driver aggression
            <select
              value={spec.regime.aggression ?? ""}
              onChange={(e) => {
                regime({
                  aggression: (e.target.value ||
                    null) as SearchSpec["regime"]["aggression"],
                });
              }}
            >
              <option value="">Scenario default</option>
              <option value="standard">Standard</option>
              <option value="moderate">Moderate</option>
              <option value="high">High</option>
            </select>
          </label>
          <label>
            Vehicle mix
            <select
              value={spec.regime.mix}
              onChange={(e) => {
                regime({ mix: e.target.value as SearchSpec["regime"]["mix"] });
              }}
            >
              <option value="default">Default</option>
              <option value="heavy_vehicles">Many buses and trucks</option>
              <option value="two_wheelers">Many two-wheelers</option>
            </select>
          </label>
          <label className="discovery-check dash-check">
            <input
              type="checkbox"
              checked={spec.regime.unevenDemand}
              onChange={(e) => {
                regime({ unevenDemand: e.target.checked });
              }}
            />
            Uneven directional demand
          </label>
          <label>
            Population
            <input
              type="number"
              min={4}
              max={24}
              value={spec.budget.population}
              onChange={(e) => {
                budget({ population: Number(e.target.value) });
              }}
            />
          </label>
          <label>
            Generations
            <input
              type="number"
              min={1}
              max={20}
              value={spec.budget.generations}
              onChange={(e) => {
                budget({ generations: Number(e.target.value) });
              }}
            />
          </label>
          <label>
            Search seed
            <input
              type="number"
              min={0}
              value={spec.seed}
              onChange={(e) => {
                setSpec((s) => ({ ...s, seed: Number(e.target.value) }));
              }}
            />
          </label>
        </div>

        <div className="discovery-budget">
          <StatGrid>
            <StatTile
              label="Candidate slots"
              icon={<Layers size={16} />}
              value={candidatesPerSearch.toString()}
              hint={`${spec.budget.population.toString()} × ${spec.budget.generations.toString()} generations`}
              tip="Population times generations: an upper bound on candidates evaluated."
            />
            <StatTile
              label="Max simulation runs"
              icon={<Gauge size={16} />}
              tone={cost ? "accent" : "bad"}
              value={cost ? cost.runs.toLocaleString() : "—"}
              hint={
                cost ? "Reserved, then refunded if unused" : "Out of bounds"
              }
            />
            <StatTile
              label="Simulated seconds"
              icon={<Timer size={16} />}
              value={
                cost ? Math.round(cost.simulatedSeconds).toLocaleString() : "—"
              }
              hint="Against your daily quota"
            />
            <StatTile
              label="Held-out seeds"
              icon={<ShieldAlert size={16} />}
              value={spec.budget.heldOutSeeds.toString()}
              hint="Never seen by the search"
              tip="The search is judged on these seeds; their hash is recorded before it starts."
            />
          </StatGrid>
        </div>

        <p className="copilot-muted">
          {cost
            ? `Budget: at most ${cost.runs.toString()} simulation runs, ${Math.round(cost.simulatedSeconds).toLocaleString()} simulated seconds reserved against your daily quota (unused runs are refunded). Wall-clock time: unverified.`
            : "This specification is outside the allowed bounds."}
        </p>
        <div className="copilot-actions">
          <button
            type="button"
            className="pb-btn pb-primary"
            disabled={busy || !cost || running}
            onClick={start}
          >
            <FlaskConical size={15} aria-hidden="true" />
            Start search
          </button>
        </div>
        {error ? (
          <p className="copilot-error" role="alert">
            {error}
          </p>
        ) : null}
      </Panel>

      <div className="dash-grid-2">
        {searches.length ? (
          <Panel id="disc-list" title="Your searches">
            <ul className="dash-items discovery-list">
              {searches.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    className={`dash-item discovery-pick ${s.id === selected ? "is-current" : ""}`}
                    aria-pressed={s.id === selected}
                    onClick={() => {
                      setResult(null);
                      setSelected(s.id);
                    }}
                  >
                    <span className="dash-item__name">{s.name}</span>
                    <Pill tone={STATUS_TONE[s.status]}>{s.status}</Pill>
                    <span className="dash-item__meta">
                      {s.runs.used.toString()} of {s.runs.planned.toString()}{" "}
                      runs
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </Panel>
        ) : (
          <Panel id="disc-list" title="Your searches">
            <EmptyHint icon={<Radar size={22} />} title="No searches yet">
              Start one above. Finished searches stay here so you can reopen
              their results.
            </EmptyHint>
          </Panel>
        )}

        {status ? (
          <section className="dash-panel" aria-labelledby="disc-status">
            <div className="dash-panel__head">
              <div>
                <h2 id="disc-status">{status.name}</h2>
                <p className="dash-panel__sub" role="status">
                  {status.status} · phase {status.phase} ·{" "}
                  {status.runs.used.toString()} of at most{" "}
                  {status.runs.planned.toString()} runs
                  {status.error ? ` · ${status.error}` : ""}
                </p>
              </div>
              <Pill tone={STATUS_TONE[status.status]}>{status.status}</Pill>
            </div>
            <Meter
              label="Runs used"
              value={
                status.runs.planned ? status.runs.used / status.runs.planned : 0
              }
              tone={running ? "accent" : STATUS_TONE[status.status]}
            />
            <p className="dash-stat__hint discovery-progress">
              {status.runs.planned
                ? `${Math.round((status.runs.used / status.runs.planned) * 100).toString()} % of the reserved runs`
                : ""}
            </p>
            {running ? (
              <>
                <Skeleton lines={2} />
                <div className="copilot-actions">
                  <button
                    type="button"
                    className="pb-btn pb-secondary"
                    onClick={() => {
                      void cancelSearch(status.id).then(setStatus);
                    }}
                  >
                    <Square size={14} aria-hidden="true" />
                    Cancel (stops at the next batch)
                  </button>
                </div>
              </>
            ) : null}
          </section>
        ) : (
          <Panel id="disc-status" title="Search progress">
            <EmptyHint icon={<Target size={22} />} title="Nothing selected">
              Pick a search to follow its progress and see its held-out results.
            </EmptyHint>
          </Panel>
        )}
      </div>

      {result ? (
        <DiscoveryResult result={result} searchId={selected ?? ""} />
      ) : null}
    </div>
  );
}

/** Mean difference and 95 % interval of one candidate against one baseline,
 *  on a shared axis with a zero line. Left of zero = lower delay. */
function ForestRow({
  label,
  mean,
  lo,
  hi,
  min,
  max,
}: {
  label: string;
  mean: number;
  lo: number;
  hi: number;
  min: number;
  max: number;
}) {
  const span = max - min || 1;
  const at = (v: number) => `${(((v - min) / span) * 100).toFixed(2)}%`;
  const better = hi < 0;
  const worse = lo > 0;
  const tone = better ? "good" : worse ? "bad" : "neutral";
  const verdict = better
    ? "lower delay"
    : worse
      ? "higher delay"
      : "interval includes zero";
  return (
    <li
      className="forest-row"
      aria-label={`${label}: ${fmt(mean)} s, interval ${fmt(lo)} to ${fmt(hi)}, ${verdict}`}
    >
      <span className="forest-row__label">{label}</span>
      <span className="forest-row__track" aria-hidden="true">
        <span className="forest-row__zero" style={{ left: at(0) }} />
        <span
          className={`forest-row__ci is-${tone}`}
          style={{ left: at(lo), width: `calc(${at(hi)} - ${at(lo)})` }}
        />
        <span
          className={`forest-row__dot is-${tone}`}
          style={{ left: at(mean) }}
        />
      </span>
      <Pill tone={tone === "neutral" ? "neutral" : tone}>{verdict}</Pill>
    </li>
  );
}

function DiscoveryResult({
  result,
  searchId,
}: {
  result: SearchResult;
  searchId: string;
}) {
  const held = result.heldOut;

  const candidateRows = held
    ? Object.entries(held.candidates).map(([key, row]) => ({
        key,
        name: `Candidate ${shortId(key)}`,
        strategy: String(row.genome.strategy),
        delay: objective(row.objectives, "averageDelay"),
        kind: "candidate" as const,
        fill: "var(--brand-green-ink)",
      }))
    : [];
  const baselineRows = held
    ? Object.entries(held.baselines).map(([key, row]) => ({
        key,
        name: prettyName(key),
        strategy: key,
        delay: objective(row.objectives, "averageDelay"),
        kind: "baseline" as const,
        fill: seriesColour(key),
      }))
    : [];
  const delayBars = [...candidateRows, ...baselineRows].filter(
    (r): r is typeof r & { delay: number } => r.delay !== null,
  );
  const lowest = <T extends { delay: number | null }>(rows: T[]) =>
    first(
      rows
        .filter((r) => r.delay !== null)
        .sort((x, y) => (x.delay ?? 0) - (y.delay ?? 0)),
    );
  const bestCandidate = lowest(candidateRows);
  const bestBaseline = lowest(baselineRows);
  const gap =
    bestCandidate?.delay != null && bestBaseline?.delay != null
      ? bestCandidate.delay - bestBaseline.delay
      : null;

  const forest = held
    ? Object.entries(held.candidates).flatMap(([key, row]) =>
        Object.entries(row.versusBaselines).flatMap(([b, v]) =>
          v.meanDifference != null && v.ci95
            ? [
                {
                  id: `${key}-${b}`,
                  label: `${shortId(key)} vs ${prettyName(b)}`,
                  mean: v.meanDifference,
                  lo: v.ci95[0],
                  hi: v.ci95[1],
                },
              ]
            : [],
        ),
      )
    : [];
  const fMin = Math.min(0, ...forest.map((f) => f.lo)) * 1.1;
  const fMax = Math.max(0, ...forest.map((f) => f.hi)) * 1.1;

  const scatter = result.pareto
    .map((p) => ({
      id: shortId(p.candidate),
      delay: objective(p.tuningObjectives, "averageDelay"),
      throughput: objective(p.tuningObjectives, "throughput"),
      generation: p.generation,
    }))
    .filter(
      (p): p is typeof p & { delay: number; throughput: number } =>
        p.delay !== null && p.throughput !== null,
    );

  const rejected = Object.values(result.rejected).reduce((a, b) => a + b, 0);
  const usedShare = result.runs.planned
    ? result.runs.used / result.runs.planned
    : 0;

  const demands = Array.from(
    new Set((result.preferenceChanges ?? []).map((r) => r.demandScale)),
  ).sort((a, b) => a - b);
  const aggressions = Array.from(
    new Set((result.preferenceChanges ?? []).map((r) => r.aggression)),
  );

  return (
    <section className="dash-panel" aria-labelledby="disc-result">
      <div className="dash-panel__head">
        <div>
          <h2 id="disc-result">Result</h2>
          <p className="dash-panel__sub">
            {result.complete
              ? "Complete."
              : "This search did not finish: the result is incomplete."}
          </p>
        </div>
        <p className="uf-badge discovery-badge">EXPERIMENTAL</p>
      </div>
      <p className="copilot-note">{result.experimental}</p>

      <StatGrid>
        <StatTile
          label="Runs used"
          icon={<Gauge size={16} />}
          value={result.runs.used.toLocaleString()}
          unit={`of ${result.runs.planned.toLocaleString()}`}
          hint={`${Math.round(usedShare * 100).toString()} % of the budget`}
        >
          <Meter label="Share of the run budget used" value={usedShare} />
        </StatTile>
        <StatTile
          label="Best candidate delay"
          icon={<Target size={16} />}
          tone={gap === null ? "neutral" : gap <= 0 ? "good" : "warn"}
          value={fmt(bestCandidate?.delay)}
          unit="s"
          hint={
            gap === null
              ? "On the held-out seeds"
              : `${gap <= 0 ? "" : "+"}${gap.toFixed(2)} s vs best baseline (${prettyName(bestBaseline?.strategy ?? "")})`
          }
          tip="Mean delay on held-out seeds. Lower is better."
        />
        <StatTile
          label="Pareto set"
          icon={<Layers size={16} />}
          value={result.pareto.length.toString()}
          unit="candidates"
          hint={`${held ? Object.keys(held.candidates).length.toString() : "0"} shortlisted for held-out testing`}
        />
        <StatTile
          label="Rejected genomes"
          icon={<TriangleAlert size={16} />}
          value={rejected.toString()}
          hint={
            rejected
              ? Object.keys(result.rejected).join(", ")
              : "None rejected by the validator"
          }
        />
      </StatGrid>

      <p className="copilot-muted">
        {result.method} Seeds: {result.seedPools.tuning.toString()} for tuning,{" "}
        {result.seedPools.selection.toString()} for selection,{" "}
        {result.seedPools.heldOut.toString()} held out (their hash was recorded
        before the search began). Trace <code>{result.traceFingerprint}</code>.
        {result.complete
          ? ""
          : " This search did not finish: the result is incomplete."}
      </p>

      {held ? (
        <>
          <h3>Held-out evaluation against the baselines</h3>
          <p className="copilot-muted">
            {held.differenceMeaning}. 95% bootstrap intervals over{" "}
            {held.seeds.toString()} held-out seeds.
          </p>
          {result.bestOnTuningLosesOnHeldOut ? (
            <p className="copilot-warnings">
              The best candidate on the tuning seeds does worse than a baseline
              on the held-out seeds.
            </p>
          ) : null}

          <div className="dash-grid-2 discovery-charts">
            {delayBars.length ? (
              <div>
                <h4 className="discovery-chart-title">
                  Mean delay on held-out seeds (s)
                </h4>
                <ChartFrame
                  label={`Mean delay: ${delayBars.map((d) => `${d.name} ${d.delay.toFixed(2)} seconds`).join(", ")}`}
                  height={Math.max(160, delayBars.length * 44 + 40)}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={delayBars}
                      layout="vertical"
                      margin={{ top: 4, right: 24, left: 8, bottom: 0 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 4"
                        stroke={CHART_GRID}
                        horizontal={false}
                      />
                      <XAxis
                        type="number"
                        stroke={CHART_AXIS}
                        fontSize={11}
                        tickLine={false}
                      />
                      <YAxis
                        type="category"
                        dataKey="name"
                        stroke={CHART_AXIS}
                        fontSize={11}
                        width={110}
                        tickLine={false}
                      />
                      <Tooltip
                        contentStyle={TOOLTIP_STYLE}
                        cursor={{ fill: "var(--color-accent-soft)" }}
                        formatter={(v) => [
                          `${Number(v).toFixed(2)} s`,
                          "Mean delay",
                        ]}
                      />
                      <Bar dataKey="delay" radius={[0, 4, 4, 0]} barSize={22} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartFrame>
                <ul className="dash-legend">
                  <li>
                    <i style={{ background: "var(--brand-green-ink)" }} />
                    Discovered candidate
                  </li>
                  <li>
                    <i style={{ background: "var(--series-neutral)" }} />
                    Unchanged baseline
                  </li>
                </ul>
              </div>
            ) : null}

            {forest.length ? (
              <div>
                <h4 className="discovery-chart-title">
                  Candidate minus baseline, with 95 % interval (s)
                </h4>
                <ul className="forest">
                  {forest.map((f) => (
                    <ForestRow key={f.id} {...f} min={fMin} max={fMax} />
                  ))}
                </ul>
                <p className="copilot-muted">
                  Left of the line means the candidate has lower delay. An
                  interval that crosses the line is not a clear win or loss.
                </p>
              </div>
            ) : null}
          </div>

          <div className="dash-table-wrap">
            <table className="dash-table copilot-table">
              <thead>
                <tr>
                  <th scope="col">Option</th>
                  <th scope="col">Mean delay (s)</th>
                  <th scope="col">Throughput</th>
                  <th scope="col">Max queue</th>
                  <th scope="col">Near misses /1000</th>
                  <th scope="col">vs fixed-time</th>
                  <th scope="col">vs adaptive</th>
                  <th scope="col">vs roundabout</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(held.candidates).map(([key, row]) => (
                  <tr key={key}>
                    <th scope="row" title={describeGenome(row.genome)}>
                      Candidate <code>{key.slice(0, 8)}</code> (
                      {String(row.genome.strategy)})
                    </th>
                    {objectiveCells(row.objectives)}
                    {["fixed_time", "adaptive", "roundabout"].map((b) => {
                      const v = row.versusBaselines[b] as
                        (typeof row.versusBaselines)[string] | undefined;
                      return (
                        <td key={b}>
                          {v?.meanDifference != null && v.ci95
                            ? `${fmt(v.meanDifference)} [${fmt(v.ci95[0])}, ${fmt(v.ci95[1])}]`
                            : "—"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
                {Object.entries(held.baselines).map(([name, row]) => (
                  <tr key={name}>
                    <th scope="row">Baseline: {name}</th>
                    {objectiveCells(row.objectives)}
                    <td colSpan={3}>{row.infeasible ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      {result.preferenceChanges?.length ? (
        <>
          <h3>Where the preference changes (unseen conditions)</h3>
          <div
            className="dash-heat discovery-heat"
            style={{
              gridTemplateColumns: `minmax(90px, auto) repeat(${demands.length.toString()}, minmax(80px, 1fr))`,
            }}
            role="group"
            aria-label="Option with the lowest mean delay at each demand scale and aggression level"
          >
            <span />
            {demands.map((d) => (
              <span key={d} className="dash-heat__head">
                Demand ×{d.toString()}
              </span>
            ))}
            {aggressions.map((a) => (
              <HeatRow
                key={a}
                aggression={a}
                demands={demands}
                rows={result.preferenceChanges ?? []}
              />
            ))}
          </div>
          <div className="dash-table-wrap discovery-heat-table">
            <table className="dash-table copilot-table">
              <thead>
                <tr>
                  <th scope="col">Demand</th>
                  <th scope="col">Aggression</th>
                  <th scope="col">Lowest mean delay</th>
                  <th scope="col">Seeds</th>
                </tr>
              </thead>
              <tbody>
                {result.preferenceChanges.map((row) => (
                  <tr key={`${row.demandScale.toString()}-${row.aggression}`}>
                    <td>×{row.demandScale.toString()}</td>
                    <td>{row.aggression}</td>
                    <td>{row.lowestDelay ?? "none feasible"}</td>
                    <td>{row.seeds.toString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="copilot-muted">
            Two seeds per cell: a coarse indication of where the preferred
            option changes, with wide uncertainty.
          </p>
        </>
      ) : null}

      <h3>Pareto set on the tuning seeds</h3>
      {scatter.length > 1 ? (
        <>
          <ChartFrame
            label={`Tuning-seed trade-off between delay and throughput for ${scatter.length.toString()} Pareto candidates`}
            height={260}
          >
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart
                margin={{ top: 10, right: 20, left: 0, bottom: 18 }}
              >
                <CartesianGrid strokeDasharray="3 4" stroke={CHART_GRID} />
                <XAxis
                  type="number"
                  dataKey="delay"
                  name="Mean delay"
                  unit=" s"
                  stroke={CHART_AXIS}
                  fontSize={11}
                  domain={["auto", "auto"]}
                  label={{
                    value: "Mean delay (s) — lower is better",
                    position: "insideBottom",
                    offset: -10,
                    fill: CHART_AXIS,
                    fontSize: 11,
                  }}
                />
                <YAxis
                  type="number"
                  dataKey="throughput"
                  name="Throughput"
                  stroke={CHART_AXIS}
                  fontSize={11}
                  domain={["auto", "auto"]}
                />
                <ZAxis
                  dataKey="generation"
                  range={[60, 160]}
                  name="Generation"
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  cursor={{ strokeDasharray: "3 4" }}
                />
                <Scatter data={scatter} fill="var(--brand-green-ink)" />
              </ScatterChart>
            </ResponsiveContainer>
          </ChartFrame>
          <p className="copilot-muted">
            Marker size grows with the generation that found the candidate.
          </p>
        </>
      ) : null}
      <div className="dash-table-wrap">
        <table className="dash-table copilot-table">
          <thead>
            <tr>
              <th scope="col">Candidate</th>
              <th scope="col">Mean delay (s)</th>
              <th scope="col">Throughput</th>
              <th scope="col">Max queue</th>
              <th scope="col">Near misses /1000</th>
            </tr>
          </thead>
          <tbody>
            {result.pareto.map((p) => (
              <tr key={p.candidate}>
                <th scope="row" title={describeGenome(p.genome)}>
                  <code>{p.candidate.slice(0, 8)}</code> (gen{" "}
                  {p.generation.toString()})
                </th>
                {objectiveCells(p.tuningObjectives)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {result.complete ? (
        <div className="copilot-actions">
          <button
            type="button"
            className="pb-btn pb-secondary"
            onClick={() => {
              void downloadSearchPackage(searchId).then(
                ({ filename, blob }) => {
                  saveBlob(filename, blob);
                },
              );
            }}
          >
            <Download size={14} aria-hidden="true" />
            Download package
          </button>
        </div>
      ) : null}
    </section>
  );
}

function HeatRow({
  aggression,
  demands,
  rows,
}: {
  aggression: string;
  demands: number[];
  rows: NonNullable<SearchResult["preferenceChanges"]>;
}) {
  return (
    <>
      <span className="dash-heat__row">{prettyName(aggression)}</span>
      {demands.map((d) => {
        const row = rows.find(
          (r) => r.demandScale === d && r.aggression === aggression,
        );
        const name = row?.lowestDelay ?? null;
        return (
          <span
            key={d}
            className="dash-heat__cell"
            style={
              {
                "--heat": name ? 1 : 0,
                "--heat-colour": name ? seriesColour(name) : undefined,
              } as CSSProperties
            }
          >
            {row ? (name ? prettyName(name) : "none feasible") : "—"}
          </span>
        );
      })}
    </>
  );
}
