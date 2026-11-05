import "../netcommon/network.css";
import { num } from "../netcommon/format";

const W = 640;
const ROW = 24;
const LEFT = 70;
const RIGHT = 20;
const TOP = 8;

/** One row per seed with a dot for each arm joined by a line: the pairing is
 *  the point, because both arms of a seed share the same traffic. */
export function PairedChart({
  seeds,
  baseline,
  treated,
  baselineLabel,
  treatedLabel,
  unit,
  ariaLabel,
}: {
  seeds: number[];
  baseline: number[];
  treated: number[];
  baselineLabel: string;
  treatedLabel: string;
  unit: string;
  ariaLabel: string;
}) {
  const n = Math.min(seeds.length, baseline.length, treated.length);
  if (n === 0) return <p className="nw-muted">There is nothing to plot yet.</p>;
  const all = [...baseline.slice(0, n), ...treated.slice(0, n)];
  const lo = Math.min(0, ...all);
  let hi = Math.max(...all);
  if (hi === lo) hi = lo + 1;
  const pw = W - LEFT - RIGHT;
  const sx = (v: number) => LEFT + ((v - lo) / (hi - lo)) * pw;
  const height = TOP + n * ROW + 40;
  const ticks = [lo, lo + (hi - lo) / 2, hi];
  return (
    <figure className="nw-stack" style={{ margin: 0 }}>
      <svg
        className="nw-svg"
        viewBox={`0 0 ${String(W)} ${String(height)}`}
        role="img"
        aria-label={ariaLabel}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line
              className="nw-svg__grid"
              x1={sx(t)}
              x2={sx(t)}
              y1={TOP}
              y2={TOP + n * ROW}
            />
            <text
              className="nw-svg__tick"
              x={sx(t)}
              y={TOP + n * ROW + 14}
              textAnchor="middle"
            >
              {num(t, 1)}
            </text>
          </g>
        ))}
        {seeds.slice(0, n).map((seed, i) => {
          const mid = TOP + i * ROW + ROW / 2;
          return (
            <g key={seed} data-seed={seed}>
              <text
                className="nw-svg__label"
                x={LEFT - 8}
                y={mid + 4}
                textAnchor="end"
              >
                {`Seed ${String(seed)}`}
              </text>
              <line
                className="nw-svg__axis"
                x1={sx(baseline[i])}
                x2={sx(treated[i])}
                y1={mid}
                y2={mid}
              />
              <circle
                className="nw-dot is-peak"
                cx={sx(baseline[i])}
                cy={mid}
                r={5}
              >
                <title>{`${baselineLabel}: ${num(baseline[i])} ${unit}`}</title>
              </circle>
              <circle className="nw-dot" cx={sx(treated[i])} cy={mid} r={5}>
                <title>{`${treatedLabel}: ${num(treated[i])} ${unit}`}</title>
              </circle>
            </g>
          );
        })}
        <text
          className="nw-svg__tick"
          x={LEFT + pw / 2}
          y={height - 4}
          textAnchor="middle"
        >
          {unit}
        </text>
      </svg>
      <figcaption>
        <ul className="nw-legend">
          <li>
            <span style={{ color: "var(--color-danger)" }} aria-hidden="true">
              ●
            </span>{" "}
            {baselineLabel}
          </li>
          <li>
            <span style={{ color: "var(--color-accent)" }} aria-hidden="true">
              ●
            </span>{" "}
            {treatedLabel}
          </li>
        </ul>
      </figcaption>
    </figure>
  );
}
