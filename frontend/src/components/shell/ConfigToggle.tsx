import { useId } from "react";

/** An On/Off switch for a map display option. */
export function ConfigToggle({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  const id = useId();
  return (
    <div className="config-item config-toggle-item">
      <span className="config-label" id={id}>
        {label}
      </span>
      <button
        type="button"
        className={`toggle-btn ${value ? "toggle-on" : "toggle-off"}`}
        aria-pressed={value}
        aria-labelledby={id}
        onClick={() => {
          onChange(!value);
        }}
      >
        {value ? "On" : "Off"}
      </button>
    </div>
  );
}
