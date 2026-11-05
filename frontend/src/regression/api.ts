import { V3, getJson, query } from "../insights/http";
import type { NightlyRegression } from "./types";

export function getNightlyRegression(limit = 30): Promise<NightlyRegression> {
  return getJson(`${V3}/regression/nightly${query({ limit })}`);
}
