import { useState } from "react";
import { AlertTriangle, CheckCircle2, Send, Wand2 } from "lucide-react";
import "./Copilot.css";
import {
  applySuggestion,
  confirmProposal,
  propose,
  type ExperimentProposal,
  type Provenance,
} from "../../services/v3/copilot";
import { ExperimentsApiError } from "../../services/v3/experiments";
import { experimentPath, followLink, navigate } from "../../routing";

const EXAMPLE =
  "Compare a conventional roundabout, a signalised roundabout and an adaptive signal under highly aggressive driving and uneven peak-hour demand.";

const PROVENANCE_TEXT: Record<Provenance, string> = {
  user: "from you",
  rule: "rule",
  model: "AI",
};

const FIELD_TITLE: Record<string, string> = {
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

function describe(key: string, proposal: ExperimentProposal): string {
  const intent = proposal.intent as unknown as Record<string, unknown>;
  const value = intent[key];
  if (Array.isArray(value)) return value.join(", ");
  if (value === null || value === undefined) return "scenario default";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "string" || typeof value === "number")
    return String(value);
  return "—";
}

function message(err: unknown, fallback: string): string {
  return err instanceof ExperimentsApiError ? err.message : fallback;
}

/** The Experiment Copilot: a research question becomes a proposal the backend
 *  has validated; nothing runs until you confirm it. */
export function CopilotPage() {
  const [question, setQuestion] = useState("");
  const [proposal, setProposal] = useState<ExperimentProposal | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const ask = (mode: "auto" | "deterministic") => {
    if (!question.trim()) return;
    setBusy(true);
    setError(null);
    propose(question, mode)
      .then(setProposal)
      .catch((err: unknown) => {
        setError(message(err, "The proposal could not be made."));
      })
      .finally(() => {
        setBusy(false);
      });
  };

  const fix = (code: string) => {
    if (!proposal) return;
    setBusy(true);
    setError(null);
    applySuggestion(proposal.id, code)
      .then(setProposal)
      .catch((err: unknown) => {
        setError(message(err, "The suggestion could not be applied."));
      })
      .finally(() => {
        setBusy(false);
      });
  };

  const submit = () => {
    if (!proposal) return;
    setBusy(true);
    setError(null);
    confirmProposal(proposal)
      .then((status) => {
        navigate(experimentPath(status.id));
      })
      .catch((err: unknown) => {
        setError(message(err, "The experiment could not be submitted."));
        setBusy(false);
      });
  };

  return (
    <div className="copilot-page">
      <header className="copilot-header">
        <p className="guided-eyebrow">Plan</p>
        <h1>Experiment Copilot</h1>
        <p>
          Describe what you want to compare. The Copilot proposes a Robustness
          Lab experiment, the server checks it, and you decide whether to run
          it. A proposal is a suggestion, not a result.
        </p>
      </header>

      <section className="copilot-card" aria-labelledby="copilot-question">
        <h2 id="copilot-question">Your question</h2>
        <textarea
          value={question}
          maxLength={2000}
          rows={4}
          placeholder={EXAMPLE}
          onChange={(e) => {
            setQuestion(e.target.value);
          }}
          aria-label="Research question"
        />
        <div className="copilot-actions">
          <button
            type="button"
            className="pb-btn pb-primary"
            disabled={busy || !question.trim()}
            onClick={() => {
              ask("auto");
            }}
          >
            <Wand2 size={15} aria-hidden="true" />
            Propose an experiment
          </button>
          <button
            type="button"
            className="pb-btn pb-secondary"
            disabled={busy || !question.trim()}
            onClick={() => {
              ask("deterministic");
            }}
          >
            Use the rule-based assistant
          </button>
          <button
            type="button"
            className="uf-link copilot-example"
            onClick={() => {
              setQuestion(EXAMPLE);
            }}
          >
            Use the example question
          </button>
        </div>
        {error ? (
          <p className="copilot-error" role="alert">
            {error}
          </p>
        ) : null}
      </section>

      {proposal ? (
        <section className="copilot-card" aria-labelledby="copilot-proposal">
          <h2 id="copilot-proposal">Proposal</h2>
          <p className="copilot-mode">
            {proposal.mode === "model"
              ? "AI-assisted proposal — validated by the backend; you confirm it."
              : "Rule-based proposal (no AI model was used)."}
            {proposal.mode === "deterministic" && proposal.aiUnavailableReason
              ? ` AI assistance unavailable: ${proposal.aiUnavailableReason}.`
              : ""}
          </p>
          {proposal.clarification ? (
            <p className="copilot-note">{proposal.clarification}</p>
          ) : null}
          <table className="copilot-table">
            <thead>
              <tr>
                <th scope="col">Field</th>
                <th scope="col">Proposed</th>
                <th scope="col">Source</th>
              </tr>
            </thead>
            <tbody>
              {Object.keys(FIELD_TITLE).map((key) => (
                <tr key={key}>
                  <th scope="row">{FIELD_TITLE[key]}</th>
                  <td>{describe(key, proposal)}</td>
                  <td>
                    <span
                      className={`copilot-source is-${proposal.fieldProvenance[key] ?? "rule"}`}
                    >
                      {PROVENANCE_TEXT[proposal.fieldProvenance[key] ?? "rule"]}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="copilot-muted">
            {proposal.estimatedRuns !== null
              ? `${proposal.estimatedRuns.toString()} simulation runs`
              : "Run count unknown"}
            {proposal.estimatedSimulatedSeconds !== null
              ? `, ${Math.round(proposal.estimatedSimulatedSeconds).toLocaleString()} simulated seconds (counted against your daily quota)`
              : ""}
            . Wall-clock time: unverified.
          </p>
          {proposal.assumptions.length ? (
            <>
              <h3>Assumptions</h3>
              <ul>
                {proposal.assumptions.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </>
          ) : null}
          {proposal.warnings.length ? (
            <ul className="copilot-warnings">
              {proposal.warnings.map((w) => (
                <li key={w}>
                  <AlertTriangle size={14} aria-hidden="true" /> {w}
                </li>
              ))}
            </ul>
          ) : null}
          {proposal.issues.length ? (
            <>
              <h3>Problems found by the server</h3>
              <ul className="copilot-issues">
                {proposal.issues.map((issue) => (
                  <li key={issue.code + issue.message}>
                    <code>{issue.code}</code> {issue.message}
                    {issue.suggestion ? (
                      <button
                        type="button"
                        className="pb-btn pb-secondary"
                        disabled={busy}
                        onClick={() => {
                          fix(issue.code);
                        }}
                      >
                        Make a corrected proposal
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {proposal.suggestedChecks.length ? (
            <>
              <h3>Checks worth running next</h3>
              <ul>
                {proposal.suggestedChecks.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </>
          ) : null}
          <div className="copilot-actions">
            <button
              type="button"
              className="pb-btn pb-primary"
              disabled={busy || !proposal.validated || proposal.confirmed}
              onClick={submit}
            >
              {proposal.validated ? (
                <CheckCircle2 size={15} aria-hidden="true" />
              ) : (
                <Send size={15} aria-hidden="true" />
              )}
              {proposal.validated
                ? "Confirm and run"
                : "Cannot run until the problems are fixed"}
            </button>
            {proposal.experimentId ? (
              <a
                className="uf-link"
                href={experimentPath(proposal.experimentId)}
                onClick={(event) => {
                  followLink(
                    event,
                    experimentPath(proposal.experimentId ?? ""),
                  );
                }}
              >
                Open the experiment
              </a>
            ) : null}
          </div>
        </section>
      ) : null}
    </div>
  );
}
