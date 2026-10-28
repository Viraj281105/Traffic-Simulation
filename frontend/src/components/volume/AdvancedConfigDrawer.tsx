import {
  Car,
  ChartColumn,
  Microscope,
  Scale,
  Settings2,
  X,
  Zap,
} from "lucide-react";
import { CloseButton } from "../ui/CloseButton";
import type { SweepConfig } from "../volumeSweepModel";

interface AdvancedConfigDrawerProps {
  config: SweepConfig;
  onChange: (patch: Partial<SweepConfig>) => void;
  /** Number of demand tiers the chosen preset and lane count give. */
  tierCount: number;
  onReset: () => void;
  onClose: () => void;
  onRun: () => void;
  isRunning: boolean;
}

/** Demand spectrum, physics, geometry and speed settings for the sweep. */
export function AdvancedConfigDrawer({
  config,
  onChange,
  tierCount,
  onReset,
  onClose,
  onRun,
  isRunning,
}: AdvancedConfigDrawerProps) {
  return (
    <div className="volume-advanced-drawer">
      <div className="volume-advanced-drawer-header">
        <div>
          <h3>
            <Settings2 size={14} aria-hidden="true" className="uf-glyph" />{" "}
            Advanced Experiment Configuration
          </h3>
          <p>
            Tailor arrival spectrum granularity, integration fidelity, road
            geometry, and vehicle kinematics.
          </p>
        </div>
        <CloseButton label="Close advanced configuration" onClick={onClose} />
      </div>

      <div className="volume-advanced-config-grid">
        {/* Card 1: Traffic Demand Spectrum & Rates */}
        <div className="volume-advanced-card">
          <div className="advanced-card-header">
            <span className="card-badge">01</span>
            <div>
              <h4>
                <ChartColumn
                  size={14}
                  aria-hidden="true"
                  className="uf-glyph"
                />{" "}
                Demand Spectrum & Arrivals
              </h4>
              <span className="card-desc">
                Volume sweep resolution & arrival process
              </span>
            </div>
          </div>

          <div className="advanced-field-group">
            <label>Demand Tiers Spectrum ({tierCount} Points)</label>
            <div className="option-pill-group vertical">
              <button
                type="button"
                className={`option-pill ${config.demandTierPreset === "standard" ? "active" : ""}`}
                onClick={() => {
                  onChange({ demandTierPreset: "standard" });
                }}
              >
                <span className="pill-title">Standard 8-Tier</span>
                <span className="pill-desc">20% to 160% of capacity</span>
              </button>
              <button
                type="button"
                className={`option-pill ${config.demandTierPreset === "dense" ? "active" : ""}`}
                onClick={() => {
                  onChange({ demandTierPreset: "dense" });
                }}
              >
                <span className="pill-title">Dense Congestion 10-Tier</span>
                <span className="pill-desc">10% to 200% of capacity</span>
              </button>
              <button
                type="button"
                className={`option-pill ${config.demandTierPreset === "granular" ? "active" : ""}`}
                onClick={() => {
                  onChange({ demandTierPreset: "granular" });
                }}
              >
                <span className="pill-title">Granular Transition 10-Tier</span>
                <span className="pill-desc">60% to 150% of capacity</span>
              </button>
            </div>
          </div>

          <div className="advanced-field-group">
            <label>Arrival Distribution</label>
            <div className="option-pill-group">
              <button
                type="button"
                className={`option-pill ${config.arrivalDistribution === "poisson" ? "active" : ""}`}
                onClick={() => {
                  onChange({ arrivalDistribution: "poisson" });
                }}
              >
                Poisson (Stochastic)
              </button>
              <button
                type="button"
                className={`option-pill ${config.arrivalDistribution === "uniform" ? "active" : ""}`}
                onClick={() => {
                  onChange({ arrivalDistribution: "uniform" });
                }}
              >
                Uniform (Deterministic)
              </button>
            </div>
            <span className="field-hint">
              Poisson captures realistic random platooning & headway gaps.
            </span>
          </div>
        </div>

        {/* Card 2: Simulation Physics & Road Geometry */}
        <div className="volume-advanced-card">
          <div className="advanced-card-header">
            <span className="card-badge">02</span>
            <div>
              <h4>
                <Settings2 size={14} aria-hidden="true" className="uf-glyph" />{" "}
                Physics & Road Geometry
              </h4>
              <span className="card-desc">
                Numerical step size, warmup duration & approach road
              </span>
            </div>
          </div>

          <div className="advanced-field-group">
            <div className="field-label-row">
              <label>Warmup Duration (t_warm)</label>
              <span className="field-val-badge">
                {config.warmupTime.toFixed(1)}s
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={60}
              step={5}
              value={config.warmupTime}
              onChange={(e) => {
                onChange({ warmupTime: Number(e.target.value) });
              }}
              className="advanced-slider"
            />
            <span className="field-hint">
              Allows network queues to pre-populate before metrics accrue.
            </span>
          </div>

          <div className="advanced-field-group">
            <label>Integration Time Step (Δt)</label>
            <div className="option-pill-group">
              <button
                type="button"
                className={`option-pill ${config.timeStep === 0.05 ? "active" : ""}`}
                onClick={() => {
                  onChange({ timeStep: 0.05 });
                }}
              >
                0.05s (High Precision)
              </button>
              <button
                type="button"
                className={`option-pill ${config.timeStep === 0.1 ? "active" : ""}`}
                onClick={() => {
                  onChange({ timeStep: 0.1 });
                }}
              >
                0.10s (Balanced)
              </button>
              <button
                type="button"
                className={`option-pill ${config.timeStep === 0.2 ? "active" : ""}`}
                onClick={() => {
                  onChange({ timeStep: 0.2 });
                }}
              >
                0.20s (Fast Sweep)
              </button>
            </div>
          </div>

          <div className="advanced-field-group">
            <label>Approach Road Length</label>
            <div className="option-pill-group">
              <button
                type="button"
                className={`option-pill ${config.approachLength === 150 ? "active" : ""}`}
                onClick={() => {
                  onChange({ approachLength: 150 });
                }}
              >
                150m (Urban Tight)
              </button>
              <button
                type="button"
                className={`option-pill ${config.approachLength === 200 ? "active" : ""}`}
                onClick={() => {
                  onChange({ approachLength: 200 });
                }}
              >
                200m (Standard)
              </button>
              <button
                type="button"
                className={`option-pill ${config.approachLength === 300 ? "active" : ""}`}
                onClick={() => {
                  onChange({ approachLength: 300 });
                }}
              >
                300m (Extended)
              </button>
            </div>
          </div>
        </div>

        {/* Card 3: Intersection Lanes & Fleet Speed */}
        <div className="volume-advanced-card">
          <div className="advanced-card-header">
            <span className="card-badge">03</span>
            <div>
              <h4>
                <Car size={14} aria-hidden="true" className="uf-glyph" />{" "}
                Approach Lanes & Fleet Speed
              </h4>
              <span className="card-desc">
                Lane capacity configuration and driver velocity bounds
              </span>
            </div>
          </div>

          <div className="advanced-field-group">
            <label>Lanes per Approach (All 4 Legs)</label>
            <div className="option-pill-group">
              {[1, 2, 3].map((n) => (
                <button
                  key={n}
                  type="button"
                  className={`option-pill ${config.lanesCount === n ? "active" : ""}`}
                  onClick={() => {
                    onChange({ lanesCount: n });
                  }}
                >
                  {n === 1
                    ? "1 Lane (calibrated comparison)"
                    : `${String(n)} Lanes (exploratory)`}
                </button>
              ))}
            </div>
            <span className="field-hint">
              One lane per approach is the calibrated comparison. With more
              lanes both junctions model every lane, but multi-lane capacity has
              not been checked against real junctions, so multi-lane results are
              exploratory.
            </span>
          </div>

          <div className="advanced-field-group">
            <label>Road Speed Limit</label>
            <div className="option-pill-group vertical">
              <button
                type="button"
                className={`option-pill ${config.speedProfileKey === "standard" ? "active" : ""}`}
                onClick={() => {
                  onChange({ speedProfileKey: "standard" });
                }}
              >
                <span className="pill-title">Standard Urban</span>
                <span className="pill-desc">50 km/h limit</span>
              </button>
              <button
                type="button"
                className={`option-pill ${config.speedProfileKey === "calmed" ? "active" : ""}`}
                onClick={() => {
                  onChange({ speedProfileKey: "calmed" });
                }}
              >
                <span className="pill-title">Traffic Calmed</span>
                <span className="pill-desc">30 km/h limit</span>
              </button>
              <button
                type="button"
                className={`option-pill ${config.speedProfileKey === "arterial" ? "active" : ""}`}
                onClick={() => {
                  onChange({ speedProfileKey: "arterial" });
                }}
              >
                <span className="pill-title">Arterial Corridor</span>
                <span className="pill-desc">60 km/h limit</span>
              </button>
            </div>
          </div>

          <div className="advanced-field-group">
            <label>Quick Duration Presets</label>
            <div className="preset-pill-row">
              <button
                type="button"
                className={`preset-pill ${config.duration === 120 ? "active" : ""}`}
                onClick={() => {
                  onChange({ duration: 120 });
                }}
              >
                <Zap size={14} aria-hidden="true" className="uf-glyph" /> 120s
                Rapid
              </button>
              <button
                type="button"
                className={`preset-pill ${config.duration === 240 ? "active" : ""}`}
                onClick={() => {
                  onChange({ duration: 240 });
                }}
              >
                <Scale size={14} aria-hidden="true" className="uf-glyph" /> 240s
                Balanced
              </button>
              <button
                type="button"
                className={`preset-pill ${config.duration === 300 ? "active" : ""}`}
                onClick={() => {
                  onChange({ duration: 300 });
                }}
              >
                <Microscope size={14} aria-hidden="true" className="uf-glyph" />{" "}
                300s High Rigor
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="volume-advanced-drawer-footer">
        <div className="drawer-footprint-chip">
          Active Parameters: <strong>{tierCount} Rates</strong> ·{" "}
          <strong>{config.arrivalDistribution.toUpperCase()}</strong> ·{" "}
          <strong>Δt={config.timeStep.toFixed(2)}s</strong> ·{" "}
          <strong>
            {config.lanesCount} Lanes/Leg
            {config.lanesCount === 1 ? "" : " (exploratory)"}
          </strong>{" "}
          · <strong>{config.approachLength}m Approach</strong>
        </div>

        <div className="drawer-actions-right">
          <button
            type="button"
            className="advanced-reset-btn"
            onClick={onReset}
          >
            ↺ Reset Defaults
          </button>
          <button
            type="button"
            className="advanced-close-btn"
            onClick={onClose}
          >
            <X size={14} aria-hidden="true" className="uf-glyph" /> Close
          </button>
          <button
            type="button"
            className="advanced-apply-btn"
            onClick={onRun}
            disabled={isRunning}
          >
            {isRunning ? "Simulating…" : "Apply & Run Sweep"}
          </button>
        </div>
      </div>
    </div>
  );
}
