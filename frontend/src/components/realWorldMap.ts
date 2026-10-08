/**
 * Live-map drawing for real-world junctions (V1.5): three-arm junctions,
 * arms on their own bearings, arms with their own lane widths.
 *
 * The standard junction keeps its own renderer (IntersectionMap /
 * RoundaboutMap), which mirrors the backend's axis-aligned layout. A
 * real-world junction's snapshot carries each arm's laid-out geometry
 * (bearing, lane width, stop-line distance — backend
 * roads/junction_geometry.py), and this draws the roads from exactly that,
 * so vehicles drive on the lanes shown.
 */

import type { Approach, SignalDirection } from "../types/simulation";
import { drawArrowAt } from "./laneMarkings";

type Point = (x: number, y: number) => [number, number];

export interface RealWorldArm {
  direction: SignalDirection;
  bearing: number;
  laneWidth: number;
  stopLineDistance: number;
  laneCount: number;
  lanePermittedTurns?: Approach["lanePermittedTurns"];
}

/** The snapshot's arms when it describes a real-world junction, else null
 *  (the standard junction, drawn by the existing renderers). */
export function realWorldArms(approaches: Approach[]): RealWorldArm[] | null {
  if (!approaches.length) return null;
  const arms: RealWorldArm[] = [];
  for (const a of approaches) {
    if (a.bearing == null || a.laneWidth == null || a.stopLineDistance == null)
      return null;
    arms.push({
      direction: a.direction,
      bearing: a.bearing,
      laneWidth: a.laneWidth,
      stopLineDistance: a.stopLineDistance,
      laneCount: a.laneCount,
      lanePermittedTurns: a.lanePermittedTurns,
    });
  }
  return arms;
}

/** World point ``along`` m out on an arm, ``lateral`` m to its exit side
 *  (mirrors ArmGeometry.point in the backend). */
export function armWorldPoint(
  bearing: number,
  along: number,
  lateral: number,
): [number, number] {
  const rad = (bearing * Math.PI) / 180;
  const ux = Math.sin(rad);
  const uy = Math.cos(rad);
  return [along * ux + lateral * uy, along * uy - lateral * ux];
}

export interface RealWorldDrawOptions {
  point: Point;
  ppm: number;
  /** How far out (m) to draw each arm. */
  reach: number;
  /** Half-width (m) of the splitter island; 0 at a signal. */
  splitter: number;
  roundabout?: { innerRadius: number; outerRadius: number; ringLanes: number };
  signals?: { direction: SignalDirection; color: string }[];
  ground: string;
}

const ROAD = "#343b42";

