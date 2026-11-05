import type { TwinObservation } from "./types";

/** Reads the observations box: a JSON list of {linkId, timestamp, count}. */
export function parseObservations(text: string): TwinObservation[] {
  let doc: unknown;
  try {
    doc = JSON.parse(text);
  } catch {
    throw new Error("The observations are not valid JSON.");
  }
  if (!Array.isArray(doc) || doc.length === 0) {
    throw new Error(
      "The observations must be a JSON list with at least one entry.",
    );
  }
  const bad = doc.findIndex((o: unknown) => {
    if (typeof o !== "object" || o === null) return true;
    const r = o as Record<string, unknown>;
    return (
      typeof r.linkId !== "string" ||
      typeof r.timestamp !== "number" ||
      typeof r.count !== "number"
    );
  });
  if (bad >= 0) {
    throw new Error(
      `Observation ${String(bad + 1)} needs a linkId (text), a timestamp (seconds) and a count (number).`,
    );
  }
  return doc as TwinObservation[];
}
