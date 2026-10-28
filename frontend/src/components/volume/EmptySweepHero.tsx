import { ChartSpline, FolderOpen, Play, Settings2 } from "lucide-react";

interface EmptySweepHeroProps {
  tierCount: number;
  savedCount: number;
  isRunning: boolean;
  onRun: () => void;
  onOpenAdvanced: () => void;
  onOpenHistory: () => void;
}

/** Shown before any sweep is loaded or running. */
export function EmptySweepHero({
  tierCount,
  savedCount,
  isRunning,
  onRun,
  onOpenAdvanced,
  onOpenHistory,
}: EmptySweepHeroProps) {
  return (
    <div className="empty-sweep-hero">
      <div className="empty-hero-icon">
        <ChartSpline size={26} strokeWidth={1.7} aria-hidden="true" />
      </div>
      <h3>Ready to Execute Volume & Capacity Sweep</h3>
      <p>
        Systematic sensitivity study comparing Fixed-Time Signals vs. Modern
        Roundabouts across demand tiers. Configure your parameters or click
        below to launch the automated benchmark sweep.
      </p>
      <div className="empty-hero-actions">
        <button
          type="button"
          className="hero-run-btn"
          onClick={onRun}
          disabled={isRunning}
        >
          <Play size={14} aria-hidden="true" className="uf-glyph" /> Run Volume
          Sweep ({tierCount} Tiers)
        </button>
        <button
          type="button"
          className="hero-secondary-btn"
          onClick={onOpenAdvanced}
        >
          <Settings2 size={14} aria-hidden="true" className="uf-glyph" />{" "}
          Advanced Config
        </button>
        {savedCount > 0 && (
          <button
            type="button"
            className="hero-secondary-btn"
            onClick={onOpenHistory}
          >
            <FolderOpen size={14} aria-hidden="true" className="uf-glyph" />{" "}
            Load Past Sweep ({savedCount.toString()})
          </button>
        )}
      </div>
    </div>
  );
}
