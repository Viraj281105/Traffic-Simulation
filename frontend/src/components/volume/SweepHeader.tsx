import {
  ChartSpline,
  Dices,
  Download,
  FolderOpen,
  Settings2,
} from "lucide-react";
import type { SweepConfig } from "../volumeSweepModel";

interface SweepHeaderProps {
  config: SweepConfig;
  onChange: (patch: Partial<SweepConfig>) => void;
  onRun: () => void;
  isRunning: boolean;
  advancedOpen: boolean;
  historyOpen: boolean;
  onToggleAdvanced: () => void;
  onToggleHistory: () => void;
  savedCount: number;
  canExport: boolean;
  onExport: () => void;
}

/** Page heading with the inline duration / seed controls, the run button and
 *  the drawer and export toggles. */
export function SweepHeader({
  config,
  onChange,
  onRun,
  isRunning,
  advancedOpen,
  historyOpen,
  onToggleAdvanced,
  onToggleHistory,
  savedCount,
  canExport,
  onExport,
}: SweepHeaderProps) {
  return (
    <div className="volume-header-row">
      <div className="uf-dash-head">
        <p className="guided-eyebrow">Research lab</p>
        <h1 className="uf-dash-head__title">
          <ChartSpline size={22} aria-hidden="true" className="uf-glyph" />
          Traffic Volume & Capacity Analysis
        </h1>
        <div className="uf-dash-head__tags">
          <span className="uf-tag">Capacity studio</span>
          <span className="uf-tag">HCM 6th Ed.</span>
        </div>
        <p className="uf-dash-head__lead">
          Systematic sensitivity study comparing Fixed-Time Signals vs. Modern
          Roundabouts across demand tiers. Uses its own study scenario (set
          under Advanced Config), one seed per tier.
        </p>
      </div>

      <div className="volume-header-actions">
        {/* Inline Duration & Seed controls in line with the heading */}
        <div className="volume-header-inline-controls">
          <div className="volume-inline-param">
            <label>Duration</label>
            <div className="volume-inline-unit-wrap">
              <input
                type="number"
                min={10}
                max={300}
                step={10}
                value={config.duration}
                onChange={(e) => {
                  onChange({ duration: Number(e.target.value) });
                }}
                title="Duration per rate tier (10–300s)"
              />
              <span>s</span>
            </div>
          </div>

          <div className="volume-inline-param">
            <label>Seed</label>
            <div className="inline-seed-wrap">
              <input
                type="number"
                min={1}
                value={config.randomSeed}
                onChange={(e) => {
                  onChange({ randomSeed: Number(e.target.value) });
                }}
                title="Random seed for traffic generation"
              />
              <button
                type="button"
                className="dice-btn"
                onClick={() => {
                  onChange({
                    randomSeed: Math.floor(Math.random() * 999999) + 1,
                  });
                }}
                title="Randomize seed"
              >
                <Dices size={14} aria-hidden="true" className="uf-glyph" />
              </button>
            </div>
          </div>

          <button
            type="button"
            className="volume-header-run-btn"
            onClick={onRun}
            disabled={isRunning}
            title="Execute capacity volume sweep"
          >
            {isRunning ? "Running…" : "Run Sweep"}
          </button>
        </div>

        {/* Button strictly named 'Advanced Config' */}
        <button
          type="button"
          className={`volume-header-tool-btn ${advancedOpen ? "active" : ""}`}
          onClick={onToggleAdvanced}
          title="Configure granular demand tiers, physics, geometry and speed dynamics"
        >
          <Settings2 size={14} aria-hidden="true" className="uf-glyph" />{" "}
          Advanced Config
        </button>

        {/* Saved Sweeps button */}
        <button
          type="button"
          className={`volume-header-tool-btn ${historyOpen ? "active" : ""}`}
          onClick={onToggleHistory}
          title="Browse and restore past saved sweep sessions"
        >
          <FolderOpen size={14} aria-hidden="true" className="uf-glyph" /> Saved
          Sweeps ({savedCount.toString()})
        </button>

        {canExport && (
          <button
            type="button"
            className="volume-export-csv-btn"
            onClick={onExport}
            title="Download study dataset as CSV"
          >
            <Download size={14} aria-hidden="true" className="uf-glyph" />{" "}
            Export CSV
          </button>
        )}
      </div>
    </div>
  );
}
