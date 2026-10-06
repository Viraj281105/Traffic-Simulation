/**
 * Draws a vehicle on a map canvas, true to its class and its real size.
 *
 * Shared by the signal and roundabout maps. Each class has its own outline so
 * it can be told apart without relying on colour alone: a car's cabin, an
 * SUV's square roof, a bus's window band, a truck's separate cab and load
 * body, a motorcycle's narrow frame and rider. Bodies are drawn at the
 * vehicle's actual length and width (the backend's collision footprint), with
 * a small legibility minimum so a 2 m motorcycle stays visible at low zoom.
 */

import type { SnapshotVehicle, VehicleClass } from "../types/simulation";
import { VEHICLE_CLASS_INFO } from "./vehicleClasses";

/** Smallest drawn size in pixels, so far-zoomed vehicles stay visible. */
const MIN_LENGTH_PX = 6;
const MIN_WIDTH_PX = 3;

/** Car colours vary per vehicle so a stream of cars stays readable; every
 *  other class has one colour (see VEHICLE_CLASSES). */
const CAR_PALETTE = ["#4d96ff", "#5fa8ff", "#3b7dd8", "#6c8ebf", "#8fb3e8"];

function hashId(id: string): number {
  let hash = 0;
  for (const character of id)
    hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  return hash;
}

export function vehicleClassOf(vehicle: SnapshotVehicle): VehicleClass {
  return vehicle.vehicleType ?? "car";
}

export function vehicleColor(vehicle: SnapshotVehicle): string {
  const cls = vehicleClassOf(vehicle);
  if (cls === "car")
    return CAR_PALETTE[hashId(vehicle.id) % CAR_PALETTE.length];
  return VEHICLE_CLASS_INFO[cls].color;
}

const OUTLINE = "#172027";
const GLASS = "rgba(224,243,255,.8)";

/**
 * Draw ``vehicle`` centred at canvas point (x, y), heading in degrees
 * (0 = +y world, i.e. up the canvas), ``ppm`` pixels per metre. ``now`` (ms)
 * drives the indicator blink during a lane change.
 */
export function drawVehicleSprite(
  ctx: CanvasRenderingContext2D,
  vehicle: SnapshotVehicle,
  x: number,
  y: number,
  headingDeg: number,
  ppm: number,
  now: number = 0,
): void {
  const cls = vehicleClassOf(vehicle);
  const length = Math.max(MIN_LENGTH_PX, vehicle.length * ppm);
  const width = Math.max(MIN_WIDTH_PX, vehicle.width * ppm);
  const halfL = length / 2;
  const halfW = width / 2;
  const radius = Math.min(4, width / 3);

  ctx.save();
  ctx.translate(x, y);
  ctx.rotate((headingDeg * Math.PI) / 180);
  ctx.fillStyle = vehicleColor(vehicle);
  ctx.strokeStyle = OUTLINE;
  ctx.lineWidth = cls === "motorcycle" ? 1.2 : 2;

  // The canvas front is -y after rotation (heading 0 points up the canvas).
  switch (cls) {
    case "bus": {
      ctx.beginPath();
      ctx.roundRect(-halfW, -halfL, width, length, radius);
      ctx.fill();
      ctx.stroke();
      // Continuous side window band and a windscreen.
      ctx.fillStyle = "rgba(30,40,48,.55)";
      ctx.fillRect(
        -halfW * 0.72,
        -halfL + length * 0.1,
        width * 0.12,
        length * 0.78,
      );
      ctx.fillRect(
        halfW * 0.6,
        -halfL + length * 0.1,
        width * 0.12,
        length * 0.78,
      );
      ctx.fillStyle = GLASS;
      ctx.fillRect(-width * 0.35, -halfL + 2, width * 0.7, length * 0.05);
      break;
    }
    case "truck": {
      // Cab at the front, a gap, then the load body.
      const cab = Math.min(length * 0.22, 2.6 * ppm);
      ctx.beginPath();
      ctx.roundRect(-halfW, -halfL, width, cab, radius);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = GLASS;
      ctx.fillRect(-halfW * 0.7, -halfL + cab * 0.15, width * 0.7, cab * 0.3);
      ctx.fillStyle = "#c9d1d9";
      ctx.beginPath();
      ctx.roundRect(-halfW, -halfL + cab + 1, width, length - cab - 1, 2);
      ctx.fill();
      ctx.stroke();
      break;
    }
    case "motorcycle": {
      ctx.beginPath();
      ctx.roundRect(-halfW, -halfL, width, length, width / 2);
      ctx.fill();
      ctx.stroke();
      // Rider.
      ctx.fillStyle = "#2b2d42";
      ctx.beginPath();
      ctx.arc(0, length * 0.05, Math.max(1.5, halfW * 0.9), 0, Math.PI * 2);
      ctx.fill();
      break;
    }
    case "suv": {
      ctx.beginPath();
      ctx.roundRect(-halfW, -halfL, width, length, Math.min(2, radius));
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = GLASS;
      ctx.fillRect(-width * 0.36, -length * 0.3, width * 0.72, length * 0.2);
      // Square roof.
      ctx.strokeStyle = "rgba(23,32,39,.55)";
      ctx.lineWidth = 1;
      ctx.strokeRect(-width * 0.3, -length * 0.06, width * 0.6, length * 0.34);
      break;
    }
    default: {
      ctx.beginPath();
      ctx.roundRect(-halfW, -halfL, width, length, radius);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = GLASS;
      ctx.beginPath();
      ctx.roundRect(
        -width * 0.34,
        -length * 0.28,
        width * 0.68,
        length * 0.24,
        2,
      );
      ctx.fill();
    }
  }

  const lamp = Math.max(1.5, Math.min(2.5, width * 0.12));
  if (vehicle.state === "waiting" && cls !== "motorcycle") {
    ctx.fillStyle = "#ff1744";
    ctx.beginPath();
    ctx.arc(-halfW * 0.6, halfL, lamp, 0, Math.PI * 2);
    ctx.arc(halfW * 0.6, halfL, lamp, 0, Math.PI * 2);
    ctx.fill();
  }

  // Indicator on the side the vehicle is moving to, blinking at ~1.5 Hz.
  if (vehicle.laneChange && Math.floor(now / 330) % 2 === 0) {
    const side = vehicle.laneChange === "left" ? -1 : 1;
    ctx.fillStyle = "#ffb703";
    ctx.beginPath();
    ctx.arc(side * halfW, -halfL + lamp, lamp + 0.5, 0, Math.PI * 2);
    ctx.arc(side * halfW, halfL - lamp, lamp + 0.5, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.restore();
}
