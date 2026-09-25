import React, { useCallback, useEffect, useRef, useState } from "react";
import { useContainerSize } from "../hooks/useContainerSize";
import type { LiveSnapshot, SignalDirection } from "../types/simulation";
import { SnapshotInterpolator, type VehiclePose } from "./snapshotInterpolator";
import { mapScale, signalStopLineDistance } from "./mapGeometry";
import {
  EnvironmentLayer,
  GROUND_BASE,
  signalEnvironment,
} from "./mapEnvironment";

export interface IntersectionMapProps {
  snapshot: LiveSnapshot | null;
  width?: number;
  height?: number;
  lanesNorth?: number;
  lanesSouth?: number;
  lanesEast?: number;
  lanesWest?: number;
  laneWidth?: number;
  showCrosswalks?: boolean;
  showStopLines?: boolean;
  debug?: boolean;
  /** Pixels per metre. Defaults to the scale shared with the roundabout map
   *  (see mapScale), so the two render at the same size side by side. */
  ppm?: number;
}

type Direction = "north" | "south" | "east" | "west";
type Widths = Record<Direction, number>;
type Point = (x: number, y: number) => [number, number];

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

function signalColor(color: string): string {
  return color === "green"
    ? "#55d66b"
    : color === "yellow"
      ? "#ffd166"
      : color === "red"
        ? "#f04f4f"
        : "#555b60";
}

