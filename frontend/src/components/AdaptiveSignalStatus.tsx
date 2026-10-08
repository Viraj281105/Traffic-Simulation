import type { LiveSnapshot, SignalDirection } from "../types/simulation";
import { adaptiveStateOf, adaptiveStatusText } from "../signals/signalControl";
import "./AdaptiveSignalStatus.css";

const ORDER: SignalDirection[] = ["north", "south", "east", "west"];
const SHORT: Record<SignalDirection, string> = {
  north: "N",
  south: "S",
  east: "E",
  west: "W",
};

/**
 * Map overlay for a signal that responds to traffic (V1.3): what it is doing
 * now, in words, and how many vehicles its stop-line detectors see on each
 * approach. Hidden for a fixed-timetable signal, so that view is unchanged.
 */
export function AdaptiveSignalStatus({
  snapshot,
}: {
  snapshot: LiveSnapshot | null | undefined;
}) {
  const controller = snapshot?.controller;
  const state = adaptiveStateOf(controller);
  const text = adaptiveStatusText(controller);
  if (!state || !text) return null;
  return (
    <div className="adaptive-status" aria-label="Signal responding to traffic">
      <p className="adaptive-status__title">
        <span className="adaptive-status__pulse" aria-hidden="true" />
        Responds to traffic
      </p>
      <p className="adaptive-status__text">{text}</p>
      <p className="adaptive-status__detected">
        <span>Detected near the stop line:</span>{" "}
        {ORDER.map((d) => (
          <span key={d} className="adaptive-status__count">
            {SHORT[d]} {String(state.detected[d] ?? 0)}
          </span>
        ))}
      </p>
    </div>
  );
}
