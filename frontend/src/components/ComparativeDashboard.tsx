import React, { useEffect, useRef, useState } from "react";
import type { DualSnapshot, LiveSnapshot } from "../types/simulation";
import type { ConnectionStatus } from "../services/websocket";
import { WeightedScoringPanel } from "./WeightedScoringPanel";
import type { ScoringWeights } from "../types/scoring";
import { DEFAULT_WEIGHTS } from "../types/scoring";
import {
  comparisonCsv,
  downloadText,
  isInWarmup,
  type MetricContext,
} from "../metrics/catalog";
import { ComparisonSections } from "./MetricSections";
import { ConnectionBadge } from "./MetricsSidebar";
import "./ComparativeDashboard.css";

function contexts(snapshot: DualSnapshot | null): {
  signal: MetricContext;
  roundabout: MetricContext;
} {
  const warm = (s: LiveSnapshot | undefined) =>
    isInWarmup(s?.timestamp, s?.warmupTime);
  return {
    signal: {
      metrics: snapshot?.signal.metrics,
      geometry: "fixed_time_signal",
      inWarmup: warm(snapshot?.signal),
    },
    roundabout: {
      metrics: snapshot?.roundabout.metrics,
      geometry: "roundabout",
      inWarmup: warm(snapshot?.roundabout),
    },
  };
}

/** Simulated time of a snapshot. Saved-run snapshots carry metrics only,
 *  so this can be absent even though live snapshots always have it. */
function simTime(s: LiveSnapshot | undefined): number | undefined {
  return (s as Partial<LiveSnapshot> | undefined)?.timestamp;
}

function exportComparison(snapshot: DualSnapshot, source: string) {
  const { signal, roundabout } = contexts(snapshot);
  const t = simTime(snapshot.signal);
  const header = [
    `Signal vs roundabout — ${source}`,
    t !== undefined
      ? `Simulated time: ${t.toFixed(1)} s (both run in lockstep with the same seed)`
      : "",
    snapshot.signal.warmupTime !== undefined
      ? `Warm-up excluded: ${snapshot.signal.warmupTime.toFixed(0)} s`
      : "",
  ].filter(Boolean);
  downloadText(
    `comparison_${Date.now().toString()}.csv`,
    comparisonCsv(signal, roundabout, header),
    "text/csv;charset=utf-8",
  );
}

/** Live side-by-side metrics beside the two maps. */
export function ComparisonPanel({
  snapshot,
  connectionStatus,
  replayName,
  canSave,
  onSave,
  onOpenDetails,
}: {
  snapshot: DualSnapshot | null;
  connectionStatus: ConnectionStatus;
  replayName: string | null;
  canSave: boolean;
  onSave: () => void;
  onOpenDetails: () => void;
}) {
  const { signal, roundabout } = contexts(snapshot);
  const sig = snapshot?.signal;
  const rnd = snapshot?.roundabout;
  const warmupLeft =
    sig?.warmupTime !== undefined && signal.inWarmup
      ? Math.max(0, sig.warmupTime - sig.timestamp)
      : null;

  return (
    <aside
      className="comparison-side-panel metrics-sidebar"
      aria-labelledby="comparison-panel-title"
    >
      <div className="sidebar-header">
        <h2 className="sidebar-title" id="comparison-panel-title">
          {replayName ? "Saved comparison" : "Live comparison"}
        </h2>
        {!replayName && <ConnectionBadge status={connectionStatus} />}
      </div>
      {replayName && <p className="replay-note">{replayName}</p>}
      {warmupLeft !== null && sig?.warmupTime !== undefined && (
        <p className="warmup-notice" role="status">
          Warm-up: most metrics start at {sig.warmupTime.toFixed(0)} s of
          simulated time ({warmupLeft.toFixed(0)} s to go).
        </p>
      )}

      {sig?.vehicleCounts !== undefined && rnd?.vehicleCounts !== undefined && (
        <section className="sidebar-section" aria-label="Vehicles now">
          <h3 className="section-title">Vehicles now</h3>
          <table className="comparison-grid counts">
            <thead>
              <tr>
                <th scope="col">State</th>
                <th scope="col">Signal</th>
                <th scope="col">Roundabout</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">In network</th>
                <td>{sig.vehicleCounts.active}</td>
                <td>{rnd.vehicleCounts.active}</td>
              </tr>
              <tr>
                <th scope="row">Waiting</th>
                <td>{sig.vehicleCounts.waiting}</td>
                <td>{rnd.vehicleCounts.waiting}</td>
              </tr>
              <tr>
                <th scope="row">In junction</th>
                <td>{sig.vehicleCounts.crossing}</td>
                <td>
                  {rnd.vehicleCounts.crossing + rnd.vehicleCounts.inRoundabout}
                </td>
              </tr>
              <tr>
                <th scope="row">Exited (whole run)</th>
                <td>{sig.vehicleCounts.exited}</td>
                <td>{rnd.vehicleCounts.exited}</td>
              </tr>
            </tbody>
          </table>
        </section>
      )}

      {snapshot ? (
        <ComparisonSections
          signal={signal}
          roundabout={roundabout}
          compact
          collapsed={["flow", "capacity", "diagnostic"]}
        />
      ) : (
        <p className="sidebar-empty">
          Metrics appear once the comparison stream connects. Press Play to run
          both controls on the same seed and demand.
        </p>
      )}

      <div className="sidebar-actions stacked">
        <button
          type="button"
          className="pb-btn pb-secondary"
          onClick={onOpenDetails}
          disabled={!snapshot}
        >
          Full comparison &amp; weighting
        </button>
        {snapshot && (
          <button
            type="button"
            className="pb-btn pb-secondary"
            onClick={() => {
              exportComparison(snapshot, replayName ?? "live run");
            }}
          >
            Download all metrics (CSV)
          </button>
        )}
        {!replayName && (
          <button
            type="button"
            className="pb-btn pb-primary"
            onClick={onSave}
            disabled={!canSave}
            title={
              canSave
                ? "Save this comparison to History"
                : "Pause or finish the run (after it has started) to save it"
            }
          >
            Save to History
          </button>
        )}
      </div>
    </aside>
  );
}

