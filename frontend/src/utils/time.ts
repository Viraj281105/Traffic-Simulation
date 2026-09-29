/** The backend stores SQLite CURRENT_TIMESTAMP, which is UTC without a zone
 *  marker ("2026-09-04 10:31:23"). Parse it as UTC; parsing it as local time
 *  shifts every saved run by the viewer's UTC offset. */
export function parseStoredTimestamp(value: string): Date {
  const hasZone = /[zZ]|[+-]\d\d:?\d\d$/.test(value);
  return new Date(hasZone ? value : `${value.replace(" ", "T")}Z`);
}

/** Elapsed or remaining time for progress text: "42s", "1m 18s". */
export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s.toString()}s`;
  const rest = s % 60;
  return `${Math.floor(s / 60).toString()}m ${rest.toString().padStart(2, "0")}s`;
}
