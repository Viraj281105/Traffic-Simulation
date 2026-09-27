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
import { useLiveComparisonHistory } from "../hooks/useLiveComparisonHistory";
import { VehiclesFlowVisualizer } from "./analytics/VehiclesFlowVisualizer";
import { PerformanceCharts } from "./analytics/PerformanceCharts";
import { TrafficFlowVisualizer } from "./analytics/TrafficFlowVisualizer";
import { SafetyTimelineVisualizer } from "./analytics/SafetyTimelineVisualizer";
import { CapacityDemandVisualizer } from "./analytics/CapacityDemandVisualizer";
import { DistributionDiagnosticsVisualizer } from "./analytics/DistributionDiagnosticsVisualizer";
import "./ComparativeDashboard.css";
import { CloseButton } from "./ui/CloseButton";

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

type PanelCategory =
  "overview" | "performance" | "flow" | "safety" | "capacity" | "table";

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

  const [activeCategory, setActiveCategory] =
    useState<PanelCategory>("overview");
  const { history, collisionEvents } = useLiveComparisonHistory(snapshot);

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
        <div className="warmup-notice" role="status">
          <span className="warmup-dot-pulse" aria-hidden="true" />
          <span>
            Warm-up: metrics accumulate after {sig.warmupTime.toFixed(0)} s of
            simulated time ({warmupLeft.toFixed(0)} s to go).
          </span>
        </div>
      )}

      {/* Scannable Category Selector Pills */}
      <nav className="panel-category-tabs" aria-label="Comparison categories">
        <button
          type="button"
          className={`cat-pill ${activeCategory === "overview" ? "active" : ""}`}
          onClick={() => {
            setActiveCategory("overview");
          }}
        >
          Flow
        </button>
        <button
          type="button"
          className={`cat-pill ${activeCategory === "performance" ? "active" : ""}`}
          onClick={() => {
            setActiveCategory("performance");
          }}
        >
          Performance
        </button>
        <button
          type="button"
          className={`cat-pill ${activeCategory === "flow" ? "active" : ""}`}
          onClick={() => {
            setActiveCategory("flow");
          }}
        >
          Queues
        </button>
        <button
          type="button"
          className={`cat-pill ${activeCategory === "safety" ? "active" : ""}`}
          onClick={() => {
            setActiveCategory("safety");
          }}
        >
          Safety
        </button>
        <button
          type="button"
          className={`cat-pill ${activeCategory === "capacity" ? "active" : ""}`}
          onClick={() => {
            setActiveCategory("capacity");
          }}
        >
          Capacity
        </button>
        <button
          type="button"
          className={`cat-pill ${activeCategory === "table" ? "active" : ""}`}
          onClick={() => {
            setActiveCategory("table");
          }}
        >
          Table
        </button>
      </nav>

      {/* Main Panel Content Area */}
      <div className="panel-content-scroll">
        {!snapshot ? (
          <p className="sidebar-empty">
            Metrics appear once the comparison stream connects. Press Play to
            run both controls on the same seed and demand.
          </p>
        ) : (
          <>
            {activeCategory === "overview" && (
              <section className="sidebar-section" aria-label="Vehicles now">
                <div className="section-header-compact">
                  <h3 className="section-title">Vehicles Now &amp; Pipeline</h3>
                  <span className="live-pill-tag">Live</span>
                </div>
                <VehiclesFlowVisualizer
                  signal={sig}
                  roundabout={rnd}
                  compact={true}
                />
                <div className="section-divider" />
                <PerformanceCharts
                  history={history}
                  signalCtx={signal}
                  roundaboutCtx={roundabout}
                  compact={true}
                />
              </section>
            )}

            {activeCategory === "performance" && (
              <section
                className="sidebar-section"
                aria-label="Performance trends"
              >
                <PerformanceCharts
                  history={history}
                  signalCtx={signal}
                  roundaboutCtx={roundabout}
                  compact={true}
                />
              </section>
            )}

            {activeCategory === "flow" && (
              <section
                className="sidebar-section"
                aria-label="Traffic flow and queues"
              >
                <TrafficFlowVisualizer
                  signalCtx={signal}
                  roundaboutCtx={roundabout}
                  compact={true}
                />
              </section>
            )}

            {activeCategory === "safety" && (
              <section
                className="sidebar-section"
                aria-label="Safety analytics"
              >
                <SafetyTimelineVisualizer
                  history={history}
                  collisionEvents={collisionEvents}
                  signalCtx={signal}
                  roundaboutCtx={roundabout}
                  compact={true}
                />
              </section>
            )}

            {activeCategory === "capacity" && (
              <section
                className="sidebar-section"
                aria-label="Capacity and demand"
              >
                <CapacityDemandVisualizer
                  signalCtx={signal}
                  roundaboutCtx={roundabout}
                  compact={true}
                />
                <div className="section-divider" />
                <DistributionDiagnosticsVisualizer
                  signalCtx={signal}
                  roundaboutCtx={roundabout}
                  compact={true}
                />
              </section>
            )}

            {activeCategory === "table" && (
              <ComparisonSections
                signal={signal}
                roundabout={roundabout}
                compact
                collapsed={["flow", "capacity", "diagnostic"]}
              />
            )}
          </>
        )}
      </div>

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

