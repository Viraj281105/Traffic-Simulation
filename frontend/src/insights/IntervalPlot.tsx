import { isNum, num } from "./format";

export interface IntervalRow {
  id: string;
  label: string;
  value: number | null;
  /** 95% (or stated) interval; omitted when the server gave none. */
  ci?: readonly [number, number] | null;
  tone?: "accent" | "good" | "warn" | "muted";
}

const ROW_H = 34;
const LABEL_W = 170;
const RIGHT_PAD = 24;
const WIDTH = 640;

/**
 * Dot-and-whisker chart: one row per item, a dot for the value and a bar for
 * its confidence interval. Plain SVG so it prints and scales with the page.
 * Rows with no value are listed as "not available" rather than drawn at zero.
 */
export function IntervalPlot({
  rows,
  unit,
  ariaLabel,
  reference,
  referenceLabel,
}: {
  rows: IntervalRow[];
  unit: string;
  ariaLabel: string;
  /** A vertical guide, for example 0 for "no difference". */
  reference?: number;
  referenceLabel?: string;
}) {
  const xs: number[] = [];
  for (const row of rows) {
    if (isNum(row.value)) xs.push(row.value);
    if (row.ci) xs.push(row.ci[0], row.ci[1]);
  }
  if (isNum(reference)) xs.push(reference);
  let lo = xs.length ? Math.min(...xs) : 0;
  let hi = xs.length ? Math.max(...xs) : 1;
  if (lo === hi) {
    lo -= 1;
    hi += 1;
  }
  const pad = (hi - lo) * 0.06;
  lo -= pad;
  hi += pad;
  const plotW = WIDTH - LABEL_W - RIGHT_PAD;
  const x = (v: number) => LABEL_W + ((v - lo) / (hi - lo)) * plotW;
  const height = rows.length * ROW_H + 36;
  const axisY = rows.length * ROW_H + 6;
  const ticks = [lo + pad, (lo + hi) / 2, hi - pad];

  return (
    <svg
      className="ins-plot"
      viewBox={`0 0 ${String(WIDTH)} ${String(height)}`}
      role="img"
      aria-label={ariaLabel}
    >
      {isNum(reference) && (
        <g>
          <line
            className="ins-plot__ref"
            x1={x(reference)}
            x2={x(reference)}
            y1={0}
            y2={axisY}
          />
          {referenceLabel && (
            <text
              className="ins-plot__tick"
              x={x(reference)}
              y={axisY + 28}
              textAnchor="middle"
            >
              {referenceLabel}
            </text>
          )}
        </g>
      )}
      {rows.map((row, i) => {
        const cy = i * ROW_H + ROW_H / 2;
        const tone = row.tone ?? "accent";
        return (
          <g key={row.id}>
            <text className="ins-plot__label" x={0} y={cy + 4}>
              {row.label.length > 26 ? `${row.label.slice(0, 25)}…` : row.label}
            </text>
            {isNum(row.value) ? (
              <>
                {row.ci && (
                  <>
                    <line
                      className={`ins-plot__ci is-${tone}`}
                      x1={x(row.ci[0])}
                      x2={x(row.ci[1])}
                      y1={cy}
                      y2={cy}
                    />
                    <line
                      className={`ins-plot__ci is-${tone}`}
                      x1={x(row.ci[0])}
                      x2={x(row.ci[0])}
                      y1={cy - 5}
                      y2={cy + 5}
                    />
                    <line
                      className={`ins-plot__ci is-${tone}`}
                      x1={x(row.ci[1])}
                      x2={x(row.ci[1])}
                      y1={cy - 5}
                      y2={cy + 5}
                    />
                  </>
                )}
                <circle
                  className={`ins-plot__dot is-${tone}`}
                  cx={x(row.value)}
                  cy={cy}
                  r={5}
                />
              </>
            ) : (
              <text className="ins-plot__tick" x={LABEL_W} y={cy + 4}>
                not available
              </text>
            )}
          </g>
        );
      })}
      <line
        className="ins-plot__axis"
        x1={LABEL_W}
        x2={LABEL_W + plotW}
        y1={axisY}
        y2={axisY}
      />
      {ticks.map((t, i) => (
        <text
          key={i}
          className="ins-plot__tick"
          x={x(t)}
          y={axisY + 14}
          textAnchor="middle"
        >
          {num(t, 1)}
          {i === 2 && unit ? ` ${unit}` : ""}
        </text>
      ))}
    </svg>
  );
}
