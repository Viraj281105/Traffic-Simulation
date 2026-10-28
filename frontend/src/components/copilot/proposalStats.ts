import type { ExperimentProposal, Provenance } from "../../services/v3/copilot";

export const FIELD_TITLE: Record<string, string> = {
  alternatives: "Alternatives",
  baseline: "Baseline",
  aggression: "Driver aggression",
  demand: "Demand",
  unevenDemand: "Uneven demand",
  mix: "Vehicle mix",
  depth: "Study size",
  replications: "Replications",
  primaryIndicator: "Primary indicator",
};

/** Simulated seconds as a short human duration. */
export function simulatedTime(seconds: number): string {
  if (seconds < 90) return `${Math.round(seconds).toString()} s`;
  const minutes = seconds / 60;
  if (minutes < 120) return `${minutes.toFixed(0)} min`;
  return `${(minutes / 60).toFixed(1)} h`;
}

/** How many of the proposal's fields came from each source. */
export function provenanceCounts(
  proposal: ExperimentProposal,
): Record<Provenance, number> {
  const counts: Record<Provenance, number> = { user: 0, rule: 0, model: 0 };
  for (const key of Object.keys(FIELD_TITLE)) {
    counts[proposal.fieldProvenance[key] ?? "rule"] += 1;
  }
  return counts;
}