export const IntersectionMap: React.FC<IntersectionMapProps> = ({
  snapshot,
  width: fallbackWidth = 800,
  height: fallbackHeight = 680,
  lanesNorth = 2,
  lanesSouth = 2,
  lanesEast = 2,
  lanesWest = 2,
  laneWidth = 3.5,
  showCrosswalks = true,
  showStopLines = true,
  debug = false,
  ppm: ppmOverride,
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
  const ppm = ppmOverride ?? mapScale(width, height);
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

    // The junction box ends at the stop line, where the backend ends each
    // incoming lane and holds traffic on red (see mapGeometry.ts).
    const half = signalStopLineDistance(
      Math.max(lanesNorth, lanesSouth, lanesEast, lanesWest),
      laneWidth,
    );
    const widths: Widths = {
      north: lanesNorth * laneWidth * 2,
      south: lanesSouth * laneWidth * 2,
      east: lanesEast * laneWidth * 2,
      west: lanesWest * laneWidth * 2,
    };
    const roadLength = Math.max(46, Math.ceil(Math.max(width, height) / ppm));
    const road = signalEnvironment(widths, half, roadLength);

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

      const point: Point = (x, y) => [
        x * ppm + width / 2,
        -y * ppm + height / 2,
      ];
      const line = (x1: number, y1: number, x2: number, y2: number) => {
        const [a, b] = point(x1, y1);
        const [c, d] = point(x2, y2);
        ctx.beginPath();
        ctx.moveTo(a, b);
        ctx.lineTo(c, d);
        ctx.stroke();
      };
      const rect = (x1: number, y1: number, x2: number, y2: number) => {
        const [left, top] = point(x1, y2);
        const [right, bottom] = point(x2, y1);
        ctx.fillRect(left, top, right - left, bottom - top);
      };

      // Grass, sidewalk and roadside planting, all beneath the roads.
      environment.paint(ctx, road, { width, height, ppm, dpr });

      // Draw roads
      ctx.fillStyle = "#343b42";
      rect(-widths.north / 2, half, widths.north / 2, roadLength);
      rect(-widths.south / 2, -roadLength, widths.south / 2, -half);
      rect(half, -widths.east / 2, roadLength, widths.east / 2);
      rect(-roadLength, -widths.west / 2, -half, widths.west / 2);
      rect(-half, -half, half, half);

      // Draw road borders
      ctx.strokeStyle = "#d7dde0";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([]);
      line(-widths.north / 2, half, -widths.north / 2, roadLength);
      line(widths.north / 2, half, widths.north / 2, roadLength);
      line(-widths.south / 2, -half, -widths.south / 2, -roadLength);
      line(widths.south / 2, -half, widths.south / 2, -roadLength);
      line(half, widths.east / 2, roadLength, widths.east / 2);
      line(half, -widths.east / 2, roadLength, -widths.east / 2);
      line(-half, widths.west / 2, -roadLength, widths.west / 2);
      line(-half, -widths.west / 2, -roadLength, -widths.west / 2);

      // Draw dividers
      const divider = (direction: Direction, count: number) => {
        for (let i = -count; i <= count; i += 1) {
          const center = i === 0;
          const offset = i * laneWidth;
          ctx.strokeStyle = center ? "#f2c230" : "rgba(255,255,255,.55)";
          ctx.lineWidth = center ? 2.2 : 1.2;
          ctx.setLineDash(center ? [] : [7, 9]);
          if (direction === "north") line(offset, half, offset, roadLength);
          if (direction === "south") line(offset, -half, offset, -roadLength);
          if (direction === "east") line(half, offset, roadLength, offset);
          if (direction === "west") line(-half, offset, -roadLength, offset);
        }
      };
      divider("north", lanesNorth);
      divider("south", lanesSouth);
      divider("east", lanesEast);
      divider("west", lanesWest);

      if (showStopLines) {
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 3;
        ctx.setLineDash([]);
        line(-widths.north / 2, half, 0, half);
        line(0, -half, widths.south / 2, -half);
        line(half, 0, half, widths.east / 2);
        line(-half, -widths.west / 2, -half, 0);
      }
      if (showCrosswalks) drawCrosswalks(ctx, half, widths, ppm, point);

      const controller = current.controller;
      if (controller.type === "roundabout") {
        const [cx, cy] = point(0, 0);
        ctx.fillStyle = "#343b42";
        ctx.beginPath();
        ctx.arc(cx, cy, controller.outerRadius * ppm, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.arc(cx, cy, controller.innerRadius * ppm, 0, Math.PI * 2);
        environment.fillWithGround(ctx);
        ctx.strokeStyle = "#e5eaed";
        ctx.setLineDash([7, 8]);
        ctx.stroke();
        ctx.setLineDash([]);
      }
      if (controller.type === "fixed_time_signal")
        drawSignals(ctx, controller.signals, half, widths, ppm, point);

      for (const pose of frame.vehicles) {
        drawVehicle(ctx, pose, ppm, point);
      }

      if (debug)
        drawQueues(
          ctx,
          current.intersection.approaches,
          half,
          widths,
          ppm,
          point,
        );
    };

    render();

    return () => {
      active = false;
      cancelAnimationFrame(frameId);
    };
  }, [
    width,
    height,
    lanesNorth,
    lanesSouth,
    lanesEast,
    lanesWest,
    laneWidth,
    showCrosswalks,
    showStopLines,
    debug,
    ppm,
    dpr,
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

function drawCrosswalks(
  ctx: CanvasRenderingContext2D,
  half: number,
  widths: Widths,
  ppm: number,
  point: Point,
) {
  ctx.fillStyle = "rgba(255,255,255,.75)";
  (Object.keys(widths) as Direction[]).forEach((direction) => {
    const distance = half + 2.8;
    const count = Math.max(3, Math.floor(widths[direction] / 2));
    for (let i = 0; i < count; i += 1) {
      const offset =
        -widths[direction] / 2 + i * (widths[direction] / count) + 0.3;
      if (direction === "north" || direction === "south") {
        const [x, y] = point(
          offset,
          direction === "north" ? distance : -distance,
        );
        ctx.fillRect(x, y - ppm * 0.9, ppm * 0.55, ppm * 1.8);
      } else {
        const [x, y] = point(
          direction === "east" ? distance : -distance,
          offset,
        );
        ctx.fillRect(x - ppm * 0.9, y, ppm * 1.8, ppm * 0.55);
      }
    }
  });
}

function drawSignals(
  ctx: CanvasRenderingContext2D,
  signals: { direction: SignalDirection; color: string }[],
  half: number,
  widths: Widths,
  ppm: number,
  point: Point,
) {
  const positions: Record<Direction, [number, number]> = {
    north: [-widths.north / 2 - 2.5, half + 2.5],
    south: [widths.south / 2 + 2.5, -half - 2.5],
    east: [half + 2.5, widths.east / 2 + 2.5],
    west: [-half - 2.5, -widths.west / 2 - 2.5],
  };
  for (const signal of signals) {
    const [x, y] = point(...positions[signal.direction]);
    // Sized in metres (about 2.4 m x 4.4 m) so heads keep their proportion
    // to the road at any map scale, with a legible minimum.
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

function drawVehicle(
  ctx: CanvasRenderingContext2D,
  pose: VehiclePose,
  ppm: number,
  point: Point,
) {
  const { vehicle } = pose;
  const [x, y] = point(pose.x, pose.y);
  const length = Math.max(vehicle.length, 4.5) * ppm;
  const width = Math.max(vehicle.width, 2) * ppm;
  ctx.save();
  ctx.translate(x, y);
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

function drawQueues(
  ctx: CanvasRenderingContext2D,
  approaches: { direction: string; queueLength: number }[],
  half: number,
  widths: Widths,
  ppm: number,
  point: Point,
) {
  const locations: Record<string, [number, number]> = {
    north: [-widths.north / 2 - 6, half + 3],
    south: [widths.south / 2 + 6, -half - 3],
    east: [half + 3, widths.east / 2 + 6],
    west: [-half - 3, -widths.west / 2 - 6],
  };
  for (const approach of approaches) {
    const location = locations[approach.direction] ?? [0, 0];
    const [x, y] = point(...location);
    ctx.fillStyle = "rgba(22,28,32,.85)";
    ctx.fillRect(x - 25, y - 11, 50, 22);
    ctx.fillStyle = "#fff";
    ctx.font = `${String(Math.max(10, ppm * 1.5))}px monospace`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(`Q ${String(approach.queueLength)}`, x, y);
  }
}
