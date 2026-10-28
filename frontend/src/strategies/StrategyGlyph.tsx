import type { StrategyInfo } from "./strategyCatalog";

/** A small plan-view drawing of a strategy: a crossroads with signal heads
 *  for the signals (sensor arcs for the adaptive one), a ring for the
 *  roundabouts (entry lights for the metered one). Drawn in the strategy's
 *  colour; decorative, so hidden from assistive technology. */
export function StrategyGlyph({
  strategy,
  size = 44,
}: {
  strategy: Pick<StrategyInfo, "glyph" | "color">;
  size?: number;
}) {
  const g = strategy.glyph;
  const signal = g === "fixed" || g === "adaptive" || g === "signal";
  return (
    <svg
      className="strategy-glyph"
      width={size}
      height={size}
      viewBox="0 0 48 48"
      aria-hidden="true"
      focusable="false"
      style={{ color: strategy.color }}
    >
      <rect
        x="1"
        y="1"
        width="46"
        height="46"
        rx="12"
        fill="currentColor"
        opacity="0.12"
      />
      {signal ? (
        <>
          <path
            d="M19 6h10v13h13v10H29v13H19V29H6V19h13z"
            fill="var(--color-text-3)"
            opacity="0.38"
          />
          {[
            [15, 15],
            [33, 15],
            [15, 33],
            [33, 33],
          ].map(([cx, cy], i) => (
            <circle
              key={`${String(cx)}-${String(cy)}`}
              cx={cx}
              cy={cy}
              r="3"
              fill={i % 3 === 0 ? "currentColor" : "var(--color-text-3)"}
            />
          ))}
          {g === "adaptive" && (
            <g fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M19.5 10.5a7 7 0 0 1 9 0" strokeLinecap="round" />
              <path d="M17 7.5a11 11 0 0 1 14 0" strokeLinecap="round" />
            </g>
          )}
          {g === "fixed" && (
            <g fill="none" stroke="currentColor" strokeWidth="1.8">
              <circle cx="24" cy="24" r="4.5" />
              <path d="M24 21.5V24l1.8 1.2" strokeLinecap="round" />
            </g>
          )}
        </>
      ) : (
        <>
          <path
            d="M21 4h6v10h-6zM21 34h6v10h-6zM4 21h10v6H4zM34 21h10v6H34z"
            fill="var(--color-text-3)"
            opacity="0.38"
          />
          <circle
            cx="24"
            cy="24"
            r="10"
            fill="none"
            stroke="currentColor"
            strokeWidth="4"
          />
          <circle
            cx="24"
            cy="24"
            r="4"
            fill="var(--color-text-3)"
            opacity="0.5"
          />
          {g === "metered" &&
            [
              [24, 10],
              [38, 24],
              [24, 38],
              [10, 24],
            ].map(([cx, cy]) => (
              <circle
                key={`${String(cx)}-${String(cy)}`}
                cx={cx}
                cy={cy}
                r="2.6"
                fill="var(--color-bg, #fff)"
                stroke="currentColor"
                strokeWidth="1.6"
              />
            ))}
        </>
      )}
    </svg>
  );
}
