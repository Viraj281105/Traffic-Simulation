/**
 * A small projected-3D renderer for the recorded junction scenes.
 *
 * Canvas 2D with a perspective camera, extruded vehicles and buildings and
 * painter's-order depth sorting: enough depth for a cinematic junction without
 * shipping a WebGL stack for a few dozen boxes. Vehicles are coloured by their
 * recorded speed (green flowing, amber slowing, red stopped), so congestion
 * is visible at a glance. Geometry follows the engine: arms along the axes,
 * stop lines 9.4 m from the centre, a 10 to 20 m ring for roundabouts.
 */
import type { ControlState, DrawVehicle, StrategyId } from "./sceneData";

export interface Camera {
  /** Degrees about the vertical axis. */
  yaw: number;
  /** Degrees above the horizon: 90 looks straight down. */
  elev: number;
  zoom: number;
  /** Vertical shift of the scene centre, as a fraction of the height. */
  shiftY: number;
  /** Horizontal shift, as a fraction of the width. */
  shiftX: number;
}

type P = [number, number, number];

const EXTENT = 150; // metres from the centre that fill the shorter side
const ROAD_HALF = 4.2;
const STOP = 9.4;
const ARM = 230;
const SPEED_TOP = 12.5;
/** Vehicles are drawn larger than life so they read at junction scale. */
const VEHICLE_SCALE = 1.7;

const CAR: [number, number, number] = [4.5, 1.9, 1.5];
const DIM: Record<string, [number, number, number]> = {
  car: [4.5, 1.9, 1.5],
  suv: [4.8, 2.0, 1.8],
  bus: [11, 2.5, 3.0],
  truck: [8, 2.4, 3.0],
  motorcycle: [2.1, 0.8, 1.3],
};

export type SceneTheme = "dark" | "light";

type RGB = [number, number, number];

/** Everything the renderer colours, per theme. Light is a daylight map:
 *  pale ground and buildings, mid-grey asphalt, deeper vehicle hues and soft
 *  ground shadows, so traffic stays the strongest thing in the frame. */
interface Palette {
  ground: string;
  grid: string;
  road: string;
  edge: string;
  dash: string;
  stopLine: string;
  giveWay: string;
  island: [string, string, string];
  ringIsland: string;
  pole: string;
  lampGlow: string;
  heat: [RGB, RGB, RGB];
  vehicleShade: [number, number, number];
  vehicleOutline: string | null;
  buildingOutline: string | null;
  shadow: string | null;
  building: (tone: number) => [string, string, string];
}

const clamp255 = (v: number) => Math.max(0, Math.min(255, Math.round(v)));
const tint = (c: RGB, k: number) =>
  `rgb(${clamp255(c[0] * k).toString()},${clamp255(c[1] * k).toString()},${clamp255(c[2] * k).toString()})`;

const PALETTES: Record<SceneTheme, Palette> = {
  dark: {
    ground: "#0a1626",
    grid: "rgba(127,176,255,0.07)",
    road: "#1d3150",
    edge: "rgba(233,238,246,0.42)",
    dash: "rgba(245,192,74,0.55)",
    stopLine: "rgba(233,238,246,0.85)",
    giveWay: "rgba(233,238,246,0.45)",
    island: ["#0f3b35", "#17564a", "#1c6a5a"],
    ringIsland: "#0f3b35",
    pole: "#5b6b86",
    lampGlow: "cc",
    heat: [
      [240, 106, 106],
      [227, 167, 58],
      [61, 220, 132],
    ],
    vehicleShade: [1, 0.55, 0.4],
    vehicleOutline: null,
    buildingOutline: null,
    shadow: null,
    building: (t) => [
      tint([36, 58, 96], t),
      tint([18, 32, 58], t),
      tint([24, 42, 74], t),
    ],
  },
  light: {
    ground: "#edf1f7",
    grid: "rgba(14,33,70,0.08)",
    road: "#76839a",
    edge: "rgba(255,255,255,0.8)",
    dash: "rgba(255,214,102,0.95)",
    stopLine: "rgba(255,255,255,0.95)",
    giveWay: "rgba(255,255,255,0.8)",
    island: ["#a5dcc2", "#86cdab", "#6bbd96"],
    ringIsland: "#a5dcc2",
    pole: "#46546e",
    lampGlow: "99",
    heat: [
      [214, 58, 58],
      [226, 140, 14],
      [18, 160, 88],
    ],
    vehicleShade: [1, 0.72, 0.58],
    vehicleOutline: "rgba(14,33,70,0.45)",
    buildingOutline: "rgba(14,33,70,0.14)",
    shadow: "rgba(18,34,68,0.17)",
    building: (t) => {
      const k = 0.95 + (t - 1) * 0.14;
      return [
        tint([251, 252, 255], k),
        tint([203, 213, 229], k),
        tint([184, 196, 216], k),
      ];
    },
  },
};

