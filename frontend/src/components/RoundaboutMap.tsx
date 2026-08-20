import React, { useEffect, useRef } from "react";
import type { LiveSnapshot, SnapshotVehicle } from "../types/simulation";

interface RoundaboutMapProps {
  snapshot: LiveSnapshot | null;
  width?: number;
  height?: number;
  laneWidth?: number;
  showCrosswalks?: boolean;
  debug?: boolean;
}

type Direction = "north" | "south" | "east" | "west";

const COLORS = [
  "#4d96ff",
  "#f8961e",
  "#43aa8b",
  "#e76f51",
  "#c77dff",
  "#f9c74f",
];

function vehicleColor(id: string): string {
  let hash = 0;
  for (const character of id)
    hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  return COLORS[hash % COLORS.length];
}

function laneIndex(laneId: string): number {
  const match = laneId.match(/_(?:in|out)_(\d+)/);
  return match ? Number(match[1]) : 0;
}

function entryAngle(direction: Direction): number {
  return { north: Math.PI / 2, east: 0, south: -Math.PI / 2, west: Math.PI }[
    direction
  ];
}

function exitDirection(
  origin: Direction,
  turnIntent: SnapshotVehicle["turnIntent"],
): Direction {
  const order: Direction[] = ["north", "east", "south", "west"];
  const originIndex = order.indexOf(origin);
  const offset = turnIntent === "right" ? 1 : turnIntent === "left" ? 3 : 2;
  return order[(originIndex + offset) % order.length];
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(maximum, value));
}

function turnArc(turnIntent: SnapshotVehicle["turnIntent"]): number {
  if (turnIntent === "right") return Math.PI / 2;
  if (turnIntent === "left") return Math.PI * 1.5;
  return Math.PI;
}

function laneDirection(laneId: string, fallback: Direction): Direction {
  const prefix = laneId.charAt(0).toLowerCase();
  const directions: Record<string, Direction> = {
    n: "north",
    s: "south",
    e: "east",
    w: "west",
  };
  return directions[prefix] ?? fallback;
}

