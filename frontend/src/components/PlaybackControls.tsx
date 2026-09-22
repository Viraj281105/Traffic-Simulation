import React from "react";
import type { LiveSnapshot } from "../types/simulation";

interface PlaybackControlsProps {
  snapshot: LiveSnapshot | null;
  isPlaying: boolean;
  onPlay: () => void;
  onPause: () => void;
  onStop: () => void;
  disabled?: boolean;
}

export const PlaybackControls: React.FC<PlaybackControlsProps> = ({
  snapshot,
  isPlaying,
  onPlay,
  onPause,
  onStop,
  disabled = false,
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
          title="Stop and reset the simulation with a new random seed"
        >
          <span aria-hidden="true">⏹ </span>Reset
        </button>
      </div>

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
        <div className="pb-stat" title="Simulation steps per simulated second">
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
    </div>
  );
};
