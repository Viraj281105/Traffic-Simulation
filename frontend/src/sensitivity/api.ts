import { V3, getJson, query } from "../insights/http";
import type { SensitivityResult } from "./types";

export function getSensitivity(
  experimentId: string,
  options: { metric?: string } = {},
): Promise<SensitivityResult> {
  return getJson(
    `${V3}/experiments/${encodeURIComponent(experimentId)}/sensitivity${query(options)}`,
  );
}
