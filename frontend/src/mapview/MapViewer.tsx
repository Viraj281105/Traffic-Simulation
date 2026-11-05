import { useId, useMemo, useState } from "react";
import "../netcommon/network.css";
import { RAMP_STOPS, rampColor } from "../netcommon/colors";
import { num } from "../netcommon/format";
import type { LinkMetrics } from "../netmetrics/types";
import { linkValue, metricOptions } from "./linkMetrics";
import type { MapData } from "./types";

const WIDTH = 760;
const MARGIN = 36;

/**
 * Multi-junction map. Draws the network from its local x/y metres (north up),
 * so it needs no map tiles and works when the network has no coordinates
 * (`hasGeo` false). Links are coloured by the chosen metric; wider lines are
 * links with more lanes. Gates (where vehicles enter and leave) are hollow
 * circles, junctions are filled, and a signalised junction has a ring.
 */
export function MapViewer({
  map,
  perLink,
}: {
  map: MapData;
  /** The run's per-link metrics (`perLink` of the simulate answer). */
  perLink?: Record<string, LinkMetrics>;
}) {
  const uid = useId();
  const options = useMemo(() => metricOptions(map, perLink), [map, perLink]);
  const [chosen, setChosen] = useState(options[0].key);
  const metric = options.find((o) => o.key === chosen) ?? options[0];
  const key = metric.key;

  const values = map.links.map((l) => linkValue(l, key, perLink));
  const finite = values.filter((v): v is number => v !== null);
  const top = metric.fixedMax ?? (finite.length ? Math.max(...finite) : 1);
  const scaleMax = top > 0 ? top : 1;

  const b = map.boundsLocal;
  const spanX = Math.max(b.maxX - b.minX, 1);
  const spanY = Math.max(b.maxY - b.minY, 1);
  const scale = (WIDTH - 2 * MARGIN) / spanX;
  const height = Math.round(spanY * scale + 2 * MARGIN);
  const px = (x: number) => MARGIN + (x - b.minX) * scale;
  const py = (y: number) => height - MARGIN - (y - b.minY) * scale;

  const ranked = map.links
    .map((l, i) => ({ id: l.id, v: values[i] }))
    .filter((r): r is { id: string; v: number } => r.v !== null)
    .sort((x, y) => y.v - x.v || x.id.localeCompare(y.id))
    .slice(0, 5);
  const unit = metric.unit;
  const kinds = {
    gates: map.nodes.filter((n) => n.kind === "gate").length,
    junctions: map.nodes.filter((n) => n.kind === "junction").length,
    signals: map.nodes.filter((n) => n.signal).length,
  };

  return (
    <div className="nw-stack">
      <div className="nw-form">
        <div className="uf-field">
          <label className="uf-label" htmlFor={`${uid}-metric`}>
            Colour roads by
          </label>
          <select
            id={`${uid}-metric`}
            className="uf-select"
            value={key}
            onChange={(e) => {
              setChosen(e.target.value);
            }}
          >
            {options.map((o) => (
              <option key={o.key} value={o.key}>
                {o.label}
                {o.unit ? ` (${o.unit})` : ""}
              </option>
            ))}
          </select>
        </div>
        <p className="nw-muted">
          {map.name}: {map.nodes.length} nodes, {map.links.length} links.{" "}
          {map.hasGeo
            ? "Real-world coordinates are available."
            : "Drawn in local metres; no real-world coordinates."}
        </p>
      </div>
      <svg
        className="nw-map"
        viewBox={`0 0 ${String(WIDTH)} ${String(height)}`}
        role="img"
        aria-label={`Map of ${map.name}: roads coloured by ${metric.label}`}
      >
        {map.links.map((l, i) => {
          const v = values[i];
          const [[x1, y1], [x2, y2]] = l.path;
          return (
            <line
              key={l.id}
              data-link={l.id}
              x1={px(x1)}
              y1={py(y1)}
              x2={px(x2)}
              y2={py(y2)}
              stroke={
                v === null ? "var(--color-text-3)" : rampColor(v / scaleMax)
              }
              strokeWidth={3 + 2 * l.lanes}
              strokeLinecap="round"
            >
              <title>
                {`${l.id}: ${v === null ? "no value" : `${num(v, 3)} ${unit}`.trim()}`}
              </title>
            </line>
          );
        })}
        {map.nodes.map((n) => (
          <g key={n.id}>
            <circle
              data-node={n.id}
              className={`nw-map__node is-${n.kind}${n.signal ? " is-signal" : ""}`}
              cx={px(n.x)}
              cy={py(n.y)}
              r={n.kind === "gate" ? 6 : 8}
            >
              <title>{`${n.id} (${n.kind}${n.signal ? ", signalised" : ""})`}</title>
            </circle>
            <text
              className="nw-svg__label"
              x={px(n.x) + 10}
              y={py(n.y) - 8}
              aria-hidden="true"
            >
              {n.id}
            </text>
          </g>
        ))}
      </svg>
      <div
        className="nw-ramp"
        role="group"
        aria-label={`Legend: ${metric.label}`}
      >
        <span>Low</span>
        {RAMP_STOPS.map((s) => (
          <span
            key={s}
            className="nw-ramp__cell"
            style={{ background: rampColor(s) }}
          >
            <span className="sr-only">{num(s * scaleMax, 2)}</span>
          </span>
        ))}
        <span>
          High ({num(scaleMax, 2)}
          {unit ? ` ${unit}` : ""})
        </span>
      </div>
      <ul className="nw-facts" aria-label="Node kinds">
        <li>
          Hollow circle: gate, where vehicles enter or leave ({kinds.gates}).
        </li>
        <li>Filled circle: junction ({kinds.junctions}).</li>
        <li>Blue ring: junction controlled by a signal ({kinds.signals}).</li>
        <li>Thicker line: more lanes.</li>
      </ul>
      {ranked.length > 0 && (
        <p>
          Highest {metric.label.toLowerCase()}:{" "}
          {ranked.map((r) => `${r.id} (${num(r.v, 3)})`).join(", ")}.
        </p>
      )}
    </div>
  );
}
