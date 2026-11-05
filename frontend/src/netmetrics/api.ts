import { V2, postJson } from "../netcommon/api";
import { runBody, type ScenarioInput } from "../netcommon/scenario";
import type { NetworkMetrics } from "./types";

/** POST /api/v2/network-metrics/simulate for a grid scenario, with map data
 *  (link `value` = mean occupancy ratio). */
export function simulateNetwork(
  scenario: ScenarioInput,
): Promise<NetworkMetrics> {
  return postJson(`${V2}/network-metrics/simulate`, runBody(scenario));
}