function polygon(ctx: CanvasRenderingContext2D, pts: [number, number][]) {
  ctx.beginPath();
  pts.forEach(([x, y], i) => {
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.closePath();
}

function signalColor(color: string): string {
  return color === "green"
    ? "#55d66b"
    : color === "yellow"
      ? "#ffd166"
      : color === "red"
        ? "#f04f4f"
        : "#555b60";
}

export function drawRealWorldJunction(
  ctx: CanvasRenderingContext2D,
  arms: RealWorldArm[],
  opts: RealWorldDrawOptions,
): void {
  const { point, ppm, reach, splitter, roundabout } = opts;
  const P = (b: number, along: number, lateral: number) =>
    point(...armWorldPoint(b, along, lateral));
  const half = (arm: RealWorldArm) => arm.laneCount * arm.laneWidth + splitter;

  // Carriageways. At a roundabout each arm runs in to the ring; at a signal
  // to its stop line, and the conflict area joins the stop lines.
  ctx.fillStyle = ROAD;
  for (const arm of arms) {
    const start = roundabout ? 0 : arm.stopLineDistance;
    polygon(ctx, [
      P(arm.bearing, start, -half(arm)),
      P(arm.bearing, reach, -half(arm)),
      P(arm.bearing, reach, half(arm)),
      P(arm.bearing, start, half(arm)),
    ]);
    ctx.fill();
  }
  if (roundabout) {
    const [cx, cy] = point(0, 0);
    ctx.beginPath();
    ctx.arc(cx, cy, roundabout.outerRadius * ppm, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = opts.ground;
    ctx.beginPath();
    ctx.arc(cx, cy, roundabout.innerRadius * ppm, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,.55)";
    ctx.lineWidth = 1.2;
    ctx.setLineDash([7, 9]);
    for (let k = 1; k < roundabout.ringLanes; k += 1) {
      const r =
        roundabout.innerRadius +
        (k * (roundabout.outerRadius - roundabout.innerRadius)) /
          roundabout.ringLanes;
      ctx.beginPath();
      ctx.arc(cx, cy, r * ppm, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.setLineDash([]);
  } else {
    const corners = [...arms]
      .sort((a, b) => a.bearing - b.bearing)
      .flatMap((arm) => [
        P(arm.bearing, arm.stopLineDistance, -half(arm)),
        P(arm.bearing, arm.stopLineDistance, half(arm)),
      ]);
    polygon(ctx, corners);
    ctx.fill();
  }

  for (const arm of arms) {
    const stop = arm.stopLineDistance;
    const b = arm.bearing;
    const line = (a1: number, l1: number, a2: number, l2: number) => {
      const [x1, y1] = P(b, a1, l1);
      const [x2, y2] = P(b, a2, l2);
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    };
    // Kerbs.
    ctx.strokeStyle = "#d7dde0";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([]);
    line(stop, -half(arm), reach, -half(arm));
    line(stop, half(arm), reach, half(arm));
    // Splitter island or centre line.
    if (splitter > 0) {
      ctx.fillStyle = "#6f8f62";
      polygon(ctx, [
        P(b, stop + 1, -splitter),
        P(b, reach, -splitter),
        P(b, reach, splitter),
        P(b, stop + 1, splitter),
      ]);
      ctx.fill();
    } else {
      ctx.strokeStyle = "#f2c230";
      ctx.lineWidth = 2.2;
      line(stop, 0, reach, 0);
    }
    // Lane dividers.
    ctx.strokeStyle = "rgba(255,255,255,.55)";
    ctx.lineWidth = 1.2;
    ctx.setLineDash([7, 9]);
    for (let i = 1; i < arm.laneCount; i += 1) {
      const off = i * arm.laneWidth + splitter;
      line(stop, -off, reach, -off);
      line(stop, off, reach, off);
    }
    ctx.setLineDash([]);
    // Stop / give-way line across the incoming lanes.
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = roundabout ? 1.5 : 3;
    if (roundabout) ctx.setLineDash([4, 4]);
    line(stop, -splitter, stop, -half(arm));
    ctx.setLineDash([]);
    // Lane arrows, heading towards the junction.
    const turns = arm.lanePermittedTurns;
    if (turns && turns.length > 1) {
      ctx.save();
      ctx.strokeStyle = "rgba(255,255,255,.8)";
      ctx.lineWidth = Math.max(1, ppm * 0.18);
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      turns.forEach((laneTurns, i) => {
        const [x, y] = P(
          b,
          stop + 5.5,
          -((i + 0.5) * arm.laneWidth + splitter),
        );
        drawArrowAt(ctx, laneTurns, x, y, b + 180, Math.max(4, ppm * 1.1));
      });
      ctx.restore();
    }
  }

  // Signal heads beside each arm's kerb, at its stop line.
  for (const signal of opts.signals ?? []) {
    const arm = arms.find((a) => a.direction === signal.direction);
    if (!arm) continue;
    const [x, y] = P(arm.bearing, arm.stopLineDistance + 2.5, -half(arm) - 2.5);
    const w = Math.max(9, ppm * 2.4);
    const h = Math.max(16, ppm * 4.4);
    ctx.fillStyle = "#171b1f";
    ctx.fillRect(x - w / 2, y - h / 2, w, h);
    ctx.fillStyle = signalColor(signal.color);
    ctx.shadowColor = ctx.fillStyle;
    ctx.shadowBlur = 9;
    ctx.beginPath();
    ctx.arc(x, y, Math.max(3.5, ppm * 0.8), 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
  }
}
