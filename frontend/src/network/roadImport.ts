import type { ImportPreviewRequest, RoadClass } from "./types";

export const ROAD_CLASSES: { value: RoadClass; label: string }[] = [
  { value: "motorway", label: "Motorway" },
  { value: "trunk", label: "Trunk" },
  { value: "primary", label: "Primary" },
  { value: "secondary", label: "Secondary" },
  { value: "tertiary", label: "Tertiary" },
  { value: "residential", label: "Residential" },
];

/** "west,south,east,north" as a box, a place name otherwise; null if the
 *  input is empty or a box with impossible numbers. */
export function parseArea(
  text: string,
): Pick<ImportPreviewRequest, "place" | "bbox"> | null {
  const value = text.trim();
  if (!value) return null;
  const parts = value.split(/[\s,]+/);
  if (parts.length === 4 && parts.every((p) => p !== "" && !isNaN(Number(p)))) {
    const [w, s, e, n] = parts.map(Number);
    if (w >= e || s >= n || w < -180 || e > 180 || s < -90 || n > 90) {
      return null;
    }
    return { bbox: [w, s, e, n] };
  }
  return { place: value };
}
