import { useMemo, useState } from "react";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock,
  Layers,
  ListChecks,
  Send,
  ShieldCheck,
  Sparkles,
  Wand2,
} from "lucide-react";
import { Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
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
import { TOOLTIP_STYLE } from "../../theme/chart";
import {
  ChartFrame,
  EmptyHint,
  PageHero,
  Panel,
  Pill,
  Skeleton,
  StatGrid,
  StatTile,
  Stepper,
} from "../dashboard/Dashboard";
import { FIELD_TITLE, provenanceCounts, simulatedTime } from "./proposalStats";

const EXAMPLE =
  "Compare a conventional roundabout, a signalised roundabout and an adaptive signal under highly aggressive driving and uneven peak-hour demand.";

const STARTERS = [
  {
    label: "Fixed-time vs adaptive",
    text: "Does an adaptive signal beat a fixed-time signal at a busy four-arm junction?",
  },
  {
    label: "Aggressive drivers",
    text: "Which control strategy copes best with highly aggressive driving?",
  },
  {
    label: "Uneven demand",
    text: "How do a roundabout and an adaptive signal compare when demand is uneven between arms?",
  },
  { label: "Full example", text: EXAMPLE },
];

const PROVENANCE_TEXT: Record<Provenance, string> = {
  user: "from you",
  rule: "rule",
  model: "AI",
};

const PROVENANCE_LEGEND: Record<Provenance, string> = {
  user: "Your words",
  rule: "Rule-based defaults",
  model: "AI model",
};

const PROVENANCE_COLOUR: Record<Provenance, string> = {
  user: "var(--brand-green-ink)",
  rule: "var(--series-neutral)",
  model: "var(--color-accent)",
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

function ProvenanceDonut({ proposal }: { proposal: ExperimentProposal }) {
  const counts = provenanceCounts(proposal);
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const data = (Object.keys(counts) as Provenance[])
    .filter((k) => counts[k] > 0)
    .map((k) => ({
      key: k,
      name: PROVENANCE_LEGEND[k],
      value: counts[k],
      fill: PROVENANCE_COLOUR[k],
    }));
  return (
    <div className="copilot-donut">
      <ChartFrame
        label={`Where the ${total.toString()} proposal fields came from: ${data
          .map((d) => `${d.name} ${d.value.toString()}`)
          .join(", ")}`}
        height={150}
      >
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius="62%"
              outerRadius="92%"
              paddingAngle={2}
              stroke="none"
            ></Pie>
            <Tooltip contentStyle={TOOLTIP_STYLE} />
          </PieChart>
        </ResponsiveContainer>
      </ChartFrame>
      <ul className="dash-legend copilot-donut__legend">
        {data.map((d) => (
          <li key={d.key}>
            <i style={{ background: PROVENANCE_COLOUR[d.key] }} />
            {d.name}: <strong>{d.value.toString()}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
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

  const step = !proposal ? 0 : proposal.confirmed ? 2 : 1;
  const counts = useMemo(
    () => (proposal ? provenanceCounts(proposal) : null),
    [proposal],
  );
  const perRun =
    proposal?.estimatedRuns && proposal.estimatedSimulatedSeconds !== null
      ? proposal.estimatedSimulatedSeconds / proposal.estimatedRuns
      : null;

  return (
    <div className="dash-page copilot-page">
      <PageHero
        title="Experiment Copilot"
        aside={
          <Stepper
            steps={["Ask", "Review the proposal", "Confirm"]}
            current={step}
          />
        }
      >
        Describe what you want to compare. The Copilot proposes a Robustness Lab
        experiment, the server checks it, and you decide whether to run it. A
        proposal is a suggestion, not a result.
      </PageHero>

      <section className="dash-panel" aria-labelledby="copilot-question">
        <div className="dash-panel__head">
          <div>
            <h2 id="copilot-question">Your question</h2>
            <p className="dash-panel__sub">
              Name the strategies, the traffic conditions and what “better”
              means. Anything you leave out gets a stated default.
            </p>
          </div>
          <span className="copilot-count" aria-live="polite">
            {question.length.toString()} / 2000
          </span>
        </div>
        <textarea
          className="dash-textarea"
          value={question}
          maxLength={2000}
          rows={4}
          placeholder={EXAMPLE}
          onChange={(e) => {
            setQuestion(e.target.value);
          }}
          aria-label="Research question"
        />
        <div className="dash-chips" aria-label="Starting points">
          {STARTERS.map((s) => (
            <button
              key={s.label}
              type="button"
              className="dash-chip"
              title={s.text}
              onClick={() => {
                setQuestion(s.text);
              }}
            >
              {s.label}
            </button>
          ))}
        </div>
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

      {busy && !proposal ? (
        <Panel id="copilot-loading" title="Drafting a proposal…">
          <div role="status" aria-label="Drafting a proposal">
            <Skeleton lines={4} />
          </div>
        </Panel>
      ) : null}

      {!proposal && !busy ? (
        <EmptyHint icon={<Sparkles size={22} />} title="No proposal yet">
          Ask a question above. You will see the experiment the Copilot would
          run, which parts came from you, rules or the AI model, how many runs
          it needs, and any problems the server found.
        </EmptyHint>
      ) : null}

      {proposal && counts ? (
        <>
          <StatGrid>
            <StatTile
              label="Simulation runs"
              icon={<Layers size={16} />}
              value={
                proposal.estimatedRuns !== null
                  ? proposal.estimatedRuns.toLocaleString()
                  : "—"
              }
              hint={
                perRun !== null
                  ? `About ${simulatedTime(perRun)} simulated per run`
                  : "Run count unknown"
              }
              tip="The server's count of simulation runs this experiment needs."
            />
            <StatTile
              label="Simulated time"
              icon={<Clock size={16} />}
              value={
                proposal.estimatedSimulatedSeconds !== null
                  ? simulatedTime(proposal.estimatedSimulatedSeconds)
                  : "—"
              }
              hint="Counted against your daily quota"
              tip="Simulated seconds, not wall-clock time. Wall-clock time is unverified."
            />
            <StatTile
              label="Server validation"
              icon={<ShieldCheck size={16} />}
              tone={proposal.validated ? "good" : "bad"}
              value={proposal.validated ? "Passed" : "Blocked"}
              hint={
                proposal.issues.length
                  ? `${proposal.issues.length.toString()} problem${proposal.issues.length === 1 ? "" : "s"} to fix`
                  : "No problems found"
              }
            />
            <StatTile
              label="Model-suggested fields"
              icon={<Bot size={16} />}
              tone={counts.model > 0 ? "info" : "neutral"}
              value={counts.model.toString()}
              unit={`of ${Object.keys(FIELD_TITLE).length.toString()}`}
              hint={
                proposal.mode === "model"
                  ? "AI-assisted"
                  : "No AI model was used"
              }
            />
          </StatGrid>

          <div className="dash-split">
            <section className="dash-panel" aria-labelledby="copilot-proposal">
              <div className="dash-panel__head">
                <div>
                  <h2 id="copilot-proposal">Proposal</h2>
                  <p className="dash-panel__sub copilot-mode">
                    {proposal.mode === "model"
                      ? "AI-assisted proposal — validated by the backend; you confirm it."
                      : "Rule-based proposal (no AI model was used)."}
                    {proposal.mode === "deterministic" &&
                    proposal.aiUnavailableReason
                      ? ` AI assistance unavailable: ${proposal.aiUnavailableReason}.`
                      : ""}
                  </p>
                </div>
                <Pill tone={proposal.validated ? "good" : "bad"}>
                  {proposal.validated ? "Validated" : "Needs fixes"}
                </Pill>
              </div>
              {proposal.clarification ? (
                <p className="copilot-note">{proposal.clarification}</p>
              ) : null}
              <div className="dash-table-wrap">
                <table className="dash-table">
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
                            {
                              PROVENANCE_TEXT[
                                proposal.fieldProvenance[key] ?? "rule"
                              ]
                            }
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="copilot-muted">
                {proposal.estimatedRuns !== null
                  ? `${proposal.estimatedRuns.toString()} simulation runs`
                  : "Run count unknown"}
                {proposal.estimatedSimulatedSeconds !== null
                  ? `, ${Math.round(proposal.estimatedSimulatedSeconds).toLocaleString()} simulated seconds (counted against your daily quota)`
                  : ""}
                . Wall-clock time: unverified.
              </p>
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

            <div className="copilot-side">
              <Panel
                id="copilot-sources"
                title="Who decided what"
                subtitle="How each proposed field was filled in."
              >
                <ProvenanceDonut proposal={proposal} />
              </Panel>

              {proposal.intent.alternatives.length ? (
                <Panel id="copilot-alts" title="Strategies compared">
                  <div className="dash-chips">
                    {proposal.intent.alternatives.map((a) => (
                      <Pill
                        key={a}
                        tone={a === proposal.intent.baseline ? "warn" : "info"}
                      >
                        {a}
                        {a === proposal.intent.baseline ? " · baseline" : ""}
                      </Pill>
                    ))}
                  </div>
                </Panel>
              ) : null}

              {proposal.assumptions.length ? (
                <Panel id="copilot-assume" title="Assumptions">
                  <ul className="copilot-list">
                    {proposal.assumptions.map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                </Panel>
              ) : null}

              {proposal.warnings.length ? (
                <Panel id="copilot-warn" title="Warnings">
                  <ul className="copilot-warnings">
                    {proposal.warnings.map((w) => (
                      <li key={w}>
                        <AlertTriangle size={14} aria-hidden="true" /> {w}
                      </li>
                    ))}
                  </ul>
                </Panel>
              ) : null}

              {proposal.suggestedChecks.length ? (
                <Panel
                  id="copilot-checks"
                  title={
                    <>
                      <ListChecks size={16} aria-hidden="true" /> Checks worth
                      running next
                    </>
                  }
                >
                  <ul className="copilot-list">
                    {proposal.suggestedChecks.map((c) => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                </Panel>
              ) : null}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
