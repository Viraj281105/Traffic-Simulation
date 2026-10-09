/**
 * Tile illustrations for the research workflow, one per stage. Decorative to
 * assistive technology (aria-hidden): the stage's title and sentences carry
 * the meaning. Stage 1 reuses the scenario builder's own junction plan.
 */
import { JunctionPreview } from "../scenario/JunctionPreview";
import { DEFAULT_SCENARIO } from "../../scenario/scenarioModel";

const TILE = "0 0 120 72";

function Arrow({
  x,
  y,
  deg,
  w,
}: {
  x: number;
  y: number;
  deg: number;
  w: number;
}) {
  return (
    <g
      transform={`translate(${String(x)} ${String(y)}) rotate(${String(deg)})`}
    >
      <line
        className="rl-arrow-line"
        x1="-9"
        y1="0"
        x2="1"
        y2="0"
        strokeWidth={w}
      />
      <polygon className="rl-arrow-head" points="0,-3.4 6,0 0,3.4" />
    </g>
  );
}

export function SetupArt() {
  return (
    <div className="rl-tile rl-tile-plan" aria-hidden="true">
      <JunctionPreview scenario={DEFAULT_SCENARIO} view="signal" />
    </div>
  );
}

export function DemandArt() {
  return (
    <svg className="rl-svg is-tile" viewBox={TILE} aria-hidden="true">
      <rect className="rl-ground" width="120" height="72" />
      <rect className="rl-road" x="50" y="0" width="20" height="72" />
      <rect className="rl-road" x="0" y="26" width="120" height="20" />
      <Arrow x={60} y={13} deg={90} w={3.4} />
      <Arrow x={60} y={59} deg={-90} w={1.6} />
      <Arrow x={17} y={36} deg={0} w={2.6} />
      <Arrow x={103} y={36} deg={180} w={1.2} />
    </svg>
  );
}

export function ControlsArt() {
  return (
    <svg className="rl-svg is-tile" viewBox={TILE} aria-hidden="true">
      <rect className="rl-head" x="12" y="14" width="18" height="44" rx="6" />
      <circle className="rl-lamp-stop" cx="21" cy="25" r="4.5" />
      <circle className="rl-lamp-warn" cx="21" cy="36" r="4.5" />
      <circle className="rl-lamp-go" cx="21" cy="47" r="4.5" />
      <rect className="rl-road" x="46" y="20" width="30" height="32" rx="3" />
      <rect className="rl-zone" x="52" y="26" width="18" height="20" />
      <rect className="rl-car" x="57" y="30" width="8" height="12" rx="2" />
      <circle
        className="rl-ring"
        cx="100"
        cy="36"
        r="13"
        style={{ strokeWidth: 9 }}
      />
      <circle className="rl-island" cx="100" cy="36" r="8.5" />
    </svg>
  );
}

export function RunsArt() {
  const rows = [14, 36, 58];
  return (
    <svg className="rl-svg is-tile" viewBox={TILE} aria-hidden="true">
      {rows.map((y, i) => (
        <g key={y}>
          <text className="rl-note" x="8" y={y + 4}>
            {i + 1}
          </text>
          <line className="rl-ink" x1="20" y1={y} x2="34" y2={y} />
          <rect
            className="rl-seg-warn is-solid"
            x="38"
            y={y - 6}
            width="22"
            height="12"
            rx="3"
          />
          <rect
            className="rl-seg-warn is-outline"
            x="64"
            y={y - 6}
            width="22"
            height="12"
            rx="3"
          />
          <rect
            className="rl-block is-roundabout"
            x="90"
            y={y - 6}
            width="22"
            height="12"
            rx="3"
          />
        </g>
      ))}
    </svg>
  );
}

export function MetricsArt() {
  return (
    <svg className="rl-svg is-tile" viewBox={TILE} aria-hidden="true">
      <line className="rl-axis" x1="14" y1="60" x2="106" y2="60" />
      <rect className="rl-bar" x="20" y="34" width="14" height="26" rx="2" />
      <rect
        className="rl-bar is-accent"
        x="42"
        y="18"
        width="14"
        height="42"
        rx="2"
      />
      <rect className="rl-bar" x="64" y="40" width="14" height="20" rx="2" />
      <rect
        className="rl-bar is-accent"
        x="86"
        y="28"
        width="14"
        height="32"
        rx="2"
      />
    </svg>
  );
}

export function StatsArt() {
  return (
    <svg className="rl-svg is-tile" viewBox={TILE} aria-hidden="true">
      <line className="rl-zero" x1="60" y1="8" x2="60" y2="64" />
      <line className="rl-ci" x1="68" y1="22" x2="104" y2="22" />
      <line className="rl-ci" x1="68" y1="17" x2="68" y2="27" />
      <line className="rl-ci" x1="104" y1="17" x2="104" y2="27" />
      <rect
        className="rl-mean"
        x="82"
        y="18"
        width="8"
        height="8"
        transform="rotate(45 86 22)"
      />
      <line className="rl-ci" x1="30" y1="48" x2="84" y2="48" />
      <line className="rl-ci" x1="30" y1="43" x2="30" y2="53" />
      <line className="rl-ci" x1="84" y1="43" x2="84" y2="53" />
      <rect
        className="rl-mean"
        x="53"
        y="44"
        width="8"
        height="8"
        transform="rotate(45 57 48)"
      />
    </svg>
  );
}

export function FindingsArt() {
  const chips = [
    { y: 8, label: "lower" },
    { y: 28, label: "about the same" },
    { y: 48, label: "inconclusive" },
  ];
  return (
    <svg className="rl-svg is-tile" viewBox={TILE} aria-hidden="true">
      {chips.map((c) => (
        <g key={c.label}>
          <rect
            className="rl-chip"
            x="14"
            y={c.y}
            width="92"
            height="16"
            rx="8"
          />
          <text
            className="rl-chip-text"
            x="60"
            y={c.y + 11.5}
            textAnchor="middle"
          >
            {c.label}
          </text>
        </g>
      ))}
    </svg>
  );
}
