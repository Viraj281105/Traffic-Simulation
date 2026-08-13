import React, { useRef, useEffect } from "react";
import type { SingleVehicleResponse, Viewport } from "../types/simulation";

interface IntersectionCanvasProps {
  vehicle: SingleVehicleResponse | null;
  width: number;
  height: number;
}

/**
 * IntersectionCanvas renders a top-down view of a 4-way signalized intersection
 * with lanes, markings, stop lines, crosswalks, traffic lights, and the vehicle.
 */
export const IntersectionCanvas: React.FC<IntersectionCanvasProps> = ({
  vehicle,
  width,
  height,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Draw the entire scene
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Define viewport: world center at origin, vehicle starts at (0, -70)
    const viewport: Viewport = {
      canvasW: width,
      canvasH: height,
      ppm: 2.5, // pixels per meter
      centerWorldX: 0,
      centerWorldY: 0, // center at origin, so intersection is visible
    };

    // Convert world coordinates to canvas coordinates
    const worldToCanvas = (
      worldX: number,
      worldY: number,
    ): [number, number] => {
      const canvasX =
        (worldX - viewport.centerWorldX) * viewport.ppm + width / 2;
      const canvasY =
        -(worldY - viewport.centerWorldY) * viewport.ppm + height / 2;
      return [canvasX, canvasY];
    };

    // Clear canvas
    ctx.fillStyle = "#2a5a3a";
    ctx.fillRect(0, 0, width, height);

    // Draw intersection and roads
    drawRoads(ctx, width, height, worldToCanvas);
    drawIntersection(ctx, worldToCanvas);
    drawTrafficLights(ctx, worldToCanvas, vehicle);
    drawCrosswalk(ctx, worldToCanvas);

    // Draw vehicle if available
    if (vehicle) {
      drawVehicle(ctx, viewport, vehicle, worldToCanvas);
    }

    // Draw info overlay
    drawInfoOverlay(ctx, width, height, vehicle);
  }, [vehicle, width, height]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{
        border: "1px solid #333",
        backgroundColor: "#2a5a3a",
        display: "block",
      }}
    />
  );
};

// ── Road and intersection drawing ───────────────────────────────────────────

function drawRoads(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  worldToCanvas: (x: number, y: number) => [number, number],
) {
  ctx.fillStyle = "#444";

  // North-South road
  const [nsLeft] = worldToCanvas(-7, 100);
  const [nsRight] = worldToCanvas(7, 100);
  ctx.fillRect(nsLeft, 0, nsRight - nsLeft, height);

  // East-West road
  const [, ewTopY] = worldToCanvas(100, 7);
  const [, ewBottomY] = worldToCanvas(100, -7);
  ctx.fillRect(0, ewBottomY, width, ewTopY - ewBottomY);
}

function drawIntersection(
  ctx: CanvasRenderingContext2D,
  worldToCanvas: (x: number, y: number) => [number, number],
) {
  // Draw lane markings (dashed center lines and solid outer edges)
  ctx.strokeStyle = "#fff";
  ctx.lineWidth = 1;

  // North-South lanes (two in each direction)
  // West lane center line
  ctx.setLineDash([5, 5]);
  ctx.beginPath();
  const [westLeft, northEnd] = worldToCanvas(-3.5, 100);
  const [westLeft2, southStart] = worldToCanvas(-3.5, -100);
  ctx.moveTo(westLeft, northEnd);
  ctx.lineTo(westLeft2, southStart);
  ctx.stroke();

  // East lane center line
  ctx.beginPath();
  const [eastRight, northEnd2] = worldToCanvas(3.5, 100);
  const [eastRight2, southStart2] = worldToCanvas(3.5, -100);
  ctx.moveTo(eastRight, northEnd2);
  ctx.lineTo(eastRight2, southStart2);
  ctx.stroke();

  // East-West lanes (two in each direction)
  // South lane center line
  ctx.beginPath();
  const [westStart, southLane] = worldToCanvas(-100, -3.5);
  const [eastEnd, southLane2] = worldToCanvas(100, -3.5);
  ctx.moveTo(westStart, southLane);
  ctx.lineTo(eastEnd, southLane2);
  ctx.stroke();

  // North lane center line
  ctx.beginPath();
  const [westStart2, northLane] = worldToCanvas(-100, 3.5);
  const [eastEnd2, northLane2] = worldToCanvas(100, 3.5);
  ctx.moveTo(westStart2, northLane);
  ctx.lineTo(eastEnd2, northLane2);
  ctx.stroke();

  ctx.setLineDash([]);

  // Yellow edge lines on intersection area
  ctx.strokeStyle = "#ffaa00";
  ctx.lineWidth = 2;
  const [topLeft, topLeftY] = worldToCanvas(-7, 15);
  const [topRight, topRightY] = worldToCanvas(7, 15);
  const [bottomLeft, bottomLeftY] = worldToCanvas(-7, -15);
  const [bottomRight, bottomRightY] = worldToCanvas(7, -15);

  ctx.beginPath();
  ctx.moveTo(topLeft, topLeftY);
  ctx.lineTo(topRight, topRightY);
  ctx.stroke();

  ctx.beginPath();
  ctx.moveTo(bottomLeft, bottomLeftY);
  ctx.lineTo(bottomRight, bottomRightY);
  ctx.stroke();
}

