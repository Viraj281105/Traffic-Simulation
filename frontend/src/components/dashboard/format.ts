const SERIES_COLOURS: Partial<Record<string, string>> = {
  fixed_time: "var(--series-signal)",
  adaptive: "var(--color-accent)",
  roundabout: "var(--series-roundabout)",
  signalised_roundabout: "var(--brand-green-ink)",
  metered_roundabout: "var(--color-orange)",
};
const FALLBACK = [
  "var(--series-signal)",
  "var(--series-roundabout)",
  "var(--color-accent)",
  "var(--brand-green-ink)",
  "var(--color-orange)",
  "var(--series-neutral)",
];

/** A stable colour per strategy name, so a strategy keeps its colour across
 *  every chart on every page. */
export function seriesColour(name: string, index = 0): string {
  const key = name.replace(/^baseline:/, "");
  return SERIES_COLOURS[key] ?? FALLBACK[index % FALLBACK.length];
}

/** "fixed_time" → "Fixed time"; "baseline:roundabout" → "Roundabout". */
export function prettyName(name: string): string {
  const s = name.replace(/^baseline:/, "").replace(/[_-]+/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** The first item, typed as possibly missing. */
export function first<T>(items: readonly T[]): T | undefined {
  return items.length ? items[0] : undefined;
}
