import { Scale, Target, Timer } from "lucide-react";
import {
  crossoverSummary,
  largestDelayGap,
  tieText,
  type SweepRun,
  type SweepSession,
  type TierTally,
} from "../volumeSweepModel";

interface SweepOverviewProps {
  session: SweepSession;
  runs: SweepRun[];
  crossover: number | null;
  tally: TierTally;
}

/** Calibration and demand-cap banners, then the four headline KPI cards. */
export function SweepOverview({
  session,
  runs,
  crossover,
  tally,
}: SweepOverviewProps) {
  const largestGap = largestDelayGap(runs);

  return (
    <>
      {session.calibration && !session.calibration.calibrated && (
        <p className="sweep-banner is-exploratory" role="note">
          <strong>Exploratory, not calibrated.</strong>{" "}
          {session.calibration.note}
        </p>
      )}
      {!session.calibration && (
        <p className="sweep-banner" role="note">
          This sweep was saved before its lane configuration was recorded, so it
          cannot be identified as the calibrated one-lane comparison.
        </p>
      )}
      {tally.capped > 0 && (
        <p className="sweep-banner is-exploratory" role="note">
          <strong>Demand was cut off.</strong> Vehicle generation reached its
          per-run limit in {tally.capped.toString()} of {tally.total.toString()}{" "}
          tiers, so those tiers did not receive their full demand and are marked
          inconclusive.
        </p>
      )}
      {/* Executive KPI Cards */}
      <div className="volume-kpi-grid">
        <div className="kpi-card kpi-crossover-card">
          <div className="kpi-top">
            <span className="kpi-icon-badge">
              <Target size={14} aria-hidden="true" className="uf-glyph" />
            </span>
            <span className="kpi-category">Delay ordering</span>
          </div>
          <span className="kpi-label">
            Where the lower-delay control changes
          </span>
          <span className="kpi-value highlight-amber">
            {crossover
              ? `${crossover.toLocaleString()} veh/h`
              : "No change observed"}
          </span>
          <span className="kpi-hint">
            {crossover
              ? crossoverSummary(
                  runs,
                  crossover,
                  session.curves.crossoverBracketArrivalRates,
                )
              : crossoverSummary(runs, null)}
          </span>
        </div>

        <div className="kpi-card">
          <div className="kpi-top">
            <span className="kpi-icon-badge">
              <Scale size={14} aria-hidden="true" className="uf-glyph" />
            </span>
            <span className="kpi-category">Tier tally</span>
          </div>
          <span className="kpi-label">Lower mean delay, by tier</span>
          <span className="kpi-value">
            <span className="series-dot is-roundabout" aria-hidden="true" />{" "}
            {tally.roundabout.toString()} ·{" "}
            <span className="series-dot is-signal" aria-hidden="true" />{" "}
            {tally.signal.toString()} ·{" "}
            <Scale size={14} aria-hidden="true" className="uf-glyph" />{" "}
            {tally.tie.toString()}
          </span>
          <span className="kpi-hint">
            Roundabout · signal · about the same (
            {tieText(session.tieTolerance)})
            {tally.inconclusive > 0
              ? ` · ${tally.inconclusive.toString()} inconclusive`
              : ""}
            , of {tally.total.toString()} tiers — one seed each
          </span>
        </div>

        <div className="kpi-card">
          <div className="kpi-top">
            <span className="kpi-icon-badge">
              <Timer size={14} aria-hidden="true" className="uf-glyph" />
            </span>
            <span className="kpi-category">Largest gap</span>
          </div>
          <span className="kpi-label">Largest mean-delay difference</span>
          <span className="kpi-value">
            {largestGap ? `${Math.abs(largestGap.diff).toFixed(1)} s` : "N/A"}
          </span>
          <span className="kpi-hint">
            {largestGap
              ? `Lower for the ${largestGap.diff < 0 ? "roundabout" : "signal"} at ${largestGap.run.hourlyVolumeVehPerHour.toLocaleString()} veh/h (one seed)`
              : "No tiers yet"}
          </span>
        </div>

        <div className="kpi-card">
          <div className="kpi-top">
            <span className="kpi-icon-badge">
              <span className="series-dot is-signal" aria-hidden="true" />
            </span>
            <span className="kpi-category">Stress Boundary</span>
          </div>
          <span className="kpi-label">Peak Evaluated Volume</span>
          <span className="kpi-value highlight-blue">
            {session.curves.volumesVehPerHour.length > 0
              ? `${Math.max(...session.curves.volumesVehPerHour).toLocaleString()} veh/h`
              : "—"}
          </span>
          <span className="kpi-hint">
            Highest capacity stress tier analyzed
          </span>
        </div>
      </div>
    </>
  );
}
