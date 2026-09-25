import React from "react";
import type { LiveSnapshot } from "../types/simulation";

interface PlaybackControlsProps {
  snapshot: LiveSnapshot | null;
  isPlaying: boolean;
  onPlay: () => void;
  onPause: () => void;
  onStop: () => void;
  disabled?: boolean;
  /** Everyday wording for the guided comparison: simulated time against
   *  the run's length and a status word, without tick counters. */
  simple?: boolean;
  /** Configured run length, shown in simple mode. */
  durationSeconds?: number;
}

const STATUS_WORDS: Record<string, string> = {
  running: "Running",
  paused: "Paused",
  completed: "Finished",
};

function clockText(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(s / 60))}:${String(s % 60).padStart(2, "0")}`;
}

export const PlaybackControls: React.FC<PlaybackControlsProps> = ({
  snapshot,
  isPlaying,
  onPlay,
  onPause,
  onStop,
  disabled = false,
  simple = false,
  durationSeconds,
}) => {
  const simTime = snapshot?.timestamp ?? 0;
  const tick = snapshot?.tick ?? 0;
  const hz = snapshot?.samplingFrequency ?? 10;
  const status = snapshot?.simulationStatus ?? "stopped";

  const statusTone =
    status === "running"
      ? "var(--accent-green)"
      : status === "paused"
        ? "var(--accent-yellow)"
        : "var(--text-secondary)";

  return (
    <div className="playback-bar" role="group" aria-label="Playback">
      <div className="playback-btns">
        <button
          id="btn-play"
          type="button"
          className={`pb-btn pb-primary ${isPlaying ? "active" : ""}`}
          onClick={onPlay}
          disabled={disabled || isPlaying}
          title={
            status === "completed"
              ? "Run the same scenario again"
              : "Start or resume the simulation"
          }
        >
          <span aria-hidden="true">▶ </span>
          {status === "completed" ? "Run again" : "Play"}
        </button>
        <button
          id="btn-pause"
          type="button"
          className={`pb-btn pb-secondary ${!isPlaying ? "active" : ""}`}
          onClick={onPause}
          disabled={disabled || !isPlaying || status === "completed"}
          title="Pause the simulation"
        >
          <span aria-hidden="true">⏸ </span>Pause
        </button>
        <button
          id="btn-stop"
          type="button"
          className="pb-btn pb-danger"
          onClick={onStop}
          disabled={disabled}
          title={
            simple
              ? "Stop and start over with a new random traffic pattern"
              : "Stop and reset the simulation with a new random seed"
          }
        >
          <span aria-hidden="true">⏹ </span>
          {simple ? "Start over" : "Reset"}
        </button>
      </div>

      {simple ? (
        <dl className="playback-info">
          <div className="pb-stat">
            <dt className="pb-stat-label">Simulated time</dt>
            <dd className="pb-stat-value">
              {clockText(simTime)}
              {durationSeconds !== undefined
                ? ` / ${clockText(durationSeconds)}`
                : ""}
            </dd>
          </div>
          <div className="pb-divider" aria-hidden="true" />
          <div className="pb-stat">
            <dt className="pb-stat-label">Status</dt>
            <dd
              className="pb-stat-value"
              style={{ color: statusTone }}
              aria-live="polite"
            >
              {STATUS_WORDS[status] ?? "Ready"}
            </dd>
          </div>
        </dl>
      ) : (
        <dl className="playback-info">
          <div className="pb-stat">
            <dt className="pb-stat-label">Sim time</dt>
            <dd className="pb-stat-value">{simTime.toFixed(1)} s</dd>
          </div>
          <div className="pb-divider" aria-hidden="true" />
          <div className="pb-stat">
            <dt className="pb-stat-label">Tick</dt>
            <dd className="pb-stat-value">{tick}</dd>
          </div>
          <div className="pb-divider" aria-hidden="true" />
          <div
            className="pb-stat"
            title="Simulation steps per simulated second"
          >
            <dt className="pb-stat-label">Tick rate</dt>
            <dd className="pb-stat-value">{hz} Hz</dd>
          </div>
          <div className="pb-divider" aria-hidden="true" />
          <div className="pb-stat">
            <dt className="pb-stat-label">Status</dt>
            <dd
              className="pb-stat-value"
              style={{ color: statusTone }}
              aria-live="polite"
            >
              {status.toUpperCase()}
            </dd>
          </div>
        </dl>
      )}
    </div>
  );
};