function drawCrosswalk(
  ctx: CanvasRenderingContext2D,
  worldToCanvas: (x: number, y: number) => [number, number],
) {
  ctx.fillStyle = "rgba(255, 255, 255, 0.3)";
  const stripeWidth = 1.2;
  const stripeSpacing = 2.4;

  // North crosswalk
  const [cwNorth1, cwNorthY] = worldToCanvas(-7, 8);
  for (let i = 0; i < 20; i++) {
    ctx.fillRect(cwNorth1 + i * stripeSpacing, cwNorthY, stripeWidth, 20);
  }

  // South crosswalk
  const [cwSouth1, cwSouthY] = worldToCanvas(-7, -8);
  for (let i = 0; i < 20; i++) {
    ctx.fillRect(cwSouth1 + i * stripeSpacing, cwSouthY, stripeWidth, 20);
  }

  // East crosswalk
  const [cwEast1, cwEastY1] = worldToCanvas(8, -7);
  for (let i = 0; i < 20; i++) {
    ctx.fillRect(cwEast1, cwEastY1 + i * stripeSpacing, 20, stripeWidth);
  }

  // West crosswalk
  const [cwWest1, cwWestY1] = worldToCanvas(-8, -7);
  for (let i = 0; i < 20; i++) {
    ctx.fillRect(cwWest1, cwWestY1 + i * stripeSpacing, 20, stripeWidth);
  }
}

function drawTrafficLights(
  ctx: CanvasRenderingContext2D,
  worldToCanvas: (x: number, y: number) => [number, number],
  vehicle: SingleVehicleResponse | null,
) {
  const lightSize = 4;

  // South traffic light (for vehicle approaching from south)
  const [southLightX, southLightY] = worldToCanvas(-9, -3);
  const simTime = vehicle?.sim_time ?? 0;
  const isRed = simTime < 10;
  ctx.fillStyle = isRed ? "#ff2222" : "#22ff22";
  ctx.fillRect(
    southLightX - lightSize / 2,
    southLightY - lightSize / 2,
    lightSize,
    lightSize,
  );

  // North traffic light
  const [northLightX, northLightY] = worldToCanvas(9, 3);
  ctx.fillStyle = isRed ? "#22ff22" : "#ff2222";
  ctx.fillRect(
    northLightX - lightSize / 2,
    northLightY - lightSize / 2,
    lightSize,
    lightSize,
  );

  // Draw light labels
  ctx.fillStyle = "#fff";
  ctx.font = "bold 10px Arial";
  ctx.textAlign = "center";
  ctx.fillText("R/G", southLightX, southLightY + 12);
}

function drawVehicle(
  ctx: CanvasRenderingContext2D,
  viewport: Viewport,
  vehicle: SingleVehicleResponse,
  worldToCanvas: (x: number, y: number) => [number, number],
) {
  const [canvasX, canvasY] = worldToCanvas(vehicle.x, vehicle.y);
  const length = 4.5; // meters
  const width = 2.0; // meters

  const lengthPx = length * viewport.ppm;
  const widthPx = width * viewport.ppm;

  // Save context state
  ctx.save();

  // Translate to vehicle position and rotate by heading
  ctx.translate(canvasX, canvasY);
  ctx.rotate((vehicle.heading * Math.PI) / 180);

  // Draw vehicle body (rectangle)
  ctx.fillStyle = vehicle.speed > 0.3 ? "#ff6b35" : "#ff9b50";
  ctx.fillRect(-widthPx / 2, -lengthPx / 2, widthPx, lengthPx);

  // Draw vehicle outline
  ctx.strokeStyle = "#333";
  ctx.lineWidth = 1;
  ctx.strokeRect(-widthPx / 2, -lengthPx / 2, widthPx, lengthPx);

  // Draw front indicator (small triangle at front)
  ctx.fillStyle = "#fff";
  ctx.beginPath();
  ctx.moveTo(0, -lengthPx / 2 - 3);
  ctx.lineTo(-3, -lengthPx / 2 + 2);
  ctx.lineTo(3, -lengthPx / 2 + 2);
  ctx.closePath();
  ctx.fill();

  ctx.restore();
}

function drawInfoOverlay(
  ctx: CanvasRenderingContext2D,
  _width: number,
  _height: number,
  vehicle: SingleVehicleResponse | null,
) {
  if (!vehicle) return;

  ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
  ctx.fillRect(10, 10, 250, 130);

  ctx.fillStyle = "#fff";
  ctx.font = "11px monospace";
  ctx.textAlign = "left";

  let y = 25;
  const lines = [
    `Vehicle: ${vehicle.vehicle_id}`,
    `Position: ${vehicle.position.toFixed(1)} m`,
    `Speed: ${(vehicle.speed * 3.6).toFixed(1)} km/h (${vehicle.speed.toFixed(2)} m/s)`,
    `Accel: ${vehicle.acceleration.toFixed(2)} m/s²`,
    `State: ${vehicle.state}`,
    `Lane: ${vehicle.lane_id}`,
    `Sim Time: ${vehicle.sim_time.toFixed(1)}s`,
    `Tick: ${vehicle.tick.toString()}`,
    `Waiting: ${vehicle.wait_time.toFixed(1)}s`,
    `Stops: ${vehicle.stop_count.toString()}`,
  ];

  lines.forEach((line) => {
    ctx.fillText(line, 20, y);
    y += 12;
  });
}