function heat(speed: number, stops: [RGB, RGB, RGB]): RGB {
  const t = Math.max(0, Math.min(1, speed / SPEED_TOP));
  const f = t * 2;
  const i = Math.min(1, Math.floor(f));
  const k = f - i;
  const a = stops[i];
  const b = stops[i + 1];
  return [
    a[0] + (b[0] - a[0]) * k,
    a[1] + (b[1] - a[1]) * k,
    a[2] + (b[2] - a[2]) * k,
  ];
}

function rgb(c: [number, number, number], shade = 1, alpha = 1): string {
  return `rgba(${Math.round(c[0] * shade).toString()},${Math.round(c[1] * shade).toString()},${Math.round(c[2] * shade).toString()},${alpha.toFixed(3)})`;
}

const SIGNAL_COLOURS: Record<string, string> = {
  green: "#3ddc84",
  yellow: "#f5c04a",
  amber: "#f5c04a",
  red: "#f06a6a",
};

// Buildings: a deterministic block layout outside the road corridors.
interface Building {
  x: number;
  y: number;
  hx: number;
  hy: number;
  h: number;
  tone: number;
}

function makeBuildings(roundabout: boolean): Building[] {
  const out: Building[] = [];
  let seed = 7;
  const rnd = () => {
    seed = (seed * 1664525 + 1013904223) % 4294967296;
    return seed / 4294967296;
  };
  const clear = roundabout ? 30 : 16;
  for (let gx = -130; gx <= 130; gx += 30) {
    for (let gy = -130; gy <= 130; gy += 30) {
      if (Math.abs(gx) < 14 || Math.abs(gy) < 14) continue;
      if (Math.hypot(gx, gy) < clear + 14) continue;
      if (rnd() < 0.18) continue;
      out.push({
        x: gx + (rnd() - 0.5) * 6,
        y: gy + (rnd() - 0.5) * 6,
        hx: 7 + rnd() * 6,
        hy: 7 + rnd() * 6,
        h: 5 + rnd() * rnd() * 34,
        tone: 0.8 + rnd() * 0.4,
      });
    }
  }
  return out;
}

const BUILDINGS = { signal: makeBuildings(false), ring: makeBuildings(true) };

const ARM_ORDER = ["north", "east", "south", "west"] as const;

function turnQuarter(p: [number, number], quarters: number): [number, number] {
  let [x, y] = p;
  for (let i = 0; i < quarters; i++) [x, y] = [y, -x];
  return [x, y];
}

export interface RenderOptions {
  strategy: StrategyId;
  vehicles: DrawVehicle[];
  control: ControlState;
  camera: Camera;
  innerRadius: number;
  outerRadius: number;
  /** Simulated seconds, for light pulses. */
  clock: number;
  theme: SceneTheme;
}

