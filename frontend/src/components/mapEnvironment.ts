/**
 * Roadside scenery for the signal and roundabout maps.
 *
 * Presentation only. Everything here is painted *beneath* the roads, in one
 * cached layer, so it can never cover a road, marking, signal or vehicle, and
 * it is built purely from the road outline the map hands in: it does not read
 * or alter the simulation, the road geometry or the vehicle coordinates.
 *
 * The layer has three parts, all in world metres so both maps get the same
 * scenery from the same seed:
 *   1. mottled grass (soft light/dark patches and fine flecks);
 *   2. a sidewalk with a darker curb line, stroked along the road's outer
 *      boundary (the half that falls on the road is hidden by the road fill);
 *   3. sparse trees and shrubs, kept clear of the road and its sidewalk.
 */

type Point = [number, number];

/** One straight or quadratic-curve step of a road boundary. */
export interface EdgeSegment {
  to: Point;
  /** Control point; the step is a straight line when omitted. */
  control?: Point;
}

/** An open stretch of road boundary, in world metres. */
export interface RoadEdge {
  start: Point;
  segments: EdgeSegment[];
}

/** What a map tells the environment about its roads. */
export interface RoadEnvironment {
  /** Distinguishes layouts, so the cached layer is rebuilt when it changes. */
  key: string;
  /** Road boundaries to give a sidewalk. */
  edges: RoadEdge[];
  /** Radii of circular road boundaries centred on the origin. */
  circles: number[];
  /** Metres from a world point to the nearest road surface (0 or less when
   *  on it). Decides where vegetation may stand. */
  clearance: (x: number, y: number) => number;
}

export interface EnvironmentSize {
  width: number;
  height: number;
  ppm: number;
  dpr: number;
}

/** Base grass colour, also used for the empty (no data yet) state. */
export const GROUND_BASE = "#4f7a3b";

/** Sidewalk width (m). */
export const SIDEWALK_WIDTH_M = 2.0;
/** Gap (m) kept between the sidewalk and the nearest canopy. */
const VEGETATION_BUFFER_M = 2.5;

const SIDEWALK_COLOR = "#868d91";
const CURB_COLOR = "rgba(20, 26, 30, 0.55)";

// ── Deterministic randomness ────────────────────────────────────────────────

/** Stable pseudo-random value in [0, 1) for an integer cell and a salt, so a
 *  given spot of ground looks the same at any canvas size. */
function cellRandom(ix: number, iy: number, salt: number): number {
  let h = Math.imul(ix, 374761393) ^ Math.imul(iy, 668265263) ^ salt;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}

