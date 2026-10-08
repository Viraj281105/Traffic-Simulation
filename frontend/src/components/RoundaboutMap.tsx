import React, { useCallback, useEffect, useRef, useState } from "react";
import { useContainerSize } from "../hooks/useContainerSize";
import type { LiveSnapshot } from "../types/simulation";
import {
  ROUNDABOUT_SPLITTER_HALF_WIDTH,
  roundaboutCarriagewayEdge,
  roundaboutGiveWayRadius,
  roundaboutLaneCentres,
  roundaboutLaneDividers,
  roundaboutRingDividers,
  mapScale,
} from "./mapGeometry";
import {
  EnvironmentLayer,
  GROUND_BASE,
  paintIslandPlanting,
  roundaboutEnvironment,
} from "./mapEnvironment";
import { SnapshotInterpolator } from "./snapshotInterpolator";
import { drawLaneArrows } from "./laneMarkings";
import { drawRealWorldFrame } from "./realWorldFrame";
import { drawVehicleSprite } from "../vehicles/vehicleSprites";

interface RoundaboutMapProps {
  snapshot: LiveSnapshot | null;
  width?: number;
  height?: number;
  laneWidth?: number;
  /** Lanes on every approach (used for an approach the snapshot does not
   *  describe yet). */
  lanes?: number;
  showCrosswalks?: boolean;
  debug?: boolean;
}

/** Arms in the order the drawing rotates through them: north, then
 *  anticlockwise (west, south, east), matching the 90° rotations below. */
const ARM_ORDER = ["north", "west", "south", "east"] as const;
type Arm = (typeof ARM_ORDER)[number];

