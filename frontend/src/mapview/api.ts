import { V2, getJson } from "../netcommon/api";
import type { ScenarioInput } from "../netcommon/scenario";
import type { GridResponse } from "./types";

/** GET /api/v2/network-metrics/grid: the grid's graph, default flows and map. */
export function getGrid(scenario: ScenarioInput): Promise<GridResponse> {
  const q = new URLSearchParams({
    vehiclesPerHour: String(scenario.vehiclesPerHour),
  });
  if (scenario.preset === "custom") {
    q.set("rows", String(scenario.rows));
    q.set("cols", String(scenario.cols));
  } else {
    q.set("preset", scenario.preset);
  }
  return getJson(`${V2}/network-metrics/grid?${q.toString()}`);
}
