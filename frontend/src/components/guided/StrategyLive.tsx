import type { CSSProperties } from "react";
import { ArrowLeft, Maximize2 } from "lucide-react";
import { IntersectionMap } from "../IntersectionMap";
import { RoundaboutMap } from "../RoundaboutMap";
import { AdaptiveSignalStatus } from "../AdaptiveSignalStatus";
import { MeteredRoundaboutStatus } from "../MeteredRoundaboutStatus";
import { VehicleLegend } from "../VehicleLegend";
import { ConnectionBadge, MetricsSidebar } from "../MetricsSidebar";
import type { ComparisonSnapshot, LiveSnapshot } from "../../types/simulation";
import type { ConnectionStatus } from "../../services/websocket";
import { isInWarmup } from "../../metrics/catalog";
import { clock } from "../../metrics/plainLanguage";
import {
  strategyInfo,
  type StrategyInfo,
} from "../../strategies/strategyCatalog";
import {
  hasComparisonResults,
  strategyRuns,
  type StrategyRun,
} from "./comparisonRun";
import "../../strategies/Strategies.css";

const colorStyle = (s: StrategyInfo) =>
  ({ "--strategy-color": s.color }) as CSSProperties;

/** The strategies on screen: the stream's runs once it has sent one, else
 *  the chosen strategies with empty maps. */
function shownRuns(
  snapshot: ComparisonSnapshot | null,
  strategies: string[],
): StrategyRun[] {
  const streamed = strategyRuns(snapshot);
  const sameChoice =
    streamed.length === strategies.length &&
    streamed.every((r, i) => r.strategy.id === strategies[i]);
  if (sameChoice || strategies.length === 0) return streamed;
  return strategies.map((id, i) => {
    const strategy = strategyInfo(id, undefined, i);
    return {
      strategy,
      snapshot: undefined,
      ctx: {
        metrics: undefined,
        geometry:
          strategy.family === "roundabout" ? "roundabout" : "fixed_time_signal",
        inWarmup: false,
      },
      summary: {
        delay: null,
        queuedTime: null,
        p95Delay: null,
        stops: null,
        served: null,
        inNetwork: null,
        avgQueue: null,
        maxQueue: null,
        congestedSeconds: null,
        fairness: null,
        collisions: null,
        idleGreenPct: null,
      },
    };
  });
}

/** Step 2: every chosen strategy's live map, laid out for how many there
 *  are (one wide, two or three side by side, four as a grid). */
