import "../netcommon/network.css";
import { num } from "../netcommon/format";

export interface Bar {
  id: string;
  label: string;
  value: number;
  /** [low, high] drawn as a whisker; null when there is none (one seed). */
  interval: readonly [number, number] | null;
}

const W = 640;
const ROW = 34;
const LEFT = 130;
const RIGHT = 24;
const TOP = 8;

/** Horizontal bars on a fixed scale with an optional interval whisker. The
 *  value and interval are also written beside each bar, so the numbers do not
 *  depend on the drawing. */
export function BarChart({
  bars,
  max = 1,
  ariaLabel,
  axisLabel,
  digits = 2,
}: {
  bars: Bar[];
  max?: number;
  ariaLabel: string;
  axisLabel: string;
  digits?: number;
}) {
  if (bars.length === 0) {
    return <p className="nw-muted">There is nothing to plot yet.</p>;
  }
  const height = TOP + bars.length * ROW + 28;
  const pw = W - LEFT - RIGHT - 120;
  const sx = (v: number) => LEFT + (Math.min(max, Math.max(0, v)) / max) * pw;
  return (
    <figure className="nw-stack" style={{ margin: 0 }}>
      <svg
        className="nw-svg"
        viewBox={`0 0 ${String(W)} ${String(height)}`}
        role="img"
        aria-label={ariaLabel}
      >
        <line
          className="nw-svg__axis"
          x1={LEFT}
          x2={LEFT}
          y1={TOP}
          y2={TOP + bars.length * ROW}
        />
        {bars.map((b, i) => {
          const y = TOP + i * ROW;
          const mid = y + ROW / 2;
          return (
            <g key={b.id} data-bar={b.id}>
              <text
                className="nw-svg__label"
                x={LEFT - 8}
                y={mid + 4}
                textAnchor="end"
              >
                {b.label}
              </text>
              <rect
                className="nw-dot"
                x={LEFT}
                y={y + 6}
                width={Math.max(1, sx(b.value) - LEFT)}
                height={ROW - 12}
              />
              {b.interval && (
                <g className="nw-svg__axis">
                  <line
                    x1={sx(b.interval[0])}
                    x2={sx(b.interval[1])}
                    y1={mid}
                    y2={mid}
                  />
                  <line
                    x1={sx(b.interval[0])}
                    x2={sx(b.interval[0])}
                    y1={mid - 6}
                    y2={mid + 6}
                  />
                  <line
                    x1={sx(b.interval[1])}
                    x2={sx(b.interval[1])}
                    y1={mid - 6}
                    y2={mid + 6}
                  />
                </g>
              )}
              <text className="nw-svg__label" x={LEFT + pw + 8} y={mid + 4}>
                {num(b.value, digits)}
                {b.interval
                  ? ` (${num(b.interval[0], digits)} to ${num(b.interval[1], digits)})`
                  : ""}
              </text>
            </g>
          );
        })}
        <text
          className="nw-svg__tick"
          x={LEFT + pw / 2}
          y={height - 6}
          textAnchor="middle"
        >
          {axisLabel}
        </text>
      </svg>
    </figure>
  );
}
