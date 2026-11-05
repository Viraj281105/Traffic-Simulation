import "./network.css";

export interface LinePoint {
  x: number;
  /** null leaves a gap: a value that could not be computed is not zero. */
  y: number | null;
}

export interface LineSeries {
  id: string;
  label: string;
  tone?: "a" | "b" | "c" | "d";
  dashed?: boolean;
  points: LinePoint[];
}

const W = 640;
const H = 240;
const PAD = { left: 52, right: 14, top: 10, bottom: 38 };

function ticks(lo: number, hi: number, count = 5): number[] {
  if (hi === lo) return [lo];
  return Array.from(
    { length: count },
    (_, i) => lo + ((hi - lo) * i) / (count - 1),
  );
}

function tickText(v: number): string {
  return Number(v.toFixed(Math.abs(v) < 10 ? 2 : 0)).toLocaleString("en-US");
}

/** A plain SVG line chart with a legend; several series share one scale. */
export function LineChart({
  series,
  xLabel,
  yLabel,
  ariaLabel,
}: {
  series: LineSeries[];
  xLabel: string;
  yLabel: string;
  ariaLabel: string;
}) {
  const xs: number[] = [];
  const ys: number[] = [];
  for (const s of series) {
    for (const p of s.points) {
      xs.push(p.x);
      if (p.y !== null && Number.isFinite(p.y)) ys.push(p.y);
    }
  }
  if (xs.length === 0 || ys.length === 0) {
    return <p className="nw-muted">There is nothing to plot yet.</p>;
  }
  const xLo = Math.min(...xs);
  let xHi = Math.max(...xs);
  if (xHi === xLo) xHi = xLo + 1;
  const yLo = Math.min(0, ...ys);
  let yHi = Math.max(...ys);
  if (yHi === yLo) yHi = yLo + 1;
  const pw = W - PAD.left - PAD.right;
  const ph = H - PAD.top - PAD.bottom;
  const sx = (v: number) => PAD.left + ((v - xLo) / (xHi - xLo)) * pw;
  const sy = (v: number) => PAD.top + ph - ((v - yLo) / (yHi - yLo)) * ph;
  return (
    <figure className="nw-stack" style={{ margin: 0 }}>
      <svg
        className="nw-svg"
        viewBox={`0 0 ${String(W)} ${String(H)}`}
        role="img"
        aria-label={ariaLabel}
      >
        {ticks(yLo, yHi).map((t) => (
          <g key={`y${String(t)}`}>
            <line
              className="nw-svg__grid"
              x1={PAD.left}
              x2={W - PAD.right}
              y1={sy(t)}
              y2={sy(t)}
            />
            <text
              className="nw-svg__tick"
              x={PAD.left - 6}
              y={sy(t) + 4}
              textAnchor="end"
            >
              {tickText(t)}
            </text>
          </g>
        ))}
        {ticks(xLo, xHi).map((t) => (
          <text
            key={`x${String(t)}`}
            className="nw-svg__tick"
            x={sx(t)}
            y={H - PAD.bottom + 16}
            textAnchor="middle"
          >
            {tickText(t)}
          </text>
        ))}
        <line
          className="nw-svg__axis"
          x1={PAD.left}
          x2={W - PAD.right}
          y1={PAD.top + ph}
          y2={PAD.top + ph}
        />
        <line
          className="nw-svg__axis"
          x1={PAD.left}
          x2={PAD.left}
          y1={PAD.top}
          y2={PAD.top + ph}
        />
        <text
          className="nw-svg__tick"
          x={PAD.left + pw / 2}
          y={H - 4}
          textAnchor="middle"
        >
          {xLabel}
        </text>
        <text
          className="nw-svg__tick"
          transform={`translate(12 ${String(PAD.top + ph / 2)}) rotate(-90)`}
          textAnchor="middle"
        >
          {yLabel}
        </text>
        {series.map((s) => {
          // Break the line at gaps so a missing value is not drawn as zero.
          const runs: { x: number; y: number }[][] = [[]];
          for (const p of s.points) {
            if (p.y === null || !Number.isFinite(p.y)) runs.push([]);
            else runs[runs.length - 1].push({ x: p.x, y: p.y });
          }
          return runs
            .filter((r) => r.length > 0)
            .map((r, i) => (
              <polyline
                key={`${s.id}-${String(i)}`}
                className={`nw-line is-${s.tone ?? "a"}${s.dashed ? " is-dashed" : ""}`}
                points={r
                  .map((p) => `${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`)
                  .join(" ")}
              />
            ));
        })}
      </svg>
      <figcaption>
        <ul className="nw-legend">
          {series.map((s) => (
            <li key={s.id}>
              <span
                className={`nw-swatch is-${s.tone ?? "a"}${s.dashed ? " is-dashed" : ""}`}
                aria-hidden="true"
              />
              {s.label}
            </li>
          ))}
        </ul>
      </figcaption>
    </figure>
  );
}