export function StrategyMaps({
  snapshot,
  strategies,
  armLanes,
  lanes,
  laneWidth,
  showStopLines,
  debug,
  inspected,
  onInspect,
}: {
  snapshot: ComparisonSnapshot | null;
  strategies: string[];
  armLanes: { north: number; south: number; east: number; west: number };
  lanes: number;
  laneWidth: number;
  showStopLines: boolean;
  debug: boolean;
  inspected: string | null;
  onInspect: (id: string | null) => void;
}) {
  const runs = shownRuns(snapshot, strategies);
  const count = runs.length > 4 ? "many" : String(runs.length);
  return (
    <div className="strategy-maps" data-count={count}>
      {runs.map((run, i) => {
        const s = run.strategy;
        const live = run.snapshot as LiveSnapshot | undefined;
        const titleId = `map-${s.id}-title`;
        const focused = inspected === s.id;
        return (
          <section
            key={s.id}
            className={`strategy-map${focused ? " is-focused" : ""}`}
            style={colorStyle(s)}
            aria-labelledby={titleId}
          >
            <div className="strategy-map__head">
              <h2 className="strategy-map__title" id={titleId}>
                <span className="strategy-dot" aria-hidden="true" />
                {s.name}
              </h2>
              <button
                type="button"
                className="strategy-map__inspect"
                aria-pressed={focused}
                onClick={() => {
                  onInspect(focused ? null : s.id);
                }}
                title={`All live metrics for the ${s.name.toLowerCase()}`}
              >
                <Maximize2 size={12} aria-hidden="true" /> Inspect
              </button>
            </div>
            <div className="canvas-wrapper">
              {s.family === "roundabout" ? (
                <RoundaboutMap
                  snapshot={live ?? null}
                  laneWidth={laneWidth}
                  lanes={lanes}
                  showCrosswalks={false}
                  debug={debug}
                />
              ) : (
                <IntersectionMap
                  snapshot={live ?? null}
                  lanesNorth={armLanes.north}
                  lanesSouth={armLanes.south}
                  lanesEast={armLanes.east}
                  lanesWest={armLanes.west}
                  laneWidth={laneWidth}
                  showCrosswalks={true}
                  showStopLines={showStopLines}
                  debug={debug}
                />
              )}
              {/* One legend is enough: every map draws vehicles alike. */}
              {i === 0 && <VehicleLegend snapshot={live} />}
              {s.family === "roundabout" ? (
                <MeteredRoundaboutStatus snapshot={live} />
              ) : (
                <AdaptiveSignalStatus snapshot={live} />
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
}

/** What each strategy's map shows while it runs. */
const WATCH_FOR: Record<StrategyInfo["glyph"], string> = {
  fixed:
    "queues grow on the red approaches and clear in bursts when the light turns green.",
  adaptive:
    "it responds to traffic. A green stretches while vehicles keep arriving and ends early once the road empties and someone waits on red; the panel on its map says what it is doing and why.",
  roundabout:
    "drivers slow at each entry and wait for a gap in the circling traffic; nobody waits for a light.",
  metered:
    "drivers wait at each entry for a gap in the circling traffic, and also for a green on the entry signals; a green never forces a driver in.",
  signal: "watch how the signal shares green between the approaches.",
};

function waitingNow(s: Partial<LiveSnapshot> | undefined): string {
  const n = s?.vehicleCounts?.waiting;
  return n === undefined ? "—" : String(n);
}

/** Step 2's side panel: progress, the same three live measures for every
 *  strategy, and what to look for. "Inspect" on a map swaps this for that
 *  strategy's full live panel, keeping the maps and the comparison. */
export function LiveComparison({
  snapshot,
  strategies,
  durationSeconds,
  connectionStatus,
  onSeeResults,
  inspected,
  onInspect,
  isRunning,
}: {
  snapshot: ComparisonSnapshot | null;
  strategies: string[];
  durationSeconds: number;
  connectionStatus: ConnectionStatus;
  onSeeResults: () => void;
  inspected: string | null;
  onInspect: (id: string | null) => void;
  isRunning: boolean;
}) {
  const runs = shownRuns(snapshot, strategies);
  const lead = runs[0]?.snapshot;
  const elapsed = snapshot?.elapsed ?? 0;
  const warmup = lead?.warmupTime;
  const inWarmup = isInWarmup(lead?.timestamp, warmup);
  const status = lead?.simulationStatus;
  const complete = status === "completed";
  const started = elapsed > 0;
  const ready = hasComparisonResults(runs);
  const progress = Math.min(100, (elapsed / durationSeconds) * 100);
  const focus = runs.find((r) => r.strategy.id === inspected);

  if (focus) {
    return (
      <div className="live-guide-column" style={colorStyle(focus.strategy)}>
        <div className="live-guide-toggle">
          <button
            type="button"
            className="pb-btn pb-secondary small"
            onClick={() => {
              onInspect(null);
            }}
          >
            <ArrowLeft size={14} aria-hidden="true" />
            Back to the comparison
          </button>
          <span className="strategy-label">
            <span className="strategy-dot" aria-hidden="true" />
            {focus.strategy.name}
          </span>
        </div>
        <MetricsSidebar
          snapshot={(focus.snapshot as LiveSnapshot | undefined) ?? null}
          connectionStatus={connectionStatus}
          geometry={focus.ctx.geometry}
          isRunning={isRunning}
        />
      </div>
    );
  }

  const rows: {
    label: string;
    hint: string;
    value: (run: StrategyRun) => string;
  }[] = [
    {
      label: "Waiting now",
      hint: "Stopped or crawling in a queue at this moment.",
      value: (run) => waitingNow(run.snapshot),
    },
    {
      label: "Through",
      hint: "Vehicles that got through so far, after the warm-up.",
      value: (run) =>
        run.summary.served === null
          ? "—"
          : String(Math.round(run.summary.served)),
    },
    {
      label: "Lost per driver",
      hint: "Time lost per driver so far: average extra travel time compared with an empty junction, including slowing the layout forces. Not the same as waiting.",
      value: (run) =>
        run.summary.delay === null ? "—" : `${run.summary.delay.toFixed(0)} s`,
    },
  ];
  const n = runs.length;

  return (
    <aside
      className="live-guide metrics-sidebar comparison-side-panel"
      aria-labelledby="live-guide-title"
    >
      <div className="sidebar-header">
        <h2 className="sidebar-title" id="live-guide-title">
          Step 2 · Watch{" "}
          {n === 1 ? "it run" : n === 2 ? "both run" : `all ${String(n)} run`}
        </h2>
        <ConnectionBadge status={connectionStatus} />
      </div>

      <div className="live-guide-body">
        <div className="live-progress">
          <div className="live-progress-label">
            <span>
              {complete
                ? "Finished"
                : started
                  ? status === "paused"
                    ? "Paused"
                    : "Running"
                  : "Ready"}
            </span>
            <span className="mono">
              {clock(elapsed)} of {clock(durationSeconds)}
            </span>
          </div>
          <div
            className="live-progress-track"
            role="progressbar"
            aria-label="Simulated time"
            aria-valuemin={0}
            aria-valuemax={durationSeconds}
            aria-valuenow={Math.round(elapsed)}
          >
            <div
              className="live-progress-fill"
              style={{ width: `${String(progress)}%` }}
            />
            {warmup !== undefined && (
              <div
                className="live-progress-warmup"
                style={{
                  width: `${String(Math.min(100, (warmup / durationSeconds) * 100))}%`,
                }}
                title="Warm-up (not counted)"
              />
            )}
          </div>
          <p className="live-status-text" aria-live="polite">
            {!started
              ? `Press Play below to start ${n === 1 ? "the run" : `all ${String(n)} at once`}.`
              : inWarmup && warmup !== undefined
                ? `Warming up: traffic is building from an empty road. Measuring starts at ${clock(warmup)}.`
                : complete
                  ? "The run has finished. Your results are ready."
                  : n === 1
                    ? "Measuring."
                    : "Measuring. Every strategy is receiving exactly the same vehicles."}
          </p>
        </div>

        <div className="multi-run-scroll">
          <table className="live-table strategy-live-table">
            <thead>
              <tr>
                <th scope="col">
                  <span className="sr-only">Strategy</span>
                </th>
                {rows.map((row) => (
                  <th scope="col" key={row.label} title={row.hint}>
                    {row.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.strategy.id} style={colorStyle(run.strategy)}>
                  <th scope="row">
                    <span className="strategy-label">
                      <span className="strategy-dot" aria-hidden="true" />
                      {run.strategy.name}
                    </span>
                  </th>
                  {rows.map((row) => (
                    <td key={row.label}>{row.value(run)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="live-tips">
          <h3>What to look for</h3>
          <ul>
            {runs.map((run) => (
              <li key={run.strategy.id}>
                <strong>{run.strategy.name}:</strong>{" "}
                {WATCH_FOR[run.strategy.glyph]}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="sidebar-actions stacked">
        <button
          type="button"
          className={complete ? "guided-primary-btn" : "pb-btn pb-secondary"}
          onClick={onSeeResults}
          disabled={!ready}
          title={
            ready
              ? undefined
              : "Available once the warm-up is over and vehicles have got through"
          }
        >
          {complete ? "See your results →" : "See results so far →"}
        </button>
      </div>
    </aside>
  );
}
