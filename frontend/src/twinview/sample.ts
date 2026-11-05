import type { TwinObservation } from "./types";

/** Links of the default two-junction corridor the twin uses when no graph is
 *  sent (backend/src/networks/corridor.py). */
export const CORRIDOR_LINKS = [
  "W>J1",
  "J1>J2",
  "J2>E",
  "N1>J1",
  "J2>S2",
] as const;

const BASE = [10, 9, 9, 3, 2];

/** Example observations for the default corridor: `windows` intervals of
 *  `intervalSeconds`, with traffic building after the third window so the
 *  twin's prediction falls behind. Deterministic. */
export function sampleObservations(
  windows = 6,
  intervalSeconds = 60,
): TwinObservation[] {
  const out: TwinObservation[] = [];
  for (let w = 0; w < windows; w++) {
    const surge = w >= 3 ? 1 + 0.25 * (w - 2) : 1;
    CORRIDOR_LINKS.forEach((linkId, i) => {
      out.push({
        linkId,
        timestamp: w * intervalSeconds,
        count: Math.round(BASE[i] * surge),
      });
    });
  }
  return out;
}