export function drawScene(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  o: RenderOptions,
): void {
  const ring =
    o.strategy === "roundabout" || o.strategy === "metered_entry_roundabout";
  const pal = PALETTES[o.theme];
  const cam = o.camera;
  const yaw = (cam.yaw * Math.PI) / 180;
  const e = (cam.elev * Math.PI) / 180;
  const cy = Math.cos(yaw);
  const sy = Math.sin(yaw);
  const ce = Math.cos(e);
  const se = Math.sin(e);
  const scale = (Math.min(w, h) / (2 * EXTENT)) * cam.zoom * 1.55;
  const D = EXTENT * 3.4;
  const ox = w / 2 + cam.shiftX * w;
  const oy = h / 2 + cam.shiftY * h;

  const project = (x: number, y: number, z: number): P => {
    const X = x * cy - y * sy;
    const Y = x * sy + y * cy;
    const up = Y * se + z * ce;
    const dep = Y * ce - z * se;
    const f = D / (D + dep);
    return [ox + X * scale * f, oy - up * scale * f, dep];
  };
  const depthOf = (x: number, y: number, z: number): number => {
    const Y = x * sy + y * cy;
    return Y * ce - z * se;
  };

  ctx.clearRect(0, 0, w, h);

  const poly = (pts: P[], fill: string, stroke?: string, lw = 1) => {
    ctx.beginPath();
    pts.forEach((p, i) => {
      if (i === 0) ctx.moveTo(p[0], p[1]);
      else ctx.lineTo(p[0], p[1]);
    });
    ctx.closePath();
    ctx.fillStyle = fill;
    ctx.fill();
    if (stroke) {
      ctx.strokeStyle = stroke;
      ctx.lineWidth = lw;
      ctx.stroke();
    }
  };
  const flat = (pts: [number, number][], z: number): P[] =>
    pts.map(([x, y]) => project(x, y, z));
  const rect = (
    x0: number,
    y0: number,
    x1: number,
    y1: number,
    z: number,
  ): P[] =>
    flat(
      [
        [x0, y0],
        [x1, y0],
        [x1, y1],
        [x0, y1],
      ],
      z,
    );

  // Ground and a faint survey grid.
  poly(rect(-420, -420, 420, 420, 0), pal.ground);
  ctx.strokeStyle = pal.grid;
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let g = -180; g <= 180; g += 30) {
    const a = project(g, -180, 0);
    const b = project(g, 180, 0);
    ctx.moveTo(a[0], a[1]);
    ctx.lineTo(b[0], b[1]);
    const c = project(-180, g, 0);
    const d = project(180, g, 0);
    ctx.moveTo(c[0], c[1]);
    ctx.lineTo(d[0], d[1]);
  }
  ctx.stroke();

  // Roads.
  const road = pal.road;
  const edge = pal.edge;
  if (ring) {
    const r1 = o.outerRadius;
    poly(rect(-ARM, -ROAD_HALF, ARM, ROAD_HALF, 0.02), road);
    poly(rect(-ROAD_HALF, -ARM, ROAD_HALF, ARM, 0.02), road);
    const disc = (r: number, z: number): P[] => {
      const pts: [number, number][] = [];
      for (let i = 0; i < 56; i++) {
        const a = (i / 56) * Math.PI * 2;
        pts.push([Math.cos(a) * r, Math.sin(a) * r]);
      }
      return flat(pts, z);
    };
    poly(disc(r1 + 0.6, 0.03), road, edge, 1.2);
    poly(disc(o.innerRadius, 0.05), pal.ringIsland);
    poly(disc(o.innerRadius - 1.2, 0.5), pal.island[1]);
    poly(disc(o.innerRadius - 3, 0.55), pal.island[2]);
  } else {
    poly(rect(-ARM, -ROAD_HALF, ARM, ROAD_HALF, 0.02), road);
    poly(rect(-ROAD_HALF, -ARM, ROAD_HALF, ARM, 0.02), road);
  }
  // Road edges and centre dashes.
  ctx.strokeStyle = edge;
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (const s of [-1, 1]) {
    const reach = ring ? o.outerRadius + 1 : STOP + 3;
    for (const sign of [-1, 1]) {
      let a = project(sign * ARM, s * ROAD_HALF, 0.05);
      let b = project(sign * reach, s * ROAD_HALF, 0.05);
      ctx.moveTo(a[0], a[1]);
      ctx.lineTo(b[0], b[1]);
      a = project(s * ROAD_HALF, sign * ARM, 0.05);
      b = project(s * ROAD_HALF, sign * reach, 0.05);
      ctx.moveTo(a[0], a[1]);
      ctx.lineTo(b[0], b[1]);
    }
  }
  ctx.stroke();
  ctx.fillStyle = pal.dash;
  const dashFrom = (ring ? o.outerRadius : STOP) + 6;
  for (let d = dashFrom; d < ARM; d += 9) {
    for (const sign of [-1, 1]) {
      poly(rect(sign * d, -0.12, sign * (d + 4), 0.12, 0.06), ctx.fillStyle);
      poly(rect(-0.12, sign * d, 0.12, sign * (d + 4), 0.06), ctx.fillStyle);
    }
  }

  // Stop lines (signals) or give-way lines (ring).
  const lineAt = ring ? o.outerRadius + 0.4 : STOP;
  for (let q = 0; q < 4; q++) {
    const p0 = turnQuarter([-ROAD_HALF, lineAt], q);
    const p1 = turnQuarter([0, lineAt], q);
    const p2 = turnQuarter([0, lineAt + 0.7], q);
    const p3 = turnQuarter([-ROAD_HALF, lineAt + 0.7], q);
    poly(flat([p0, p1, p2, p3], 0.07), ring ? pal.giveWay : pal.stopLine);
  }

  // Everything with height is depth sorted, far to near.
  interface Item {
    depth: number;
    draw: () => void;
  }
  const items: Item[] = [];
  const shadows: (() => void)[] = [];
  const box = (
    cx: number,
    cyy: number,
    hx: number,
    hy: number,
    angle: number,
    hgt: number,
    top: string,
    side: string,
    side2: string,
    outline: string | null = null,
    shadowAlpha = 1,
  ) => {
    const ca = Math.cos(angle);
    const sa = Math.sin(angle);
    const base: [number, number][] = [
      [-hx, -hy],
      [hx, -hy],
      [hx, hy],
      [-hx, hy],
    ].map(([lx, ly]) => [cx + lx * ca - ly * sa, cyy + lx * sa + ly * ca]);
    if (pal.shadow) {
      // A soft cast shadow: the footprint swept away from the light.
      const dx = hgt * 0.55;
      const dy = -hgt * 0.4;
      shadows.push(() => {
        const fill = pal.shadow ?? "transparent";
        ctx.globalAlpha = shadowAlpha;
        const foot = base.map(([x, y]) => project(x, y, 0.06));
        const cast = base.map(([x, y]) => project(x + dx, y + dy, 0.06));
        poly(foot, fill);
        poly(cast, fill);
        for (let i = 0; i < 4; i++) {
          const j = (i + 1) % 4;
          poly([foot[i], foot[j], cast[j], cast[i]], fill);
        }
        ctx.globalAlpha = 1;
      });
    }
    items.push({
      depth: depthOf(cx, cyy, hgt / 2),
      draw: () => {
        const lo = base.map(([x, y]) => project(x, y, 0.05));
        const hi = base.map(([x, y]) => project(x, y, hgt));
        const faces: { d: number; pts: P[]; fill: string }[] = [];
        for (let i = 0; i < 4; i++) {
          const j = (i + 1) % 4;
          const a = base[i];
          const b = base[j];
          const la = lo[i];
          const lb = lo[j];
          const ha = hi[i];
          const hb = hi[j];
          faces.push({
            d: depthOf((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, hgt / 2),
            pts: [la, lb, hb, ha],
            fill: i % 2 === 0 ? side : side2,
          });
        }
        faces.sort((p, q) => q.d - p.d);
        // Back faces first; the nearest two are the ones in view.
        for (const f of faces.slice(0, 4)) poly(f.pts, f.fill);
        poly(hi, top, outline ?? undefined, 1);
      },
    });
  };

  const b = ring ? BUILDINGS.ring : BUILDINGS.signal;
  for (const bd of b) {
    const [top, side, side2] = pal.building(bd.tone);
    box(
      bd.x,
      bd.y,
      bd.hx,
      bd.hy,
      0,
      bd.h,
      top,
      side,
      side2,
      pal.buildingOutline,
    );
  }

  for (const v of o.vehicles) {
    const found = DIM[v.type] as [number, number, number] | undefined;
    const dim = found ?? CAR;
    const [len, wid, hgt] = dim.map((d) => d * VEHICLE_SCALE) as [
      number,
      number,
      number,
    ];
    const c = heat(v.speed, pal.heat);
    // Compass heading (0 north, clockwise) to a world angle (0 along +x).
    const angle = ((90 - v.heading) * Math.PI) / 180;
    const alpha = v.alpha;
    if (alpha <= 0.02) continue;
    box(
      v.x,
      v.y,
      len / 2,
      wid / 2,
      angle,
      hgt,
      rgb(c, pal.vehicleShade[0], alpha),
      rgb(c, pal.vehicleShade[1], alpha),
      rgb(c, pal.vehicleShade[2], alpha),
      pal.vehicleOutline,
      alpha,
    );
  }

  // Signal heads: a post and a glowing lamp at each approach.
  const lamps: { x: number; y: number; colour: string }[] = [];
  const colourOf = (direction: string): string | undefined => {
    const list = o.control.signals ?? o.control.metering?.arms;
    const found = list?.find((s) => s.direction === direction);
    return found ? (SIGNAL_COLOURS[found.color] ?? "#8d9bb2") : undefined;
  };
  if (o.control.signals || o.control.metering) {
    const dist = ring ? o.outerRadius + 2.6 : STOP + 0.4;
    ARM_ORDER.forEach((dir, q) => {
      const colour = colourOf(dir);
      if (!colour) return;
      const [x, y] = turnQuarter([-ROAD_HALF - 1, dist], q);
      lamps.push({ x, y, colour });
    });
  }
  for (const l of lamps) {
    items.push({
      depth: depthOf(l.x, l.y, 4),
      draw: () => {
        const base = project(l.x, l.y, 0);
        const top = project(l.x, l.y, 5);
        ctx.strokeStyle = pal.pole;
        ctx.lineWidth = Math.max(1, scale * 0.35);
        ctx.beginPath();
        ctx.moveTo(base[0], base[1]);
        ctx.lineTo(top[0], top[1]);
        ctx.stroke();
        const r = Math.max(2, scale * 1.15);
        const g = ctx.createRadialGradient(
          top[0],
          top[1],
          0,
          top[0],
          top[1],
          r * 4,
        );
        g.addColorStop(0, `${l.colour}${pal.lampGlow}`);
        g.addColorStop(1, `${l.colour}00`);
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(top[0], top[1], r * 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = l.colour;
        ctx.beginPath();
        ctx.arc(top[0], top[1], r, 0, Math.PI * 2);
        ctx.fill();
      },
    });
  }

  for (const draw of shadows) draw();
  items.sort((p, q) => q.depth - p.depth);
  for (const it of items) it.draw();
}
