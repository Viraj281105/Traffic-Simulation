import { MapPin, SlidersHorizontal } from "lucide-react";
import { winnerLabel, type SweepRun } from "../volumeSweepModel";
import { getLevelOfService } from "./levelOfService";

interface DemandScrubberProps {
  /** The tier nearest the scrubber's volume. */
  run: SweepRun;
  volume: number;
  minVol: number;
  maxVol: number;
  crossover: number | null;
  onVolumeChange: (volume: number) => void;
}

/** Demand explorer: a volume slider with both controls' delay and grade at
 *  the nearest tier. */
export function DemandScrubber({
  run,
  volume,
  minVol,
  maxVol,
  crossover,
  onVolumeChange,
}: DemandScrubberProps) {
  const sigLOS = getLevelOfService(run.signal.delay, "signal");
  const rndLOS = getLevelOfService(run.roundabout.delay, "roundabout");
  return (
    <div className="volume-scrubber-bar">
      <div className="scrubber-bar-left">
        <div className="scrubber-label-group">
          <span className="scrubber-title">
            <SlidersHorizontal
              size={14}
              aria-hidden="true"
              className="uf-glyph"
            />{" "}
            Demand Explorer
          </span>
          <span className="scrubber-rate">
            Rate: {run.arrivalRate.toFixed(2)} veh/s
          </span>
        </div>
        <div className="scrubber-vol-badge">
          <strong>{run.hourlyVolumeVehPerHour.toLocaleString()}</strong> veh/h
        </div>
      </div>

      <div className="scrubber-bar-center">
        <span className="slider-edge-label">{minVol.toLocaleString()}</span>
        <div className="slider-input-wrapper">
          <input
            type="range"
            min={minVol}
            max={maxVol}
            step={100}
            value={volume}
            onChange={(e) => {
              onVolumeChange(Number(e.target.value));
            }}
            className="volume-slider-input"
            aria-label="Volume demand scrubber"
          />
          {crossover && (
            <div
              className="slider-crossover-marker"
              style={{
                left: `${Math.max(0, Math.min(100, ((crossover - minVol) / (maxVol - minVol)) * 100)).toString()}%`,
              }}
              title={`Crossover: ${crossover.toLocaleString()} veh/h`}
            >
              <span className="marker-pin">
                <MapPin size={14} aria-hidden="true" className="uf-glyph" />
              </span>
            </div>
          )}
        </div>
        <span className="slider-edge-label">{maxVol.toLocaleString()}</span>
      </div>

      <div className="scrubber-bar-right">
        <div className="scrubber-chip signal-chip">
          <span className="chip-label">
            <span className="series-dot is-signal" aria-hidden="true" />{" "}
            Fixed-Time Signal
          </span>
          <span className="chip-val">{run.signal.delay.toFixed(1)}s</span>
          <span
            className="los-chip mini"
            style={{ color: sigLOS.color, background: sigLOS.bg }}
          >
            LOS {sigLOS.grade}
          </span>
        </div>

        <div className="scrubber-chip roundabout-chip">
          <span className="chip-label">
            <span className="series-dot is-roundabout" aria-hidden="true" />{" "}
            Modern Roundabout
          </span>
          <span className="chip-val">{run.roundabout.delay.toFixed(1)}s</span>
          <span
            className="los-chip mini"
            style={{ color: rndLOS.color, background: rndLOS.bg }}
          >
            LOS {rndLOS.grade}
          </span>
        </div>

        <div className={`scrubber-verdict-chip winner-${run.winner}`}>
          <span className="verdict-name">{winnerLabel(run.winner)}</span>
          <span className="verdict-delta">
            {run.delayDeltaPercent > 0 ? "+" : ""}
            {run.delayDeltaPercent.toFixed(1)}%
          </span>
        </div>
      </div>
    </div>
  );
}
