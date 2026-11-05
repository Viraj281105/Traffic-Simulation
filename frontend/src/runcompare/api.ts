import { V3, getJson, query } from "../insights/http";
import type { RunDiff } from "./types";

export function compareRuns(a: string, b: string): Promise<RunDiff> {
  return getJson(`${V3}/runs/compare${query({ a, b })}`);
}