/** Full comparison dialog: every metric, rich charts, distributions expanded, and the
 *  user-weighted score. */
export const ComparativeDashboard: React.FC<ComparativeDashboardProps> = ({
  snapshot,
  replayName,
  onClose,
}) => {
  const [weights, setWeights] = useState<ScoringWeights>(DEFAULT_WEIGHTS);
  const [viewMode, setViewMode] = useState<"visual" | "table">("visual");
  const dialogRef = useRef<HTMLDivElement>(null);

  const { history, collisionEvents } = useLiveComparisonHistory(snapshot);

  // Escape closes; focus moves into the dialog and back out on close.
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
          <div className="modal-header-left">
            <h2 className="modal-title" id="comparison-dialog-title">
              Signal vs roundabout — full comparison
            </h2>
            <div
              className="modal-view-toggle"
              role="group"
              aria-label="Dashboard view"
            >
              <button
                type="button"
                className={`toggle-tab-btn ${viewMode === "visual" ? "active" : ""}`}
                onClick={() => {
                  setViewMode("visual");
                }}
              >
                📊 Visual Analytics
              </button>
              <button
                type="button"
                className={`toggle-tab-btn ${viewMode === "table" ? "active" : ""}`}
                onClick={() => {
                  setViewMode("table");
                }}
              >
                📋 Data Table
              </button>
            </div>
          </div>

          <CloseButton label="Close comparison" onClick={onClose} />
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
                  . Differences are roundabout minus signal in each
                  metric&apos;s own units; a single seed is one sample, so use
                  the Validation page for statistical comparisons.
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

              {viewMode === "visual" ? (
                <div className="modal-visual-sections">
                  {/* Section 1: Vehicles Now */}
                  <div className="modal-section-card">
                    <h3 className="modal-section-title">
                      Vehicles Now &amp; Pipeline Flow
                    </h3>
                    <VehiclesFlowVisualizer
                      signal={snapshot.signal}
                      roundabout={snapshot.roundabout}
                      compact={false}
                    />
                  </div>

                  {/* Section 2: Performance Dynamics */}
                  <div className="modal-section-card">
                    <h3 className="modal-section-title">
                      Performance &amp; Service Dynamics
                    </h3>
                    <PerformanceCharts
                      history={history}
                      signalCtx={signal}
                      roundaboutCtx={roundabout}
                      compact={false}
                    />
                  </div>

                  {/* Section 3: Traffic Flow & Queues */}
                  <div className="modal-section-card">
                    <h3 className="modal-section-title">
                      Traffic Flow, Queues &amp; Approach Fairness
                    </h3>
                    <TrafficFlowVisualizer
                      signalCtx={signal}
                      roundaboutCtx={roundabout}
                      compact={false}
                    />
                  </div>

                  {/* Section 4: Safety & Surrogate Measures */}
                  <div className="modal-section-card">
                    <h3 className="modal-section-title">
                      Safety &amp; Surrogate Conflict Measures
                    </h3>
                    <SafetyTimelineVisualizer
                      history={history}
                      collisionEvents={collisionEvents}
                      signalCtx={signal}
                      roundaboutCtx={roundabout}
                      compact={false}
                    />
                  </div>

                  {/* Section 5: Capacity & Demand */}
                  <div className="modal-section-card">
                    <h3 className="modal-section-title">
                      Capacity, Service Utilization &amp; Demand Balance
                    </h3>
                    <CapacityDemandVisualizer
                      signalCtx={signal}
                      roundaboutCtx={roundabout}
                      compact={false}
                    />
                  </div>

                  {/* Section 6: Diagnostics */}
                  <div className="modal-section-card">
                    <h3 className="modal-section-title">
                      Distribution Spread &amp; Diagnostics
                    </h3>
                    <DistributionDiagnosticsVisualizer
                      signalCtx={signal}
                      roundaboutCtx={roundabout}
                      compact={false}
                    />
                  </div>

                  {/* Section 7: User-Weighted Scoring Panel */}
                  <div className="modal-section-card">
                    <h3 className="modal-section-title">
                      Multi-Criteria Evaluation (User-Configured Weights)
                    </h3>
                    <WeightedScoringPanel
                      metricsSignal={snapshot.signal.metrics}
                      metricsRoundabout={snapshot.roundabout.metrics}
                      signalCtx={signal}
                      roundaboutCtx={roundabout}
                      weights={weights}
                      onWeightsChange={setWeights}
                    />
                  </div>
                </div>
              ) : (
                <>
                  <ComparisonSections
                    signal={signal}
                    roundabout={roundabout}
                    collapsed={[]}
                  />
                  <WeightedScoringPanel
                    metricsSignal={snapshot.signal.metrics}
                    metricsRoundabout={snapshot.roundabout.metrics}
                    signalCtx={signal}
                    roundaboutCtx={roundabout}
                    weights={weights}
                    onWeightsChange={setWeights}
                  />
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
