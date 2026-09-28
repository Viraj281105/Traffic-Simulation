/**
 * The UrbanFlow mark, drawn in code: a four-way intersection whose arms sweep
 * into a central roundabout, with the green traffic-flow path woven through
 * it. The white (or navy) separation around the flow path is real negative
 * space — the roads are masked, not painted over — so the mark sits cleanly
 * on any surface, including translucent ones.
 *
 * One geometry, used everywhere: the header, the loader, empty states and
 * (as a static copy of these paths) public/favicon.svg — logoGeometry.test.ts
 * keeps the favicon in step with LOGO_GEOMETRY.
 */
export const LOGO_GEOMETRY = {
  viewBox: "0 0 64 64",
  /** One arm; the other three are the same path rotated about the centre. */
  arm: "M26.9 20.6C30 16.8 32 13 32 4",
  armRotations: [0, 90, 180, 270],
  ring: { cx: 32, cy: 32, r: 12.5 },
  island: { cx: 32, cy: 32, r: 4.2 },
  /** Enters from the south-west, rides half the ring, leaves north-east. */
  flow: "M5 53C12 50 17 46 23.2 40.8A12.5 12.5 0 0 1 40.8 23.2C46 17 50 12 59 11",
  roadWidth: 7,
  flowWidth: 4.6,
  /** Flow width plus the separation either side. */
  gapWidth: 9.6,
} as const;

/** Fixed palettes for an explicit variant; "auto" follows the theme through
 *  the --logo-* tokens (styles/tokens.css). */
export const LOGO_PALETTES = {
  light: { road: "#0e2146", flow: "#12a150" },
  dark: { road: "#f4f7fb", flow: "#3ddc84" },
} as const;
