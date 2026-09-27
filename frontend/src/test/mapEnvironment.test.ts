/**
 * The roadside scenery is presentation only. These tests pin the two promises
 * that keep it that way: planting never reaches the road or its sidewalk, and
 * the same seed gives both layouts the same scenery.
 */
import { describe, expect, it } from "vitest";
import {
  SIDEWALK_WIDTH_M,
  placePlants,
  roundaboutEnvironment,
  signalEnvironment,
  type Plant,
} from "../components/mapEnvironment";
import {
  MAP_VIEW_HALF_EXTENT_M,
  mapScale,
  roundaboutCarriagewayEdge,
  signalStopLineDistance,
} from "../components/mapGeometry";

const HALF_W = 90;
const HALF_H = 90;
const LAYOUTS = [1, 2, 3, 4].flatMap((lanes) =>
  [2.5, 3.5, 4.8].map((laneWidth) => ({ lanes, laneWidth })),
);

function rectDistance(
  x: number,
  y: number,
  [x1, y1, x2, y2]: [number, number, number, number],
): number {
  return Math.hypot(Math.max(x1 - x, 0, x - x2), Math.max(y1 - y, 0, y - y2));
}

function signalFor(lanes: number, laneWidth: number) {
  const width = lanes * laneWidth * 2;
  const half = signalStopLineDistance(lanes, laneWidth);
  const reach = 200;
  const widths = { north: width, south: width, east: width, west: width };
  return { half, reach, width, env: signalEnvironment(widths, half, reach) };
}

function roundaboutFor(lanes: number, laneWidth: number) {
  const edge = roundaboutCarriagewayEdge(lanes, laneWidth);
  return { edge, env: roundaboutEnvironment(edge, 20, 200) };
}

describe("signal scenery", () => {
  it.each(LAYOUTS)(
    "keeps every plant off the road and sidewalk ($lanes lanes, $laneWidth m)",
    ({ lanes, laneWidth }) => {
      const { half, reach, width, env } = signalFor(lanes, laneWidth);
      const n = width / 2;
      const roads: [number, number, number, number][] = [
        [-n, half, n, reach],
        [-n, -reach, n, -half],
        [half, -n, reach, n],
        [-reach, -n, -half, n],
        [-half, -half, half, half],
      ];
      const plants = placePlants(env.clearance, HALF_W, HALF_H);
      expect(plants.length).toBeGreaterThan(0);
      for (const plant of plants) {
        for (const road of roads) {
          expect(rectDistance(plant.x, plant.y, road)).toBeGreaterThanOrEqual(
            SIDEWALK_WIDTH_M + plant.radius,
          );
        }
      }
    },
  );
});

describe("roundabout scenery", () => {
  it.each(LAYOUTS)(
    "keeps every plant off the road and sidewalk ($lanes lanes, $laneWidth m)",
    ({ lanes, laneWidth }) => {
      const { edge, env } = roundaboutFor(lanes, laneWidth);
      const plants = placePlants(env.clearance, HALF_W, HALF_H);
      expect(plants.length).toBeGreaterThan(0);
      // The flared entries, sampled independently of the environment.
      const flare = 35;
      const fillet: [number, number][] = [];
      for (let i = 0; i <= 64; i += 1) {
        const t = i / 64;
        const u = 1 - t;
        fillet.push([
          u * u * edge + 2 * u * t * edge + t * t * flare,
          u * u * flare + 2 * u * t * edge + t * t * edge,
        ]);
      }
      for (const { x, y, radius } of plants) {
        const clear = SIDEWALK_WIDTH_M + radius;
        expect(Math.hypot(x, y)).toBeGreaterThanOrEqual(20 + clear);
        // Outside both straight arms (|x| or |y| beyond the carriageway).
        expect(Math.min(Math.abs(x), Math.abs(y))).toBeGreaterThanOrEqual(
          edge + clear,
        );
        for (const [fx, fy] of fillet) {
          expect(
            Math.hypot(Math.abs(x) - fx, Math.abs(y) - fy),
          ).toBeGreaterThanOrEqual(clear);
        }
      }
    },
  );
});

describe("shared scenery", () => {
  const key = (p: Plant) => `${p.x.toFixed(3)},${p.y.toFixed(3)}`;

  it("is deterministic", () => {
    const { env } = signalFor(2, 3.5);
    expect(placePlants(env.clearance, HALF_W, HALF_H)).toEqual(
      placePlants(env.clearance, HALF_W, HALF_H),
    );
  });

  it("gives both layouts the same plant wherever both have room", () => {
    const signal = placePlants(signalFor(2, 3.5).env.clearance, HALF_W, HALF_H);
    const ring = placePlants(
      roundaboutFor(2, 3.5).env.clearance,
      HALF_W,
      HALF_H,
    );
    const ringByPosition = new Map(ring.map((p) => [key(p), p]));
    const shared = signal.filter((p) => ringByPosition.has(key(p)));
    expect(shared.length).toBeGreaterThan(10);
    for (const plant of shared) {
      expect(ringByPosition.get(key(plant))).toEqual(plant);
    }
  });

  it("does not depend on the canvas size", () => {
    const { env } = signalFor(2, 3.5);
    const small = placePlants(env.clearance, 40, 40);
    const large = placePlants(env.clearance, HALF_W, HALF_H);
    const largeKeys = new Set(large.map(key));
    // Every plant in the smaller view is at the same spot in the larger one.
    for (const plant of small) {
      if (Math.abs(plant.x) <= 40 && Math.abs(plant.y) <= 40) {
        expect(largeKeys.has(key(plant))).toBe(true);
      }
    }
  });
});

describe("camera framing", () => {
  it("draws the world 10-15% larger than the original 62 m half-extent", () => {
    const ratio = mapScale(800, 680) / (680 / (62 * 2));
    expect(ratio).toBeGreaterThanOrEqual(1.1);
    expect(ratio).toBeLessThanOrEqual(1.15);
  });

  it("still shows the whole roundabout and its flared entries", () => {
    // Flares begin 35 m from the centre; the widest signal box, four 4.8 m
    // lanes plus stop-line setback, is 22.7 m.
    expect(MAP_VIEW_HALF_EXTENT_M).toBeGreaterThan(35);
    expect(MAP_VIEW_HALF_EXTENT_M).toBeGreaterThan(
      signalStopLineDistance(4, 4.8) + 2.8 + SIDEWALK_WIDTH_M,
    );
  });
});