function sequence(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ── Vegetation placement ────────────────────────────────────────────────────

export interface Plant {
  x: number;
  y: number;
  /** Canopy radius in metres. */
  radius: number;
  kind: "tree" | "shrub";
}

const PLANT_CELL_M = 13;

/** Trees and shrubs for the world rectangle |x| <= halfW, |y| <= halfH,
 *  none closer to a road than its sidewalk, a buffer and its own canopy. */
export function placePlants(
  clearance: (x: number, y: number) => number,
  halfW: number,
  halfH: number,
): Plant[] {
  const plants: Plant[] = [];
  const nx = Math.ceil(halfW / PLANT_CELL_M) + 1;
  const ny = Math.ceil(halfH / PLANT_CELL_M) + 1;
  for (let ix = -nx; ix <= nx; ix += 1) {
    for (let iy = -ny; iy <= ny; iy += 1) {
      if (cellRandom(ix, iy, 11) > 0.38) continue;
      const isTree = cellRandom(ix, iy, 12) < 0.4;
      const radius = isTree
        ? 2.4 + cellRandom(ix, iy, 13) * 1.2
        : 0.9 + cellRandom(ix, iy, 13) * 0.6;
      // Jitter kept inside the cell's middle so neighbours never overlap.
      const x = (ix + 0.2 + cellRandom(ix, iy, 14) * 0.6) * PLANT_CELL_M;
      const y = (iy + 0.2 + cellRandom(ix, iy, 15) * 0.6) * PLANT_CELL_M;
      if (clearance(x, y) < SIDEWALK_WIDTH_M + VEGETATION_BUFFER_M + radius) {
        continue;
      }
      plants.push({ x, y, radius, kind: isTree ? "tree" : "shrub" });
    }
  }
  return plants;
}

// ── Layer painting ──────────────────────────────────────────────────────────

function paintGrass(
  ctx: CanvasRenderingContext2D,
  { width, height, ppm }: EnvironmentSize,
) {
  ctx.fillStyle = GROUND_BASE;
  ctx.fillRect(0, 0, width, height);

  // Soft patches of lighter and darker grass, one candidate per 7 m cell.
  const cell = 7;
  const halfW = width / ppm / 2;
  const halfH = height / ppm / 2;
  for (
    let ix = Math.floor(-halfW / cell) - 1;
    ix <= halfW / cell + 1;
    ix += 1
  ) {
    for (
      let iy = Math.floor(-halfH / cell) - 1;
      iy <= halfH / cell + 1;
      iy += 1
    ) {
      if (cellRandom(ix, iy, 21) > 0.75) continue;
      const light = cellRandom(ix, iy, 22) > 0.45;
      const cx = width / 2 + (ix + cellRandom(ix, iy, 23)) * cell * ppm;
      const cy = height / 2 - (iy + cellRandom(ix, iy, 24)) * cell * ppm;
      const radius = (4.5 + cellRandom(ix, iy, 25) * 4.5) * ppm;
      const patch = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
      const tint = light ? "112, 158, 78" : "34, 68, 38";
      patch.addColorStop(0, `rgba(${tint}, ${light ? "0.20" : "0.17"})`);
      patch.addColorStop(1, `rgba(${tint}, 0)`);
      ctx.fillStyle = patch;
      ctx.fillRect(cx - radius, cy - radius, radius * 2, radius * 2);
    }
  }

  // Fine flecks, so the ground reads as grass rather than a smooth gradient.
  const next = sequence(0x9e3779b9);
  const flecks = Math.round((width * height) / 90);
  for (let i = 0; i < flecks; i += 1) {
    const x = next() * width;
    const y = next() * height;
    ctx.fillStyle =
      next() > 0.5 ? "rgba(150, 196, 104, 0.16)" : "rgba(22, 52, 26, 0.16)";
    ctx.fillRect(x, y, 1, 1.6);
  }
}

function traceEdge(
  ctx: CanvasRenderingContext2D,
  edge: RoadEdge,
  toCanvas: (p: Point) => Point,
) {
  ctx.moveTo(...toCanvas(edge.start));
  for (const segment of edge.segments) {
    if (segment.control) {
      const [cx, cy] = toCanvas(segment.control);
      const [x, y] = toCanvas(segment.to);
      ctx.quadraticCurveTo(cx, cy, x, y);
    } else {
      ctx.lineTo(...toCanvas(segment.to));
    }
  }
}

function paintSidewalk(
  ctx: CanvasRenderingContext2D,
  road: RoadEnvironment,
  { width, height, ppm }: EnvironmentSize,
) {
  const toCanvas = ([x, y]: Point): Point => [
    width / 2 + x * ppm,
    height / 2 - y * ppm,
  ];
  const stroke = (color: string, lineWidth: number) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.lineJoin = "round";
    ctx.lineCap = "butt";
    for (const edge of road.edges) {
      ctx.beginPath();
      traceEdge(ctx, edge, toCanvas);
      ctx.stroke();
    }
    for (const radius of road.circles) {
      ctx.beginPath();
      ctx.arc(width / 2, height / 2, radius * ppm, 0, Math.PI * 2);
      ctx.stroke();
    }
  };
  // The stroke is centred on the road boundary, so only its outer half shows:
  // the road is painted over the rest. Curb line first, sidewalk on top.
  stroke(CURB_COLOR, SIDEWALK_WIDTH_M * 2 * ppm + 2);
  stroke(SIDEWALK_COLOR, SIDEWALK_WIDTH_M * 2 * ppm);
}

