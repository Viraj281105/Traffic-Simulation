const ROWS = [
  { seed: "Seed 1", y: 12 },
  { seed: "Seed 2", y: 52 },
  { seed: "Seed 3", y: 92 },
];

const COLUMNS = [
  { x: 190, name: "Fixed-time", cls: "rl-seg-warn is-solid" },
  { x: 262, name: "Adaptive", cls: "rl-seg-warn is-outline" },
  { x: 334, name: "Roundabout", cls: "rl-block is-roundabout" },
];

/** One row per seed: the same arrival sequence goes to a run of each control.
 *  The seed fixes which vehicles arrive when, so a row is one matched
 *  condition (vehicles/spawner.py). */
export function MatchedSeedsDiagram() {
  return (
    <svg
      className="rl-svg rl-matched"
      viewBox="0 0 420 148"
      role="img"
      aria-label="Each seed is run once under the fixed-time signal, the adaptive signal and the roundabout. For a given seed, all three runs receive the same arrivals, vehicles, geometry, lanes, duration and warm-up. Further seeds repeat the pattern."
    >
      {COLUMNS.map((c) => (
        <text
          key={c.name}
          className="rl-note is-strong"
          x={c.x + 25}
          y="8"
          textAnchor="middle"
        >
          {c.name}
        </text>
      ))}
      {ROWS.map((row) => (
        <g key={row.seed}>
          <rect
            className="rl-seed-tile"
            x="8"
            y={row.y + 6}
            width="76"
            height="26"
            rx="6"
          />
          <text
            className="rl-note is-strong"
            x="46"
            y={row.y + 23}
            textAnchor="middle"
          >
            {row.seed}
          </text>
          <path
            className="rl-ink"
            d={`M84 ${String(row.y + 19)} H112 M112 ${String(row.y + 19)} H132`}
          />
          <rect
            className="rl-bracket"
            x="132"
            y={row.y + 2}
            width="248"
            height="34"
            rx="8"
          />
          {COLUMNS.map((c) => (
            <rect
              key={c.name}
              className={c.cls}
              x={c.x}
              y={row.y + 8}
              width="50"
              height="22"
              rx="4"
            />
          ))}
        </g>
      ))}
      <text className="rl-note" x="46" y="140" textAnchor="middle">
        … more seeds
      </text>
      <text className="rl-note" x="256" y="140" textAnchor="middle">
        each row: one matched condition, same arrivals for all three
      </text>
    </svg>
  );
}
