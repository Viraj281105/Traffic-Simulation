/** Contract fixtures for the map viewer: a small one-way corridor (the
 *  two-junction scenario of backend/src/networks/corridor.py, oneway), in the
 *  shape map_data() returns. Not real measurements. */
import type { GridResponse, MapData, MapLink, MapNode } from "./types";

const node = (
  id: string,
  kind: MapNode["kind"],
  signal: boolean,
  x: number,
  y: number,
): MapNode => ({ id, kind, signal, x, y });

const nodes: MapNode[] = [
  node("E", "gate", false, 700, 0),
  node("J1", "junction", true, 0, 0),
  node("J2", "junction", true, 400, 0),
  node("N1", "gate", false, 0, 300),
  node("S2", "gate", false, 400, -300),
  node("W", "gate", false, -300, 0),
];

const at = (id: string) => {
  const found = nodes.find((n) => n.id === id);
  if (!found) throw new Error(`fixture node ${id}`);
  return found;
};

function link(
  from: string,
  to: string,
  lanes: number,
  speed: number,
  value?: number,
): MapLink {
  const a = at(from);
  const b = at(to);
  return {
    id: `${from}>${to}`,
    from,
    to,
    name: null,
    length: Math.abs(b.x - a.x) + Math.abs(b.y - a.y),
    lanes,
    speed,
    path: [
      [a.x, a.y],
      [b.x, b.y],
    ],
    bearingDegrees:
      Math.round(
        (((Math.atan2(b.x - a.x, b.y - a.y) * 180) / Math.PI + 360) % 360) * 10,
      ) / 10,
    ...(value === undefined ? {} : { value }),
  };
}

const specs: [string, string, number, number, number][] = [
  ["J1", "J2", 2, 13.89, 0.62],
  ["J2", "E", 2, 13.89, 0.12],
  ["J2", "S2", 1, 11.11, 0.05],
  ["N1", "J1", 1, 11.11, 0.31],
  ["W", "J1", 2, 13.89, 0.28],
];

export const corridorMap: MapData = {
  format: "urbanflow-map-data",
  version: 1,
  name: "Two-junction corridor",
  hasGeo: false,
  boundsLocal: { minX: -300, maxX: 700, minY: -300, maxY: 300 },
  nodes,
  links: specs.map(([f, t, lanes, speed, v]) => link(f, t, lanes, speed, v)),
  valueLabel: "meanOccupancyRatio",
};

export const gridFixture: GridResponse = {
  graph: { format: "urbanflow-graph", version: 1, name: corridorMap.name },
  flows: [
    { origin: "W", destination: "E", vehiclesPerHour: 600 },
    { origin: "N1", destination: "S2", vehiclesPerHour: 150 },
  ],
  validation: {
    valid: true,
    errors: [],
    warnings: [],
    stats: { nodes: 6, links: 5, junctions: 2, gates: 4, signals: 2 },
  },
  map: {
    ...corridorMap,
    links: specs.map(([f, t, lanes, speed]) => link(f, t, lanes, speed)),
    valueLabel: undefined,
  },
};
