import React, { useId, useMemo, useState } from "react";
import type { SimulationConfigValues } from "../types/config";
import { DEFAULT_CONFIG_VALUES, SCENARIO_PRESETS } from "../types/config";
import { Overlay } from "./ui/Overlay";
import "./ConfigurationSidebar.css";

export type ConfigMode = "signal" | "roundabout" | "comparative";

interface ConfigurationSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  config: SimulationConfigValues;
  onApply: (newConfig: SimulationConfigValues) => void;
  /** Which controls are relevant to the current view. */
  mode: ConfigMode;
  /** Set when applying only updates a draft (the guided setup step) rather
   *  than resetting a live run. */
  draftOnly?: boolean;
}

interface ValidationAlert {
  type: "error" | "warning";
  message: string;
}

/** Same bounds as the backend's corridor greens (gt 5, le 120). */
const CORRIDOR_MIN = 6;
const CORRIDOR_MAX = 120;

function sameConfig(a: SimulationConfigValues, b: SimulationConfigValues) {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]) as Set<
    keyof SimulationConfigValues
  >;
  return [...keys].every((k) => (a[k] ?? null) === (b[k] ?? null));
}

function SliderField({
  label,
  unit,
  hint,
  value,
  display,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  unit: string;
  hint?: string;
  value: number;
  display: string;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  const id = useId();
  return (
    <div className="config-control-group">
      <div className="config-control-header">
        <label htmlFor={id}>{label}</label>
        <output htmlFor={id} className="config-control-value">
          {display} {unit}
        </output>
      </div>
      <input
        id={id}
        type="range"
        className="config-slider"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-valuetext={`${display} ${unit}`}
        aria-describedby={hint ? `${id}-hint` : undefined}
        onChange={(e) => {
          onChange(Number(e.target.value));
        }}
      />
      {hint && (
        <p className="config-hint" id={`${id}-hint`}>
          {hint}
        </p>
      )}
    </div>
  );
}

export const ConfigurationSidebar: React.FC<ConfigurationSidebarProps> = ({
  isOpen,
  onClose,
  config,
  onApply,
  mode,
  draftOnly = false,
}) => {
  const [prevConfig, setPrevConfig] = useState<SimulationConfigValues>(config);
  const [form, setForm] = useState<SimulationConfigValues>(config);
  const [isApplied, setIsApplied] = useState(false);
  const titleId = useId();
  const seedId = useId();
  const splitId = useId();

  // Synchronize when outer config changes (e.g. on reset or replay) without calling setState in an effect
  if (config !== prevConfig) {
    setPrevConfig(config);
    setForm(config);
  }

  const showSignal = mode !== "roundabout";
  const showRoundabout = mode !== "signal";
  const splitGreens =
    form.nsGreenDuration !== null &&
    form.nsGreenDuration !== undefined &&
    form.ewGreenDuration !== null &&
    form.ewGreenDuration !== undefined;

  const isDirty = useMemo(() => !sameConfig(form, config), [form, config]);

  // Checks describe what the model supports; they do not claim behaviour the
  // simulation does not model.
  const validationAlerts = useMemo<ValidationAlert[]>(() => {
    const alerts: ValidationAlert[] = [];
    if (form.laneWidth < 2.8) {
      alerts.push({
        type: "error",
        message: "Lane width below 2.8 m is outside the supported range.",
      });
    } else if (form.laneWidth > 4.5) {
      alerts.push({
        type: "warning",
        message:
          "Lane width above 4.5 m is outside typical urban design ranges (lane width changes geometry only, not driver behaviour, in this model).",
      });
    }
    if (form.arrivalRate > 0.8) {
      alerts.push({
        type: "warning",
        message:
          "High demand (above 0.8 veh/s ≈ 2,880 veh/h offered): queues may keep growing for the whole run.",
      });
    }
    if (showRoundabout && form.criticalGap <= form.followUpTime) {
      alerts.push({
        type: "error",
        message:
          "Critical gap must be longer than the follow-up headway (gap-acceptance models require t_c > t_f).",
      });
    }
    if (showRoundabout && form.criticalGap < 2.0) {
      alerts.push({
        type: "error",
        message: "Critical gap below 2.0 s is outside the supported range.",
      });
    }
    return alerts;
  }, [form, showRoundabout]);

  const hasErrors = validationAlerts.some((a) => a.type === "error");

  const handleChange = <K extends keyof SimulationConfigValues>(
    key: K,
    value: SimulationConfigValues[K],
  ) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = (e: React.SyntheticEvent) => {
    e.preventDefault();
    if (hasErrors) return;
    onApply(form);
    setIsApplied(true);
    setTimeout(() => {
      setIsApplied(false);
    }, 2000);
  };

  if (!isOpen) return null;

  const hourly = Math.round(form.arrivalRate * 3600).toLocaleString();

  return (
    <Overlay
      variant="drawer"
      title="Scenario settings"
      description={
        (draftOnly
          ? "Used when you run the comparison."
          : "Applying restarts the current run with these settings.") +
        (mode === "comparative"
          ? " Both controls get the same demand, geometry and seed."
          : "")
      }
      headerExtra={
        isDirty ? (
          <span className="uf-badge uf-badge--warning config-dirty-badge">
            Unsaved
          </span>
        ) : undefined
      }
      closeLabel="Close scenario settings"
      onClose={onClose}
      onSubmit={handleSubmit}
      className="config-drawer"
      footer={
        <>
          <button
            type="button"
            className="uf-btn uf-btn--ghost"
            onClick={() => {
              setForm({
                ...DEFAULT_CONFIG_VALUES,
                randomSeed: form.randomSeed,
              });
              setIsApplied(false);
            }}
          >
            Reset to defaults
          </button>
          <button
            type="button"
            className="uf-btn uf-btn--primary"
            disabled={hasErrors || !isDirty}
            onClick={handleSubmit}
          >
            {isApplied
              ? "Applied"
              : hasErrors
                ? "Fix the errors above"
                : isDirty
                  ? draftOnly
                    ? "Use these settings"
                    : "Apply & reset run"
                  : "No changes"}
          </button>
        </>
      }
    >
      <div className="config-sidebar-body">
        <div className="config-presets-container">
          <span className="config-presets-label" id={`${titleId}-presets`}>
            Presets
          </span>
          <div
            className="config-presets-grid"
            role="group"
            aria-labelledby={`${titleId}-presets`}
          >
            {SCENARIO_PRESETS.map((preset) => (
              <button
                key={preset.id}
                type="button"
                className="uf-btn uf-btn--sm config-preset-pill"
                title={preset.description}
                onClick={() => {
                  setForm(preset.config);
                }}
              >
                {preset.name}
              </button>
            ))}
          </div>
        </div>

        <div className="config-alerts-container" aria-live="polite">
          {validationAlerts.map((alert) => (
            <div
              key={alert.message}
              className={`uf-callout ${
                alert.type === "error"
                  ? "uf-callout--danger"
                  : "uf-callout--warning"
              }`}
              role={alert.type === "error" ? "alert" : undefined}
            >
              <span>
                <strong>{alert.type === "error" ? "Error: " : "Note: "}</strong>
                {alert.message}
              </span>
            </div>
          ))}
        </div>

        <fieldset className="config-section">
          <legend className="config-section-title">Traffic &amp; demand</legend>
          <SliderField
            label="Arrival rate (whole junction)"
            unit="veh/s"
            display={form.arrivalRate.toFixed(2)}
            hint={`≈ ${hourly} veh/h offered, split across the four approaches.`}
            value={form.arrivalRate}
            min={0.05}
            max={1.2}
            step={0.05}
            onChange={(v) => {
              handleChange("arrivalRate", v);
            }}
          />
          <SliderField
            label="Simulation duration"
            unit="s"
            display={String(form.duration)}
            hint="Simulated seconds. An initial warm-up period is excluded from most metrics."
            value={form.duration}
            min={30}
            max={600}
            step={10}
            onChange={(v) => {
              handleChange("duration", v);
            }}
          />
          <div className="config-control-group">
            <div className="config-control-header">
              <label htmlFor={seedId}>Random seed</label>
            </div>
            <div className="config-seed-row">
              <input
                id={seedId}
                type="number"
                min={1}
                className="uf-input config-seed-input"
                value={form.randomSeed}
                aria-describedby={`${seedId}-hint`}
                onChange={(e) => {
                  handleChange(
                    "randomSeed",
                    Math.max(1, parseInt(e.target.value, 10) || 1),
                  );
                }}
              />
              <button
                type="button"
                className="uf-btn uf-btn--sm config-reroll-btn"
                onClick={() => {
                  handleChange(
                    "randomSeed",
                    Math.floor(Math.random() * 1000000) + 1,
                  );
                }}
              >
                New seed
              </button>
            </div>
            <p className="config-hint" id={`${seedId}-hint`}>
              The same seed and settings reproduce the same arrivals.
            </p>
          </div>
        </fieldset>

        <fieldset className="config-section">
          <legend className="config-section-title">Geometry</legend>
          <SliderField
            label="Lanes per approach"
            unit={form.lanes === 1 ? "lane" : "lanes"}
            display={String(form.lanes)}
            value={form.lanes}
            min={1}
            max={3}
            step={1}
            onChange={(v) => {
              handleChange("lanes", v);
            }}
          />
          <SliderField
            label="Lane width"
            unit="m"
            display={form.laneWidth.toFixed(1)}
            value={form.laneWidth}
            min={2.5}
            max={4.8}
            step={0.1}
            onChange={(v) => {
              handleChange("laneWidth", v);
            }}
          />
        </fieldset>

        {showSignal && (
          <fieldset className="config-section">
            <legend className="config-section-title">
              Fixed-time signal timing
            </legend>
            <div className="config-checkbox-row">
              <input
                id={splitId}
                type="checkbox"
                checked={splitGreens}
                onChange={(e) => {
                  setForm((prev) =>
                    e.target.checked
                      ? {
                          ...prev,
                          nsGreenDuration: prev.greenDuration,
                          ewGreenDuration: prev.greenDuration,
                        }
                      : {
                          ...prev,
                          nsGreenDuration: null,
                          ewGreenDuration: null,
                        },
                  );
                }}
              />
              <label htmlFor={splitId}>
                Separate north–south and east–west greens
              </label>
            </div>
            {splitGreens ? (
              <>
                <SliderField
                  label="North–south green"
                  unit="s"
                  display={String(form.nsGreenDuration)}
                  value={form.nsGreenDuration ?? form.greenDuration}
                  min={CORRIDOR_MIN}
                  max={CORRIDOR_MAX}
                  step={1}
                  onChange={(v) => {
                    handleChange("nsGreenDuration", v);
                  }}
                />
                <SliderField
                  label="East–west green"
                  unit="s"
                  display={String(form.ewGreenDuration)}
                  value={form.ewGreenDuration ?? form.greenDuration}
                  min={CORRIDOR_MIN}
                  max={CORRIDOR_MAX}
                  step={1}
                  onChange={(v) => {
                    handleChange("ewGreenDuration", v);
                  }}
                />
              </>
            ) : (
              <SliderField
                label="Green (both corridors)"
                unit="s"
                display={String(form.greenDuration)}
                value={form.greenDuration}
                min={5}
                max={60}
                step={1}
                onChange={(v) => {
                  handleChange("greenDuration", v);
                }}
              />
            )}
            <SliderField
              label="Yellow"
              unit="s"
              display={String(form.yellowDuration)}
              value={form.yellowDuration}
              min={2}
              max={8}
              step={1}
              onChange={(v) => {
                handleChange("yellowDuration", v);
              }}
            />
            <SliderField
              label="All-red clearance"
              unit="s"
              display={String(form.allRedDuration)}
              value={form.allRedDuration}
              min={1}
              max={6}
              step={1}
              onChange={(v) => {
                handleChange("allRedDuration", v);
              }}
            />
          </fieldset>
        )}

        {showRoundabout && (
          <fieldset className="config-section">
            <legend className="config-section-title">
              Roundabout gap acceptance
            </legend>
            <SliderField
              label="Critical gap (t_c)"
              unit="s"
              display={form.criticalGap.toFixed(1)}
              hint="Smallest gap in circulating traffic an entering driver accepts."
              value={form.criticalGap}
              min={2}
              max={6}
              step={0.1}
              onChange={(v) => {
                handleChange("criticalGap", v);
              }}
            />
            <SliderField
              label="Follow-up headway (t_f)"
              unit="s"
              display={form.followUpTime.toFixed(1)}
              hint="Headway between queued vehicles entering the same gap."
              value={form.followUpTime}
              min={1}
              max={3.5}
              step={0.1}
              onChange={(v) => {
                handleChange("followUpTime", v);
              }}
            />
          </fieldset>
        )}
      </div>
    </Overlay>
  );
};
