import type { ReactNode } from "react";
import type { DualSnapshot } from "../../types/simulation";
import type { SimulationConfigValues } from "../../types/config";
import {
  DEMAND_LEVELS,
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
  SIDE_NAME,
  SIDE_TITLE,
  SIMILARITY,
  compare,
  count,
  duration,
  explanations,
  fairnessBand,
  hasResults,
  headlineFindings,
  levelOfService,
  metricDef,
  seconds,
  sideSummary,
  trustNotes,
  type SideSummary,
  type Side,
} from "../../metrics/plainLanguage";
import { ComparisonSections } from "../MetricSections";
import { ReliabilityCheck } from "./ReliabilityCheck";
import {
  contextsOf,
  downloadComparisonCsv,
  scenarioLabel,
  type SessionRun,
} from "./comparisonRun";
import type { MetricDef } from "../../metrics/catalog";

const LOW_SAMPLE_NOTE =
  "Fewer than 20 vehicles got through on at least one side, so read the “1 in 20” and per-direction figures as rough.";

// ── Building blocks ────────────────────────────────────────────────────────

interface Row {
  label: string;
  signal: number | null;
  roundabout: number | null;
  format: (v: number) => string;
}

function PairBars({ row }: { row: Row }) {
  const max = Math.max(row.signal ?? 0, row.roundabout ?? 0);
  const width = (v: number | null) =>
    v === null || max <= 0 ? 0 : Math.max(2, (v / max) * 100);
  return (
    <div className="pair-row">
      <div className="pair-label">{row.label}</div>
      {(["signal", "roundabout"] as Side[]).map((side) => {
        const v = row[side];
        return (
          <div className={`pair-bar is-${side}`} key={side}>
            <span className="pair-side">{SIDE_TITLE[side]}</span>
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
  keys,
  extra,
  measuredNote,
}: {
  question: string;
  lead: string | null;
  rows: Row[];
  keys: MetricDef["key"][];
  extra?: ReactNode;
  measuredNote?: ReactNode;
}) {
  return (
    <article className="question-card">
      <h3>{question}</h3>
      {lead && <p className="question-lead">{lead}</p>}
      {rows.map((row) => (
        <PairBars row={row} key={row.label} />
      ))}
      {extra}
      <HowMeasured keys={keys}>{measuredNote}</HowMeasured>
    </article>
  );
}

function leadSentence(
  signal: number | null,
  roundabout: number | null,
  tolerance: { abs: number; rel: number },
  same: string,
  differs: (lower: Side, higher: Side, gap: number) => string,
): string | null {
  const c = compare(signal, roundabout, tolerance);
  if (!c) return null;
  if (c.similar || !c.lower || !c.higher) return same;
  return differs(c.lower, c.higher, c.gap);
}

// ── The report ─────────────────────────────────────────────────────────────

export function ResultsReport({
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
  snapshot: DualSnapshot | null;
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
  onOpenAnalytics: () => void;
  sessionRuns: SessionRun[];
  currentRunId: string | null;
}) {
  const ctx = contextsOf(snapshot);
  const s = sideSummary(ctx.signal);
  const r = sideSummary(ctx.roundabout);
  const ready = snapshot !== null && hasResults(s, r);
  const measured =
    elapsedSeconds !== null && warmupSeconds !== null
      ? Math.max(0, elapsedSeconds - warmupSeconds)
      : null;
  const summaries: Record<Side, SideSummary> = { signal: s, roundabout: r };
  // The backend flags fewer than 20 vehicles through; spread and
  // per-direction readings rest on very few drivers then.
  const lowSample = Boolean(
    ctx.signal.metrics?.travelTimeReliabilityLowSampleSize ||
    ctx.roundabout.metrics?.travelTimeReliabilityLowSampleSize,
  );

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

  const downloadCsv = () => {
    if (!snapshot) return;
    downloadComparisonCsv(
      snapshot,
      config,
      replayName ?? "live run",
      elapsedSeconds,
      warmupSeconds,
    );
  };

  return (
    <div className="guided-page results-page">
      <header className="guided-intro">
        <p className="guided-eyebrow">Step 3 of 3</p>
        <h1>Results for your junction</h1>
        <ul className="scenario-chips" aria-label="Scenario">
          <li>{scenarioLabel(config)}</li>
          <li>
            {config.lanes === 1 ? "1 lane" : `${String(config.lanes)} lanes`}{" "}
            per approach
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
            over and vehicles have got through both junctions.
          </p>
          <button
            type="button"
            className="guided-primary-btn"
            onClick={onWatch}
          >
            ← Back to watching
          </button>
        </section>
      ) : (
        <>
          <section
            className="results-section in-short"
            aria-labelledby="r-short"
          >
            <h2 id="r-short">In short</h2>
            <ul>
              {headlineFindings(s, r).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <p className="results-note">
              UrbanFlow shows the evidence; it does not pick a winner. Which
              result matters most depends on what you care about at this
              junction.
            </p>
          </section>

          <section className="results-section" aria-labelledby="r-matters">
            <h2 id="r-matters">What people using the junction would notice</h2>
            <div className="question-grid">
              <QuestionCard
                question="How much time do drivers lose?"
                lead={leadSentence(
                  s.delay,
                  r.delay,
                  SIMILARITY.delay,
                  "Drivers lost about the same time at both.",
                  (lower, _h, gap) =>
                    `Drivers lost ${seconds(gap)} less per journey at the ${SIDE_NAME[lower]}.`,
                )}
                rows={[
                  {
                    label: "Time lost per driver, on average",
                    signal: s.delay,
                    roundabout: r.delay,
                    format: (v) => seconds(v),
                  },
                  {
                    label: "Time spent nearly stopped, on average",
                    signal: s.queuedTime,
                    roundabout: r.queuedTime,
                    format: (v) => seconds(v, 1),
                  },
                  {
                    label: "1 in 20 drivers lost more than",
                    signal: s.p95Delay,
                    roundabout: r.p95Delay,
                    format: (v) => seconds(v),
                  },
                  {
                    label: "Stops per driver",
                    signal: s.stops,
                    roundabout: r.stops,
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
                  <p className="question-extra">
                    Is that a lot of time lost?{" "}
                    {(["signal", "roundabout"] as Side[]).map((side, i) => {
                      const d = summaries[side].delay;
                      if (d === null) return null;
                      const grade = levelOfService(d, side);
                      return (
                        <span key={side}>
                          {i > 0 ? " · " : ""}
                          {SIDE_TITLE[side]}:{" "}
                          <strong>{LOS_WORDS[grade].toLowerCase()}</strong>{" "}
                          (grade {grade})
                        </span>
                      );
                    })}
                    {lowSample && (
                      <span className="sample-note"> {LOW_SAMPLE_NOTE}</span>
                    )}
                  </p>
                }
                measuredNote={
                  <p>
                    “Time lost” is the extra time a journey took compared with
                    driving through an empty junction at the driver’s own speed.
                    It counts queuing and also any slowing the layout itself
                    forces (for example easing into a roundabout), so it is not
                    the same as “time spent nearly stopped”, which counts only
                    standing time. Grades A–F are the Highway Capacity Manual’s
                    delay bands, used here as an indicative guide: for signals A
                    ≤ {LOS_THRESHOLDS.signal[0]} s, B ≤{" "}
                    {LOS_THRESHOLDS.signal[1]} s, C ≤ {LOS_THRESHOLDS.signal[2]}{" "}
                    s, D ≤ {LOS_THRESHOLDS.signal[3]} s, E ≤{" "}
                    {LOS_THRESHOLDS.signal[4]} s; for roundabouts the stricter A
                    ≤ {LOS_THRESHOLDS.roundabout[0]} s, B ≤{" "}
                    {LOS_THRESHOLDS.roundabout[1]} s, C ≤{" "}
                    {LOS_THRESHOLDS.roundabout[2]} s, D ≤{" "}
                    {LOS_THRESHOLDS.roundabout[3]} s, E ≤{" "}
                    {LOS_THRESHOLDS.roundabout[4]} s, because drivers expect
                    shorter waits where there is no red light. The manual grades
                    longer study periods than a single short run.
                  </p>
                }
              />

              <QuestionCard
                question="How much traffic gets through?"
                lead={leadSentence(
                  s.served,
                  r.served,
                  SIMILARITY.vehicles,
                  "Both got about the same number of vehicles through.",
                  (_l, higher, gap) =>
                    `The ${SIDE_NAME[higher]} got ${count(gap)} more vehicles through from exactly the same arrivals.`,
                )}
                rows={[
                  {
                    label:
                      measured !== null
                        ? `Got through in the ${duration(measured)} measured`
                        : "Got through after the warm-up",
                    signal: s.served,
                    roundabout: r.served,
                    format: count,
                  },
                  {
                    label: "Still waiting or moving when the clock stopped",
                    signal: s.inNetwork,
                    roundabout: r.inNetwork,
                    format: count,
                  },
                ]}
                keys={["throughput", "activeVehicleCount"]}
                measuredNote={
                  <p>
                    Both junctions received the same vehicles, so a difference
                    in vehicles through means one cleared traffic faster. A
                    growing number still in the network means traffic was
                    arriving faster than it could be cleared.
                  </p>
                }
              />

              <QuestionCard
                question="How long do queues get?"
                lead={leadSentence(
                  s.avgQueue,
                  r.avgQueue,
                  SIMILARITY.queue,
                  "Queues were typically about the same length.",
                  (lower) =>
                    `Queues were typically shorter at the ${SIDE_NAME[lower]}.`,
                )}
                rows={[
                  {
                    label: "Typical queue on one approach",
                    signal: s.avgQueue,
                    roundabout: r.avgQueue,
                    format: (v) => `${v.toFixed(1)} vehicles`,
                  },
                  {
                    label: "Longest queue seen",
                    signal: s.maxQueue,
                    roundabout: r.maxQueue,
                    format: (v) => `${count(v)} vehicles`,
                  },
                  {
                    label: "Time with more than 5 vehicles queued",
                    signal: s.congestedSeconds,
                    roundabout: r.congestedSeconds,
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
                lead={leadSentence(
                  s.fairness,
                  r.fairness,
                  SIMILARITY.fairness,
                  "Waiting was shared about as evenly at both.",
                  (_l, higher) =>
                    `Waiting was shared more evenly between directions at the ${SIDE_NAME[higher]}.`,
                )}
                rows={[]}
                keys={["directionalFairnessIndex"]}
                extra={
                  <ul className="fairness-list">
                    {(["signal", "roundabout"] as Side[]).map((side) => {
                      const f = summaries[side].fairness;
                      if (f === null)
                        return (
                          <li key={side}>
                            {SIDE_TITLE[side]}: not enough data yet
                          </li>
                        );
                      const band = fairnessBand(f);
                      return (
                        <li key={side}>
                          <strong>
                            {SIDE_TITLE[side]}: {band.label}
                          </strong>{" "}
                          — {band.meaning} (index {f.toFixed(2)})
                        </li>
                      );
                    })}
                    {lowSample && (
                      <li className="sample-note">{LOW_SAMPLE_NOTE}</li>
                    )}
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

          <section className="results-section" aria-labelledby="r-why">
            <h2 id="r-why">Why did this happen?</h2>
            <div className="why-grid">
              {explanations(s, r, {
                lanes: config.lanes,
                arrivalRate: config.arrivalRate,
                greenNs: config.nsGreenDuration ?? config.greenDuration,
                greenEw: config.ewGreenDuration ?? config.greenDuration,
                cycleSeconds: signalCycleSeconds(config),
                criticalGap: config.criticalGap,
              }).map((e) => (
                <div className="why-item" key={e.title}>
                  <h3>{e.title}</h3>
                  <p>{e.body}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="results-section" aria-labelledby="r-trust">
            <h2 id="r-trust">How reliable is this?</h2>
            <ul className="trust-list">
              {trustNotes({
                seed: config.randomSeed,
                lanes: config.lanes,
                warmupSeconds,
                measuredSeconds: measured,
                complete: complete || replayName !== null,
                collisions: (s.collisions ?? 0) + (r.collisions ?? 0),
                lowReliabilitySample: lowSample,
                vehicleLimitReached: Boolean(
                  ctx.signal.metrics?.vehicleLimitReached ||
                  ctx.roundabout.metrics?.vehicleLimitReached,
                ),
                vehicleLimit: ctx.signal.metrics?.vehicleLimit ?? null,
              }).map((note) => (
                <li key={note.text} className={`trust-${note.tone}`}>
                  {note.text}
                </li>
              ))}
            </ul>
            <ReliabilityCheck config={config} />
          </section>
        </>
      )}

      <section className="results-section" aria-labelledby="r-next">
        <h2 id="r-next">Try another scenario</h2>
        <p>
          Results can change a lot with traffic level and layout. Try the
          alternatives that matter for your decision — each run is added to the
          table below so you can read them side by side.
        </p>
        <div className="next-actions">
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
            Change the junction
          </button>
          <button
            type="button"
            className="pb-btn pb-secondary"
            onClick={onWatch}
          >
            {replayName ? "Watch this scenario" : "Back to the maps"}
          </button>
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
              Save this comparison
            </button>
          )}
        </div>

        {sessionRuns.length > 0 && (
          <div className="multi-run-scroll">
            <table className="plain-table session-table">
              <caption>Scenarios you have run this session</caption>
              <thead>
                <tr>
                  <th scope="col">Scenario</th>
                  <th scope="col">
                    Time lost per driver (signal · roundabout)
                  </th>
                  <th scope="col">Vehicles through</th>
                  <th scope="col">Longest queue</th>
                  <th scope="col">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sessionRuns.map((run) => (
                  <tr
                    key={run.id}
                    className={
                      run.id === currentRunId ? "is-current" : undefined
                    }
                  >
                    <th scope="row">
                      {scenarioLabel(run.config)}, {run.config.lanes} lane
                      {run.config.lanes === 1 ? "" : "s"},{" "}
                      {duration(run.config.duration)}
                      {run.complete ? "" : " (partial)"}
                      {run.id === currentRunId ? " — this run" : ""}
                    </th>
                    <td>{pair(run.delay, (v) => seconds(v))}</td>
                    <td>{pair(run.served, count)}</td>
                    <td>{pair(run.maxQueue, count)}</td>
                    <td>
                      <button
                        type="button"
                        className="guided-link-btn small"
                        onClick={() => {
                          onTryScenario(run.config);
                        }}
                      >
                        Run again
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {snapshot && (
        <details className="results-section specialist">
          <summary>
            <h2>All measurements &amp; method (for specialists)</h2>
          </summary>
          <p>
            Every metric the simulation reports, with definitions, units and the
            plain difference (roundabout − signal). Nothing is ranked or
            weighted here.
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
                seed {config.randomSeed}, identical for both controls
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
                veh/h, the mean of both controls&apos; measured maximum)
              </dd>
            </div>
            <div>
              <dt>Speeds</dt>
              <dd>
                50 km/h limit; drivers want 85–105% of it. Every curved path at
                both junctions is taken at the same lateral-acceleration limit
                (3 m/s²).
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
            <div>
              <dt>Signal plan</dt>
              <dd>
                NS / EW green {config.nsGreenDuration ?? config.greenDuration} /{" "}
                {config.ewGreenDuration ?? config.greenDuration} s, yellow{" "}
                {config.yellowDuration} s, all-red {config.allRedDuration} s
              </dd>
            </div>
            <div>
              <dt>Roundabout</dt>
              <dd>
                Single circulating lane, critical gap t_c ={" "}
                {config.criticalGap.toFixed(1)} s, follow-up t_f ={" "}
                {config.followUpTime.toFixed(1)} s
              </dd>
            </div>
          </dl>
          <div className="next-actions">
            <button
              type="button"
              className="pb-btn pb-secondary"
              onClick={onOpenAnalytics}
            >
              Open charts &amp; user-weighted scoring
            </button>
            <button
              type="button"
              className="pb-btn pb-secondary"
              onClick={downloadCsv}
            >
              Download all metrics (CSV)
            </button>
          </div>
          <ComparisonSections
            signal={ctx.signal}
            roundabout={ctx.roundabout}
            collapsed={["diagnostic"]}
          />
        </details>
      )}
    </div>
  );
}

function pair(
  values: [number | null, number | null],
  format: (v: number) => string,
): string {
  const [a, b] = values;
  return `${a === null ? "—" : format(a)} · ${b === null ? "—" : format(b)}`;
}
