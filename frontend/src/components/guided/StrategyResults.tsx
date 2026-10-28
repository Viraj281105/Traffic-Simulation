import { useState, type CSSProperties, type ReactNode } from "react";
import {
  ArrowLeft,
  BarChart3,
  Download,
  Play,
  Save,
  SlidersHorizontal,
} from "lucide-react";
import type { ComparisonSnapshot } from "../../types/simulation";
import type { SimulationConfigValues } from "../../types/config";
import {
  DEMAND_LEVELS,
  adaptiveSettings,
  demandLevelFor,
  demandRate,
  signalCycleSeconds,
} from "../../types/config";
import {
  REFERENCE_CAPACITY_VPH,
  saturationRatio,
  type LaneCount,
} from "../../types/demand";
import {
  LOS_THRESHOLDS,
  LOS_WORDS,
  SIMILARITY,
  compare,
  count,
  duration,
  explanations,
  fairnessBand,
  levelOfService,
  metricDef,
  seconds,
  trustNotes,
  type SideSummary,
  type Similarity,
} from "../../metrics/plainLanguage";
import type { MetricDef } from "../../metrics/catalog";
import { MetricSections, MultiRunSections } from "../MetricSections";
import { ReliabilityCheck } from "./ReliabilityCheck";
import { ResearchLink } from "../research/LabSection";
import "../research/ResearchLab.css";
import { VIEW_ROUTES } from "../../routing";
import {
  downloadComparisonCsv,
  hasComparisonResults,
  scenarioLabel,
  strategyRuns,
  type SessionRun,
  type StrategyRun,
} from "./comparisonRun";
import { VehicleClassResults } from "./VehicleClassResults";
import { ApproachResults } from "./ApproachResults";
import { describeRoads, ringLanes } from "../../scenario/scenarioModel";
import { describeMix, hasMixedTraffic } from "../../vehicles/vehicleClasses";
import { StrategyGlyph } from "../../strategies/StrategyGlyph";
import { strategyName } from "../../strategies/strategyCatalog";
import "../../strategies/Strategies.css";

const LOW_SAMPLE_NOTE =
  "Fewer than 20 vehicles got through under at least one strategy, so read the “1 in 20” and per-direction figures as rough.";

const colorStyle = (run: StrategyRun) =>
  ({
    "--strategy-color": run.strategy.color,
    "--side-color": run.strategy.color,
  }) as CSSProperties;

// ── Reading several strategies at once ─────────────────────────────────────

interface Spread {
  low: StrategyRun;
  high: StrategyRun;
  gap: number;
  similar: boolean;
}

/** The lowest and highest value of one measure across the strategies, and
 *  whether they are close enough to call "about the same" (the same
 *  presentation tolerance the plain-language layer uses). */
function spread(
  runs: StrategyRun[],
  pick: (s: SideSummary) => number | null,
  tol: Similarity,
): Spread | null {
  const valued = runs.filter((r) => pick(r.summary) !== null);
  if (valued.length < 2) return null;
  const sorted = [...valued].sort(
    (a, b) => (pick(a.summary) as number) - (pick(b.summary) as number),
  );
  const low = sorted[0];
  const high = sorted[sorted.length - 1];
  const c = compare(pick(low.summary), pick(high.summary), tol);
  if (!c) return null;
  return { low, high, gap: c.gap, similar: c.similar };
}

interface Row {
  label: string;
  pick: (s: SideSummary) => number | null;
  format: (v: number) => string;
}

/** One bar per strategy for one measure, scaled to the largest value. The
 *  lowest and highest are named in words, never coloured as better or
 *  worse: whether lower is better depends on the measure and the reader. */
