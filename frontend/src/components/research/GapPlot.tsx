/**
 * The gap between two controls (A minus B, in seconds of average delay): each
 * run's gap as a dot, the mean gap with its 95 % interval, zero marked, and
 * optionally the "about the same" band. Used by the overview's comparison
 * explainer and the methods page, always with labelled example numbers.
 */
export function GapPlot({
  diffs,
  mean,
  low,
  high,
  domain,
  tieBand,
  label,
}: {
  diffs: readonly number[];
  mean: number;
  low: number;
  high: number;
  domain: readonly [number, number];
  tieBand?: number;
  label: string;
}) {
  const [d0, d1] = domain;
  const x = (v: number) => 24 + ((v - d0) / (d1 - d0)) * 312;
  const ticks: number[] = [];
  for (let t = Math.ceil(d0 / 5) * 5; t <= d1; t += 5) ticks.push(t);
  return (
    <svg
      className="rl-svg rl-plot"
      viewBox="0 0 360 124"
      role="img"
      aria-label={label}
    >
      {tieBand !== undefined && (
        <rect
          className="rl-band"
          x={x(-tieBand)}
          y="22"
          width={x(tieBand) - x(-tieBand)}
          height="62"
        />
      )}
      <line className="rl-zero" x1={x(0)} y1="16" x2={x(0)} y2="86" />
      <text className="rl-note" x={x(0)} y="11" textAnchor="middle">
        no difference
      </text>
      <line className="rl-axis" x1="24" y1="88" x2="336" y2="88" />
      {ticks.map((t) => (
        <g key={t}>
          <line className="rl-axis" x1={x(t)} y1="88" x2={x(t)} y2="92" />
          <text className="rl-tick-label" x={x(t)} y="102" textAnchor="middle">
            {t}
          </text>
        </g>
      ))}
      {diffs.map((d, i) => (
        <circle
          key={i}
          className="rl-dot is-run"
          cx={x(d)}
          cy={34 + (i % 3) * 8}
          r="3"
        />
      ))}
      <line className="rl-ci" x1={x(low)} y1="68" x2={x(high)} y2="68" />
      <line className="rl-ci" x1={x(low)} y1="62" x2={x(low)} y2="74" />
      <line className="rl-ci" x1={x(high)} y1="62" x2={x(high)} y2="74" />
      <rect
        className="rl-mean"
        x={x(mean) - 5}
        y="63"
        width="10"
        height="10"
        transform={`rotate(45 ${String(x(mean))} 68)`}
      />
      <text className="rl-note" x="180" y="118" textAnchor="middle">
        A − B, average delay (s)
      </text>
    </svg>
  );
}