interface ComparativeDashboardProps {
  snapshot: DualSnapshot | null;
  replayName: string | null;
  onClose: () => void;
}

/** Full comparison dialog: every metric, distributions expanded, and the
 *  user-weighted score. */
export const ComparativeDashboard: React.FC<ComparativeDashboardProps> = ({
  snapshot,
  replayName,
  onClose,
}) => {
  const [weights, setWeights] = useState<ScoringWeights>(DEFAULT_WEIGHTS);
  const dialogRef = useRef<HTMLDivElement>(null);

  // Escape closes; focus moves into the dialog and back out on close. onClose
  // is read through a ref so live snapshot re-renders don't re-run this.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCloseRef.current();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      previous?.focus();
    };
  }, []);

  const { signal, roundabout } = contexts(snapshot);

  return (
    <div className="analytics-modal-overlay" onClick={onClose}>
      <div
        ref={dialogRef}
        className="analytics-modal-content comparative-dashboard"
        role="dialog"
        aria-modal="true"
        aria-labelledby="comparison-dialog-title"
        tabIndex={-1}
        onClick={(e) => {
          e.stopPropagation();
        }}
      >
        <div className="modal-header">
          <h2 className="modal-title" id="comparison-dialog-title">
            Signal vs roundabout — full comparison
          </h2>
          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close comparison"
          >
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div className="modal-body">
          {!snapshot ? (
            <p className="comparison-empty">
              No comparison data yet. Start a comparative run first.
            </p>
          ) : (
            <>
              <div className="comparison-intro">
                <p>
                  Both controls run in lockstep on the same random seed and
                  demand
                  {replayName ? ` (saved run: ${replayName})` : ""}
                  {simTime(snapshot.signal) !== undefined
                    ? `, here at ${String(simTime(snapshot.signal)?.toFixed(1))} s of simulated time`
                    : ""}
                  . Differences are roundabout minus signal in each metric's own
                  units; a single seed is one sample, so use the Validation page
                  for statistical comparisons.
                </p>
                <button
                  type="button"
                  className="pb-btn pb-secondary"
                  onClick={() => {
                    exportComparison(snapshot, replayName ?? "live run");
                  }}
                >
                  Download all metrics (CSV)
                </button>
              </div>
              <ComparisonSections
                signal={signal}
                roundabout={roundabout}
                collapsed={[]}
              />
              <WeightedScoringPanel
                metricsSignal={snapshot.signal.metrics}
                metricsRoundabout={snapshot.roundabout.metrics}
                weights={weights}
                onWeightsChange={setWeights}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
};
