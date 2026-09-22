/**
 * Map geometry, derived from the same rules the backend uses to lay out
 * vehicle lanes (backend/src/roads/network.py).
 *
 * The renderer must draw roads where vehicles actually drive. The backend
 * offsets every roundabout lane by a splitter island, ends each entry lane
 * short of the ring, and holds signal traffic back from the conflict area; if
 * the renderer draws its own idea of the roads instead, vehicles straddle
 * lane markings and stop in the wrong place. The constants below mirror the
 * backend's and are pinned to it by mapGeometry.test.ts.
 */

/** Half-width (m) of the splitter island between entry and exit carriageways.
 *  Mirrors ROUNDABOUT_SPLITTER_HALF_WIDTH. */
export const ROUNDABOUT_SPLITTER_HALF_WIDTH = 1.5;

/** Radial distance (m) from the ring's outer edge to the give-way line, where
 *  each entry lane ends. Mirrors ROUNDABOUT_ENTRY_SETBACK. */
export const ROUNDABOUT_ENTRY_SETBACK = 4.0;

/** Arc length (m) over which a path blends radially between an approach lane
 *  and its circulating lane. Mirrors ROUNDABOUT_TRANSITION_ARC. */
export const ROUNDABOUT_TRANSITION_ARC = 10.0;

/** Clearance (m) between a signalised junction's conflict area and the stop
 *  line where waiting vehicles are held. Mirrors SIGNAL_STOP_LINE_SETBACK. */
export const SIGNAL_STOP_LINE_SETBACK = 3.5;

/** Distance (m) from the centre to a signal approach's stop line: where the
 *  backend ends each incoming lane and holds vehicles on red. */
export function signalStopLineDistance(
  lanes: number,
  laneWidth: number,
): number {
  return lanes * laneWidth + SIGNAL_STOP_LINE_SETBACK;
}

/** Half the width (m) of the square of world both maps show, so the signal
 *  and roundabout render at the same scale when shown side by side. Sized to
 *  fit the roundabout ring (20 m) plus its approaches. */
export const MAP_VIEW_HALF_EXTENT_M = 62;

/** Pixels per metre for a canvas of the given CSS size. */
export function mapScale(width: number, height: number): number {
  return Math.min(width, height) / (MAP_VIEW_HALF_EXTENT_M * 2);
}

/** Lateral offsets (m, from the approach axis) of each lane's centreline on
 *  one carriageway, innermost (next to the island) first. */
export function roundaboutLaneCentres(
  lanes: number,
  laneWidth: number,
): number[] {
  return Array.from(
    { length: lanes },
    (_, i) => (i + 0.5) * laneWidth + ROUNDABOUT_SPLITTER_HALF_WIDTH,
  );
}

/** Lateral offsets (m) of the markings between adjacent lanes of one
 *  carriageway (none for a single lane). */
export function roundaboutLaneDividers(
  lanes: number,
  laneWidth: number,
): number[] {
  return Array.from(
    { length: Math.max(0, lanes - 1) },
    (_, i) => (i + 1) * laneWidth + ROUNDABOUT_SPLITTER_HALF_WIDTH,
  );
}

/** Lateral offset (m) of a carriageway's outer road edge. */
export function roundaboutCarriagewayEdge(
  lanes: number,
  laneWidth: number,
): number {
  return lanes * laneWidth + ROUNDABOUT_SPLITTER_HALF_WIDTH;
}

/** Radii (m) of the markings between circulating lanes. The backend splits the
 *  ring evenly into one circulating lane per approach lane. */
export function roundaboutRingDividers(
  innerRadius: number,
  outerRadius: number,
  lanes: number,
): number[] {
  const width = (outerRadius - innerRadius) / Math.max(1, lanes);
  return Array.from(
    { length: Math.max(0, lanes - 1) },
    (_, i) => innerRadius + (i + 1) * width,
  );
}

/** Distance (m) from the centre to the give-way line where entry lanes end. */
export function roundaboutGiveWayRadius(outerRadius: number): number {
  return outerRadius + ROUNDABOUT_ENTRY_SETBACK;
}

type Point = [number, number];

/**
 * Centrelines (world metres) of the entry and exit tapers on all four arms:
 * where a path leaves an approach lane at the ring's edge and blends onto its
 * circulating lane, or the reverse. Between neighbouring arms these tapers
 * bulge beyond both the arm's straight edge and the ring's outer circle, so
 * they must be drawn as road too.
 *
 * The backend blends radius linearly with angle over at most
 * ROUNDABOUT_TRANSITION_ARC of arc (less for sharp turns); using the full arc
 * — and, for exits, the outermost circulating lane — gives the widest taper
 * any movement can take, so every path lies within it.
 */
export function roundaboutTaperPaths(
  innerRadius: number,
  outerRadius: number,
  lanes: number,
  laneWidth: number,
): Point[][] {
  const ringLane = (outerRadius - innerRadius) / Math.max(1, lanes);
  const target = (i: number) => innerRadius + (i + 0.5) * ringLane;
  const outermost = target(lanes - 1);

  const taper = (start: Point, to: number, direction: 1 | -1): Point[] => {
    const from = Math.hypot(start[0], start[1]);
    const angle0 = Math.atan2(start[1], start[0]);
    const span = ROUNDABOUT_TRANSITION_ARC / to;
    const points: Point[] = [];
    for (let k = 0; k <= 24; k += 1) {
      const f = k / 24;
      const angle = angle0 + direction * f * span;
      const radius = from + f * (to - from);
      points.push([radius * Math.cos(angle), radius * Math.sin(angle)]);
    }
    return points;
  };

  // North arm: traffic keeps right and circulates anticlockwise, so entries
  // (x < 0) turn anticlockwise onto the ring and exits (x > 0) arrive from it.
  const north: Point[][] = [];
  roundaboutLaneCentres(lanes, laneWidth).forEach((lateral, i) => {
    north.push(taper([-lateral, outerRadius], target(i), 1));
    north.push(taper([lateral, outerRadius], outermost, -1));
  });

  // The other arms are the north arm rotated anticlockwise in 90° steps.
  const arms: Point[][] = [];
  for (let quarter = 0; quarter < 4; quarter += 1) {
    const c = Math.round(Math.cos((quarter * Math.PI) / 2));
    const s = Math.round(Math.sin((quarter * Math.PI) / 2));
    for (const path of north) {
      arms.push(path.map(([x, y]): Point => [x * c - y * s, x * s + y * c]));
    }
  }
  return arms;
}

/** Half-width (m) of the road drawn along each taper: one lane, and never
 *  less than 1.5 m, which keeps the largest drawn vehicle body (5 m x 2 m)
 *  on the road along every path for 2.5-4.8 m lanes and 1-4 lanes. */
export function roundaboutTaperHalfWidth(laneWidth: number): number {
  return Math.max(1.5, laneWidth / 2);
}
