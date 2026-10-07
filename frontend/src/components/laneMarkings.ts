/**
 * Lane-use arrows (V1.2): painted on each incoming lane just upstream of the
 * stop/give-way line, showing the movements the backend permits from that
 * lane (snapshot `intersection.approaches[].lanePermittedTurns`).
 */

import type { Approach, SignalDirection } from "../types/simulation";

type Turn = "uturn" | "left" | "straight" | "right";
type Point = (x: number, y: number) => [number, number];

/** Direction of travel on each approach's incoming lanes, in degrees with
 *  0 = up the canvas (world +y), clockwise. */
const TRAVEL_HEADING: Record<SignalDirection, number> = {
  north: 180,
  south: 0,
  east: 270,
  west: 90,
};

/** World point on incoming lane ``lateral`` metres from the approach axis,
 *  ``distance`` metres from the junction centre. Mirrors the lane layout in
 *  backend/src/roads/network.py (traffic keeps right). */
function lanePoint(
  direction: SignalDirection,
  lateral: number,
  distance: number,
): [number, number] {
  switch (direction) {
    case "north":
      return [-lateral, distance];
    case "south":
      return [lateral, -distance];
    case "east":
      return [distance, lateral];
    default:
      return [-distance, -lateral];
  }
}

function drawArrow(ctx: CanvasRenderingContext2D, turns: Turn[], size: number) {
  const s = size;
  const head = s * 0.35;
  ctx.beginPath();
  // Common stem from the back of the marking to its middle.
  ctx.moveTo(0, s);
  ctx.lineTo(0, 0);
  if (turns.includes("straight")) {
    ctx.moveTo(0, 0);
    ctx.lineTo(0, -s);
    ctx.moveTo(-head, -s + head);
    ctx.lineTo(0, -s);
    ctx.lineTo(head, -s + head);
  }
  for (const side of ["left", "right"] as const) {
    if (!turns.includes(side)) continue;
    const dir = side === "left" ? -1 : 1;
    ctx.moveTo(0, 0);
    ctx.quadraticCurveTo(0, -s * 0.45, dir * s * 0.7, -s * 0.45);
    ctx.moveTo(dir * (s * 0.7 - head), -s * 0.45 - head);
    ctx.lineTo(dir * s * 0.7, -s * 0.45);
    ctx.lineTo(dir * (s * 0.7 - head), -s * 0.45 + head);
  }
  if (turns.includes("uturn")) {
    // V1.5: a hook to the left and back down.
    const r = s * 0.3;
    ctx.moveTo(0, 0);
    ctx.lineTo(0, -s * 0.4);
    ctx.arc(-r, -s * 0.4, r, 0, Math.PI, true);
    ctx.lineTo(-2 * r, s * 0.2);
    ctx.moveTo(-2 * r - head * 0.7, s * 0.2 - head * 0.7);
    ctx.lineTo(-2 * r, s * 0.2);
    ctx.lineTo(-2 * r + head * 0.7, s * 0.2 - head * 0.7);
  }
  ctx.stroke();
}

/** Paint one lane's arrow centred on canvas point (cx, cy), pointing along
 *  ``headingDeg`` (0 = up the canvas, clockwise). Stroke style is the
 *  caller's. */
export function drawArrowAt(
  ctx: CanvasRenderingContext2D,
  turns: Turn[],
  cx: number,
  cy: number,
  headingDeg: number,
  size: number,
): void {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate((headingDeg * Math.PI) / 180);
  drawArrow(ctx, turns, size);
  ctx.restore();
}

/**
 * Paint lane arrows. ``laneOffsets(direction, count)`` gives each lane's
 * lateral offset from the approach axis (lane 0 first); ``distance`` is how
 * far from the centre the arrows sit.
 */
export function drawLaneArrows(
  ctx: CanvasRenderingContext2D,
  approaches: Approach[],
  laneOffsets: (direction: SignalDirection, count: number) => number[],
  distance: number,
  ppm: number,
  point: Point,
): void {
  const size = Math.max(4, ppm * 1.1);
  ctx.save();
  ctx.strokeStyle = "rgba(255,255,255,.8)";
  ctx.lineWidth = Math.max(1, ppm * 0.18);
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  for (const approach of approaches) {
    const turns = approach.lanePermittedTurns;
    if (!turns || turns.length <= 1) continue; // nothing to tell apart
    const offsets = laneOffsets(approach.direction, turns.length);
    turns.forEach((laneTurns, i) => {
      const [wx, wy] = lanePoint(approach.direction, offsets[i], distance);
      const [cx, cy] = point(wx, wy);
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate((TRAVEL_HEADING[approach.direction] * Math.PI) / 180);
      drawArrow(ctx, laneTurns, size);
      ctx.restore();
    });
  }
  ctx.restore();
}
