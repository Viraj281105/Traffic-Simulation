/**
 * UrbanFlow's loading indicator: a small roundabout with three vehicles
 * circulating. One component, used wherever real work is in progress —
 * never shown for a fixed time, and never used to delay a ready page.
 */
interface LoaderProps {
  /** What is being waited for, e.g. "Loading saved runs". */
  label?: string;
  /** Layout: centred block (default), filling its container, or inline. */
  layout?: "block" | "fill" | "inline";
  /** Diagram size in px. */
  size?: number;
}

export function Loader({
  label = "Loading",
  layout = "block",
  size,
}: LoaderProps) {
  const px = size ?? (layout === "inline" ? 20 : 48);
  const className = [
    "uf-loader",
    layout === "inline" ? "uf-loader--inline" : "",
    layout === "fill" ? "uf-loader--fill" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={className} role="status" aria-live="polite">
      <svg width={px} height={px} viewBox="0 0 48 48" aria-hidden="true">
        {/* approach roads */}
        <path
          className="uf-loader__road"
          d="M24 0v10M24 38v10M0 24h10M38 24h10"
          strokeWidth="3"
        />
        {/* circulating carriageway */}
        <circle
          className="uf-loader__road"
          cx="24"
          cy="24"
          r="14"
          strokeWidth="5"
        />
        <circle
          className="uf-loader__island"
          cx="24"
          cy="24"
          r="8"
          strokeWidth="1"
        />
        <rect
          className="uf-loader__car"
          x="-2.5"
          y="-1.5"
          width="5"
          height="3"
          rx="1"
        />
        <rect
          className="uf-loader__car uf-loader__car--2"
          x="-2.5"
          y="-1.5"
          width="5"
          height="3"
          rx="1"
        />
        <rect
          className="uf-loader__car uf-loader__car--3"
          x="-2.5"
          y="-1.5"
          width="5"
          height="3"
          rx="1"
        />
      </svg>
      {layout === "inline" ? (
        <span className="uf-loader__label">{label}</span>
      ) : (
        <p className="uf-loader__label">{label}</p>
      )}
    </div>
  );
}
