/** A colour for a 0..1 amount: pale yellow (empty) to deep red (full). The
 *  same ramp is used by the heatmap, the map and their legends. */
export function rampColor(fraction: number): string {
  const f = Number.isFinite(fraction) ? Math.min(1, Math.max(0, fraction)) : 0;
  const hue = 52 - 52 * f;
  const light = 92 - 50 * f;
  return `hsl(${hue.toFixed(0)} 88% ${light.toFixed(0)}%)`;
}

/** The legend stops, low to high. */
export const RAMP_STOPS = [0, 0.25, 0.5, 0.75, 1] as const;
