import React, { useEffect, useRef } from "react";
import type {
  LiveSnapshot,
  SignalDirection,
  SnapshotVehicle,
} from "../types/simulation";

export interface IntersectionMapProps {
  snapshot: LiveSnapshot | null;
  width?: number;
  height?: number;
  lanesNorth?: number;
  lanesSouth?: number;
  lanesEast?: number;
  lanesWest?: number;
  laneWidth?: number;
  intersectionSize?: number;
  showCrosswalks?: boolean;
  showStopLines?: boolean;
  debug?: boolean;
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
  width = 800,
  height = 680,
  lanesNorth = 2,
  lanesSouth = 2,
  lanesEast = 2,
  lanesWest = 2,
  laneWidth = 3.5,
  intersectionSize = 15,
  showCrosswalks = true,
  showStopLines = true,
  debug = false,
  ppm = 7,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animFrameIdRef = useRef<number | null>(null);

  const snapshotRef = useRef<LiveSnapshot | null>(null);
  const prevSnapshotRef = useRef<LiveSnapshot | null>(null);
  const lastSnapshotTimeRef = useRef<number>(0);

  useEffect(() => {
    prevSnapshotRef.current = snapshotRef.current;
    snapshotRef.current = snapshot;
    lastSnapshotTimeRef.current = performance.now();
  }, [snapshot]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    let active = true;

    const render = () => {
      if (!active) return;

      const current = snapshotRef.current;
      const previous = prevSnapshotRef.current;
      const lastTime = lastSnapshotTimeRef.current;

      if (!current) {
        // Draw grass background while waiting for data
        ctx.fillStyle = "#557d35";
        ctx.fillRect(0, 0, width, height);
        animFrameIdRef.current = requestAnimationFrame(render);
        return;
      }

      // Calculate t (interpolation factor from 0 to 1)
      const elapsed = performance.now() - lastTime;
      const stepDuration = current.deltaTime ? current.deltaTime * 1000 : 100;
      const t = Math.max(0, Math.min(1, elapsed / stepDuration));

      const point: Point = (x, y) => [
        x * ppm + width / 2,
        -y * ppm + height / 2,
      ];
      const half = intersectionSize / 2;
      const widths: Widths = {
        north: lanesNorth * laneWidth * 2,
        south: lanesSouth * laneWidth * 2,
        east: lanesEast * laneWidth * 2,
        west: lanesWest * laneWidth * 2,
      };
      const roadLength = Math.max(46, Math.ceil(Math.max(width, height) / ppm));

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

      // Draw background grass
      ctx.fillStyle = "#557d35";
      ctx.fillRect(0, 0, width, height);
      ctx.strokeStyle = "rgba(28,58,28,.22)";
      ctx.lineWidth = 1;
      for (let y = 0; y < height; y += 18)
        line(0, (height / 2 - y) / ppm, width / ppm, (height / 2 - y) / ppm);

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
        ctx.fillStyle = "#557d35";
        ctx.beginPath();
        ctx.arc(cx, cy, controller.innerRadius * ppm, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "#e5eaed";
        ctx.setLineDash([7, 8]);
        ctx.stroke();
        ctx.setLineDash([]);
      }
      if (controller.type === "fixed_time_signal")
        drawSignals(ctx, controller.signals, half, widths, ppm, point);

      // Interpolate vehicle positions
      const prevVehiclesMap = new Map<string, SnapshotVehicle>();
      if (previous) {
        for (const pv of previous.vehicles) {
          prevVehiclesMap.set(pv.id, pv);
        }
      }

      for (const vehicle of current.vehicles) {
        if (vehicle.state === "exited") continue;

        let renderX = vehicle.x;
        let renderY = vehicle.y;
        let renderHeading = vehicle.heading;

        const prevVehicle = prevVehiclesMap.get(vehicle.id);
        if (prevVehicle) {
          renderX = prevVehicle.x + t * (vehicle.x - prevVehicle.x);
          renderY = prevVehicle.y + t * (vehicle.y - prevVehicle.y);

          // Interpolate heading along the shortest angular path
          let diff = vehicle.heading - prevVehicle.heading;
          while (diff < -180) diff += 360;
          while (diff > 180) diff -= 360;
          renderHeading = (prevVehicle.heading + t * diff + 360) % 360;
        }

        drawVehicle(
          ctx,
          { ...vehicle, x: renderX, y: renderY, heading: renderHeading },
          ppm,
          point,
        );
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
      drawHud(ctx, current, width);

      animFrameIdRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      active = false;
      if (animFrameIdRef.current) {
        cancelAnimationFrame(animFrameIdRef.current);
      }
    };
  }, [
    width,
    height,
    lanesNorth,
    lanesSouth,
    lanesEast,
    lanesWest,
    laneWidth,
    intersectionSize,
    showCrosswalks,
    showStopLines,
    debug,
    ppm,
  ]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
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
    ctx.fillStyle = "#171b1f";
    ctx.fillRect(x - 9, y - 16, 18, 32);
    ctx.fillStyle = signalColor(signal.color);
    ctx.shadowColor = ctx.fillStyle;
    ctx.shadowBlur = 9;
    ctx.beginPath();
    ctx.arc(x, y, Math.max(5, ppm * 0.7), 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
  }
}

function drawVehicle(
  ctx: CanvasRenderingContext2D,
  vehicle: SnapshotVehicle,
  ppm: number,
  point: Point,
) {
  const [x, y] = point(vehicle.x, vehicle.y);
  const length = Math.max(vehicle.length, 4.5) * ppm;
  const width = Math.max(vehicle.width, 2) * ppm;
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate((vehicle.heading * Math.PI) / 180);

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

  ctx.fillStyle = "#fff";
  ctx.beginPath();
  ctx.moveTo(0, -length / 2 - 4);
  ctx.lineTo(-4, -length / 2 + 3);
  ctx.lineTo(4, -length / 2 + 3);
  ctx.closePath();
  ctx.fill();
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

function drawHud(
  ctx: CanvasRenderingContext2D,
  snapshot: LiveSnapshot | null,
  width: number,
) {
  const status = snapshot?.simulationStatus ?? "disconnected";
  const timestamp = snapshot ? snapshot.timestamp.toFixed(1) : "0.0";
  ctx.fillStyle = "rgba(15,20,24,.86)";
  ctx.fillRect(width - 190, 14, 176, 48);
  ctx.fillStyle = status === "running" ? "#55d66b" : "#ffd166";
  ctx.beginPath();
  ctx.arc(width - 174, 30, 5, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#fff";
  ctx.font = "bold 11px sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(status.toUpperCase(), width - 162, 34);
  ctx.fillStyle = "rgba(255,255,255,.7)";
  ctx.font = "10px monospace";
  ctx.fillText(`T ${timestamp}s`, width - 174, 51);
}
