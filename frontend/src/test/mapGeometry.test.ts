/**
 * The roundabout renderer draws roads from its own copy of the backend's lane
 * layout rules. When the backend moved its lanes (splitter island, entry
 * setback) and the renderer did not, vehicles drove on lane markings and road
 * edges. These tests pin the copy to the backend source and to the lane
 * positions the backend actually produces.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  ROUNDABOUT_ENTRY_SETBACK,
  ROUNDABOUT_SPLITTER_HALF_WIDTH,
  ROUNDABOUT_TRANSITION_ARC,
  roundaboutCarriagewayEdge,
  roundaboutGiveWayRadius,
  roundaboutLaneCentres,
  roundaboutLaneDividers,
  roundaboutRingDividers,
  roundaboutTaperHalfWidth,
  roundaboutTaperPaths,
} from "../components/mapGeometry";

// Outside the frontend package, so read from disk (relative to the package
// root vitest runs in) rather than via a Vite import, which the dev server's
// file-system sandbox refuses.
const networkSource = readFileSync(
  resolve(process.cwd(), "../backend/src/roads/network.py"),
  "utf8",
);

function backendConstant(name: string): number {
  const match = new RegExp(
    `^${name}\\s*:\\s*float\\s*=\\s*([0-9.]+)`,
    "m",
  ).exec(networkSource);
  if (!match) throw new Error(`${name} not found in network.py`);
  return Number(match[1]);
}

describe("roundabout map geometry", () => {
  it("mirrors the backend's splitter island, entry setback and taper arc", () => {
    expect(ROUNDABOUT_SPLITTER_HALF_WIDTH).toBe(
      backendConstant("ROUNDABOUT_SPLITTER_HALF_WIDTH"),
    );
    expect(ROUNDABOUT_ENTRY_SETBACK).toBe(
      backendConstant("ROUNDABOUT_ENTRY_SETBACK"),
    );
    expect(ROUNDABOUT_TRANSITION_ARC).toBe(
      backendConstant("ROUNDABOUT_TRANSITION_ARC"),
    );
  });

  // Lateral offsets measured from backend snapshots (3.5 m lanes).
  it.each([
    [1, [3.25]],
    [2, [3.25, 6.75]],
    [3, [3.25, 6.75, 10.25]],
  ])("places %i-lane centrelines where vehicles drive", (lanes, centres) => {
    expect(roundaboutLaneCentres(lanes, 3.5)).toEqual(centres);
  });

  it("keeps every lane centreline between its markings", () => {
    for (const lanes of [1, 2, 3]) {
      const bounds = [
        ROUNDABOUT_SPLITTER_HALF_WIDTH,
        ...roundaboutLaneDividers(lanes, 3.5),
        roundaboutCarriagewayEdge(lanes, 3.5),
      ];
      roundaboutLaneCentres(lanes, 3.5).forEach((centre, i) => {
        expect(centre).toBeGreaterThan(bounds[i]);
        expect(centre).toBeLessThan(bounds[i + 1]);
      });
    }
  });

  it("splits the ring into one circulating lane per approach lane", () => {
    expect(roundaboutRingDividers(10, 20, 1)).toEqual([]);
    expect(roundaboutRingDividers(10, 20, 2)).toEqual([15]);
    const three = roundaboutRingDividers(10, 20, 3);
    expect(three[0]).toBeCloseTo(13.333, 3);
    expect(three[1]).toBeCloseTo(16.667, 3);
  });

  it("puts the give-way line where entry lanes end", () => {
    expect(roundaboutGiveWayRadius(20)).toBe(24);
  });

  it("draws an entry and an exit taper per lane on each of the four arms", () => {
    const paths = roundaboutTaperPaths(10, 20, 2, 3.5);
    expect(paths).toHaveLength(4 * 2 * 2);

    // North arm, lane 0: the entry leaves the lane where it meets the ring's
    // edge (x = -3.25, y = 20) and ends on its circulating lane (r = 12.5)...
    const [entry, exit] = paths;
    expect(entry[0][0]).toBeCloseTo(-3.25);
    expect(entry[0][1]).toBeCloseTo(20);
    expect(Math.hypot(...entry[entry.length - 1])).toBeCloseTo(12.5);
    // ...turning anticlockwise (westwards) as traffic circulates.
    expect(entry[entry.length - 1][0]).toBeLessThan(entry[0][0]);

    // The exit joins exit lane 0 (x = +3.25) from the outermost ring lane.
    expect(exit[0][0]).toBeCloseTo(3.25);
    expect(exit[0][1]).toBeCloseTo(20);
    expect(Math.hypot(...exit[exit.length - 1])).toBeCloseTo(17.5);
  });

  it("repeats the north arm's tapers on the other arms by rotation", () => {
    const paths = roundaboutTaperPaths(10, 20, 1, 3.5);
    const [nx, ny] = paths[0][0]; // north entry start
    const [wx, wy] = paths[2][0]; // same taper, rotated 90° anticlockwise
    expect(wx).toBeCloseTo(-ny);
    expect(wy).toBeCloseTo(nx);
  });

  it("draws tapers at least a lane wide", () => {
    expect(roundaboutTaperHalfWidth(3.5)).toBe(1.75);
    expect(roundaboutTaperHalfWidth(2.5)).toBe(1.5);
  });
});
