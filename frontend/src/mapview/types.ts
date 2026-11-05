/**
 * Contract: map data of the multi-junction viewer. Source of truth is
 * backend/src/netmetrics/mapdata.py (map_data), returned as `map` by
 * GET /api/v2/network-metrics/grid and, with `includeMap: true`, by
 * POST /api/v2/network-metrics/simulate and /congestion. See
 * src/CONTRACTS_P5.md.
 *
 * Coordinates are local metres (x east, y north). `lat`/`lon` and
 * `pathLatLon` exist only when `hasGeo` is true; the viewer never needs them.
 */

export interface MapNode {
  id: string;
  /** "junction" or "gate" (a network boundary where vehicles enter or leave). */
  kind: "junction" | "gate";
  /** True for a junction controlled by a signal. */
  signal: boolean;
  x: number;
  y: number;
  lat?: number;
  lon?: number;
}

export interface MapLink {
  id: string;
  from: string;
  to: string;
  name?: string | null;
  /** Metres. */
  length: number;
  lanes: number;
  /** Free-flow speed, m/s. */
  speed: number;
  /** [[x, y], [x, y]] in local metres. */
  path: [[number, number], [number, number]];
  bearingDegrees: number;
  pathLatLon?: [[number, number], [number, number]];
  /** The metric the request asked the server to attach (see `valueLabel`). */
  value?: number;
}

export interface MapData {
  format: "urbanflow-map-data";
  version: number;
  name: string;
  hasGeo: boolean;
  boundsLocal: { minX: number; maxX: number; minY: number; maxY: number };
  boundsLatLon?: { south: number; north: number; west: number; east: number };
  nodes: MapNode[];
  links: MapLink[];
  /** Present when links carry `value`: the name of that metric. */
  valueLabel?: string;
}

/** GET /api/v2/network-metrics/grid. */
export interface GridResponse {
  graph: Record<string, unknown>;
  flows: { origin: string; destination: string; vehiclesPerHour: number }[];
  validation: {
    valid: boolean;
    errors: string[];
    warnings: string[];
    stats?: Record<string, unknown>;
  };
  map: MapData;
}
