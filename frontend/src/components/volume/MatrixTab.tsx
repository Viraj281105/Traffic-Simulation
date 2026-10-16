import { Scale } from "lucide-react";
import { TierMetrics } from "../TierMetrics";
import {
  maxTierDelay,
  tieText,
  type SweepRun,
  type SweepSession,
  type TierTally,
} from "../volumeSweepModel";
import { getLevelOfService } from "./levelOfService";

export type WinnerFilter = "all" | "roundabout" | "signal" | "tie";

interface MatrixTabProps {
  session: SweepSession;
  runs: SweepRun[];
  tally: TierTally;
  filterWinner: WinnerFilter;
  onFilterWinnerChange: (filter: WinnerFilter) => void;
}

/** Studio tab 2: every tier side by side, with delay bars, grades and the
 *  lower-delay control, filterable by that control. */
export function MatrixTab({
  session,
  runs,
  tally,
  filterWinner,
  onFilterWinnerChange,
}: MatrixTabProps) {
  const filteredRuns =
    filterWinner === "all"
      ? runs
      : runs.filter((r) => r.winner === filterWinner);
  const maxDelay = maxTierDelay(runs);

  return (
    <div className="sweep-summary-table-wrapper">
      <div className="table-header-controls">
        <div>
          <h4>Volume Sweep Results: {session.name}</h4>
          <p className="table-subtitle">
            Comparative telemetry data with side-by-side delay bars & HCM Level
            of Service
          </p>
        </div>
        <div className="table-filter-group">
          <span className="filter-label">Filter:</span>
          <button
            type="button"
            className={`table-filter-btn ${filterWinner === "all" ? "active" : ""}`}
            onClick={() => {
              onFilterWinnerChange("all");
            }}
          >
            All ({runs.length.toString()})
          </button>
          <button
            type="button"
            className={`table-filter-btn ${filterWinner === "roundabout" ? "active" : ""}`}
            onClick={() => {
              onFilterWinnerChange("roundabout");
            }}
          >
            <span className="series-dot is-roundabout" aria-hidden="true" />{" "}
            Roundabout ({tally.roundabout.toString()})
          </button>
          <button
            type="button"
            className={`table-filter-btn ${filterWinner === "signal" ? "active" : ""}`}
            onClick={() => {
              onFilterWinnerChange("signal");
            }}
          >
            <span className="series-dot is-signal" aria-hidden="true" /> Signal
            ({tally.signal.toString()})
          </button>
          <button
            type="button"
            className={`table-filter-btn ${filterWinner === "tie" ? "active" : ""}`}
            onClick={() => {
              onFilterWinnerChange("tie");
            }}
          >
            <Scale size={14} aria-hidden="true" className="uf-glyph" /> About
            the same ({tally.tie.toString()})
          </button>
        </div>
      </div>

      <div className="volume-table-scroll-container">
        <table className="modern-telemetry-table">
          <thead>
            <tr>
              <th>Demand Tier</th>
              <th>Delay Comparison Bar</th>
              <th>Signal Delay & LOS</th>
              <th>Roundabout Delay & LOS</th>
              <th>Throughput</th>
              <th>Queues</th>
              <th
                title={`Lower mean delay at this tier (one random pattern); tie when within ${tieText(session.tieTolerance)}; inconclusive when a side served fewer than 20 vehicles or the vehicle limit cut demand off`}
              >
                Lower mean delay
              </th>
              <th>Δ Delay</th>
            </tr>
          </thead>
          <tbody>
            {filteredRuns.map((run) => {
              const sigLOS = getLevelOfService(run.signal.delay, "signal");
              const rndLOS = getLevelOfService(
                run.roundabout.delay,
                "roundabout",
              );
              const sigPct = Math.min(
                100,
                Math.round((run.signal.delay / maxDelay) * 100),
              );
              const rndPct = Math.min(
                100,
                Math.round((run.roundabout.delay / maxDelay) * 100),
              );

              return (
                <tr key={run.arrivalRate}>
                  <td>
                    <div className="table-tier-col">
                      <strong>
                        {run.hourlyVolumeVehPerHour.toLocaleString()} veh/h
                      </strong>
                      <span className="table-tier-rate">
                        {run.arrivalRate.toFixed(2)} veh/s
                      </span>
                    </div>
                  </td>

                  {/* Visual Micro Delay Bar */}
                  <td className="delay-bar-cell">
                    <div className="dual-delay-bars">
                      <div className="bar-row">
                        <span className="bar-label">Sig</span>
                        <div className="bar-track">
                          <div
                            className="bar-fill sig-fill"
                            style={{ width: `${sigPct.toString()}%` }}
                          />
                        </div>
                      </div>
                      <div className="bar-row">
                        <span className="bar-label">Rnd</span>
                        <div className="bar-track">
                          <div
                            className="bar-fill rnd-fill"
                            style={{ width: `${rndPct.toString()}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Signal Delay */}
                  <td>
                    <div className="delay-los-cell">
                      <span className="delay-val">
                        {run.signal.delay.toFixed(2)}s
                      </span>
                      <span
                        className="los-chip mini"
                        style={{
                          color: sigLOS.color,
                          background: sigLOS.bg,
                        }}
                      >
                        LOS {sigLOS.grade}
                      </span>
                    </div>
                    {run.signal.delayStdDev !== undefined && (
                      <div
                        style={{
                          fontSize: "11px",
                          color: "hsl(var(--muted-foreground))",
                          marginTop: "2px",
                        }}
                      >
                        ±{run.signal.delayStdDev.toFixed(1)}s [
                        {run.signal.delayMin?.toFixed(1)}–
                        {run.signal.delayMax?.toFixed(1)}s]
                      </div>
                    )}
                  </td>

                  {/* Roundabout Delay */}
                  <td>
                    <div className="delay-los-cell">
                      <span className="delay-val">
                        {run.roundabout.delay.toFixed(2)}s
                      </span>
                      <span
                        className="los-chip mini"
                        style={{
                          color: rndLOS.color,
                          background: rndLOS.bg,
                        }}
                      >
                        LOS {rndLOS.grade}
                      </span>
                    </div>
                    {run.roundabout.delayStdDev !== undefined && (
                      <div
                        style={{
                          fontSize: "11px",
                          color: "hsl(var(--muted-foreground))",
                          marginTop: "2px",
                        }}
                      >
                        ±{run.roundabout.delayStdDev.toFixed(1)}s [
                        {run.roundabout.delayMin?.toFixed(1)}–
                        {run.roundabout.delayMax?.toFixed(1)}s]
                      </div>
                    )}
                  </td>

                  {/* Throughput */}
                  <td>
                    <div className="table-multi-col">
                      <span>
                        <span
                          className="series-dot is-signal"
                          aria-hidden="true"
                        />{" "}
                        {run.signal.throughput}
                      </span>
                      <span>
                        <span
                          className="series-dot is-roundabout"
                          aria-hidden="true"
                        />{" "}
                        {run.roundabout.throughput}
                      </span>
                    </div>
                  </td>

                  {/* Queues */}
                  <td>
                    <div className="table-multi-col">
                      <span>
                        <span
                          className="series-dot is-signal"
                          aria-hidden="true"
                        />{" "}
                        {run.signal.queue.toFixed(1)}
                        {run.signal.queueMax !== undefined && (
                          <span className="queue-peak-note">
                            (pk {run.signal.queueMax.toFixed(0)})
                          </span>
                        )}
                      </span>
                      <span>
                        <span
                          className="series-dot is-roundabout"
                          aria-hidden="true"
                        />{" "}
                        {run.roundabout.queue.toFixed(1)}
                        {run.roundabout.queueMax !== undefined && (
                          <span className="queue-peak-note">
                            (pk {run.roundabout.queueMax.toFixed(0)})
                          </span>
                        )}
                      </span>
                    </div>
                  </td>

                  {/* Winner Badge */}
                  <td>
                    <span
                      className={
                        run.winner === "roundabout"
                          ? "winner-roundabout"
                          : run.winner === "signal"
                            ? "winner-signal"
                            : "winner-tie"
                      }
                      title={
                        run.inconclusiveReason === "vehicle_limit_reached"
                          ? "Vehicle generation hit its limit, so demand was cut off at this tier"
                          : run.inconclusiveReason === "low_sample"
                            ? "Fewer than 20 vehicles got through on a side"
                            : undefined
                      }
                    >
                      {run.winner === "roundabout"
                        ? "Roundabout"
                        : run.winner === "signal"
                          ? "Signal"
                          : run.winner === "tie"
                            ? "About the same"
                            : "Inconclusive"}
                    </span>
                  </td>

                  {/* Delta */}
                  <td>
                    <span
                      className="volume-delta-pill"
                      style={{
                        color:
                          run.delayDeltaPercent > 0
                            ? "#38bdf8"
                            : run.delayDeltaPercent < 0
                              ? "#10b981"
                              : "#94a3b8",
                        background:
                          run.delayDeltaPercent > 0
                            ? "rgba(56, 189, 248, 0.12)"
                            : run.delayDeltaPercent < 0
                              ? "rgba(16, 185, 129, 0.12)"
                              : "rgba(148, 163, 184, 0.12)",
                      }}
                      title={
                        run.delayDeltaPercent > 0
                          ? `+${run.delayDeltaPercent.toFixed(1)}% (signal lower)`
                          : run.delayDeltaPercent < 0
                            ? `${run.delayDeltaPercent.toFixed(1)}% (roundabout lower)`
                            : "0.0% Parity"
                      }
                    >
                      {run.delayDeltaPercent > 0 ? "+" : ""}
                      {run.delayDeltaPercent.toFixed(1)}%
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <TierMetrics runs={runs} />
    </div>
  );
}