/** Paints a plant at its world position, relative to the canvas point that
 *  is the world origin. */
function paintPlant(
  ctx: CanvasRenderingContext2D,
  plant: Plant,
  [originX, originY]: Point,
  ppm: number,
) {
  const cx = originX + plant.x * ppm;
  const cy = originY - plant.y * ppm;
  const r = plant.radius * ppm;
  const disc = (dx: number, dy: number, radius: number, color: string) => {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(cx + dx * r, cy + dy * r, radius * r, 0, Math.PI * 2);
    ctx.fill();
  };
  // Soft ground shadow, then the canopy in three tones for a hint of volume.
  disc(0.35, 0.4, 1.0, "rgba(10, 24, 12, 0.22)");
  if (plant.kind === "tree") {
    disc(0, 0, 1.0, "#2e5a2c");
    disc(-0.1, -0.1, 0.82, "#3a6b34");
    disc(-0.28, -0.3, 0.42, "#4b8040");
  } else {
    disc(0, 0, 1.0, "#356533");
    disc(-0.35, -0.2, 0.62, "#417540");
    disc(0.3, 0.25, 0.55, "#3b6d38");
  }
}

/** Trees and shrubs on the central island: one small tree ringed by shrubs.
 *  Drawn by the map on top of its own island fill. */
export function paintIslandPlanting(
  ctx: CanvasRenderingContext2D,
  center: Point,
  innerRadius: number,
  ppm: number,
) {
  const shrub = Math.min(1.3, innerRadius * 0.13);
  const ring = innerRadius * 0.62;
  const at = (x: number, y: number, radius: number, kind: Plant["kind"]) => {
    paintPlant(ctx, { x, y, radius, kind }, center, ppm);
  };
  for (let i = 0; i < 4; i += 1) {
    const angle = Math.PI / 4 + (i * Math.PI) / 2;
    at(Math.cos(angle) * ring, Math.sin(angle) * ring, shrub, "shrub");
  }
  at(0, 0, Math.min(3.2, innerRadius * 0.32), "tree");
}

function buildLayer(
  road: RoadEnvironment,
  size: EnvironmentSize,
): HTMLCanvasElement | null {
  const layer = document.createElement("canvas");
  layer.width = Math.max(1, Math.round(size.width * size.dpr));
  layer.height = Math.max(1, Math.round(size.height * size.dpr));
  const ctx = layer.getContext("2d");
  if (!ctx) return null;
  ctx.setTransform(size.dpr, 0, 0, size.dpr, 0, 0);

  paintGrass(ctx, size);
  paintSidewalk(ctx, road, size);
  for (const plant of placePlants(
    road.clearance,
    size.width / size.ppm / 2 + 4,
    size.height / size.ppm / 2 + 4,
  )) {
    paintPlant(ctx, plant, [size.width / 2, size.height / 2], size.ppm);
  }
  return layer;
}

/**
 * Caches a map's environment layer. The layer is rebuilt only when the canvas
 * size, scale, pixel ratio or road layout changes, so each animation frame
 * costs a single drawImage.
 */
export class EnvironmentLayer {
  private layer: HTMLCanvasElement | null = null;
  private pattern: CanvasPattern | null = null;
  private builtFor = "";

  /** Paints the whole environment (grass, sidewalk, plants) as the backdrop. */
  paint(
    ctx: CanvasRenderingContext2D,
    road: RoadEnvironment,
    size: EnvironmentSize,
  ) {
    const key = `${road.key}|${String(size.width)}x${String(size.height)}@${String(size.ppm)}x${String(size.dpr)}`;
    if (key !== this.builtFor) {
      this.layer = buildLayer(road, size);
      this.pattern = this.layer
        ? ctx.createPattern(this.layer, "no-repeat")
        : null;
      // The layer is in device pixels but the context is scaled by dpr.
      this.pattern?.setTransform({ a: 1 / size.dpr, d: 1 / size.dpr });
      this.builtFor = key;
    }
    if (this.layer) {
      ctx.drawImage(this.layer, 0, 0, size.width, size.height);
    } else {
      ctx.fillStyle = GROUND_BASE;
      ctx.fillRect(0, 0, size.width, size.height);
    }
  }

