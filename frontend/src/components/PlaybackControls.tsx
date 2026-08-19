import React from "react";
import type { LiveSnapshot } from "../types/simulation";

interface PlaybackControlsProps {
  snapshot: LiveSnapshot | null;
  isPlaying: boolean;
  onPlay: () => void;
  onPause: () => void;
  disabled?: boolean;
}

export const PlaybackControls: React.FC<PlaybackControlsProps> = ({
  snapshot,
  isPlaying,
  onPlay,
  onPause,
  disabled = false,
}) => {
  const simTime = snapshot?.timestamp ?? 0;
  const tick = snapshot?.tick ?? 0;
  const hz = snapshot?.samplingFrequency ?? 10;
  const status = snapshot?.simulationStatus ?? "stopped";

  return (
    <div className="playback-bar">
      {/* Play / Pause */}
      <div className="playback-btns">
        <button
          id="btn-play"
          className={`pb-btn pb-primary ${isPlaying ? "active" : ""}`}
          onClick={onPlay}
          disabled={disabled || isPlaying}
          title="Play simulation"
        >
          ▶ Play
        </button>
        <button
          id="btn-pause"
          className={`pb-btn pb-secondary ${!isPlaying ? "active" : ""}`}
          onClick={onPause}
          disabled={disabled || !isPlaying}
          title="Pause simulation"
        >
          ⏸ Pause
        </button>
      </div>

      {/* Time info */}
      <div className="playback-info">
        <div className="pb-stat">
          <span className="pb-stat-label">SIM TIME</span>
          <span className="pb-stat-value">{simTime.toFixed(1)}s</span>
        </div>
        <div className="pb-divider" />
        <div className="pb-stat">
          <span className="pb-stat-label">TICK</span>
          <span className="pb-stat-value">{tick}</span>
        </div>
        <div className="pb-divider" />
        <div className="pb-stat">
          <span className="pb-stat-label">FREQ</span>
          <span className="pb-stat-value">{hz} Hz</span>
        </div>
        <div className="pb-divider" />
        <div className="pb-stat">
          <span className="pb-stat-label">STATUS</span>
          <span
            className="pb-stat-value"
            style={{
              color:
                status === "running"
                  ? "#2ecc40"
                  : status === "paused"
                    ? "#ffdc00"
                    : "#888",
            }}
          >
            {status.toUpperCase()}
          </span>
        </div>
      </div>
    </div>
  );
};
