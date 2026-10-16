import { BookOpen, Car, Dices, Settings2, Timer, X, Zap } from "lucide-react";
import { CloseButton } from "../ui/CloseButton";
import {
  DEMAND_LEVELS,
  REFERENCE_CAPACITY_VPH,
  demandRate,
  saturationRatio,
} from "../../types/demand";
import type { ValidationSettings } from "./validationModel";

/** Every setting of the next run: demand, physics, lanes and statistics. */
export function AdvancedConfigDrawer({
  settings,
  onChange,
  onClose,
  onReset,
  onRun,
  isRunning,
}: {
  settings: ValidationSettings;
  onChange: (patch: Partial<ValidationSettings>) => void;
  onClose: () => void;
  onReset: () => void;
  onRun: () => void;
  isRunning: boolean;
}) {
  const {
    numSeeds,
    duration,
    lanesCount,
    arrivalRate,
    arrivalDistribution,
    warmupTime,
    timeStep,
    approachLength,
    confidenceLevel,
  } = settings;
  const setNumSeeds = (numSeeds: number) => {
    onChange({ numSeeds });
  };
  const setDuration = (duration: number) => {
    onChange({ duration });
  };
  const setLanesCount = (lanesCount: ValidationSettings["lanesCount"]) => {
    onChange({ lanesCount });
  };
  const setArrivalRate = (arrivalRate: number) => {
    onChange({ arrivalRate });
  };
  const setArrivalDistribution = (
    arrivalDistribution: ValidationSettings["arrivalDistribution"],
  ) => {
    onChange({ arrivalDistribution });
  };
  const setWarmupTime = (warmupTime: number) => {
    onChange({ warmupTime });
  };
  const setTimeStep = (timeStep: number) => {
    onChange({ timeStep });
  };
  const setApproachLength = (approachLength: number) => {
    onChange({ approachLength });
  };
  const setConfidenceLevel = (
    confidenceLevel: ValidationSettings["confidenceLevel"],
  ) => {
    onChange({ confidenceLevel });
  };
  const setShowConfigPanel = (open: boolean) => {
    if (!open) onClose();
  };
  const resetAdvancedDefaults = onReset;
  const runValidation = onRun;

  return (
    <div className="validation-advanced-drawer">
      <div className="validation-advanced-drawer-header">
        <div className="advanced-title-group">
          <h4>
            <Settings2 size={14} aria-hidden="true" className="uf-glyph" />{" "}
            Advanced Stochastic Simulation & Statistical Config
          </h4>
          <span className="drawer-sub">
            Fine-tune traffic Poisson generation, physical discretization,
            warmup periods, and statistical rigor
          </span>
        </div>
        <CloseButton
          label="Close settings drawer"
          onClick={() => {
            setShowConfigPanel(false);
          }}
        />
      </div>

      <div className="validation-advanced-config-grid">
        {/* Section 1: Traffic Demand & Arrival Dynamics */}
        <div className="validation-advanced-card">
          <div className="adv-card-header">
            <span className="adv-icon">
              <Car size={14} aria-hidden="true" className="uf-glyph" />
            </span>
            <div>
              <h5>Traffic Demand & Flow Dynamics</h5>
              <span className="adv-sub">
                Arrival intensity and headway distribution
              </span>
            </div>
          </div>

          <div className="adv-field">
            <div className="adv-label-row">
              <label>Arrival Rate (λ)</label>
              <span className="adv-val-pill">
                {arrivalRate.toFixed(2)} veh/s ({Math.round(arrivalRate * 3600)}{" "}
                veh/h,{" "}
                {Math.round(saturationRatio(arrivalRate, lanesCount) * 100)}% of
                capacity)
              </span>
            </div>
            <div className="adv-slider-wrap">
              <input
                type="range"
                min={0.05}
                max={
                  Math.ceil((1.5 * REFERENCE_CAPACITY_VPH[lanesCount]) / 36) /
                  100
                }
                step={0.01}
                value={arrivalRate}
                onChange={(e) => {
                  setArrivalRate(Number(e.target.value));
                }}
              />
              <div className="adv-slider-labels">
                {[DEMAND_LEVELS[0], DEMAND_LEVELS[2], DEMAND_LEVELS[5]].map(
                  (d) => (
                    <span key={d.id}>
                      {demandRate(d, lanesCount).toFixed(2)} ({d.label})
                    </span>
                  ),
                )}
              </div>
            </div>
          </div>

          <div className="adv-field">
            <label>Arrival Pattern</label>
            <div className="adv-pill-group">
              <button
                type="button"
                className={`adv-pill-btn ${arrivalDistribution === "poisson" ? "active" : ""}`}
                onClick={() => {
                  setArrivalDistribution("poisson");
                }}
              >
                <Dices size={14} aria-hidden="true" className="uf-glyph" />{" "}
                Poisson (Stochastic Jitter)
              </button>
              <button
                type="button"
                className={`adv-pill-btn ${arrivalDistribution === "uniform" ? "active" : ""}`}
                onClick={() => {
                  setArrivalDistribution("uniform");
                }}
              >
                <Timer size={14} aria-hidden="true" className="uf-glyph" />{" "}
                Uniform (Constant Headway)
              </button>
            </div>
          </div>
        </div>

        {/* Section 2: Physical Discretization & Boundaries */}
        <div className="validation-advanced-card">
          <div className="adv-card-header">
            <span className="adv-icon">
              <Timer size={14} aria-hidden="true" className="uf-glyph" />
            </span>
            <div>
              <h5>Simulation Physics & Boundaries</h5>
              <span className="adv-sub">
                Integration step, warmup time, and road extent
              </span>
            </div>
          </div>

          <div className="adv-field">
            <div className="adv-label-row">
              <label>Warmup Time (t_warm)</label>
              <span className="adv-val-pill">{warmupTime.toFixed(1)}s</span>
            </div>
            <input
              type="number"
              min={0}
              max={60}
              step={5}
              value={warmupTime}
              onChange={(e) => {
                setWarmupTime(Number(e.target.value));
              }}
              title="Warmup time in seconds"
            />
            <span className="adv-hint">
              Clears initial startup transients before metrics recording begins.
            </span>
          </div>

          <div className="adv-field">
            <label>Integration Step (Δt)</label>
            <div className="adv-pill-group">
              <button
                type="button"
                className={`adv-pill-btn ${timeStep === 0.05 ? "active" : ""}`}
                onClick={() => {
                  setTimeStep(0.05);
                }}
              >
                0.05s (High Precision)
              </button>
              <button
                type="button"
                className={`adv-pill-btn ${timeStep === 0.1 ? "active" : ""}`}
                onClick={() => {
                  setTimeStep(0.1);
                }}
              >
                0.10s (Standard)
              </button>
              <button
                type="button"
                className={`adv-pill-btn ${timeStep === 0.2 ? "active" : ""}`}
                onClick={() => {
                  setTimeStep(0.2);
                }}
              >
                0.20s (Fast)
              </button>
            </div>
          </div>

          <div className="adv-field">
            <label>Approach Road Length</label>
            <div className="adv-pill-group">
              <button
                type="button"
                className={`adv-pill-btn ${approachLength === 150 ? "active" : ""}`}
                onClick={() => {
                  setApproachLength(150);
                }}
              >
                150m (Compact)
              </button>
              <button
                type="button"
                className={`adv-pill-btn ${approachLength === 200 ? "active" : ""}`}
                onClick={() => {
                  setApproachLength(200);
                }}
              >
                200m (Standard)
              </button>
              <button
                type="button"
                className={`adv-pill-btn ${approachLength === 300 ? "active" : ""}`}
                onClick={() => {
                  setApproachLength(300);
                }}
              >
                300m (Extended)
              </button>
            </div>
          </div>
        </div>

        {/* Section 3: Statistical Rigor & Hypothesis Testing */}
        <div className="validation-advanced-card">
          <div className="adv-card-header">
            <span className="adv-icon">
              <BookOpen size={14} aria-hidden="true" className="uf-glyph" />
            </span>
            <div>
              <h5>Statistical Rigor & Confidence</h5>
              <span className="adv-sub">
                Applies to the next run: interval width (Student-t) and the
                significance threshold
              </span>
            </div>
          </div>

          <div className="adv-field">
            <label>Lanes per approach</label>
            <div className="adv-pill-group">
              {([1, 2, 3] as const).map((n) => (
                <button
                  key={n}
                  type="button"
                  className={`adv-pill-btn ${lanesCount === n ? "active" : ""}`}
                  onClick={() => {
                    setLanesCount(n);
                  }}
                >
                  {n === 1
                    ? "1 lane (calibrated comparison)"
                    : `${String(n)} lanes (exploratory)`}
                </button>
              ))}
            </div>
            <span className="adv-sub">
              With more than one lane both junctions model every lane and the
              roundabout gets up to two circulating lanes, with lane designation
              and exits taken in turn (V1.4). Results are exploratory, not the
              calibrated baseline.
            </span>
          </div>

          <div className="adv-field">
            <label>Confidence Level (1 - α)</label>
            <div className="adv-pill-group">
              <button
                type="button"
                className={`adv-pill-btn ${confidenceLevel === 0.9 ? "active" : ""}`}
                onClick={() => {
                  setConfidenceLevel(0.9);
                }}
              >
                90% (α = 0.10)
              </button>
              <button
                type="button"
                className={`adv-pill-btn ${confidenceLevel === 0.95 ? "active" : ""}`}
                onClick={() => {
                  setConfidenceLevel(0.95);
                }}
              >
                95% (α = 0.05)
              </button>
              <button
                type="button"
                className={`adv-pill-btn ${confidenceLevel === 0.99 ? "active" : ""}`}
                onClick={() => {
                  setConfidenceLevel(0.99);
                }}
              >
                99% (α = 0.01)
              </button>
            </div>
          </div>

          <div className="adv-field">
            <label>Seeds (N) & Duration / Seed (s)</label>
            <div className="adv-two-inputs">
              <div>
                <span className="input-mini-label">Seeds (2–30):</span>
                <input
                  type="number"
                  min={2}
                  max={30}
                  value={numSeeds}
                  onChange={(e) => {
                    setNumSeeds(Number(e.target.value));
                  }}
                />
              </div>
              <div>
                <span className="input-mini-label">Duration (10–300s):</span>
                <input
                  type="number"
                  min={10}
                  max={300}
                  step={10}
                  value={duration}
                  onChange={(e) => {
                    setDuration(Number(e.target.value));
                  }}
                />
              </div>
            </div>
          </div>

          <div className="adv-summary-box">
            <span>
              <Zap size={14} aria-hidden="true" className="uf-glyph" />{" "}
              <strong>{numSeeds}</strong> seed pairs ×{" "}
              <strong>{duration}s</strong> duration ={" "}
              <strong>{numSeeds * 2}</strong> synchronized simulation trials.
            </span>
          </div>
        </div>
      </div>

      <div className="validation-advanced-drawer-footer">
        <div className="adv-foot-summary">
          <span>Active Config:</span>
          <span className="foot-chip">
            {arrivalDistribution === "poisson" ? "Poisson" : "Uniform"}
          </span>
          <span className="foot-chip">λ = {arrivalRate} veh/s</span>
          <span className="foot-chip">
            {Math.round(confidenceLevel * 100)}% CI
          </span>
          <span className="foot-chip">Δt = {timeStep}s</span>
          <span className="foot-chip">{approachLength}m roads</span>
        </div>

        <div className="adv-foot-actions">
          <button
            type="button"
            className="adv-reset-btn"
            onClick={resetAdvancedDefaults}
            title="Reset advanced configuration to default values"
          >
            ↺ Reset Defaults
          </button>
          <button
            type="button"
            className="adv-close-btn"
            onClick={() => {
              setShowConfigPanel(false);
            }}
          >
            <X size={14} aria-hidden="true" className="uf-glyph" /> Close
          </button>
          <button
            type="button"
            className="adv-apply-btn"
            onClick={runValidation}
            disabled={isRunning}
          >
            {isRunning ? "Executing Trials…" : "Apply & Run Validation"}
          </button>
        </div>
      </div>
    </div>
  );
}
