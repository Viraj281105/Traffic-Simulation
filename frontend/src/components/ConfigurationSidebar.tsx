import React, { useState, useMemo } from "react";
import "./ConfigurationSidebar.css";

export interface SimulationConfigValues {
  lanes: number;
  laneWidth: number;
  arrivalRate: number;
  duration: number;
  randomSeed: number;
  greenDuration: number;
  yellowDuration: number;
  allRedDuration: number;
  criticalGap: number;
  followUpTime: number;
}

interface ConfigurationSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  config: SimulationConfigValues;
  onApply: (newConfig: SimulationConfigValues) => void;
  isRoundaboutMode?: boolean;
}

interface ValidationAlert {
  type: "error" | "warning";
  message: string;
}

export const DEFAULT_CONFIG_VALUES: SimulationConfigValues = {
  lanes: 2,
  laneWidth: 3.5,
  arrivalRate: 0.35,
  duration: 300,
  randomSeed: 42,
  greenDuration: 15,
  yellowDuration: 3,
  allRedDuration: 2,
  criticalGap: 4.0,
  followUpTime: 2.5,
};

export const ConfigurationSidebar: React.FC<ConfigurationSidebarProps> = ({
  isOpen,
  onClose,
  config,
  onApply,
  isRoundaboutMode = false,
}) => {
  const [form, setForm] = useState<SimulationConfigValues>(config);
  const [isApplied, setIsApplied] = useState(false);

  // Synchronize when outer config changes (e.g. on reset)
  React.useEffect(() => {
    setForm(config);
  }, [config]);

  // Check if dirty (unsaved changes)
  const isDirty = useMemo(() => {
    return JSON.stringify(form) !== JSON.stringify(config);
  }, [form, config]);

  // Real-time Validation Engine
  const validationAlerts = useMemo<ValidationAlert[]>(() => {
    const alerts: ValidationAlert[] = [];

    // Lane width
    if (form.laneWidth < 2.8) {
      alerts.push({
        type: "error",
        message: "Lane width below 2.8m violates vehicle clearance safety limits.",
      });
    } else if (form.laneWidth > 4.5) {
      alerts.push({
        type: "warning",
        message: "Lane width exceeds 4.5m; excessively wide lanes increase crossing distance.",
      });
    }

    // Arrival volume
    if (form.arrivalRate > 0.8) {
      alerts.push({
        type: "warning",
        message: "Arrival rate > 0.8 veh/s creates extreme peak load that will induce queuing.",
      });
    }

    // Signal timings
    if (form.greenDuration < 5) {
      alerts.push({
        type: "error",
        message: "Signal green duration cannot be less than 5 seconds (insufficient clearance).",
      });
    }
    if (form.yellowDuration < 2) {
      alerts.push({
        type: "error",
        message: "Yellow phase duration cannot be less than 2 seconds (dilemma zone hazard).",
      });
    }

    // Roundabout critical gap
    if (form.criticalGap <= form.followUpTime) {
      alerts.push({
        type: "error",
        message: "Critical gap must be strictly greater than follow-up headway time (criticalGap > followUpTime).",
      });
    }
    if (form.criticalGap < 2.0) {
      alerts.push({
        type: "warning",
        message: "Critical gap < 2.0s represents extremely aggressive yielding behavior.",
      });
    }

    return alerts;
  }, [form]);

  const hasErrors = validationAlerts.some((a) => a.type === "error");

  const handleChange = <K extends keyof SimulationConfigValues>(
    key: K,
    value: SimulationConfigValues[K]
  ) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setIsApplied(false);
  };

  const handleRerollSeed = () => {
    const fresh = Math.floor(Math.random() * 1000000) + 1;
    handleChange("randomSeed", fresh);
  };

  const handleReset = () => {
    setForm(DEFAULT_CONFIG_VALUES);
    setIsApplied(false);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (hasErrors) return;
    onApply(form);
    setIsApplied(true);
    setTimeout(() => setIsApplied(false), 2000);
  };

  if (!isOpen) return null;

  return (
    <div className="config-sidebar-overlay" onClick={onClose}>
      <div
        className="config-sidebar-panel"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="config-sidebar-header">
          <div className="config-sidebar-title">
            <span>⚙️ Scenario Configuration</span>
            {isDirty && <span className="config-dirty-badge">Unsaved</span>}
          </div>
          <button className="config-close-btn" onClick={onClose} title="Close">
            ✕
          </button>
        </div>

        {/* Form Body */}
        <form className="config-sidebar-body" onSubmit={handleSubmit}>
          {/* Validation Alerts Section */}
          <div className="config-alerts-container">
            {validationAlerts.length === 0 ? (
              <div className="config-alert config-alert-valid">
                <span>✓ All parameters meet standard geometric and kinematic constraints.</span>
              </div>
            ) : (
              validationAlerts.map((alert, idx) => (
                <div
                  key={idx}
                  className={`config-alert ${
                    alert.type === "error"
                      ? "config-alert-error"
                      : "config-alert-warning"
                  }`}
                >
                  <span>{alert.type === "error" ? "⛔" : "⚠️"}</span>
                  <span>{alert.message}</span>
                </div>
              ))
            )}
          </div>

          {/* Section 1: Traffic & Volume */}
          <div className="config-section">
            <div className="config-section-title">
              <span>🚗 Traffic & Demand</span>
            </div>

            <div className="config-control-group">
              <div className="config-control-header">
                <label>Arrival Rate</label>
                <span className="config-control-value">
                  {form.arrivalRate.toFixed(2)} veh/s
                </span>
              </div>
              <input
                type="range"
                className="config-slider"
                min="0.05"
                max="1.20"
                step="0.05"
                value={form.arrivalRate}
                onChange={(e) =>
                  handleChange("arrivalRate", parseFloat(e.target.value))
                }
              />
            </div>

            <div className="config-control-group">
              <div className="config-control-header">
                <label>Simulation Duration</label>
                <span className="config-control-value">{form.duration}s</span>
              </div>
              <input
                type="range"
                className="config-slider"
                min="30"
                max="600"
                step="10"
                value={form.duration}
                onChange={(e) =>
                  handleChange("duration", parseInt(e.target.value, 10))
                }
              />
            </div>

            <div className="config-control-group">
              <div className="config-control-header">
                <label>Deterministic Random Seed</label>
              </div>
              <div className="config-seed-row">
                <input
                  type="number"
                  className="config-seed-input"
                  value={form.randomSeed}
                  onChange={(e) =>
                    handleChange(
                      "randomSeed",
                      parseInt(e.target.value, 10) || 1
                    )
                  }
                />
                <button
                  type="button"
                  className="config-reroll-btn"
                  onClick={handleRerollSeed}
                  title="Generate a new randomized seed"
                >
                  🎲 Re-roll
                </button>
              </div>
            </div>
          </div>

          {/* Section 2: Geometry & Widths */}
          <div className="config-section">
            <div className="config-section-title">
              <span>📐 Geometry & Widths</span>
            </div>

            <div className="config-control-group">
              <div className="config-control-header">
                <label>Lanes per Approach</label>
                <span className="config-control-value">{form.lanes} lanes</span>
              </div>
              <input
                type="range"
                className="config-slider"
                min="1"
                max="4"
                step="1"
                value={form.lanes}
                onChange={(e) =>
                  handleChange("lanes", parseInt(e.target.value, 10))
                }
              />
            </div>

            <div className="config-control-group">
              <div className="config-control-header">
                <label>Lane Width</label>
                <span className="config-control-value">
                  {form.laneWidth.toFixed(1)} m
                </span>
              </div>
              <input
                type="range"
                className="config-slider"
                min="2.5"
                max="4.8"
                step="0.1"
                value={form.laneWidth}
                onChange={(e) =>
                  handleChange("laneWidth", parseFloat(e.target.value))
                }
              />
            </div>
          </div>

          {/* Section 3: Signal Timings */}
          <div className="config-section">
            <div className="config-section-title">
              <span>🚦 Fixed-Time Signal Timings</span>
              {!isRoundaboutMode && (
                <span className="config-active-badge">Active in Signal</span>
              )}
            </div>

            <div className="config-control-group">
              <div className="config-control-header">
                <label>Green Phase Duration</label>
                <span className="config-control-value">
                  {form.greenDuration}s
                </span>
              </div>
              <input
                type="range"
                className="config-slider"
                min="5"
                max="60"
                step="1"
                value={form.greenDuration}
                onChange={(e) =>
                  handleChange("greenDuration", parseInt(e.target.value, 10))
                }
              />
            </div>

            <div className="config-control-group">
              <div className="config-control-header">
                <label>Yellow Phase Duration</label>
                <span className="config-control-value">
                  {form.yellowDuration}s
                </span>
              </div>
              <input
                type="range"
                className="config-slider"
                min="2"
                max="8"
                step="1"
                value={form.yellowDuration}
                onChange={(e) =>
                  handleChange("yellowDuration", parseInt(e.target.value, 10))
                }
              />
            </div>

            <div className="config-control-group">
              <div className="config-control-header">
                <label>All-Red Clearance Duration</label>
                <span className="config-control-value">
                  {form.allRedDuration}s
                </span>
              </div>
              <input
                type="range"
                className="config-slider"
                min="1"
                max="6"
                step="1"
                value={form.allRedDuration}
                onChange={(e) =>
                  handleChange("allRedDuration", parseInt(e.target.value, 10))
                }
              />
            </div>
          </div>

          {/* Section 4: Roundabout Gap Acceptance */}
          <div className="config-section">
            <div className="config-section-title">
              <span>🔄 Roundabout Gap Acceptance</span>
              {isRoundaboutMode && (
                <span className="config-active-badge">Active in Roundabout</span>
              )}
            </div>

            <div className="config-control-group">
              <div className="config-control-header">
                <label>Critical Gap (t_c)</label>
                <span className="config-control-value">
                  {form.criticalGap.toFixed(1)}s
                </span>
              </div>
              <input
                type="range"
                className="config-slider"
                min="1.5"
                max="6.0"
                step="0.1"
                value={form.criticalGap}
                onChange={(e) =>
                  handleChange("criticalGap", parseFloat(e.target.value))
                }
              />
            </div>

            <div className="config-control-group">
              <div className="config-control-header">
                <label>Follow-up Headway (t_f)</label>
                <span className="config-control-value">
                  {form.followUpTime.toFixed(1)}s
                </span>
              </div>
              <input
                type="range"
                className="config-slider"
                min="1.0"
                max="3.5"
                step="0.1"
                value={form.followUpTime}
                onChange={(e) =>
                  handleChange("followUpTime", parseFloat(e.target.value))
                }
              />
            </div>
          </div>
        </form>

        {/* Footer with Submission Triggers */}
        <div className="config-sidebar-footer">
          <button
            type="button"
            className="config-reset-btn"
            onClick={handleReset}
          >
            Reset Defaults
          </button>
          <button
            type="button"
            className="config-apply-btn"
            disabled={hasErrors}
            onClick={handleSubmit}
          >
            {isApplied ? "✓ Applied!" : hasErrors ? "Fix Validation Errors" : "Apply Configuration"}
          </button>
        </div>
      </div>
    </div>
  );
};
