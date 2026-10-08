/** V1.4 scenario-document endpoints (backend core/scenario.py). */
import { post } from "./api";
import type {
  ScenarioDocument,
  ScenarioValidation,
  Strategy,
} from "../scenario/scenarioTypes";

/** Whether the scenario can be simulated under each strategy. Always
 *  resolves for a reachable backend: an invalid scenario comes back with
 *  ``valid: false`` and the reasons. */
export function validateScenario(
  scenario: ScenarioDocument,
  strategies: Strategy[],
): Promise<ScenarioValidation> {
  return post("/api/v1/scenarios/validate", { scenario, strategies });
}

/** The exact engine configuration one strategy runs. */
export function compileScenario(
  scenario: ScenarioDocument,
  strategy: Strategy,
): Promise<{ strategy: Strategy; config: Record<string, unknown> }> {
  return post("/api/v1/scenarios/compile", { scenario, strategy });
}