export const RoundaboutMap: React.FC<RoundaboutMapProps> = ({
  snapshot,
  width = 800,
  height = 680,
  laneWidth = 3.5,
  showCrosswalks = true,
  debug = false,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const ctx = canvasRef.current?.getContext("2d");
    if (!ctx) return;

    const controller = snapshot?.controller;
    const innerRadius =
      controller?.type === "roundabout" ? controller.innerRadius : 10;
    const outerRadius =
      controller?.type === "roundabout" ? controller.outerRadius : 20;
    const ringRadius = (innerRadius + outerRadius) / 2;
    const armReach = outerRadius + 42;
    const scale = Math.min(width, height) / (armReach * 2);
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

    const armWidth = laneWidth * 4;
    ctx.fillStyle = "#343b42";
    fillWorldRect(
      ctx,
      toCanvas,
      -armWidth / 2,
      outerRadius,
      armWidth,
      armReach - outerRadius,
    );
    fillWorldRect(
      ctx,
      toCanvas,
      -armWidth / 2,
      -armReach,
      armWidth,
      armReach - outerRadius,
    );
    fillWorldRect(
      ctx,
      toCanvas,
      outerRadius,
      -armWidth / 2,
      armReach - outerRadius,
      armWidth,
    );
    fillWorldRect(
      ctx,
      toCanvas,
      -armReach,
      -armWidth / 2,
      armReach - outerRadius,
      armWidth,
    );

    const [cx, cy] = toCanvas(0, 0);
    ctx.fillStyle = "#343b42";
    ctx.beginPath();
    ctx.arc(cx, cy, outerRadius * scale, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#557d35";
    ctx.beginPath();
    ctx.arc(cx, cy, innerRadius * scale, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#bcc6ca";
    ctx.lineWidth = 2.5;
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.arc(cx, cy, outerRadius * scale, 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeStyle = "#dfe7e9";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(cx, cy, innerRadius * scale, 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeStyle = "#f4f6f6";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([8, 8]);
    ctx.beginPath();
    ctx.arc(cx, cy, ringRadius * scale, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);

    drawApproachMarkings(
      ctx,
      toCanvas,
      outerRadius,
      armReach,
      armWidth,
      showCrosswalks,
    );
    drawEntryYieldSigns(ctx, toCanvas, outerRadius, armReach, armWidth);

    for (const vehicle of snapshot?.vehicles ?? []) {
      if (vehicle.state !== "exited") {
        drawRoundaboutVehicle(
          ctx,
          vehicle,
          toCanvas,
          scale,
          ringRadius,
          outerRadius,
        );
      }
    }

    if (debug) drawDebugLabel(ctx, snapshot, width);
  }, [snapshot, width, height, laneWidth, showCrosswalks, debug]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
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
  armWidth: number,
  showCrosswalks: boolean,
) {
  ctx.strokeStyle = "#d7dde0";
  ctx.lineWidth = 1.5;
  ctx.setLineDash([]);
  const edge = armWidth / 2;
  for (const x of [-edge, edge]) {
    drawWorldLine(ctx, toCanvas, x, radius, x, armReach);
    drawWorldLine(ctx, toCanvas, x, -radius, x, -armReach);
  }
  for (const y of [-edge, edge]) {
    drawWorldLine(ctx, toCanvas, radius, y, armReach, y);
    drawWorldLine(ctx, toCanvas, -radius, y, -armReach, y);
  }
  ctx.lineWidth = 1.4;
  for (const offset of [
    -laneWidthForArm(armWidth),
    0,
    laneWidthForArm(armWidth),
  ]) {
    ctx.strokeStyle = offset === 0 ? "#e7bd2e" : "rgba(255,255,255,.7)";
    ctx.setLineDash(offset === 0 ? [] : [8, 10]);
    drawWorldLine(ctx, toCanvas, offset, radius, offset, armReach);
    drawWorldLine(ctx, toCanvas, offset, -radius, offset, -armReach);
    drawWorldLine(ctx, toCanvas, radius, offset, armReach, offset);
    drawWorldLine(ctx, toCanvas, -radius, offset, -armReach, offset);
  }
  ctx.setLineDash([]);
  if (!showCrosswalks) return;
  ctx.fillStyle = "rgba(255,255,255,.78)";
  for (let i = -5; i <= 5; i += 1) {
    const offset = i * (armWidth / 12);
    const [x1, y1] = toCanvas(offset, radius + 1.5);
    ctx.fillRect(x1 - 3, y1 - 5, 6, 10);
    const [x2, y2] = toCanvas(offset, -radius - 1.5);
    ctx.fillRect(x2 - 3, y2 - 5, 6, 10);
    const [x3, y3] = toCanvas(radius + 1.5, offset);
    ctx.fillRect(x3 - 5, y3 - 3, 10, 6);
    const [x4, y4] = toCanvas(-radius - 1.5, offset);
    ctx.fillRect(x4 - 5, y4 - 3, 10, 6);
  }
}

function laneWidthForArm(armWidth: number): number {
  return armWidth / 4;
}

function drawEntryYieldSigns(
  ctx: CanvasRenderingContext2D,
  toCanvas: (x: number, y: number) => [number, number],
  radius: number,
  armReach: number,
  armWidth: number,
) {
  const edge = armWidth / 2;
  const entries: Array<[number, number, "north" | "south" | "east" | "west"]> =
    [
      [0, radius + 3, "north"],
      [0, -radius - 3, "south"],
      [radius + 3, 0, "east"],
      [-radius - 3, 0, "west"],
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
  ctx.strokeStyle = "rgba(255,255,255,.55)";
  ctx.lineWidth = 1;
  ctx.setLineDash([5, 7]);
  drawWorldLine(ctx, toCanvas, -edge, armReach, edge, armReach);
  drawWorldLine(ctx, toCanvas, -edge, -armReach, edge, -armReach);
  drawWorldLine(ctx, toCanvas, armReach, -edge, armReach, edge);
  drawWorldLine(ctx, toCanvas, -armReach, -edge, -armReach, edge);
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

function drawRoundaboutVehicle(
  ctx: CanvasRenderingContext2D,
  vehicle: SnapshotVehicle,
  toCanvas: (x: number, y: number) => [number, number],
  scale: number,
  ringRadius: number,
  outerRadius: number,
) {
  const direction: Direction = vehicle.direction;
  const index = laneIndex(vehicle.laneId);
  const laneOffset = (index - 1.5) * 2.1;
  const exit = exitDirection(direction, vehicle.turnIntent);
  const startAngle = entryAngle(direction);
  const exitAngle = entryAngle(exit);
  const laneId = vehicle.laneId.toLowerCase();
  const approachLength = 200;
  const isConnection =
    laneId.startsWith("conn_") || vehicle.state === "in_roundabout";
  const isExit = laneId.includes("_out_");
  const rawDistance =
    direction === "north"
      ? 200 - vehicle.y
      : direction === "south"
        ? vehicle.y + 200
        : direction === "east"
          ? 200 - vehicle.x
          : vehicle.x + 200;
  const approachProgress = clamp(
    rawDistance / (approachLength - outerRadius),
    0,
    1,
  );
  const connectionProgress = clamp(
    vehicle.distanceTraveled / Math.max(18, outerRadius * 1.5),
    0,
    1,
  );
  const exitDirectionValue = laneDirection(laneId, exit);
  const exitDistance =
    exitDirectionValue === "north"
      ? vehicle.y
      : exitDirectionValue === "south"
        ? -vehicle.y
        : exitDirectionValue === "east"
          ? vehicle.x
          : -vehicle.x;
  const exitProgress = clamp((exitDistance - outerRadius) / 42, 0, 1);
  const angle = startAngle - turnArc(vehicle.turnIntent) * connectionProgress;
  let x: number;
  let y: number;
  let heading: number;

  if (!isConnection && !isExit) {
    const distance = outerRadius + 42 - approachProgress * 42;
    if (direction === "north") {
      x = -laneOffset;
      y = distance;
      heading = 180;
    } else if (direction === "south") {
      x = laneOffset;
      y = -distance;
      heading = 0;
    } else if (direction === "east") {
      x = distance;
      y = laneOffset;
      heading = 270;
    } else {
      x = -distance;
      y = -laneOffset;
      heading = 90;
    }
  } else if (isConnection) {
    x = ringRadius * Math.cos(angle);
    y = ringRadius * Math.sin(angle);
    heading = (angle * 180) / Math.PI - 90;
  } else {
    const startX = ringRadius * Math.cos(exitAngle);
    const startY = ringRadius * Math.sin(exitAngle);
    const endDistance = outerRadius + 42;
    const endX = endDistance * Math.cos(exitAngle);
    const endY = endDistance * Math.sin(exitAngle);
    x = startX + (endX - startX) * exitProgress;
    y = startY + (endY - startY) * exitProgress;
    heading = (exitAngle * 180) / Math.PI - 90;
  }

  const [cx, cy] = toCanvas(x, y);
  const length = Math.max(4.5, vehicle.length) * scale;
  const width = Math.max(2, vehicle.width) * scale;
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate((heading * Math.PI) / 180);
  ctx.fillStyle = vehicleColor(vehicle.id);
  ctx.strokeStyle = "#172027";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(-width / 2, -length / 2, width, length, 4);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "rgba(224,243,255,.8)";
  ctx.fillRect(-width * 0.34, -length * 0.28, width * 0.68, length * 0.24);
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
