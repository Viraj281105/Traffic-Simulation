import { CircleCheck, CircleX, Scale } from "lucide-react";
import {
  METRIC_KEYS,
  METRIC_LABELS,
  lowerDelayTally,
  type ValidationResult,
} from "./validationModel";

/** The study's headline: which metrics show a statistically supported
 *  difference at the run's alpha, the per-seed tally, and its caveats. */
export function VerdictBanner({
  result,
  duration,
}: {
  result: ValidationResult;
  /** Seconds per seed, as shown in the studio's settings. */
  duration: number;
}) {
  // The backend's flag, computed at the run's own alpha, is the only source of
  // significance on screen (no second, locally chosen threshold).
  const allSignificant = METRIC_KEYS.every(
    (k) => result.comparison[k].significant,
  );
  const anySignificant = METRIC_KEYS.some(
    (k) => result.comparison[k].significant,
  );
  const resultAlpha = result.alpha ?? 0.05;
  const resultLevelPct = Math.round((result.confidenceLevel ?? 0.95) * 100);
  const roundaboutWinStats = lowerDelayTally(result);

  return (
    <>
      <div
        className={`verdict-card ${
          allSignificant
            ? "all-sig"
            : anySignificant
              ? "partial-sig"
              : "non-sig"
        }`}
      >
        <div className="verdict-icon-box">
          {allSignificant ? (
            <CircleCheck size={22} aria-hidden="true" />
          ) : anySignificant ? (
            <Scale size={22} aria-hidden="true" />
          ) : (
            <CircleX size={22} aria-hidden="true" />
          )}
        </div>
        <div className="verdict-content">
          <div className="verdict-headline">
            <h4>
              {allSignificant
                ? `Difference statistically supported on all three metrics at α = ${resultAlpha.toString()}`
                : anySignificant
                  ? `Difference statistically supported on some metrics at α = ${resultAlpha.toString()}`
                  : `No statistically supported difference at α = ${resultAlpha.toString()}`}
            </h4>
            <span className="win-rate-pill">
              Lower delay by seed: roundabout {roundaboutWinStats.roundabout},
              signal {roundaboutWinStats.signal}, about the same{" "}
              {roundaboutWinStats.same} (of {roundaboutWinStats.total})
            </span>
          </div>

          <div className="verdict-meta-row">
            <span className="verdict-detail">
              Based on{" "}
              <strong>{result.numSeeds} randomized Monte Carlo trials</strong>{" "}
              (Duration: {duration}s / seed) with {resultLevelPct}% Student-t
              confidence intervals. Three metrics are tested separately with no
              correction for that, and a result that is not supported means the
              study cannot distinguish the controls, not that they are equal.
            </span>

            <div className="significance-tag-row">
              {METRIC_KEYS.map((k) => (
                <span
                  key={k}
                  className={`sig-pill ${result.comparison[k].significant ? "active" : "inactive"}`}
                >
                  {METRIC_LABELS[k]}:{" "}
                  {result.comparison[k].significant
                    ? `Supported (p<${resultAlpha.toString()})`
                    : result.comparison[k].untestableReason
                      ? "No test applies"
                      : "Not supported"}
                </span>
              ))}
            </div>
            {METRIC_KEYS.some((k) => result.comparison[k].untestableReason) && (
              <p className="verdict-detail">
                &quot;No test applies&quot; marks a metric with no p-value:
                every seed gave each control the same value, or there were too
                few seeds, so there is no seed-to-seed variation to test a
                difference against.
              </p>
            )}
          </div>
        </div>
      </div>

      {result.calibration && !result.calibration.calibrated && (
        <p className="validation-banner is-exploratory" role="note">
          <strong>Exploratory, not calibrated.</strong>{" "}
          {result.calibration.note}
        </p>
      )}
      {result.vehicleLimitReachedSeeds &&
        result.vehicleLimitReachedSeeds.length > 0 && (
          <p className="validation-banner is-exploratory" role="note">
            <strong>Demand was cut off.</strong> Vehicle generation reached its
            per-run limit in {result.vehicleLimitReachedSeeds.length} of{" "}
            {result.numSeeds} seeds, so those seeds did not receive their full
            demand.
          </p>
        )}
    </>
  );
}
