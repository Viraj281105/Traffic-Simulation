import { V2, postJson } from "../netcommon/api";
import { runBody, type ScenarioInput } from "../netcommon/scenario";
import type { CongestionResult } from "./types";

export interface CongestionOptions {
  /** 0..1 occupancy ratio at which a link counts as congested. */
  threshold: number;
}

export const DEFAULT_CONGESTION: CongestionOptions = { threshold: 0.3 };

/** POST /api/v2/network-metrics/congestion for a grid scenario. */
export function analyseCongestion(
  scenario: ScenarioInput,
  options: CongestionOptions = DEFAULT_CONGESTION,
): Promise<CongestionResult> {
  return postJson(
    `${V2}/network-metrics/congestion`,
    runBody(scenario, { threshold: options.threshold }),
  );
}
