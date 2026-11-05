import { V2, postJson } from "../netcommon/api";
import type {
  TwinRequest,
  TwinScenario,
  TwinState,
  WhatIfRequest,
  WhatIfResult,
} from "./types";

/** POST /api/v2/twin/compare: run the twin over the observations and get its
 *  prediction timeline, scores and alerts. */
export function compareTwin(request: TwinRequest): Promise<TwinState> {
  return postJson(`${V2}/twin/compare`, request);
}

/** POST /api/v2/twin/whatif: fork the twin at the latest observation and
 *  compare a scenario with the baseline for the next windows. */
export function whatIfTwin(
  request: TwinRequest,
  scenario: TwinScenario,
  horizonWindows = 1,
): Promise<WhatIfResult> {
  const body: WhatIfRequest = { ...request, scenario, horizonWindows };
  return postJson(`${V2}/twin/whatif`, body);
}
