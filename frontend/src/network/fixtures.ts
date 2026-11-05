import type { ImportPreview, ValidationResult } from "./types";

export const validationFixture: ValidationResult = {
  uploadId: "up1",
  filename: "corridor.net.xml",
  format: "sumo",
  valid: true,
  summary: { nodes: 14, links: 22, junctions: 2, totalLengthKm: 3.4 },
  messages: [
    {
      severity: "warning",
      code: "unsupported_element",
      message: "Pedestrian crossings are not modelled and were skipped.",
      line: 120,
      element: "crossing_7",
      hint: "Remove them from the file to hide this warning.",
    },
    {
      severity: "info",
      code: "speed_defaulted",
      message: "3 links had no speed limit; 50 km/h was used.",
    },
  ],
};

export const invalidFixture: ValidationResult = {
  uploadId: null,
  filename: "broken.osm",
  format: "osm",
  valid: false,
  summary: null,
  messages: [
    {
      severity: "error",
      code: "dangling_link",
      message: "Road 12 ends at a junction that is not in the file.",
      line: 48,
      element: "way_12",
      hint: "Export a slightly larger area so every road is complete.",
    },
    {
      severity: "warning",
      code: "unsupported_element",
      message: "Tram lines are ignored.",
    },
  ],
};

export const previewFixture: ImportPreview = {
  previewId: "pv1",
  area: "Leeds city centre",
  bbox: [-1.56, 53.79, -1.53, 53.81],
  stats: {
    nodes: 120,
    links: 190,
    signalisedJunctions: 9,
    totalLengthKm: 21.7,
    linksShown: 2,
  },
  links: [
    {
      id: "l1",
      roadClass: "primary",
      lanes: 2,
      speedLimitKmh: 50,
      lengthM: 850,
      geometry: [
        [-1.56, 53.8],
        [-1.545, 53.801],
        [-1.53, 53.8],
      ],
    },
    {
      id: "l2",
      roadClass: "residential",
      lanes: null,
      speedLimitKmh: null,
      lengthM: 420,
      geometry: [
        [-1.545, 53.801],
        [-1.545, 53.79],
      ],
    },
  ],
  messages: [
    {
      severity: "warning",
      code: "missing_lanes",
      message: "Lane counts are missing on 40 roads; one lane was assumed.",
    },
  ],
};
