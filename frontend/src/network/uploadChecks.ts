import { num } from "../insights/format";
import { MAX_UPLOAD_BYTES } from "./api";
import type { NetworkFormat, ValidationMessage } from "./types";

export const FORMAT_OPTIONS: { value: NetworkFormat; label: string }[] = [
  { value: "auto", label: "Detect automatically" },
  { value: "osm", label: "OpenStreetMap (.osm, .xml)" },
  { value: "sumo", label: "SUMO network (.net.xml)" },
  { value: "geojson", label: "GeoJSON (.geojson, .json)" },
  { value: "gtfs", label: "GTFS transit feed (.zip)" },
  { value: "synchro", label: "Synchro (.csv)" },
];

/** Checks the browser can do before sending anything. */
export function precheckFile(file: File): ValidationMessage[] {
  if (file.size === 0) {
    return [
      {
        severity: "error",
        code: "empty_file",
        message: "The file is empty.",
        hint: "Choose the exported network file.",
      },
    ];
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return [
      {
        severity: "error",
        code: "file_too_large",
        message: `The file is ${num(file.size / 1024 / 1024, 1)} MB; the limit is ${num(MAX_UPLOAD_BYTES / 1024 / 1024, 0)} MB.`,
        hint: "Export a smaller area.",
      },
    ];
  }
  return [];
}
