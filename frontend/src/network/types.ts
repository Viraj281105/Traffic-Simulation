/** Contracts for network upload and road import. See src/CONTRACTS.md.
 *
 *  POST /api/v3/networks/validate   multipart/form-data: `file`, `format`
 *  POST /api/v3/networks/import/preview   JSON ImportPreviewRequest
 */

export type NetworkFormat =
  "auto" | "osm" | "sumo" | "geojson" | "gtfs" | "synchro";

export type MessageSeverity = "error" | "warning" | "info";

export interface ValidationMessage {
  severity: MessageSeverity;
  /** Stable machine code, e.g. "unsupported_element". */
  code: string;
  /** Plain-language message for the person who uploaded the file. */
  message: string;
  /** Where in the file, when known. */
  line?: number | null;
  /** Element the message is about (node, edge or route id). */
  element?: string | null;
  /** What to do about it, when the server knows. */
  hint?: string | null;
}

export interface ValidationResult {
  uploadId: string | null;
  filename: string;
  /** The format the server detected or was told. */
  format: Exclude<NetworkFormat, "auto">;
  /** True when the network can be used. Warnings do not make it invalid. */
  valid: boolean;
  summary: {
    nodes: number;
    links: number;
    junctions: number;
    totalLengthKm: number;
  } | null;
  messages: ValidationMessage[];
}

export type RoadClass =
  "motorway" | "trunk" | "primary" | "secondary" | "tertiary" | "residential";

export interface ImportPreviewRequest {
  source: "osm";
  /** Either a place name or a bounding box, not both. */
  place?: string;
  /** [west, south, east, north] in degrees. */
  bbox?: [number, number, number, number];
  roadClasses: RoadClass[];
}

export interface PreviewLink {
  id: string;
  roadClass: RoadClass;
  lanes: number | null;
  speedLimitKmh: number | null;
  lengthM: number;
  /** [longitude, latitude] points along the road. */
  geometry: [number, number][];
}

export interface ImportPreview {
  previewId: string;
  /** What was searched: the place name or the box as text. */
  area: string;
  bbox: [number, number, number, number];
  stats: {
    nodes: number;
    links: number;
    signalisedJunctions: number;
    totalLengthKm: number;
    /** Links drawn in the preview; the server may thin a large area. */
    linksShown: number;
  };
  links: PreviewLink[];
  messages: ValidationMessage[];
}
