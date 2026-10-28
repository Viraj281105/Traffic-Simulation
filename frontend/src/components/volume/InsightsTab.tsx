import {
  BookOpen,
  ChartColumn,
  FlaskConical,
  TriangleAlert,
} from "lucide-react";
import {
  LOS_THRESHOLDS,
  LOS_WORDS,
  SIDE_TITLE,
  type LosGrade,
  type Side,
} from "../../metrics/plainLanguage";
import {
  crossoverSummary,
  tieText,
  type SweepRun,
  type SweepSession,
  type TierTally,
} from "../volumeSweepModel";
import { LOS_COLORS } from "./levelOfService";

interface InsightsTabProps {
  session: SweepSession;
  runs: SweepRun[];
  crossover: number | null;
  tally: TierTally;
}

/** Studio tab 3: what the sweep ran, what it shows and cannot show, and the
 *  level-of-service bands the grades use. */
export function InsightsTab({
  session,
  runs,
  crossover,
  tally,
}: InsightsTabProps) {
  return (
    <div className="engineering-insights-container">
      <div className="insights-header">
        <div>
          <h4>
            <BookOpen size={14} aria-hidden="true" className="uf-glyph" /> How
            to read this sweep
          </h4>
          <p className="insights-subtitle">
            What this sweep measured, what it shows, and what it cannot show.
            Every figure here comes from this sweep; the rest describes how
            UrbanFlow measures.
          </p>
        </div>
      </div>
      <div className="insights-card-grid">
        <div className="insight-card-modern">
          <div className="insight-card-top">
            <span className="insight-card-icon">
              <FlaskConical size={14} aria-hidden="true" className="uf-glyph" />
            </span>
            <span className="insight-badge recommendation-badge">
              What was run
            </span>
          </div>
          <h5>Measured, not modelled in the abstract</h5>
          <p>
            {runs.length.toString()} demand tiers, each simulated for{" "}
            {session.duration.toString()} s with one random traffic pattern
            (seed {session.randomSeed.toString()}
            ). Both controls received identical arrivals at every tier.
            {session.calibration
              ? ` ${session.calibration.note}`
              : " Whether this sweep used the calibrated one-lane configuration was not recorded."}
          </p>
        </div>
        <div className="insight-card-modern">
          <div className="insight-card-top">
            <span className="insight-card-icon">
              <ChartColumn size={14} aria-hidden="true" className="uf-glyph" />
            </span>
            <span className="insight-badge roundabout-badge">
              What this sweep shows
            </span>
          </div>
          <h5>Lower mean delay, tier by tier</h5>
          <p>
            {crossoverSummary(
              runs,
              crossover,
              session.curves.crossoverBracketArrivalRates,
            )}{" "}
            Tally: roundabout {tally.roundabout.toString()}, signal{" "}
            {tally.signal.toString()}, about the same {tally.tie.toString()},
            inconclusive {tally.inconclusive.toString()} of{" "}
            {tally.total.toString()} tiers. &ldquo;About the same&rdquo; means
            within {tieText(session.tieTolerance)}.
          </p>
        </div>
        <div className="insight-card-modern">
          <div className="insight-card-top">
            <span className="insight-card-icon">
              <TriangleAlert
                size={14}
                aria-hidden="true"
                className="uf-glyph"
              />
            </span>
            <span className="insight-badge signal-badge">
              What it cannot show
            </span>
          </div>
          <h5>Limits to keep in mind</h5>
          <ul className="insight-list">
            <li>
              One random pattern per tier: a difference here may be chance. The
              Statistical validation page repeats a scenario over many patterns
              and tests it.
            </li>
            <li>
              &ldquo;Delay&rdquo; is extra travel time against the driver&apos;s
              own desired speed. It includes slowing to enter a roundabout and
              is not the same as time queued, so read it next to the queue
              chart.
            </li>
            <li>
              The change in which control has the lower delay is not a capacity
              limit or a design threshold.
            </li>
            <li>
              UrbanFlow does not calculate emissions, fuel use, cost or crash
              risk. Nothing on this page speaks to them.
            </li>
            {tally.capped > 0 && (
              <li>
                Vehicle generation stopped at its per-run limit in{" "}
                {tally.capped.toString()} tier
                {tally.capped === 1 ? "" : "s"}, so demand there was cut off;
                those tiers are marked inconclusive.
              </li>
            )}
          </ul>
        </div>
      </div>
      {/* Level-of-service reference: one definition for the whole app */}
      <div className="hcm-los-reference-box">
        <h5>
          <BookOpen size={14} aria-hidden="true" className="uf-glyph" />{" "}
          Indicative level-of-service bands (Highway Capacity Manual delay
          bands, average delay in seconds)
        </h5>
        <p className="insights-subtitle">
          Used as a reference for how large a delay is. The grades on this page
          apply the manual&apos;s bands to simulated delay, which also includes
          geometric slow-down, so they are an indicative guide and not a
          level-of-service analysis. Signal: signalised-intersection bands.
          Roundabout: the stricter unsignalised bands.
        </p>
        <div className="los-grid-chips">
          {(["A", "B", "C", "D", "E", "F"] as LosGrade[]).map((grade, i) => (
            <div className="los-card-chip" key={grade}>
              <span
                className="los-badge"
                style={{
                  color: LOS_COLORS[grade].color,
                  background: LOS_COLORS[grade].bg,
                }}
              >
                LOS {grade}
              </span>
              {(["signal", "roundabout"] as Side[]).map((side) => {
                const bounds = LOS_THRESHOLDS[side];
                const lower = i === 0 ? null : bounds[i - 1];
                const upper = i < bounds.length ? bounds[i] : null;
                const range =
                  upper === null
                    ? `> ${(lower ?? 0).toString()} s`
                    : lower === null
                      ? `≤ ${upper.toString()} s`
                      : `${lower.toString()} – ${upper.toString()} s`;
                return (
                  <span className="los-time" key={side}>
                    {SIDE_TITLE[side]}: {range}
                  </span>
                );
              })}
              <span className="los-condition">{LOS_WORDS[grade]}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