function StrategyBars({ row, runs }: { row: Row; runs: StrategyRun[] }) {
  const values = runs.map((r) => row.pick(r.summary));
  const max = Math.max(0, ...values.map((v) => v ?? 0));
  const width = (v: number | null) =>
    v === null || max <= 0 ? 0 : Math.max(2, (v / max) * 100);
  return (
    <div className="pair-row" role="group" aria-label={row.label}>
      <div className="pair-label">{row.label}</div>
      {runs.map((run, i) => {
        const v = values[i];
        return (
          <div
            className="pair-bar is-strategy"
            key={run.strategy.id}
            style={colorStyle(run)}
          >
            <span className="pair-side">{run.strategy.name}</span>
            <span className="pair-track" aria-hidden="true">
              <span
                className="pair-fill"
                style={{ width: `${String(width(v))}%` }}
              />
            </span>
            <span className="pair-value">
              {v === null ? "—" : row.format(v)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function HowMeasured({
  keys,
  children,
}: {
  keys: MetricDef["key"][];
  children?: ReactNode;
}) {
  return (
    <details className="how-measured">
      <summary>How is this measured?</summary>
      <dl>
        {keys.map((key) => {
          const def = metricDef(key);
          return (
            <div key={key}>
              <dt>
                {def.label} <code>{def.key}</code>
              </dt>
              <dd>{def.description}</dd>
            </div>
          );
        })}
      </dl>
      {children}
    </details>
  );
}

function QuestionCard({
  question,
  lead,
  rows,
  runs,
  keys,
  extra,
  measuredNote,
}: {
  question: string;
  lead: string | null;
  rows: Row[];
  runs: StrategyRun[];
  keys: MetricDef["key"][];
  extra?: ReactNode;
  measuredNote?: ReactNode;
}) {
  return (
    <article className="question-card">
      <h3>{question}</h3>
      {lead && <p className="question-lead">{lead}</p>}
      {rows.map((row) => (
        <StrategyBars row={row} runs={runs} key={row.label} />
      ))}
      {extra}
      <HowMeasured keys={keys}>{measuredNote}</HowMeasured>
    </article>
  );
}

/** A lead sentence for a measure: "about the same" within tolerance,
 *  otherwise which strategy had the lowest and the highest value. */
function lead(
  runs: StrategyRun[],
  pick: (s: SideSummary) => number | null,
  tol: Similarity,
  same: string,
  differs: (s: Spread) => string,
): string | null {
  const s = spread(runs, pick, tol);
  if (!s) return null;
  return s.similar ? same : differs(s);
}

const lc = (run: StrategyRun) => run.strategy.name.toLowerCase();

// ── The report ─────────────────────────────────────────────────────────────

/** Step 3: the chosen strategies' results side by side, in plain language
 *  first, with every measurement on demand. Each strategy keeps its own
 *  colour, name and drawing throughout; nothing is ranked or weighted. */
export function StrategyResults({
  snapshot,
  config,
  replayName,
  complete,
  running,
  warmupSeconds,
  elapsedSeconds,
  canSave,
  onSave,
  onWatch,
  onChangeScenario,
  onTryScenario,
  onOpenAnalytics,
  sessionRuns,
  currentRunId,
}: {
  snapshot: ComparisonSnapshot | null;
  config: SimulationConfigValues;
  replayName: string | null;
  complete: boolean;
  running: boolean;
  warmupSeconds: number | null;
  elapsedSeconds: number | null;
  canSave: boolean;
  onSave: () => void;
  onWatch: () => void;
  onChangeScenario: () => void;
  /** Runs the comparison again with these settings. */
  onTryScenario: (config: SimulationConfigValues) => void;
  /** Opens the signal-vs-roundabout charts; only for such a pair. */
  onOpenAnalytics: (() => void) | null;
  sessionRuns: SessionRun[];
  currentRunId: string | null;
}) {
  const runs = strategyRuns(snapshot);
  const ready = hasComparisonResults(runs);
  const [inspected, setInspected] = useState<string | null>(null);
  const focus = runs.find((r) => r.strategy.id === inspected) ?? runs[0];
  const measured =
    elapsedSeconds !== null && warmupSeconds !== null
      ? Math.max(0, elapsedSeconds - warmupSeconds)
      : null;
  // The backend flags fewer than 20 vehicles through; spread and
  // per-direction readings rest on very few drivers then.
  const lowSample = runs.some(
    (r) => r.ctx.metrics?.travelTimeReliabilityLowSampleSize,
  );
  const signalRun = runs.find((r) => r.strategy.family === "signal");
  const roundaboutRun = runs.find((r) => r.strategy.family === "roundabout");
  const ids = runs.map((r) => r.strategy.id);
  const n = runs.length;

  const level = demandLevelFor(config.arrivalRate, config.lanes);
  const levelIndex = level ? DEMAND_LEVELS.indexOf(level) : -1;
  const busier = levelIndex >= 0 ? DEMAND_LEVELS[levelIndex + 1] : undefined;
  const quieter = levelIndex > 0 ? DEMAND_LEVELS[levelIndex - 1] : undefined;

  const status = replayName
    ? `Saved comparison: ${replayName}`
    : complete
      ? "Complete run"
      : running
        ? "Results so far — still running, numbers update live"
        : "Results so far — run paused before the end";

  const strategyList = runs.map((r) => r.strategy.name).join(", ");

  return (
    <div className="guided-page results-page">
      <header className="guided-intro">
        <p className="guided-eyebrow">Step 3 of 3</p>
        <h1>Results for your junction</h1>
        <ul className="scenario-chips" aria-label="Scenario">
          <li>{scenarioLabel(config)}</li>
          <li>
            {config.scenario
              ? describeRoads(config.scenario)
              : `${config.lanes === 1 ? "1 lane" : `${String(config.lanes)} lanes`} per approach`}
          </li>
          <li>
            {config.vehicleMix
              ? `Mixed traffic: ${describeMix(config.vehicleMix)}`
              : "Cars only"}
          </li>
          <li>{duration(config.duration)} of traffic</li>
          <li>Traffic pattern #{config.randomSeed}</li>
        </ul>
        <p
          className={`results-status${complete || replayName ? "" : " is-partial"}`}
        >
          {status}
        </p>
      </header>

      {!ready ? (
        <section className="results-section">
          <p>
            There is nothing to compare yet: results appear once the warm-up is
            over and vehicles have got through under{" "}
            {n === 1 ? "the strategy" : "every strategy"}.
          </p>
          <button
            type="button"
            className="guided-primary-btn"
            onClick={onWatch}
          >
            <ArrowLeft size={16} aria-hidden="true" /> Back to watching
          </button>
        </section>
      ) : (
        <>
          <section
            className="results-section in-short"
            aria-labelledby="r-short"
          >
            <h2 id="r-short">At a glance</h2>
            <div className="strategy-glance">
              {runs.map((run) => {
                const d = run.summary.delay;
                const grade =
                  d === null ? null : levelOfService(d, run.strategy.family);
                return (
                  <article
                    className="strategy-glance__card"
                    key={run.strategy.id}
                    style={colorStyle(run)}
                  >
                    <div className="strategy-glance__head">
                      <StrategyGlyph strategy={run.strategy} size={36} />
                      <h3 className="strategy-glance__name">
                        {run.strategy.name}
                      </h3>
                    </div>
                    <dl>
                      <div>
                        <dt>Time lost per driver</dt>
                        <dd>
                          {d === null ? "—" : seconds(d)}
                          {grade && <small>grade {grade}</small>}
                        </dd>
                      </div>
                      <div>
                        <dt>Vehicles through</dt>
                        <dd>
                          {run.summary.served === null
                            ? "—"
                            : count(run.summary.served)}
                        </dd>
                      </div>
                      <div>
                        <dt>Longest queue</dt>
                        <dd>
                          {run.summary.maxQueue === null
                            ? "—"
                            : count(run.summary.maxQueue)}
                          <small>vehicles</small>
                        </dd>
                      </div>
                      <div>
                        <dt>Stops per driver</dt>
                        <dd>
                          {run.summary.stops === null
                            ? "—"
                            : run.summary.stops.toFixed(1)}
                        </dd>
                      </div>
                    </dl>
                  </article>
                );
              })}
            </div>
            <p className="results-note">
              UrbanFlow shows the evidence; it does not pick a winner. Which
              result matters most depends on what you care about at this
              junction.
            </p>
          </section>

          {n > 1 && (
            <section className="results-section" aria-labelledby="r-matters">
              <h2 id="r-matters">
                What people using the junction would notice
              </h2>
              <div className="question-grid">
                <QuestionCard
                  question="How much time do drivers lose?"
                  runs={runs}
                  lead={lead(
                    runs,
                    (s) => s.delay,
                    SIMILARITY.delay,
                    "Drivers lost about the same time under every strategy.",
                    (s) =>
                      `Least time lost with the ${lc(s.low)}, most with the ${lc(s.high)}: ${seconds(s.gap)} apart per journey.`,
                  )}
                  rows={[
                    {
                      label: "Time lost per driver, on average",
                      pick: (s) => s.delay,
                      format: (v) => seconds(v),
                    },
                    {
                      label: "Time spent nearly stopped, on average",
                      pick: (s) => s.queuedTime,
                      format: (v) => seconds(v, 1),
                    },
                    {
                      label: "1 in 20 drivers lost more than",
                      pick: (s) => s.p95Delay,
                      format: (v) => seconds(v),
                    },
                    {
                      label: "Stops per driver",
                      pick: (s) => s.stops,
                      format: (v) => v.toFixed(1),
                    },
                  ]}
                  keys={[
                    "averageDelay",
                    "p95Delay",
                    "averageWaitTime",
                    "averageStopsPerVehicle",
                  ]}
                  extra={
                    lowSample ? (
                      <p className="question-extra sample-note">
                        {LOW_SAMPLE_NOTE}
                      </p>
                    ) : undefined
                  }
                  measuredNote={
                    <p>
                      “Time lost” is the extra time a journey took compared with
                      driving through an empty junction at the driver’s own
                      speed. It counts queuing and also any slowing the layout
                      itself forces (for example easing into a roundabout), so
                      it is not the same as “time spent nearly stopped”, which
                      counts only standing time. The grades under “At a glance”
                      are the Highway Capacity Manual’s delay bands, used as an
                      indicative guide: for signals A ≤{" "}
                      {LOS_THRESHOLDS.signal[0]} s, B ≤{" "}
                      {LOS_THRESHOLDS.signal[1]} s, C ≤{" "}
                      {LOS_THRESHOLDS.signal[2]} s, D ≤{" "}
                      {LOS_THRESHOLDS.signal[3]} s, E ≤{" "}
                      {LOS_THRESHOLDS.signal[4]} s; for roundabouts the stricter
                      A ≤ {LOS_THRESHOLDS.roundabout[0]} s, B ≤{" "}
                      {LOS_THRESHOLDS.roundabout[1]} s, C ≤{" "}
                      {LOS_THRESHOLDS.roundabout[2]} s, D ≤{" "}
                      {LOS_THRESHOLDS.roundabout[3]} s, E ≤{" "}
                      {LOS_THRESHOLDS.roundabout[4]} s. In words:{" "}
                      {(["A", "C", "F"] as const)
                        .map((g) => `${g} ${LOS_WORDS[g].toLowerCase()}`)
                        .join(", ")}
                      . The manual grades longer study periods than a single
                      short run.
                    </p>
                  }
                />

                <QuestionCard
                  question="How much traffic gets through?"
                  runs={runs}
                  lead={lead(
                    runs,
                    (s) => s.served,
                    SIMILARITY.vehicles,
                    "Every strategy got about the same number of vehicles through.",
                    (s) =>
                      `The ${lc(s.high)} got ${count(s.gap)} more vehicles through than the ${lc(s.low)}, from exactly the same arrivals.`,
                  )}
                  rows={[
                    {
                      label:
                        measured !== null
                          ? `Got through in the ${duration(measured)} measured`
                          : "Got through after the warm-up",
                      pick: (s) => s.served,
                      format: count,
                    },
                    {
                      label: "Still waiting or moving when the clock stopped",
                      pick: (s) => s.inNetwork,
                      format: count,
                    },
                  ]}
                  keys={["throughput", "activeVehicleCount"]}
                  measuredNote={
                    <p>
                      Every strategy received the same vehicles, so a difference
                      in vehicles through means one cleared traffic faster. A
                      growing number still in the network means traffic was
                      arriving faster than it could be cleared.
                    </p>
                  }
                />

                <QuestionCard
                  question="How long do queues get?"
                  runs={runs}
                  lead={lead(
                    runs,
                    (s) => s.avgQueue,
                    SIMILARITY.queue,
                    "Queues were typically about the same length under every strategy.",
                    (s) =>
                      `Queues were typically shortest with the ${lc(s.low)} and longest with the ${lc(s.high)}.`,
                  )}
                  rows={[
                    {
                      label: "Typical queue on one approach",
                      pick: (s) => s.avgQueue,
                      format: (v) => `${v.toFixed(1)} vehicles`,
                    },
                    {
                      label: "Longest queue seen",
                      pick: (s) => s.maxQueue,
                      format: (v) => `${count(v)} vehicles`,
                    },
                    {
                      label: "Time with more than 5 vehicles queued",
                      pick: (s) => s.congestedSeconds,
                      format: (v) =>
                        measured !== null && measured > 0
                          ? `${duration(v)} (${String(Math.round((v / measured) * 100))}%)`
                          : duration(v),
                    },
                  ]}
                  keys={[
                    "averageQueueLength",
                    "maxQueueLength",
                    "congestionRecoveryTime",
                  ]}
                />

                <QuestionCard
                  question="Is every direction treated alike?"
                  runs={runs}
                  lead={lead(
                    runs,
                    (s) => s.fairness,
                    SIMILARITY.fairness,
                    "Waiting was shared about as evenly under every strategy.",
                    (s) =>
                      `Waiting was shared most evenly with the ${lc(s.high)} and least evenly with the ${lc(s.low)}.`,
                  )}
                  rows={[]}
                  keys={["directionalFairnessIndex"]}
                  extra={
                    <ul className="fairness-list">
                      {runs.map((run) => {
                        const f = run.summary.fairness;
                        if (f === null)
                          return (
                            <li key={run.strategy.id}>
                              {run.strategy.name}: not enough data yet
                            </li>
                          );
                        const band = fairnessBand(f);
                        return (
                          <li key={run.strategy.id}>
                            <strong>
                              {run.strategy.name}: {band.label}
                            </strong>{" "}
                            — {band.meaning} (index {f.toFixed(2)})
                          </li>
                        );
                      })}
                    </ul>
                  }
                  measuredNote={
                    <p>
                      The index runs from 1.00 (every approach waits the same)
                      down to 0.25 (one approach bears all the waiting). Words
                      used here: 0.95 and above “very even”, 0.85 “mostly even”,
                      0.70 “uneven”, below that “very uneven”.
                    </p>
                  }
                />
              </div>
            </section>
          )}

          <VehicleClassResults
            columns={runs.map((r) => ({
              strategy: r.strategy,
              breakdown: r.ctx.metrics?.vehicleTypeBreakdown,
            }))}
          />

          {config.scenario && (
            <ApproachResults
              scenario={config.scenario}
              columns={runs.map((r) => ({
                strategy: r.strategy,
                breakdown: r.ctx.metrics?.approachBreakdown,
              }))}
            />
          )}

          {signalRun && roundaboutRun && (
            <section className="results-section" aria-labelledby="r-why">
              <h2 id="r-why">Why did this happen?</h2>
              <p className="results-note">
                Reading the {lc(signalRun)} against the {lc(roundaboutRun)}.
              </p>
              <div className="why-grid">
                {explanations(signalRun.summary, roundaboutRun.summary, {
                  lanes: config.lanes,
                  arrivalRate: config.arrivalRate,
                  greenNs: config.nsGreenDuration ?? config.greenDuration,
                  greenEw: config.ewGreenDuration ?? config.greenDuration,
                  cycleSeconds: signalCycleSeconds(config),
                  criticalGap: config.criticalGap,
                  meteredEntry:
                    roundaboutRun.strategy.id === "metered_entry_roundabout",
                  adaptive:
                    signalRun.strategy.id === "adaptive_signal"
                      ? adaptiveSettings(config)
                      : null,
                }).map((e) => (
                  <div className="why-item" key={e.title}>
                    <h3>{e.title}</h3>
                    <p>{e.body}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="results-section" aria-labelledby="r-trust">
            <h2 id="r-trust">How reliable is this?</h2>
            <ul className="trust-list">
              {trustNotes({
                seed: config.randomSeed,
                lanes: config.lanes,
                warmupSeconds,
                measuredSeconds: measured,
                complete: complete || replayName !== null,
                collisions: runs.reduce(
                  (sum, r) => sum + (r.summary.collisions ?? 0),
                  0,
                ),
                lowReliabilitySample: lowSample,
                vehicleLimitReached: runs.some(
                  (r) => r.ctx.metrics?.vehicleLimitReached,
                ),
                vehicleLimit: runs[0]?.ctx.metrics?.vehicleLimit ?? null,
                mixedTraffic: hasMixedTraffic(config.vehicleMix),
              }).map((note) => (
                <li key={note.text} className={`trust-${note.tone}`}>
                  {note.text}
                </li>
              ))}
            </ul>
            {ids.includes("fixed_time_signal") &&
              ids.includes("conventional_roundabout") && (
                <ReliabilityCheck config={config} />
              )}
          </section>

          <section className="results-section" aria-labelledby="r-inspect">
            <h2 id="r-inspect">Look closely at one strategy</h2>
            <p>
              Every measurement for one strategy, grouped, without leaving the
              comparison.
            </p>
            {n > 1 && (
              <div
                className="strategy-tabs"
                role="tablist"
                aria-label="Strategy"
              >
                {runs.map((run) => (
                  <button
                    key={run.strategy.id}
                    type="button"
                    role="tab"
                    className="strategy-tab"
                    style={colorStyle(run)}
                    aria-selected={focus.strategy.id === run.strategy.id}
                    aria-controls="r-inspect-panel"
                    onClick={() => {
                      setInspected(run.strategy.id);
                    }}
                  >
                    <span className="strategy-dot" aria-hidden="true" />
                    {run.strategy.name}
                  </button>
                ))}
              </div>
            )}
            <div
              id="r-inspect-panel"
              role="tabpanel"
              aria-label={focus.strategy.name}
            >
              <MetricSections
                key={focus.strategy.id}
                ctx={focus.ctx}
                collapsed={["diagnostic", "safety", "capacity"]}
              />
            </div>
          </section>
        </>
      )}

      <section className="results-section" aria-labelledby="r-next">
        <h2 id="r-next">What next?</h2>
        <p>
          Results can change a lot with traffic level and layout. Try the
          alternatives that matter for your decision — each run is added to the
          table below so you can read them side by side.
        </p>
        <div className="next-actions">
          {!replayName && (
            <button
              type="button"
              className="pb-btn pb-primary"
              onClick={onSave}
              disabled={!canSave}
              title={
                canSave
                  ? "Keep this comparison under Saved"
                  : "Pause or finish the run to save it"
              }
            >
              <Save size={15} aria-hidden="true" />
              Save this comparison
            </button>
          )}
          {quieter && (
            <button
              type="button"
              className="pb-btn pb-secondary"
              onClick={() => {
                onTryScenario({
                  ...config,
                  arrivalRate: demandRate(quieter, config.lanes),
                });
              }}
            >
              Try quieter traffic ({quieter.label.toLowerCase()})
            </button>
          )}
          {busier && (
            <button
              type="button"
              className="pb-btn pb-secondary"
              onClick={() => {
                onTryScenario({
                  ...config,
                  arrivalRate: demandRate(busier, config.lanes),
                });
              }}
            >
              Try busier traffic ({busier.label.toLowerCase()})
            </button>
          )}
          <button
            type="button"
            className="pb-btn pb-secondary"
            onClick={onChangeScenario}
          >
            <SlidersHorizontal size={15} aria-hidden="true" />
            Change the junction or strategies
          </button>
          <button
            type="button"
            className="pb-btn pb-secondary"
            onClick={onWatch}
          >
            <Play size={15} aria-hidden="true" />
            {replayName ? "Watch this scenario" : "Back to the maps"}
          </button>
        </div>
        <div className="rl-links next-links">
          <span className="rl-small-label">Take it further</span>
          <ResearchLink to={VIEW_ROUTES.volume}>
            Across a range of traffic levels
          </ResearchLink>
          <ResearchLink to={VIEW_ROUTES.junction}>
            On a junction you build or import, over matched seeds
          </ResearchLink>
          <ResearchLink to={VIEW_ROUTES.planner}>
            As a planned study of named alternatives
          </ResearchLink>
          <ResearchLink to={VIEW_ROUTES.history}>Saved runs</ResearchLink>
        </div>

        {sessionRuns.length > 0 && (
          <div className="multi-run-scroll">
            <table className="plain-table session-table">
              <caption>Scenarios you have run this session</caption>
              <thead>
                <tr>
                  <th scope="col">Scenario</th>
                  <th scope="col">Strategy</th>
                  <th scope="col">Time lost per driver</th>
                  <th scope="col">Vehicles through</th>
                  <th scope="col">Longest queue</th>
                  <th scope="col">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sessionRuns.flatMap((run) =>
                  run.strategies.map((id, i) => {
                    const v = run.values[id];
                    const current = run.id === currentRunId;
                    return (
                      <tr
                        key={`${run.id}:${id}`}
                        className={current ? "is-current" : undefined}
                      >
                        {i === 0 && (
                          <th scope="rowgroup" rowSpan={run.strategies.length}>
                            {scenarioLabel(run.config)}, {run.config.lanes} lane
                            {run.config.lanes === 1 ? "" : "s"},{" "}
                            {duration(run.config.duration)}
                            {run.complete ? "" : " (partial)"}
                            {current ? " — this run" : ""}
                          </th>
                        )}
                        <td>{strategyName(id)}</td>
                        <td>{v.delay === null ? "—" : seconds(v.delay)}</td>
                        <td>{v.served === null ? "—" : count(v.served)}</td>
                        <td>{v.maxQueue === null ? "—" : count(v.maxQueue)}</td>
                        {i === 0 && (
                          <td rowSpan={run.strategies.length}>
                            <button
                              type="button"
                              className="pb-btn pb-secondary small"
                              onClick={() => {
                                onTryScenario(run.config);
                              }}
                            >
                              Run again
                            </button>
                          </td>
                        )}
                      </tr>
                    );
                  }),
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {snapshot && ready && (
        <details className="results-section specialist">
          <summary>
            <h2>All measurements &amp; method (for specialists)</h2>
          </summary>
          <p>
            Every metric the simulation reports for {strategyList}, with
            definitions, units and the plain difference from the first strategy.
            Nothing is ranked or weighted here.
          </p>
          <dl className="method-list">
            <div>
              <dt>Driver behaviour</dt>
              <dd>Intelligent Driver Model (IDM) car-following</dd>
            </div>
            <div>
              <dt>Arrivals</dt>
              <dd>
                Random (Poisson), {config.arrivalRate.toFixed(2)} veh/s total,
                seed {config.randomSeed}, identical for every strategy
              </dd>
            </div>
            <div>
              <dt>Demand level</dt>
              <dd>
                {Math.round(
                  saturationRatio(config.arrivalRate, config.lanes) * 100,
                )}
                % of the reference capacity for {config.lanes} lane
                {config.lanes === 1 ? "" : "s"} (
                {REFERENCE_CAPACITY_VPH[
                  Math.min(3, Math.max(1, config.lanes)) as LaneCount
                ].toLocaleString()}{" "}
                veh/h, the mean of the signal&apos;s and the roundabout&apos;s
                measured maximum)
              </dd>
            </div>
            <div>
              <dt>Measurement window</dt>
              <dd>
                {warmupSeconds !== null
                  ? `Warm-up of ${warmupSeconds.toFixed(0)} s excluded`
                  : "Warm-up excluded"}
                {elapsedSeconds !== null
                  ? `; ${elapsedSeconds.toFixed(1)} s simulated`
                  : ""}
              </dd>
            </div>
            {ids.includes("fixed_time_signal") && (
              <div>
                <dt>Fixed-time signal</dt>
                <dd>
                  NS / EW green {config.nsGreenDuration ?? config.greenDuration}{" "}
                  / {config.ewGreenDuration ?? config.greenDuration} s; yellow{" "}
                  {config.yellowDuration} s, all-red {config.allRedDuration} s
                </dd>
              </div>
            )}
            {ids.includes("adaptive_signal") && (
              <div>
                <dt>Adaptive signal</dt>
                <dd>
                  Vehicle-actuated: min green{" "}
                  {adaptiveSettings(config).minGreen} s, max green{" "}
                  {adaptiveSettings(config).maxGreen} s, passage time{" "}
                  {adaptiveSettings(config).extensionStep} s over a{" "}
                  {adaptiveSettings(config).detectionDistance} m stop-line zone;
                  yellow {config.yellowDuration} s, all-red{" "}
                  {config.allRedDuration} s
                </dd>
              </div>
            )}
            {roundaboutRun && (
              <div>
                <dt>Roundabout</dt>
                <dd>
                  {(config.scenario
                    ? ringLanes(config.scenario)
                    : Math.min(config.lanes, 2)) === 1
                    ? "Single circulating lane"
                    : "Two circulating lanes (left turns inner, right turns outer; exits taken in turn)"}
                  , critical gap t_c = {config.criticalGap.toFixed(1)} s,
                  follow-up t_f = {config.followUpTime.toFixed(1)} s
                  {ids.includes("metered_entry_roundabout") && (
                    <>
                      ; the metered roundabout signals its entries
                      {config.scenario?.roundabout.entryMetering
                        ? `: ${config.scenario.roundabout.entryMetering.phases
                            .map(
                              (p) =>
                                `${p.entries.join(" and ")} ${String(p.green)} s green`,
                            )
                            .join(", then ")}`
                        : " with the default plan (north–south, then east–west, 20 s greens, 3 s yellow, 2 s all-red)"}
                    </>
                  )}
                </dd>
              </div>
            )}
          </dl>
          <div className="next-actions">
            {onOpenAnalytics && (
              <button
                type="button"
                className="pb-btn pb-secondary"
                onClick={onOpenAnalytics}
              >
                <BarChart3 size={15} aria-hidden="true" />
                Charts &amp; user-weighted scoring
              </button>
            )}
            <button
              type="button"
              className="pb-btn pb-secondary"
              onClick={() => {
                downloadComparisonCsv(
                  runs,
                  config,
                  replayName ?? "live run",
                  elapsedSeconds,
                  warmupSeconds,
                );
              }}
            >
              <Download size={15} aria-hidden="true" />
              Download all metrics (CSV)
            </button>
          </div>
          <MultiRunSections
            columns={runs.map((r) => ({
              key: r.strategy.id,
              heading: (
                <span className="strategy-label" style={colorStyle(r)}>
                  <span className="strategy-dot" aria-hidden="true" />
                  {r.strategy.name}
                </span>
              ),
              ctx: r.ctx,
            }))}
            collapsed={["diagnostic"]}
          />
        </details>
      )}
    </div>
  );
}
