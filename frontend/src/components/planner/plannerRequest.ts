/** The planning-study request the planner page sends (planning/models.py). */
import {
  METERED_ROUNDABOUT_TITLE,
  isMeteredEntry,
  type ScenarioDocument,
  type Strategy,
} from "../../scenario/scenarioTypes";
import type { PlanningStudyRequest } from "../../services/v2/planning";

export interface AlternativeRow {
  key: number;
  strategy: Strategy;
  label: string;
}

/** Alternative ids the server accepts: the strategy, numbered on repeats. */
function alternativeIds(rows: AlternativeRow[]): string[] {
  const used = new Map<string, number>();
  return rows.map((r) => {
    const n = (used.get(r.strategy) ?? 0) + 1;
    used.set(r.strategy, n);
    return n === 1 ? r.strategy : `${r.strategy}-${n.toString()}`;
  });
}

export function buildStudyRequest(input: {
  name: string;
  scenario: ScenarioDocument;
  alternatives: AlternativeRow[];
  seeds: number;
  scales: number[];
}): PlanningStudyRequest {
  const ids = alternativeIds(input.alternatives);
  return {
    format: "urbanflow-planning-study",
    version: 1,
    name: input.name.trim() || "Planning study",
    subject: { scenario: input.scenario },
    alternatives: input.alternatives.map((a, i) => ({
      id: ids[i],
      strategy: a.strategy,
      // A metered-entry roundabout is named as such in the study's findings
      // and exports; every other alternative keeps the server's own title.
      ...(a.label.trim()
        ? { label: a.label.trim() }
        : a.strategy === "roundabout" && isMeteredEntry(input.scenario)
          ? { label: METERED_ROUNDABOUT_TITLE }
          : {}),
    })),
    demand: { scales: [...input.scales].sort((a, b) => a - b) },
    repetitions: { seeds: input.seeds },
  };
}