export const RoundaboutMap: React.FC<RoundaboutMapProps> = ({
  snapshot,
  width: fallbackWidth = 800,
  height: fallbackHeight = 680,
  laneWidth = 3.5,
  lanes = 2,
  showCrosswalks = true,
  debug = false,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  // Draw at the canvas's displayed size (CSS sizes it to its container), so
  // the picture is never stretched out of proportion; the size props are
  // only used until it has been measured.
  const [measureCanvas, displayed] = useContainerSize();
  const setCanvas = useCallback(
    (node: HTMLCanvasElement | null) => {
      canvasRef.current = node;
      measureCanvas(node);
    },
    [measureCanvas],
  );
  const width = displayed.width || fallbackWidth;
  const height = displayed.height || fallbackHeight;
  // Backing store in device pixels (sharp on high-DPI screens); all drawing
  // below stays in CSS pixels via the context transform.
  const dpr = typeof window === "undefined" ? 1 : window.devicePixelRatio || 1;
  const [interpolator] = useState(() => new SnapshotInterpolator());
  const [environment] = useState(() => new EnvironmentLayer());

  useEffect(() => {
    interpolator.push(snapshot, performance.now());
  }, [snapshot, interpolator]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    let active = true;
    let frameId = 0;
    // Whether the canvas currently shows the empty (no data) state or a
    // snapshot. A (re)started effect has drawn neither, so it paints once.
    let drewEmpty = false;
    let drewFrame = false;

    const render = () => {
      if (!active) return;
      frameId = requestAnimationFrame(render);

      const frame = interpolator.sample(performance.now());
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (!frame) {
        if (!drewEmpty) {
          // Draw grass background while waiting for data
          ctx.fillStyle = GROUND_BASE;
          ctx.fillRect(0, 0, width, height);
          drewEmpty = true;
          drewFrame = false;
        }
        return;
      }
      // Nothing moved (paused/stopped/completed and no new snapshot).
      if (!frame.changed && drewFrame) return;
      drewFrame = true;
      drewEmpty = false;
      const current = frame.snapshot;

      const controller = current.controller;
      const innerRadius =
        controller.type === "roundabout" ? controller.innerRadius : 10;
      const outerRadius =
        controller.type === "roundabout" ? controller.outerRadius : 20;
      // Same pixels-per-metre as the signal map (see mapScale), so both
      // render at the same scale side by side.
      const scale = mapScale(width, height);
      const armReach = Math.max(width, height) / scale + 10;
      const toCanvas = (x: number, y: number): [number, number] => [
        width / 2 + x * scale,
        height / 2 - y * scale,
      ];

      // V1.5: a real-world junction is drawn from its snapshot geometry.
      if (
        drawRealWorldFrame(ctx, current, frame.vehicles, toCanvas, scale, {
          width,
          height,
          reach: armReach,
        })
      )
        return;

      // Roads are laid out exactly as the backend lays out vehicle lanes
      // (see mapGeometry.ts): each carriageway sits outside the splitter
      // island, and every entry lane ends at the give-way line. V1.4: every
      // arm has its own lane count, and the ring its own circulating lanes,
      // both read from the snapshot.
      const armLanes = (arm: Arm): number =>
        current.intersection.approaches.find((a) => a.direction === arm)
          ?.laneCount ?? lanes;
      const edges = ARM_ORDER.map((arm) =>
        roundaboutCarriagewayEdge(armLanes(arm), laneWidth),
      );
      const edge = Math.max(...edges);
      const ringLanes =
        (controller.type === "roundabout"
          ? controller.circulatingLanes
          : undefined) ??
        current.intersection.circulatingLanes ??
        Math.max(...ARM_ORDER.map(armLanes));
      const giveWay = roundaboutGiveWayRadius(outerRadius);

      // Grass, sidewalk and roadside planting, all beneath the roads.
      environment.paint(
        ctx,
        roundaboutEnvironment(edge, outerRadius, armReach),
        { width, height, ppm: scale, dpr },
      );

      // Arms run in from the centre so they meet the ring without gaps where
      // entry/exit paths cross from the arm onto the circulating carriageway.
      ctx.fillStyle = "#343b42";
      ARM_ORDER.forEach((_arm, i) => {
        const e = edges[i];
        const c = Math.round(Math.cos((i * Math.PI) / 2));
        const s = Math.round(Math.sin((i * Math.PI) / 2));
        const [ax, ay] = [-e * c, -e * s];
        const [bx, by] = [e * c - armReach * s, e * s + armReach * c];
        fillWorldRect(
          ctx,
          toCanvas,
          Math.min(ax, bx),
          Math.min(ay, by),
          Math.abs(bx - ax),
          Math.abs(by - ay),
        );
      });

      const [cx, cy] = toCanvas(0, 0);
      ctx.fillStyle = "#343b42";
      ctx.beginPath();
      ctx.arc(cx, cy, outerRadius * scale, 0, Math.PI * 2);
      ctx.fill();

      // Flare out the road entries smoothly for a clean intersection look.
      // Corner i lies between arm i (its +x side, in that arm's frame) and
      // the arm a quarter turn clockwise from it.
      ctx.fillStyle = "#343b42";
      for (let i = 0; i < 4; i++) {
        const angle = (i * Math.PI) / 2;
        const c = Math.round(Math.cos(angle));
        const s = Math.round(Math.sin(angle));
        const tx = (x: number, y: number) =>
          toCanvas(x * c - y * s, x * s + y * c);
        const near = edges[i];
        const far = edges[(i + 3) % 4];

        ctx.beginPath();
        const [startX, startY] = tx(near, outerRadius + 15);
        ctx.moveTo(startX, startY);
        const [cpX, cpY] = tx(near, far);
        const [endX, endY] = tx(outerRadius + 15, far);
        ctx.quadraticCurveTo(cpX, cpY, endX, endY);
        const [centerX, centerY] = tx(0, 0);
        ctx.lineTo(centerX, centerY);
        ctx.fill();
      }

      // Continuous solid white outer boundary of the road (arms + flares)
      ctx.strokeStyle = "#e5eaed";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([]);
      for (let i = 0; i < 4; i++) {
        const angle = (i * Math.PI) / 2;
        const c = Math.round(Math.cos(angle));
        const s = Math.round(Math.sin(angle));
        const tx = (x: number, y: number) =>
          toCanvas(x * c - y * s, x * s + y * c);
        const near = edges[i];
        const far = edges[(i + 3) % 4];

        ctx.beginPath();
        const [armStartX, armStartY] = tx(near, armReach);
        ctx.moveTo(armStartX, armStartY);

        const [flareStartX, flareStartY] = tx(near, outerRadius + 15);
        ctx.lineTo(flareStartX, flareStartY);

        const [cpX, cpY] = tx(near, far);
        const [flareEndX, flareEndY] = tx(outerRadius + 15, far);
        ctx.quadraticCurveTo(cpX, cpY, flareEndX, flareEndY);

        const [armEndX, armEndY] = tx(armReach, far);
        ctx.lineTo(armEndX, armEndY);
        ctx.stroke();
      }

      // Markings between circulating lanes (V1.4: the ring's own count).
      ctx.strokeStyle = "rgba(229, 234, 237, 0.65)";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([6, 8]);
      for (const radius of roundaboutRingDividers(
        innerRadius,
        outerRadius,
        ringLanes,
      )) {
        ctx.beginPath();
        ctx.arc(cx, cy, radius * scale, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.setLineDash([]);

      ctx.beginPath();
      ctx.arc(cx, cy, innerRadius * scale, 0, Math.PI * 2);
      environment.fillWithGround(ctx);
      ctx.strokeStyle = "#e5eaed";
      ctx.lineWidth = 2;
      ctx.stroke();
      paintIslandPlanting(ctx, [cx, cy], innerRadius, scale);

      drawApproachMarkings(
        ctx,
        toCanvas,
        outerRadius,
        armReach,
        ARM_ORDER.map(armLanes),
        laneWidth,
        showCrosswalks,
        environment,
      );
      drawEntryYieldSigns(ctx, toCanvas, giveWay, edges);
      drawLaneArrows(
        ctx,
        current.intersection.approaches,
        (_direction, count) => roundaboutLaneCentres(count, laneWidth),
        giveWay + 5.5,
        scale,
        toCanvas,
      );

      const now = performance.now();
      for (const pose of frame.vehicles) {
        const [vx, vy] = toCanvas(pose.x, pose.y);
        drawVehicleSprite(ctx, pose.vehicle, vx, vy, pose.heading, scale, now);
      }

      if (debug) drawDebugLabel(ctx, current, width);
    };

    render();

    return () => {
      active = false;
      cancelAnimationFrame(frameId);
    };
  }, [
    width,
    height,
    dpr,
    laneWidth,
    lanes,
    showCrosswalks,
    debug,
    interpolator,
    environment,
  ]);

  return (
    <canvas
      ref={setCanvas}
      width={Math.round(width * dpr)}
      height={Math.round(height * dpr)}
      style={{ display: "block", borderRadius: "8px" }}
    />
  );
};

function fillWorldRect(
  ctx: CanvasRenderingContext2D,
  toCanvas: (x: number, y: number) => [number, number],
  x: number,
  y: number,
  width: number,
  height: number,
) {
  const [left, top] = toCanvas(x, y + height);
  const [right, bottom] = toCanvas(x + width, y);
  ctx.fillRect(left, top, right - left, bottom - top);
}

function drawApproachMarkings(
  ctx: CanvasRenderingContext2D,
  toCanvas: (x: number, y: number) => [number, number],
  radius: number,
  armReach: number,
  /** Lanes per arm, in ARM_ORDER (north, west, south, east). */
  armLanes: number[],
  laneWidth: number,
  showCrosswalks: boolean,
  environment: EnvironmentLayer,
) {
  const island = ROUNDABOUT_SPLITTER_HALF_WIDTH;
  const giveWay = roundaboutGiveWayRadius(radius);

  /** Line at lateral offset ``offset`` (both carriageways) along arm i. */
  const alongArm = (i: number, offset: number, start: number) => {
    const c = Math.round(Math.cos((i * Math.PI) / 2));
    const s = Math.round(Math.sin((i * Math.PI) / 2));
    for (const side of [-1, 1]) {
      const o = side * offset;
      drawWorldLine(
        ctx,
        toCanvas,
        o * c - start * s,
        o * s + start * c,
        o * c - armReach * s,
        o * s + armReach * c,
      );
    }
  };

  // Splitter island between the entry and exit carriageways.
  for (let i = 0; i < 4; i++) {
    const angle = (i * Math.PI) / 2;
    const c = Math.round(Math.cos(angle));
    const s = Math.round(Math.sin(angle));
    const tx = (x: number, y: number) => toCanvas(x * c - y * s, x * s + y * c);

    ctx.beginPath();
    const [p1x, p1y] = tx(-island, armReach);
    ctx.moveTo(p1x, p1y);
    const [p2x, p2y] = tx(island, armReach);
    ctx.lineTo(p2x, p2y);
    const [p3x, p3y] = tx(island, giveWay);
    ctx.lineTo(p3x, p3y);

    // Rounded tip at the give-way line
    const [cp1x, cp1y] = tx(0, giveWay - island);
    const [p4x, p4y] = tx(-island, giveWay);
    ctx.quadraticCurveTo(cp1x, cp1y, p4x, p4y);

    environment.fillWithGround(ctx);
    ctx.strokeStyle = "#e5eaed";
    ctx.lineWidth = 1.2;
    ctx.stroke();
  }

  ctx.strokeStyle = "rgba(255,255,255,.7)";
  ctx.lineWidth = 1.4;
  ctx.setLineDash([8, 10]);
  armLanes.forEach((lanes, i) => {
    for (const offset of roundaboutLaneDividers(lanes, laneWidth)) {
      alongArm(i, offset, giveWay);
    }
  });
  ctx.setLineDash([]);

  if (!showCrosswalks) return;
  ctx.fillStyle = "rgba(255,255,255,.78)";
  const distance = roundaboutGiveWayRadius(radius) + 3;
  armLanes.forEach((lanes, arm) => {
    const edge = roundaboutCarriagewayEdge(lanes, laneWidth);
    const c = Math.round(Math.cos((arm * Math.PI) / 2));
    const s = Math.round(Math.sin((arm * Math.PI) / 2));
    for (let i = -5; i <= 5; i += 1) {
      const offset = i * (edge / 6);
      const [x, y] = toCanvas(
        offset * c - distance * s,
        offset * s + distance * c,
      );
      if (c === 0) ctx.fillRect(x - 5, y - 3, 10, 6);
      else ctx.fillRect(x - 3, y - 5, 6, 10);
    }
  });
}

function drawEntryYieldSigns(
  ctx: CanvasRenderingContext2D,
  toCanvas: (x: number, y: number) => [number, number],
  giveWay: number,
  /** Carriageway edge per arm, in ARM_ORDER (north, west, south, east). */
  edges: number[],
) {
  const [northEdge, westEdge, southEdge, eastEdge] = edges;
  const island = ROUNDABOUT_SPLITTER_HALF_WIDTH;
  // Signs stand on the splitter island at the give-way line.
  const entries: Array<[number, number, "north" | "south" | "east" | "west"]> =
    [
      [0, giveWay, "north"],
      [0, -giveWay, "south"],
      [giveWay, 0, "east"],
      [-giveWay, 0, "west"],
    ];
  for (const [x, y, direction] of entries) {
    const [cx, cy] = toCanvas(x, y);
    ctx.fillStyle = "#f5f6f3";
    ctx.strokeStyle = "#d33b35";
    ctx.lineWidth = 2;
    ctx.beginPath();
    if (direction === "north" || direction === "south") {
      ctx.moveTo(cx, direction === "north" ? cy + 10 : cy - 10);
      ctx.lineTo(cx - 9, direction === "north" ? cy - 7 : cy + 7);
      ctx.lineTo(cx + 9, direction === "north" ? cy - 7 : cy + 7);
    } else {
      ctx.moveTo(direction === "east" ? cx - 10 : cx + 10, cy);
      ctx.lineTo(direction === "east" ? cx + 7 : cx - 7, cy - 9);
      ctx.lineTo(direction === "east" ? cx + 7 : cx - 7, cy + 9);
    }
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }

  // Give-way lines across each entry carriageway, where its lanes end and
  // yielding vehicles are held. Traffic keeps right, so each arm's entry
  // carriageway is the one on the driver's right approaching the ring.
  ctx.strokeStyle = "rgba(255,255,255,.85)";
  ctx.lineWidth = 2;
  ctx.setLineDash([5, 5]);
  drawWorldLine(ctx, toCanvas, -island, giveWay, -northEdge, giveWay);
  drawWorldLine(ctx, toCanvas, island, -giveWay, southEdge, -giveWay);
  drawWorldLine(ctx, toCanvas, giveWay, island, giveWay, eastEdge);
  drawWorldLine(ctx, toCanvas, -giveWay, -island, -giveWay, -westEdge);
  ctx.setLineDash([]);
}

function drawWorldLine(
  ctx: CanvasRenderingContext2D,
  toCanvas: (x: number, y: number) => [number, number],
  x1: number,
  y1: number,
  x2: number,
  y2: number,
) {
  const [a, b] = toCanvas(x1, y1);
  const [c, d] = toCanvas(x2, y2);
  ctx.beginPath();
  ctx.moveTo(a, b);
  ctx.lineTo(c, d);
  ctx.stroke();
}

function drawDebugLabel(
  ctx: CanvasRenderingContext2D,
  snapshot: LiveSnapshot | null,
  width: number,
) {
  ctx.fillStyle = "rgba(15,20,24,.86)";
  ctx.fillRect(width - 200, 14, 186, 38);
  ctx.fillStyle = "#fff";
  ctx.font = '11px "Roboto Mono", monospace';
  ctx.fillText(
    `ROUNDABOUT  T ${(snapshot?.timestamp ?? 0).toFixed(1)}s`,
    width - 188,
    38,
  );
}
