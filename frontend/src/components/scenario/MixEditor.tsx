import { useId } from "react";
import {
  MIX_PRESETS,
  VEHICLE_CLASSES,
  emptyMix,
  mixPresetFor,
  type VehicleMix,
} from "../../vehicles/vehicleClasses";
import { VehicleMixBar } from "../VehicleLegend";
import { mixTotal } from "../../scenario/scenarioModel";

/**
 * Share of each vehicle class, edited as plain percentages. The total is
 * shown live and must reach 100 % — nothing is rescaled behind the user's
 * back. ``null`` is the calibrated cars-only population.
 */
export function MixEditor({
  value,
  onChange,
  label = "Vehicle mix",
  allowCarsOnlyNull = true,
}: {
  value: VehicleMix | null | undefined;
  onChange: (mix: VehicleMix | null) => void;
  label?: string;
  /** Offer "cars only" as the calibrated population (null). */
  allowCarsOnlyNull?: boolean;
}) {
  const id = useId();
  const mix = value ?? { ...emptyMix(), car: 1 };
  const total = mixTotal(value ?? null);
  const ok = Math.abs(total - 1) <= 0.01;
  const preset = mixPresetFor(value ?? null);

  const setShare = (cls: keyof VehicleMix, percent: number) => {
    const next = { ...mix, [cls]: Math.max(0, Math.min(100, percent)) / 100 };
    onChange(next);
  };

  return (
    <div className="mix-editor" role="group" aria-labelledby={`${id}-label`}>
      <div className="mix-editor__head">
        <span id={`${id}-label`} className="mix-editor__label">
          {label}
        </span>
        <span
          className={`mix-total ${ok ? "is-ok" : "is-bad"}`}
          role="status"
          aria-live="polite"
        >
          Total {(Math.round(total * 1000) / 10).toString()}%
          {ok ? " ✓" : " — must be 100%"}
        </span>
      </div>
      <div className="chip-row" role="group" aria-label="Mix presets">
        {MIX_PRESETS.filter((p) => allowCarsOnlyNull || p.mix !== null).map(
          (p) => (
            <button
              key={p.id}
              type="button"
              className={`chip${preset?.id === p.id ? " is-active" : ""}`}
              aria-pressed={preset?.id === p.id}
              onClick={() => {
                onChange(p.mix ? { ...p.mix } : null);
              }}
              title={p.description}
            >
              {p.label}
            </button>
          ),
        )}
      </div>
      <VehicleMixBar mix={ok ? (value ?? null) : null} />
      <div className="mix-rows">
        {VEHICLE_CLASSES.map((c) => {
          const percent = Math.round(mix[c.id] * 1000) / 10;
          return (
            <div key={c.id} className="mix-row">
              <span
                className="mix-swatch"
                style={{ background: c.color }}
                aria-hidden="true"
              />
              <label
                htmlFor={`${id}-${c.id}`}
                className="mix-name"
                title={c.description}
              >
                {c.label}
              </label>
              <input
                type="range"
                min={0}
                max={100}
                step={1}
                value={percent}
                aria-label={`${c.label} share (%)`}
                onChange={(e) => {
                  setShare(c.id, Number(e.target.value));
                }}
              />
              <input
                id={`${id}-${c.id}`}
                className="mix-number"
                type="number"
                min={0}
                max={100}
                step={0.5}
                value={percent}
                onChange={(e) => {
                  setShare(c.id, Number(e.target.value));
                }}
              />
              <span className="mix-unit">%</span>
            </div>
          );
        })}
      </div>
      {!ok && (
        <p className="q-note is-caution" role="note">
          The shares add up to {(Math.round(total * 1000) / 10).toString()}%.
          Adjust them to 100% — UrbanFlow will not rescale them for you.
        </p>
      )}
    </div>
  );
}