  /** Fills the current path with the same grass as the backdrop, so grass
   *  islands inside a road match the ground around it. Call after `paint`. */
  fillWithGround(ctx: CanvasRenderingContext2D) {
    ctx.fillStyle = this.pattern ?? GROUND_BASE;
    ctx.fill();
  }
}

// ── Road outlines for the two layouts ───────────────────────────────────────

function distanceToRect(
  x: number,
  y: number,
  [x1, y1, x2, y2]: [number, number, number, number],
): number {
  return Math.hypot(Math.max(x1 - x, 0, x - x2), Math.max(y1 - y, 0, y - y2));
}

/** Environment for the signalised junction: four arms plus the square
 *  junction box that ends at the stop lines. */
export function signalEnvironment(
  widths: { north: number; south: number; east: number; west: number },
  half: number,
  reach: number,
): RoadEnvironment {
  const n = widths.north / 2;
  const s = widths.south / 2;
  const e = widths.east / 2;
  const w = widths.west / 2;
  const rects: [number, number, number, number][] = [
    [-n, half, n, reach],
    [-s, -reach, s, -half],
    [half, -e, reach, e],
    [-reach, -w, -half, w],
    [-half, -half, half, half],
  ];
  const corner = (
    start: Point,
    a: Point,
    b: Point,
    c: Point,
    end: Point,
  ): RoadEdge => ({
    start,
    segments: [{ to: a }, { to: b }, { to: c }, { to: end }],
  });
  return {
    key: `signal:${[n, s, e, w, half, reach].map(String).join(",")}`,
    edges: [
      corner([n, reach], [n, half], [half, half], [half, e], [reach, e]),
      corner([-n, reach], [-n, half], [-half, half], [-half, w], [-reach, w]),
      corner([s, -reach], [s, -half], [half, -half], [half, -e], [reach, -e]),
      corner(
        [-s, -reach],
        [-s, -half],
        [-half, -half],
        [-half, -w],
        [-reach, -w],
      ),
    ],
    circles: [],
    clearance: (x, y) =>
      Math.min(...rects.map((rect) => distanceToRect(x, y, rect))),
  };
}

/** Environment for the roundabout: the ring, four arms, and the smooth
 *  fillets that flare each arm out to meet its neighbour. */
export function roundaboutEnvironment(
  edge: number,
  outerRadius: number,
  reach: number,
): RoadEnvironment {
  const flare = outerRadius + 15;
  // The flare in the north-east quadrant; the others mirror it.
  const fillet: Point[] = [];
  for (let i = 0; i <= 32; i += 1) {
    const t = i / 32;
    const u = 1 - t;
    fillet.push([
      u * u * edge + 2 * u * t * edge + t * t * flare,
      u * u * flare + 2 * u * t * edge + t * t * edge,
    ]);
  }
  const quadrants: [number, number][] = [
    [1, 1],
    [-1, 1],
    [1, -1],
    [-1, -1],
  ];
  return {
    key: `roundabout:${[edge, outerRadius, reach].map(String).join(",")}`,
    edges: quadrants.map(([sx, sy]) => ({
      start: [sx * edge, sy * reach],
      segments: [
        { to: [sx * edge, sy * flare] },
        { control: [sx * edge, sy * edge], to: [sx * flare, sy * edge] },
        { to: [sx * reach, sy * edge] },
      ],
    })),
    circles: [outerRadius],
    clearance: (x, y) => {
      const ax = Math.abs(x);
      const ay = Math.abs(y);
      const arms = Math.min(Math.max(0, ax - edge), Math.max(0, ay - edge));
      const ring = Math.hypot(x, y) - outerRadius;
      let nearest = Math.min(arms, ring);
      for (const [fx, fy] of fillet)
        nearest = Math.min(nearest, Math.hypot(ax - fx, ay - fy));
      return nearest;
    },
  };
}
