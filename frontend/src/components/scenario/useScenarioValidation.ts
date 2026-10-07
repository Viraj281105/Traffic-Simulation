import { useEffect, useState } from "react";
import { validateScenario } from "../../services/scenarioApi";
import type {
  ScenarioDocument,
  ScenarioValidation,
  Strategy,
} from "../../scenario/scenarioTypes";

export type ValidationState =
  | { status: "checking" }
  | { status: "unreachable" }
  | { status: "done"; result: ScenarioValidation };

/** Asks the backend whether the scenario can be simulated, a moment after
 *  the user stops editing. The backend is the authority: the builder's own
 *  checks only make it respond instantly. */
export function useScenarioValidation(
  scenario: ScenarioDocument,
  strategies: Strategy[],
  delayMs = 350,
): ValidationState {
  const key = JSON.stringify({ scenario, strategies });
  const [state, setState] = useState<{ key: string; value: ValidationState }>({
    key: "",
    value: { status: "checking" },
  });

  useEffect(() => {
    let cancelled = false;
    const { scenario: doc, strategies: wanted } = JSON.parse(key) as {
      scenario: ScenarioDocument;
      strategies: Strategy[];
    };
    const timer = setTimeout(() => {
      // Started inside the chain so a request that fails before it returns
      // a promise is reported as unreachable too, not thrown from a timer.
      Promise.resolve()
        .then(() => validateScenario(doc, wanted))
        .then((result) => {
          if (!cancelled) setState({ key, value: { status: "done", result } });
        })
        .catch(() => {
          if (!cancelled) setState({ key, value: { status: "unreachable" } });
        });
    }, delayMs);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [key, delayMs]);

  return state.key === key ? state.value : { status: "checking" };
}
