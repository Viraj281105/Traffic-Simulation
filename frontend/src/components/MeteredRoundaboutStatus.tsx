import type { LiveSnapshot } from "../types/simulation";
import { ORDER, SHORT, meteringHoldReasonText } from "./meteredRoundaboutUtils";
import "./MeteredRoundaboutStatus.css";

/**
 * Status overlay for signalised roundabouts (V3.0 W2 S8, SR-28).
 * Shows current phase, plain-language hold reason, per-arm signal labels
 * (ensuring colour is never the sole indicator), and the required disclaimer.
 * Returns null for conventional roundabouts.
 */
export function MeteredRoundaboutStatus({
  snapshot,
}: {
  snapshot: LiveSnapshot | null | undefined;
}) {
  const controller = snapshot?.controller;
  if (
    !controller ||
    controller.type !== "roundabout" ||
    controller.entryControl !== "metered_entry" ||
    !controller.metering
  ) {
    return null;
  }

  const m = controller.metering;
  const reasonText = meteringHoldReasonText(m);

  return (
    <div
      className="metered-status"
      aria-label="Signalised roundabout entry metering status"
    >
      <p className="metered-status__title">
        <span className="metered-status__pulse" aria-hidden="true" />
        Metered entry · Phase {m.currentPhase.replace(/_/g, " ")} (
        {m.timeRemaining.toFixed(1)}s left)
      </p>
      <p className="metered-status__reason">{reasonText}</p>
      <div className="metered-status__arms" aria-label="Arm signal status">
        {ORDER.map((d) => {
          const arm = m.arms.find((a) => a.direction === d);
          if (!arm || !arm.metered) return null;
          const colorClass = `is-${arm.color}`;
          return (
            <span key={d} className={`metered-status__arm ${colorClass}`}>
              <span className="metered-status__arm-dir">{SHORT[d]}:</span>{" "}
              <span className="metered-status__arm-color">
                {arm.color.toUpperCase()}
              </span>
              {arm.reason &&
                arm.reason !== "red" &&
                arm.reason !== "yellow" && (
                  <span className="metered-status__arm-reason">
                    {" "}
                    ({arm.reason})
                  </span>
                )}
            </span>
          );
        })}
      </div>
      <p className="metered-status__disclaimer" role="note">
        Simulation assumption — signal timings are not calibrated to real sites;
        no claim that signalised roundabouts are better or safer in the real
        world.
      </p>
    </div>
  );
}
