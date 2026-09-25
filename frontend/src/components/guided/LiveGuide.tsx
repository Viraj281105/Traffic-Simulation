import { useState, type ReactNode } from "react";
import type { DualSnapshot, LiveSnapshot } from "../../types/simulation";
import type { ConnectionStatus } from "../../services/websocket";
import { ConnectionBadge } from "../MetricsSidebar";
import { isInWarmup } from "../../metrics/catalog";
import {
  SIDE_TITLE,
  clock,
  hasResults,
  sideSummary,
  type Side,
} from "../../metrics/plainLanguage";

function contextOf(s: LiveSnapshot | undefined, side: Side) {
  return {
    metrics: s?.metrics,
    geometry:
      side === "signal"
        ? ("fixed_time_signal" as const)
        : ("roundabout" as const),
    inWarmup: isInWarmup(s?.timestamp, s?.warmupTime),
  };
}

/** Step 2 of the comparison: what is happening right now, in words, beside
 *  the two maps. The specialist live panel (every chart and metric) is one
 *  toggle away and replaces this view when chosen. */
export function LiveGuide({
  snapshot,
  durationSeconds,
  connectionStatus,
  onSeeResults,
  detailedPanel,
}: {
  snapshot: DualSnapshot | null;
  durationSeconds: number;
  connectionStatus: ConnectionStatus;
  onSeeResults: () => void;
  detailedPanel: ReactNode;
}) {
  const [detailed, setDetailed] = useState(false);

  const sig = snapshot?.signal;
  const rnd = snapshot?.roundabout;
  const elapsed = snapshot?.elapsed ?? 0;
  const warmup = sig?.warmupTime;
  const inWarmup = isInWarmup(sig?.timestamp, warmup);
  const status = sig?.simulationStatus;
  const complete = status === "completed";
  const started = elapsed > 0;
  const s = sideSummary(contextOf(sig, "signal"));
  const r = sideSummary(contextOf(rnd, "roundabout"));
  const ready = hasResults(s, r);
  const progress = Math.min(100, (elapsed / durationSeconds) * 100);

  const toggle = (
    <button
      type="button"
      className="guided-link-btn small"
      aria-pressed={detailed}
      onClick={() => {
        setDetailed((v) => !v);
      }}
    >
      {detailed
        ? "← Back to the simple view"
        : "Show specialist live charts & all metrics"}
    </button>
  );

  if (detailed) {
    return (
      <div className="live-guide-column">
        <div className="live-guide-toggle">{toggle}</div>
        {detailedPanel}
      </div>
    );
  }

  const live = { signal: sig, roundabout: rnd };
  const summary = { signal: s, roundabout: r };
  const rows: { label: string; hint: string; value: (side: Side) => string }[] =
    [
      {
        label: "Vehicles waiting now",
        hint: "Stopped or crawling in a queue at this moment.",
        value: (side) => waitingNow(live[side]),
      },
      {
        label: "Got through so far",
        hint: "Vehicles that made it through after the warm-up.",
        value: (side) => {
          const n = summary[side].served;
          return n === null ? "—" : String(Math.round(n));
        },
      },
      {
        label: "Time lost per driver so far",
        hint: "Average extra travel time compared with an empty junction, including slowing the layout forces. Not the same as waiting.",
        value: (side) => {
          const d = summary[side].delay;
          return d === null ? "—" : `${d.toFixed(0)} s`;
        },
      },
    ];

  return (
    <aside
      className="live-guide metrics-sidebar comparison-side-panel"
      aria-labelledby="live-guide-title"
    >
      <div className="sidebar-header">
        <h2 className="sidebar-title" id="live-guide-title">
          Step 2 · Watch the comparison
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
              ? "Press Play below to start both junctions at once."
              : inWarmup && warmup !== undefined
                ? `Warming up: traffic is building from an empty road. Measuring starts at ${clock(warmup)}.`
                : complete
                  ? "Both runs have finished. Your results are ready."
                  : "Measuring. Both junctions are receiving exactly the same vehicles."}
          </p>
        </div>

        <table className="live-table">
          <thead>
            <tr>
              <th scope="col">
                <span className="sr-only">Measure</span>
              </th>
              <th scope="col" className="is-signal">
                {SIDE_TITLE.signal}
              </th>
              <th scope="col" className="is-roundabout">
                {SIDE_TITLE.roundabout}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label}>
                <th scope="row" title={row.hint}>
                  {row.label}
                </th>
                <td>{row.value("signal")}</td>
                <td>{row.value("roundabout")}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="live-tips">
          <h3>What to look for</h3>
          <ul>
            <li>
              <strong>Signal:</strong> queues grow on the red approaches and
              clear in bursts when the light turns green.
            </li>
            <li>
              <strong>Roundabout:</strong> drivers slow at each entry and wait
              for a gap in the circling traffic; nobody waits for a light.
            </li>
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
        {toggle}
      </div>
    </aside>
  );
}

function waitingNow(s: LiveSnapshot | undefined): string {
  const n = (s as Partial<LiveSnapshot> | undefined)?.vehicleCounts?.waiting;
  return n === undefined ? "—" : String(n);
}
