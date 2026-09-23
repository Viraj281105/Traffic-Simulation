import React, { useCallback, useEffect, useRef, useState } from "react";
import { useContainerSize } from "../hooks/useContainerSize";
import type { LiveSnapshot } from "../types/simulation";
import {
  ROUNDABOUT_SPLITTER_HALF_WIDTH,
  roundaboutCarriagewayEdge,
  roundaboutGiveWayRadius,
  roundaboutLaneDividers,
  roundaboutRingDividers,
  mapScale,
} from "./mapGeometry";
import { SnapshotInterpolator, type VehiclePose } from "./snapshotInterpolator";

interface RoundaboutMapProps {
  snapshot: LiveSnapshot | null;
  width?: number;
  height?: number;
  laneWidth?: number;
  lanes?: number;
  showCrosswalks?: boolean;
  debug?: boolean;
}

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
          ctx.fillStyle = "#557d35";
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

      ctx.fillStyle = "#557d35";
      ctx.fillRect(0, 0, width, height);
      ctx.strokeStyle = "rgba(28,58,28,.2)";
      ctx.lineWidth = 1;
      for (let y = 0; y < height; y += 18) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      // Roads are laid out exactly as the backend lays out vehicle lanes
      // (see mapGeometry.ts): each carriageway sits outside the splitter
      // island, and every entry lane ends at the give-way line.
      const edge = roundaboutCarriagewayEdge(lanes, laneWidth);
      const giveWay = roundaboutGiveWayRadius(outerRadius);

      // Arms run in from the centre so they meet the ring without gaps where
      // entry/exit paths cross from the arm onto the circulating carriageway.
      ctx.fillStyle = "#343b42";
      fillWorldRect(ctx, toCanvas, -edge, 0, edge * 2, armReach);
      fillWorldRect(ctx, toCanvas, -edge, -armReach, edge * 2, armReach);
      fillWorldRect(ctx, toCanvas, 0, -edge, armReach, edge * 2);
      fillWorldRect(ctx, toCanvas, -armReach, -edge, armReach, edge * 2);

      const [cx, cy] = toCanvas(0, 0);
      ctx.fillStyle = "#343b42";
      ctx.beginPath();
      ctx.arc(cx, cy, outerRadius * scale, 0, Math.PI * 2);
      ctx.fill();

      // Flare out the road entries smoothly for a clean intersection look
      ctx.fillStyle = "#343b42";
      for (let i = 0; i < 4; i++) {
        const angle = (i * Math.PI) / 2;
        const c = Math.round(Math.cos(angle));
        const s = Math.round(Math.sin(angle));
        const tx = (x: number, y: number) =>
          toCanvas(x * c - y * s, x * s + y * c);

        ctx.beginPath();
        const [startX, startY] = tx(edge, outerRadius + 15);
        ctx.moveTo(startX, startY);
        const [cpX, cpY] = tx(edge, edge);
        const [endX, endY] = tx(outerRadius + 15, edge);
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

        ctx.beginPath();
        const [armStartX, armStartY] = tx(edge, armReach);
        ctx.moveTo(armStartX, armStartY);
        
        const [flareStartX, flareStartY] = tx(edge, outerRadius + 15);
        ctx.lineTo(flareStartX, flareStartY);

        const [cpX, cpY] = tx(edge, edge);
        const [flareEndX, flareEndY] = tx(outerRadius + 15, edge);
        ctx.quadraticCurveTo(cpX, cpY, flareEndX, flareEndY);

        const [armEndX, armEndY] = tx(armReach, edge);
        ctx.lineTo(armEndX, armEndY);
        ctx.stroke();
      }

      // Markings between circulating lanes (one lane per approach lane).
      ctx.strokeStyle = "rgba(229, 234, 237, 0.65)";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([6, 8]);
      for (const radius of roundaboutRingDividers(
        innerRadius,
        outerRadius,
        lanes,
      )) {
        ctx.beginPath();
        ctx.arc(cx, cy, radius * scale, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.setLineDash([]);

      ctx.fillStyle = "#557d35";
      ctx.beginPath();
      ctx.arc(cx, cy, innerRadius * scale, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#e5eaed";
      ctx.lineWidth = 2;
      ctx.stroke();

      drawApproachMarkings(
        ctx,
        toCanvas,
        outerRadius,
        armReach,
        lanes,
        laneWidth,
        showCrosswalks,
      );
      drawEntryYieldSigns(ctx, toCanvas, giveWay, edge);

      for (const pose of frame.vehicles) {
        drawRoundaboutVehicle(ctx, pose, toCanvas, scale);
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
  lanes: number,
  laneWidth: number,
  showCrosswalks: boolean,
) {
  const island = ROUNDABOUT_SPLITTER_HALF_WIDTH;
  const edge = roundaboutCarriagewayEdge(lanes, laneWidth);
  const giveWay = roundaboutGiveWayRadius(radius);

  const alongArms = (offset: number, start: number) => {
    for (const side of [-1, 1]) {
      const o = side * offset;
      drawWorldLine(ctx, toCanvas, o, start, o, armReach);
      drawWorldLine(ctx, toCanvas, o, -start, o, -armReach);
      drawWorldLine(ctx, toCanvas, start, o, armReach, o);
      drawWorldLine(ctx, toCanvas, -start, o, -armReach, o);
    }
  };

  // Splitter island between the entry and exit carriageways.
  for (let i = 0; i < 4; i++) {
    const angle = (i * Math.PI) / 2;
    const c = Math.round(Math.cos(angle));
    const s = Math.round(Math.sin(angle));
    const tx = (x: number, y: number) =>
      toCanvas(x * c - y * s, x * s + y * c);

    ctx.fillStyle = "#557d35";
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

    ctx.fill();
    ctx.strokeStyle = "#e5eaed";
    ctx.lineWidth = 1.2;
    ctx.stroke();
  }

  ctx.strokeStyle = "rgba(255,255,255,.7)";
  ctx.lineWidth = 1.4;
  ctx.setLineDash([8, 10]);
  for (const offset of roundaboutLaneDividers(lanes, laneWidth)) {
    alongArms(offset, giveWay);
  }
  ctx.setLineDash([]);

  if (!showCrosswalks) return;
  ctx.fillStyle = "rgba(255,255,255,.78)";
  const distance = roundaboutGiveWayRadius(radius) + 3;
  for (let i = -5; i <= 5; i += 1) {
    const offset = i * (edge / 6);
    const [x1, y1] = toCanvas(offset, distance);
    ctx.fillRect(x1 - 3, y1 - 5, 6, 10);
    const [x2, y2] = toCanvas(offset, -distance);
    ctx.fillRect(x2 - 3, y2 - 5, 6, 10);
    const [x3, y3] = toCanvas(distance, offset);
    ctx.fillRect(x3 - 5, y3 - 3, 10, 6);
    const [x4, y4] = toCanvas(-distance, offset);
    ctx.fillRect(x4 - 5, y4 - 3, 10, 6);
  }
}

function drawEntryYieldSigns(
  ctx: CanvasRenderingContext2D,
  toCanvas: (x: number, y: number) => [number, number],
  giveWay: number,
  edge: number,
) {
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
  drawWorldLine(ctx, toCanvas, -island, giveWay, -edge, giveWay);
  drawWorldLine(ctx, toCanvas, island, -giveWay, edge, -giveWay);
  drawWorldLine(ctx, toCanvas, giveWay, island, giveWay, edge);
  drawWorldLine(ctx, toCanvas, -giveWay, -island, -giveWay, -edge);
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

function carColor(id: string): string {
  const palette = [
    "#4d96ff",
    "#f8961e",
    "#43aa8b",
    "#e76f51",
    "#c77dff",
    "#f9c74f",
  ];
  let hash = 0;
  for (const character of id)
    hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  return palette[hash % palette.length];
}

function drawRoundaboutVehicle(
  ctx: CanvasRenderingContext2D,
  pose: VehiclePose,
  toCanvas: (x: number, y: number) => [number, number],
  scale: number,
) {
  const { vehicle } = pose;
  const [cx, cy] = toCanvas(pose.x, pose.y);
  const length = Math.max(4.5, vehicle.length) * scale;
  const width = Math.max(2, vehicle.width) * scale;
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate((pose.heading * Math.PI) / 180);

  ctx.fillStyle = carColor(vehicle.id);
  ctx.strokeStyle = "#172027";
  ctx.lineWidth = 2;

  ctx.beginPath();
  ctx.roundRect(-width / 2, -length / 2, width, length, 4);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = "rgba(224,243,255,.8)";
  ctx.beginPath();
  ctx.roundRect(-width * 0.34, -length * 0.28, width * 0.68, length * 0.24, 2);
  ctx.fill();

  // Draw brake lights if waiting
  if (vehicle.state === "waiting") {
    ctx.fillStyle = "#ff1744";
    ctx.beginPath();
    ctx.arc(-width * 0.3, length / 2, 2.5, 0, Math.PI * 2);
    ctx.arc(width * 0.3, length / 2, 2.5, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.restore();
}

function drawDebugLabel(
  ctx: CanvasRenderingContext2D,
  snapshot: LiveSnapshot | null,
  width: number,
) {
  ctx.fillStyle = "rgba(15,20,24,.86)";
  ctx.fillRect(width - 200, 14, 186, 38);
  ctx.fillStyle = "#fff";
  ctx.font = "11px monospace";
  ctx.fillText(
    `ROUNDABOUT  T ${(snapshot?.timestamp ?? 0).toFixed(1)}s`,
    width - 188,
    38,
  );
}
