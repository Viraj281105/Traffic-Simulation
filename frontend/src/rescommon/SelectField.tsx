import { useId } from "react";
import "../netcommon/network.css";

/** A labelled drop-down. */
export function SelectField<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { id: T; label: string }[];
  onChange: (value: T) => void;
}) {
  const id = useId();
  return (
    <div className="uf-field">
      <label className="uf-label" htmlFor={id}>
        {label}
      </label>
      <select
        id={id}
        className="uf-select"
        value={value}
        onChange={(e) => {
          onChange(e.target.value as T);
        }}
      >
        {options.map((o) => (
          <option key={o.id} value={o.id}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
