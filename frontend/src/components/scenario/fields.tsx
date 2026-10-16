import { useId } from "react";

export function NumberField({
  label,
  value,
  onChange,
  min,
  max,
  step,
  unit,
  placeholder,
}: {
  label: string;
  value: number | null | undefined;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  placeholder?: string;
}) {
  const id = useId();
  return (
    <div className="sb-field">
      <label className="sb-field-label" htmlFor={id}>
        {label}
      </label>
      <div className="sb-inline">
        <input
          id={id}
          type="number"
          value={value ?? ""}
          placeholder={placeholder}
          min={min}
          max={max}
          step={step}
          onChange={(e) => {
            if (e.target.value !== "") onChange(Number(e.target.value));
          }}
        />
        {unit && <span className="sb-unit">{unit}</span>}
      </div>
    </div>
  );
}

export function Stepper({
  value,
  min,
  max,
  onChange,
  label,
}: {
  value: number;
  min: number;
  max: number;
  onChange: (v: number) => void;
  label: string;
}) {
  return (
    <div className="stepper" role="group" aria-label={label}>
      <button
        type="button"
        aria-label={`Fewer ${label.toLowerCase()}`}
        disabled={value <= min}
        onClick={() => {
          onChange(value - 1);
        }}
      >
        −
      </button>
      <span aria-live="polite">{value}</span>
      <button
        type="button"
        aria-label={`More ${label.toLowerCase()}`}
        disabled={value >= max}
        onClick={() => {
          onChange(value + 1);
        }}
      >
        +
      </button>
    </div>
  );
}
