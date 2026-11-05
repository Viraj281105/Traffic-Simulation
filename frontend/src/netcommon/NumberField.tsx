import { useId, useState } from "react";
import "./network.css";

/**
 * A number input that lets the person type freely ("1." on the way to "1.2")
 * and only keeps the value inside [min, max] when they leave the field. The
 * parent always receives a finite number inside the range.
 */
export function NumberField({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max?: number;
  step?: number;
  onChange: (value: number) => void;
}) {
  const id = useId();
  const [draft, setDraft] = useState<string | null>(null);
  const clamp = (v: number) =>
    Math.min(max ?? Number.POSITIVE_INFINITY, Math.max(min, v));
  return (
    <div className="uf-field">
      <label className="uf-label" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        className="uf-input"
        type="number"
        min={min}
        max={max}
        step={step}
        value={draft ?? String(value)}
        onChange={(e) => {
          setDraft(e.target.value);
          const v = e.target.valueAsNumber;
          if (Number.isFinite(v)) onChange(clamp(v));
        }}
        onBlur={() => {
          setDraft(null);
        }}
      />
    </div>
  );
}
