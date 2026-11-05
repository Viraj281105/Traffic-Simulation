import { V3, getJson, query } from "../insights/http";
import type { ComparisonResult } from "./types";

export function getComparison(
  experimentId: string,
  options: { a?: string; b?: string; metric?: string } = {},
): Promise<ComparisonResult> {
  return getJson(
    `${V3}/experiments/${encodeURIComponent(experimentId)}/comparison${query(options)}`,
  );
}
