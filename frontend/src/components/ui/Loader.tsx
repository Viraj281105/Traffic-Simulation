/**
 * UrbanFlow's loading mark: a small roundabout with three vehicles
 * circulating. It replaces a plain spinner inside an existing loading
 * message and is shown only while real work is in progress.
 */
/** Just the animated roundabout mark, for an existing loading message that
 *  already carries its own text (it replaces a plain spinner in place). */
export function LoaderMark({ size = 20 }: { size?: number }) {
  return (
    <span className="uf-loader uf-loader-mark" aria-hidden="true">
      <svg width={size} height={size} viewBox="0 0 48 48">
        <path
          className="uf-loader__road"
          d="M24 0v10M24 38v10M0 24h10M38 24h10"
          strokeWidth="3"
        />
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
    </span>
  );
}
