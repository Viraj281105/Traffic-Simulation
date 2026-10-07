/** Shared live-map frame for real-world junctions (V1.5); see realWorldMap. */
import type { LiveSnapshot } from "../types/simulation";
import { drawVehicleSprite } from "../vehicles/vehicleSprites";
import { GROUND_BASE } from "./mapEnvironment";
import { ROUNDABOUT_SPLITTER_HALF_WIDTH } from "./mapGeometry";
import { drawRealWorldJunction, realWorldArms } from "./realWorldMap";

/** Draws a real-world junction (V1.5) and its vehicles; false when the
 *  snapshot describes the standard junction, which the caller draws. */
export function drawRealWorldFrame(
  ctx: CanvasRenderingContext2D,
  current: LiveSnapshot,
  vehicles: {
    vehicle: Parameters<typeof drawVehicleSprite>[1];
    x: number;
    y: number;
    heading: number;
  }[],
  point: (x: number, y: number) => [number, number],
  ppm: number,
  size: { width: number; height: number; reach: number },
): boolean {
  const arms = realWorldArms(current.intersection.approaches);
  if (!arms) return false;
  const controller = current.controller;
  ctx.fillStyle = GROUND_BASE;
  ctx.fillRect(0, 0, size.width, size.height);
  drawRealWorldJunction(ctx, arms, {
    point,
    ppm,
    reach: size.reach,
    splitter:
      controller.type === "roundabout" ? ROUNDABOUT_SPLITTER_HALF_WIDTH : 0,
    roundabout:
      controller.type === "roundabout"
        ? {
            innerRadius: controller.innerRadius,
            outerRadius: controller.outerRadius,
            ringLanes:
              controller.circulatingLanes ??
              current.intersection.circulatingLanes ??
              1,
          }
        : undefined,
    signals:
      controller.type === "fixed_time_signal" ? controller.signals : undefined,
    ground: GROUND_BASE,
  });
  const now = performance.now();
  for (const pose of vehicles) {
    const [vx, vy] = point(pose.x, pose.y);
    drawVehicleSprite(ctx, pose.vehicle, vx, vy, pose.heading, ppm, now);
  }
  return true;
}
