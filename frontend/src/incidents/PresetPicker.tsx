import { useId } from "react";
import "../netcommon/network.css";
import type { Preset } from "./types";

/** The scenario preset picker: one option per catalogue scenario, with the
 *  chosen scenario described underneath. */
export function PresetPicker({
  presets,
  value,
  onChange,
}: {
  presets: Preset[];
  value: string;
  onChange: (id: string) => void;
}) {
  const id = useId();
  const chosen = presets.find((p) => p.id === value);
  return (
    <div className="nw-stack">
      <div className="uf-field">
        <label className="uf-label" htmlFor={id}>
          Scenario preset
        </label>
        <select
          id={id}
          className="uf-select"
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
          }}
        >
          {presets.map((p) => (
            <option key={p.id} value={p.id}>
              {p.title}
            </option>
          ))}
        </select>
      </div>
      {chosen && (
        <p className="nw-muted">
          {chosen.description} Network:{" "}
          {chosen.network.kind === "corridor"
            ? "two-junction corridor"
            : `${String(chosen.network.rows ?? 3)} by ${String(chosen.network.cols ?? 3)} grid`}
          , {String(chosen.duration)} s.
        </p>
      )}
    </div>
  );
}
