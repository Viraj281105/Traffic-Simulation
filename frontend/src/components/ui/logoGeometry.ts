/**
 * The UrbanFlow mark, measured from the reference artwork on a 100-unit
 * grid: four three-lane arms (navy outer lines, green centre line) whose
 * outer lines flare into a broken outer ring, four green flow paths that
 * swirl anticlockwise round a hollow central roundabout, each tucking under
 * the next, and white separation wherever paths cross — real negative space
 * (masks), so the mark sits cleanly on any surface, including glass.
 *
 * Everything has 4-fold symmetry: one quadrant is drawn and rotated.
 *
 * One geometry, used everywhere: the header, the loader, empty states and
 * (as a static copy of these paths) public/favicon.svg — logoGeometry.test.ts
 * keeps the favicon in step with LOGO_GEOMETRY.
 */
export const LOGO_GEOMETRY = {
  viewBox: "0 0 100 100",
  rotations: [0, 90, 180, 270],
  /** One quadrant of road: the north arm's right line flaring into the
   *  outer ring, and the ring arc (from the north flow crossing) flaring
   *  into the east arm's top line. */
  road: "M60.9 0V14C60.9 17.5 62.52 21.32 65.55 23.07M50 18.9A31.1 31.1 0 0 1 76.93 34.45C78.68 37.48 82.5 39.1 86 39.1H100",
  /** The north flow path: down the arm, an S-curve in, then round the
   *  roundabout until it passes under the west path. */
  flow: "M50 0V10C50 17 43.55 23.8 39.25 28C32.81 34.28 29.8 40 29.8 50C29.8 52 35.5 60.5 40 64.3",
  ring: { cx: 50, cy: 50, r: 14.85 },
  strokeWidth: 5.6,
  /** Flow width plus the white separation either side of a crossing. */
  gapWidth: 10.4,
} as const;

/** Fixed palettes for an explicit variant (sampled from the reference);
 *  "auto" follows the theme through the --logo-* tokens (styles/tokens.css). */
export const LOGO_PALETTES = {
  light: { road: "#132a4a", flow: "#638965" },
  dark: { road: "#fdfefe", flow: "#94d182" },
} as const;
