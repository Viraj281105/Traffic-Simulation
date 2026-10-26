/**
 * Experiment Copilot client (backend src/copilot/router.py, /api/v3/copilot).
 *
 * A proposal is only a proposal: it is validated by the backend and runs
 * nothing until the user confirms it with its content hash. Measured
 * evidence and generated text arrive in separate fields and are shown apart.
 */
import { getJson, postJson, type ExperimentStatus } from "./experiments";

const PREFIX = "/api/v3/copilot";

export type Provenance = "user" | "rule" | "model";

export interface ProposalIssue {
  code: string;
  message: string;
  suggestion: Record<string, unknown> | null;
}

export interface ExperimentIntent {
  alternatives: string[];
  baseline: string | null;
  aggression: string | null;
  demand: string;
  unevenDemand: boolean;
  mix: string;
  depth: string;
  replications: number;
  primaryIndicator: string;
}

export interface ExperimentProposal {
  id: string;
  question: string;
  mode: "deterministic" | "model";
  aiUnavailableReason: string | null;
  intent: ExperimentIntent;
  experiment: Record<string, unknown>;
  fieldProvenance: Record<string, Provenance>;
  assumptions: string[];
  warnings: string[];
  suggestedChecks: string[];
  clarification: string | null;
  estimatedRuns: number | null;
  estimatedSimulatedSeconds: number | null;
  estimatedWallTime: "unverified";
  validated: boolean;
  issues: ProposalIssue[];
  contentHash: string;
  confirmed: boolean;
  experimentId: string | null;
}

export interface Interpretation {
  measured: {
    primaryIndicator: string;
    eligibilityClass: string;
    counts: Record<string, number | null>;
    alternatives: Record<string, { label: string; meanOutcome: number | null }>;
  };
  template: string;
  interpretation: { label: string; text: string } | null;
  unfavourableFindings: string[];
  aiUnavailableReason: string | null;
}

export function propose(
  question: string,
  mode: "auto" | "deterministic" = "auto",
): Promise<ExperimentProposal> {
  return postJson(`${PREFIX}/proposals`, { question, mode });
}

export function getProposal(id: string): Promise<ExperimentProposal> {
  return getJson(`${PREFIX}/proposals/${encodeURIComponent(id)}`);
}

export function applySuggestion(
  id: string,
  code: string,
): Promise<ExperimentProposal> {
  return postJson(
    `${PREFIX}/proposals/${encodeURIComponent(id)}/suggestions/${encodeURIComponent(code)}`,
  );
}

export function confirmProposal(
  proposal: ExperimentProposal,
): Promise<ExperimentStatus> {
  return postJson(
    `${PREFIX}/proposals/${encodeURIComponent(proposal.id)}/confirm`,
    { contentHash: proposal.contentHash },
  );
}

export function interpret(
  experimentId: string,
  preferred: string | null,
): Promise<Interpretation> {
  return postJson(
    `${PREFIX}/experiments/${encodeURIComponent(experimentId)}/interpretation`,
    { preferred },
  );
}
