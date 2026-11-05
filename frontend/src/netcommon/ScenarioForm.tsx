import { useId, useState } from "react";
import "./network.css";
import { NumberField } from "./NumberField";
import { LIMITS, type GridPreset, type ScenarioInput } from "./scenario";

/** The grid scenario form shared by the map, congestion and metrics tabs. */
export function ScenarioForm({
  initial,
  busy,
  runLabel,
  onRun,
  secondary,
  children,
}: {
  initial: ScenarioInput;
  busy: boolean;
  runLabel: string;
  onRun: (scenario: ScenarioInput) => void;
  /** A second, quieter action on the same inputs. */
  secondary?: { label: string; onClick: (scenario: ScenarioInput) => void };
  /** Extra fields of the screen, shown after the shared ones. */
  children?: React.ReactNode;
}) {
  const uid = useId();
  const [s, setS] = useState(initial);
  const set = <K extends keyof ScenarioInput>(
    key: K,
    value: ScenarioInput[K],
  ) => {
    setS((prev) => ({ ...prev, [key]: value }));
  };
  const numField = (
    key: "rows" | "cols" | "vehiclesPerHour" | "duration" | "seed",
    label: string,
    limits: readonly [number, number] = [-2147483648, 2147483647],
  ) => (
    <NumberField
      label={label}
      value={s[key]}
      min={limits[0]}
      max={limits[1]}
      onChange={(v) => {
        set(key, v);
      }}
    />
  );
  return (
    <form
      className="nw-form"
      onSubmit={(event) => {
        event.preventDefault();
        onRun(s);
      }}
    >
      <div className="uf-field">
        <label className="uf-label" htmlFor={`${uid}-preset`}>
          Network
        </label>
        <select
          id={`${uid}-preset`}
          className="uf-select"
          value={s.preset}
          onChange={(e) => {
            set("preset", e.target.value as GridPreset);
          }}
        >
          <option value="3x3">3 by 3 grid</option>
          <option value="12-junction">12-junction network</option>
          <option value="custom">Custom grid</option>
        </select>
      </div>
      {s.preset === "custom" && (
        <>
          {numField("rows", "Rows", LIMITS.rows)}
          {numField("cols", "Columns", LIMITS.cols)}
        </>
      )}
      {numField(
        "vehiclesPerHour",
        "Vehicles per hour per entry",
        LIMITS.vehiclesPerHour,
      )}
      {numField("duration", "Duration (s)", LIMITS.duration)}
      {numField("seed", "Seed")}
      {children}
      <button type="submit" className="nw-btn nw-btn--primary" disabled={busy}>
        {busy ? "Running…" : runLabel}
      </button>
      {secondary && (
        <button
          type="button"
          className="nw-btn"
          disabled={busy}
          onClick={() => {
            secondary.onClick(s);
          }}
        >
          {secondary.label}
        </button>
      )}
    </form>
  );
}
