/**
 * V2.0 planner: build a scenario, choose the alternatives to compare, see
 * how many simulations that is, run the study as a background job and read
 * the evidence (PlannerResults). The study id is kept in the URL
 * (``/app/planner?study=<id>``), so a reload or a shared link re-opens the
 * finished study from the server.
 *
 * Everything is checked and computed by /api/v2/planning; this page only
 * collects the request and shows what the server returns. The workflow rail
 * and every status shown follow the real request and job state — nothing is
 * advanced or estimated on the client.
 */
import { useCallback, useEffect, useId, useState } from "react";
import type { CSSProperties } from "react";
import {
  ArrowLeft,
  ArrowUpToLine,
  Check,
  CircleAlert,
  FolderOpen,
  Play,
  Plus,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { ScenarioBuilder } from "../scenario/ScenarioBuilder";
import { useScenarioValidation } from "../scenario/useScenarioValidation";
import { DEFAULT_SCENARIO, cloneScenario } from "../../scenario/scenarioModel";
import {
  STRATEGIES,
  STRATEGY_TITLE,
  type ScenarioDocument,
  type Strategy,
} from "../../scenario/scenarioTypes";
import {
  PLANNING_LIMITS,
  PlanningApiError,
  getStudy,
  startStudy,
  validateStudy,
  type PlanningStudyRequest,
  type StudyRecord,
  type ValidateResponse,
} from "../../services/v2/planning";
import { VIEW_ROUTES, navigate, useSearch } from "../../routing";
import { StatusState } from "../ui/StatusState";
import { useFlipList } from "../ui/motion";
import { SmoothHeight } from "../ui/SmoothHeight";
import { PlannerResults } from "./PlannerResults";
import { buildStudyRequest, type AlternativeRow } from "./plannerRequest";
import {
  failureText,
  formatElapsed,
  groupStudyNotes,
  plainValidationError,
} from "./plannerText";
import "./Planner.css";

const POLL_MS = 1000;
const SCALE_CHOICES = [0.5, 0.75, 1, 1.25, 1.5, 2];
const ID_PATTERN = /^[A-Za-z0-9_-]{1,128}$/;

function asError(err: unknown): PlanningApiError {
  return err instanceof PlanningApiError
    ? err
    : new PlanningApiError(0, [String(err)]);
}

function plural(n: number, one: string, many = `${one}s`): string {
  return `${n.toString()} ${n === 1 ? one : many}`;
}

type Check =
  | { status: "checking" }
  | { status: "done"; result: ValidateResponse }
  | { status: "failed"; message: string };

/** One shared object, so "still checking" is the same value on every render
 *  (the page lifts the check into the workflow rail through an effect). */
const CHECKING: Check = { status: "checking" };

/** The server's verdict on the study, a moment after the user stops editing. */
function useStudyValidation(
  request: PlanningStudyRequest,
  delayMs = 400,
): Check {
  const key = JSON.stringify(request);
  const [state, setState] = useState<{ key: string; value: Check }>({
    key: "",
    value: CHECKING,
  });
  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(() => {
      Promise.resolve()
        .then(() => validateStudy(JSON.parse(key) as PlanningStudyRequest))
        .then((result) => {
          if (!cancelled) setState({ key, value: { status: "done", result } });
        })
        .catch((err: unknown) => {
          if (!cancelled) {
            setState({
              key,
              value: { status: "failed", message: failureText(asError(err)) },
            });
          }
        });
    }, delayMs);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [key, delayMs]);
  return state.key === key ? state.value : CHECKING;
}

// ── Workflow rail ──────────────────────────────────────────────────────────

type StageState = "done" | "current" | "pending" | "blocked";

interface Stage {
  label: string;
  state: StageState;
  /** What the stage is doing now, in a word or two. */
  note: string;
}

/** Configure → Check → Run → Evidence, each marked from real state. The
 *  state is in the words (and an icon), never in colour alone. */
function PlannerFlow({ stages }: { stages: Stage[] }) {
  return (
    <ol className="planner-flow" aria-label="Study workflow">
      {stages.map((stage, i) => (
        <li
          key={stage.label}
          className={`planner-flow__step is-${stage.state}`}
          aria-current={stage.state === "current" ? "step" : undefined}
        >
          <span className="planner-flow__index" aria-hidden="true">
            {stage.state === "done" ? (
              <Check size={13} strokeWidth={2.6} />
            ) : stage.state === "blocked" ? (
              <TriangleAlert size={12} strokeWidth={2.4} />
            ) : (
              i + 1
            )}
          </span>
          <span className="planner-flow__text">
            <span className="planner-flow__label">{stage.label}</span>
            <span className="planner-flow__note">{stage.note}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}

function setupStages(check: Check): Stage[] {
  const checkStage: Stage =
    check.status === "checking"
      ? { label: "Check", state: "current", note: "Checking…" }
      : check.status === "failed"
        ? { label: "Check", state: "blocked", note: "Could not check" }
        : check.result.valid
          ? { label: "Check", state: "done", note: "Ready to run" }
          : { label: "Check", state: "blocked", note: "Needs changes" };
  return [
    { label: "Configure", state: "current", note: "Scenario and alternatives" },
    checkStage,
    { label: "Run", state: "pending", note: "Not started" },
    { label: "Evidence", state: "pending", note: "After the run" },
  ];
}

function studyStages(record: StudyRecord | undefined, error?: string): Stage[] {
  const run: Stage = error
    ? { label: "Run", state: "blocked", note: "Unavailable" }
    : !record
      ? { label: "Run", state: "current", note: "Loading…" }
      : record.status === "queued"
        ? { label: "Run", state: "current", note: "Queued" }
        : record.status === "running"
          ? { label: "Run", state: "current", note: "Running" }
          : record.status === "failed"
            ? { label: "Run", state: "blocked", note: "Failed" }
            : { label: "Run", state: "done", note: "Finished" };
  const evidence: Stage =
    record?.status === "completed" && record.result
      ? { label: "Evidence", state: "current", note: "Ready to read" }
      : { label: "Evidence", state: "pending", note: "After the run" };
  return [
    { label: "Configure", state: "done", note: "Submitted" },
    { label: "Check", state: "done", note: "Accepted by the server" },
    run,
    evidence,
  ];
}

// ── Setup ──────────────────────────────────────────────────────────────────

let nextKey = 1;
const row = (strategy: Strategy): AlternativeRow => ({
  key: nextKey++,
  strategy,
  label: "",
});

function SectionTitle({
  id,
  n,
  children,
}: {
  id: string;
  n: number;
  children: string;
}) {
  return (
    <h2 id={id} className="uf-panel__title">
      <span className="q-number" aria-hidden="true">
        {n}
      </span>
      {children}
    </h2>
  );
}

function CheckBadge({ check }: { check: Check }) {
  if (check.status === "checking") {
    return (
      <span className="uf-badge planner-check-badge is-checking">
        <span className="uf-spinner" aria-hidden="true" />
        Checking
      </span>
    );
  }
  if (check.status === "failed") {
    return (
      <span className="uf-badge planner-check-badge is-blocked">
        Not checked
      </span>
    );
  }
  return check.result.valid ? (
    <span className="uf-badge planner-check-badge is-ready">
      <Check size={12} strokeWidth={2.6} aria-hidden="true" />
      Ready
    </span>
  ) : (
    <span className="uf-badge planner-check-badge is-blocked">
      Needs changes
    </span>
  );
}

function StudySetup({ onCheck }: { onCheck: (check: Check) => void }) {
  const formId = useId();
  const [name, setName] = useState("Planning study");
  const [scenario, setScenario] = useState<ScenarioDocument>(() =>
    cloneScenario(DEFAULT_SCENARIO),
  );
  const [alternatives, setAlternatives] = useState<AlternativeRow[]>(() =>
    STRATEGIES.map(row),
  );
  const [seeds, setSeeds] = useState(5);
  const [scales, setScales] = useState<number[]>([1]);
  const [startError, setStartError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const strategies = [...new Set(alternatives.map((a) => a.strategy))];
  const scenarioCheck = useScenarioValidation(scenario, strategies);
  const request = buildStudyRequest({
    name,
    scenario,
    alternatives,
    seeds,
    scales,
  });
  const check = useStudyValidation(request);
  const ready = check.status === "done" && check.result.valid && !starting;
  const tbodyRef = useFlipList<HTMLTableSectionElement>(
    alternatives.map((a) => a.key).join(","),
  );

  useEffect(() => {
    onCheck(check);
  }, [check, onCheck]);

  // The server's warnings name alternatives by id; read them by title.
  const titleById = new Map(
    request.alternatives.map((a, i) => [
      a.id,
      alternatives[i]?.label.trim() || STRATEGY_TITLE[a.strategy] || a.id,
    ]),
  );

  const update = (key: number, change: Partial<AlternativeRow>) => {
    setAlternatives((rows) =>
      rows.map((r) => (r.key === key ? { ...r, ...change } : r)),
    );
  };

  const start = () => {
    setStartError(null);
    setStarting(true);
    startStudy(request)
      .then((record) => {
        navigate(
          `${VIEW_ROUTES.planner}?study=${encodeURIComponent(record.id)}`,
        );
      })
      .catch((err: unknown) => {
        setStartError(failureText(asError(err)));
        setStarting(false);
      });
  };

  const simulations =
    check.status === "done" ? (check.result.simulations ?? null) : null;
  const share =
    simulations === null
      ? 0
      : Math.min(1, simulations / PLANNING_LIMITS.maxTotalRuns);

  return (
    <div className="planner-setup">
      <section
        className="planner-section"
        aria-labelledby={`${formId}-scenario`}
      >
        <div className="planner-section__head">
          <SectionTitle id={`${formId}-scenario`} n={1}>
            Scenario
          </SectionTitle>
          <p className="uf-panel__desc">
            Start from a preset or build the junction yourself. Every
            alternative below runs on this junction with the same seeds.
          </p>
        </div>
        <ScenarioBuilder
          value={scenario}
          onChange={setScenario}
          strategies={strategies}
          validation={scenarioCheck}
          junctionNote="In a planning study each alternative chooses its own control; the type here only sets the default view."
        />
      </section>

      <div className="planner-config">
        <section
          className="uf-panel planner-alts"
          aria-labelledby={`${formId}-alts`}
        >
          <div>
            <SectionTitle id={`${formId}-alts`} n={2}>
              Alternatives and repetitions
            </SectionTitle>
            <p className="uf-panel__desc">
              Each alternative is a control for the same junction. Every one
              runs the same seeds, so differences come from the control alone.
            </p>
          </div>

          <div className="uf-field planner-name">
            <label className="uf-label" htmlFor={`${formId}-name`}>
              Study name
            </label>
            <input
              id={`${formId}-name`}
              className="uf-input"
              type="text"
              value={name}
              maxLength={120}
              onChange={(e) => {
                setName(e.target.value);
              }}
            />
          </div>

          <div className="planner-alt-list">
            <div className="uf-table-wrap">
              <table className="uf-table planner-alt-table">
                <caption>
                  Alternatives to compare. The first is the baseline every other
                  alternative is compared with.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Role</th>
                    <th scope="col">Control</th>
                    <th scope="col">Label (optional)</th>
                    <th scope="col">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody ref={tbodyRef}>
                  {alternatives.map((alt, i) => {
                    const who =
                      i === 0 ? "the baseline" : `alternative ${i.toString()}`;
                    return (
                      <tr key={alt.key} data-flip-key={alt.key}>
                        <th scope="row">
                          <span
                            className={`planner-role${i === 0 ? " is-baseline" : ""}`}
                          >
                            {i === 0
                              ? "Baseline"
                              : `Alternative ${i.toString()}`}
                          </span>
                        </th>
                        <td>
                          <select
                            className="uf-select"
                            aria-label={`Control for ${who}`}
                            value={alt.strategy}
                            onChange={(e) => {
                              update(alt.key, {
                                strategy: e.target.value as Strategy,
                              });
                            }}
                          >
                            {STRATEGIES.map((s) => (
                              <option key={s} value={s}>
                                {STRATEGY_TITLE[s]}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td>
                          <input
                            className="uf-input"
                            type="text"
                            aria-label={`Label for ${who}`}
                            placeholder={STRATEGY_TITLE[alt.strategy]}
                            value={alt.label}
                            maxLength={120}
                            onChange={(e) => {
                              update(alt.key, { label: e.target.value });
                            }}
                          />
                        </td>
                        <td>
                          <div className="planner-row-actions">
                            {i > 0 && (
                              <button
                                type="button"
                                className="pb-btn pb-sm pb-ghost"
                                onClick={() => {
                                  setAlternatives((rows) => [
                                    alt,
                                    ...rows.filter((r) => r.key !== alt.key),
                                  ]);
                                }}
                              >
                                <ArrowUpToLine size={14} aria-hidden="true" />
                                Make baseline
                              </button>
                            )}
                            <button
                              type="button"
                              className="pb-btn pb-sm pb-ghost planner-remove"
                              disabled={alternatives.length <= 2}
                              onClick={() => {
                                setAlternatives((rows) =>
                                  rows.filter((r) => r.key !== alt.key),
                                );
                              }}
                            >
                              <Trash2 size={14} aria-hidden="true" />
                              Remove
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="planner-alt-foot">
              <button
                type="button"
                className="pb-btn pb-secondary pb-sm"
                disabled={
                  alternatives.length >= PLANNING_LIMITS.maxAlternatives
                }
                onClick={() => {
                  setAlternatives((rows) => [...rows, row("fixed_time")]);
                }}
              >
                <Plus size={14} aria-hidden="true" />
                Add alternative
              </button>
              <span className="uf-hint">
                {alternatives.length.toString()} of{" "}
                {PLANNING_LIMITS.maxAlternatives.toString()} alternatives; at
                least two.
              </span>
            </div>
          </div>

          <div className="planner-reps">
            <div className="uf-field planner-seeds">
              <label className="uf-label" htmlFor={`${formId}-seeds`}>
                Seeds per alternative
              </label>
              <input
                id={`${formId}-seeds`}
                className="uf-input"
                type="number"
                min={1}
                max={PLANNING_LIMITS.maxSeeds}
                value={seeds}
                aria-describedby={`${formId}-seeds-hint`}
                onChange={(e) => {
                  setSeeds(Math.round(Number(e.target.value)) || 1);
                }}
              />
              <p className="uf-hint" id={`${formId}-seeds-hint`}>
                Repetitions of each alternative, 1–
                {PLANNING_LIMITS.maxSeeds.toString()}. More seeds narrow the
                intervals.
              </p>
            </div>
            <fieldset className="uf-field planner-scales">
              <legend className="uf-label">Demand levels</legend>
              <div className="uf-chip-row">
                {SCALE_CHOICES.map((s) => {
                  const on = scales.includes(s);
                  return (
                    <label key={s} className="uf-chip-check">
                      <input
                        type="checkbox"
                        checked={on}
                        disabled={
                          (on && scales.length <= 1) ||
                          (!on && scales.length >= PLANNING_LIMITS.maxScales)
                        }
                        onChange={() => {
                          setScales((cur) =>
                            on ? cur.filter((x) => x !== s) : [...cur, s],
                          );
                        }}
                      />
                      ×{s.toString()}
                    </label>
                  );
                })}
              </div>
              <p className="uf-hint">
                Multiples of the scenario's demand; up to{" "}
                {PLANNING_LIMITS.maxScales.toString()} levels, at least one.
              </p>
            </fieldset>
          </div>
        </section>

        <section
          className="uf-panel planner-check"
          aria-labelledby={`${formId}-cost`}
        >
          <div className="uf-panel__head">
            <SectionTitle id={`${formId}-cost`} n={3}>
              Check and run
            </SectionTitle>
            <CheckBadge check={check} />
          </div>

          <SmoothHeight>
            <div aria-live="polite" className="planner-check__body">
              {check.status === "checking" && (
                <p className="planner-checking uf-fade">
                  Checking the study with the server…
                </p>
              )}
              {check.status === "failed" && (
                <div
                  role="alert"
                  className="uf-callout uf-callout--danger uf-fade"
                >
                  <CircleAlert size={17} aria-hidden="true" />
                  <div className="uf-callout__body">
                    <p>{check.message}</p>
                  </div>
                </div>
              )}
              {check.status === "done" && check.result.valid && (
                <div className="planner-total uf-fade">
                  <p className="planner-total__n">
                    <strong>
                      {String(simulations ?? "an unknown number of")}{" "}
                      simulations
                    </strong>
                  </p>
                  <p className="planner-total__formula">
                    {plural(alternatives.length, "alternative")} ×{" "}
                    {plural(scales.length, "demand level")} ×{" "}
                    {plural(seeds, "seed")}
                  </p>
                  <div
                    className={`uf-meter${share >= 1 ? " is-over" : share >= 0.8 ? " is-high" : ""}`}
                    style={{ "--meter": share } as CSSProperties}
                    aria-hidden="true"
                  >
                    <span />
                  </div>
                  <p className="uf-hint">
                    The server allows at most{" "}
                    {PLANNING_LIMITS.maxTotalRuns.toString()} simulations per
                    study.
                  </p>
                  <p className="planner-muted">
                    Run time: no measured estimate is available for this server.
                    Time grows with the number of simulations, the scenario
                    duration and how busy the junction is.
                  </p>
                  {check.result.warnings.length > 0 && (
                    <div className="planner-notes">
                      <p className="uf-subhead">Notes on these results</p>
                      <ul className="planner-note-list">
                        {groupStudyNotes(check.result.warnings, (id) =>
                          titleById.get(id),
                        ).map((note) => (
                          <li key={note.message}>
                            <TriangleAlert size={14} aria-hidden="true" />
                            <div>
                              <p>{note.message}</p>
                              {note.appliesTo.length > 0 && (
                                <p className="uf-hint">
                                  Applies to {note.appliesTo.join(", ")}.
                                </p>
                              )}
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
              {check.status === "done" && !check.result.valid && (
                <div
                  role="alert"
                  className="uf-callout uf-callout--warning uf-fade"
                >
                  <TriangleAlert size={17} aria-hidden="true" />
                  <div className="uf-callout__body">
                    <p className="uf-callout__title">
                      The study cannot run yet:
                    </p>
                    <ul className="uf-list">
                      {check.result.errors.map((e) => (
                        <li key={e}>{plainValidationError(e)}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </div>
          </SmoothHeight>

          <div className="planner-run-action">
            <button
              type="button"
              className="pb-btn pb-primary pb-block pb-tall"
              disabled={!ready}
              onClick={start}
            >
              {starting ? (
                <>
                  <span className="uf-spinner" aria-hidden="true" />
                  Starting…
                </>
              ) : (
                <>
                  <Play size={16} aria-hidden="true" />
                  Run study
                </>
              )}
            </button>
            <p className="uf-hint">
              The study runs as a background job on the server; its link
              re-opens it at any time.
            </p>
            {startError && (
              <div
                role="alert"
                className="uf-callout uf-callout--danger uf-reveal"
              >
                <CircleAlert size={17} aria-hidden="true" />
                <div className="uf-callout__body">
                  <p>{startError}</p>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

// ── A submitted study ────────────────────────────────────────────────────

function StudyView({
  studyId,
  onState,
}: {
  studyId: string;
  onState: (record: StudyRecord | undefined, error?: string) => void;
}) {
  const [state, setState] = useState<{
    id: string;
    record?: StudyRecord;
    error?: string;
  }>({ id: studyId });

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = () => {
      getStudy(studyId)
        .then((record) => {
          if (cancelled) return;
          setState({ id: studyId, record });
          if (record.status === "queued" || record.status === "running") {
            timer = setTimeout(poll, POLL_MS);
          }
        })
        .catch((err: unknown) => {
          if (!cancelled) {
            setState({ id: studyId, error: failureText(asError(err)) });
          }
        });
    };
    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [studyId]);

  const current = state.id === studyId ? state : { id: studyId };
  const record = current.record;
  const active =
    record && (record.status === "queued" || record.status === "running");

  useEffect(() => {
    onState(record, current.error);
  }, [record, current.error, onState]);

  return (
    <div className="planner-study">
      <a
        className="uf-link planner-back"
        href={VIEW_ROUTES.planner}
        onClick={(e) => {
          e.preventDefault();
          navigate(VIEW_ROUTES.planner);
        }}
      >
        <ArrowLeft size={15} className="is-back" aria-hidden="true" />
        Plan a new study
      </a>

      <SmoothHeight>
        <div aria-live="polite" role="status">
          {!record && !current.error && (
            <div className="uf-panel planner-run is-loading">
              <p className="planner-run__line">
                <span className="uf-spinner" aria-hidden="true" />
                Loading study {studyId}…
              </p>
            </div>
          )}
          {record && active && (
            <div className="uf-panel planner-run">
              <div className="planner-run__head">
                <div className="planner-run__title">
                  <p className="uf-subhead">Study</p>
                  <p className="planner-run__name">{record.name}</p>
                </div>
                <span className={`uf-badge planner-status is-${record.status}`}>
                  <span className="planner-status__dot" aria-hidden="true" />
                  {record.status === "queued" ? "Queued" : "Running"}
                </span>
              </div>
              <progress
                className="uf-progress"
                max={1}
                value={record.progress?.fraction ?? undefined}
                aria-label="Study progress"
              />
              <div className="planner-run__meta">
                <p className="planner-run__count">
                  {record.progress
                    ? `${record.progress.completed.toString()} of ${record.progress.total.toString()} simulations finished`
                    : record.status === "queued"
                      ? "Waiting for the server to start the study"
                      : "Starting the simulations"}
                </p>
                {record.progress && (
                  <p className="planner-run__elapsed">
                    Elapsed {formatElapsed(record.progress.elapsedSeconds)}
                  </p>
                )}
              </div>
              <p className="uf-hint">
                You can leave this page; the study keeps running and this link
                re-opens it.
              </p>
            </div>
          )}
        </div>
      </SmoothHeight>

      {current.error && (
        <StatusState
          tone="error"
          role="alert"
          title="Could not open the study"
          className="uf-panel planner-state"
        >
          {current.error}
        </StatusState>
      )}
      {record?.status === "failed" && (
        <StatusState
          tone="error"
          role="alert"
          title="The study failed on the server"
          className="uf-panel planner-state"
        >
          {`The server reported: ${record.error ?? "no reason given"}`}
        </StatusState>
      )}
      {record?.status === "completed" && !record.result && (
        <StatusState
          tone="warning"
          title="The study finished without a result"
          className="uf-panel planner-state"
        >
          The server marked the study complete but sent no result. Re-open the
          link later, or run the study again.
        </StatusState>
      )}
      {record?.status === "completed" && record.result && (
        <PlannerResults studyId={studyId} result={record.result} />
      )}
    </div>
  );
}

function OpenStudy() {
  const inputId = useId();
  const [value, setValue] = useState("");
  const id = value.trim();
  return (
    <form
      className="planner-open"
      onSubmit={(e) => {
        e.preventDefault();
        if (ID_PATTERN.test(id)) {
          navigate(`${VIEW_ROUTES.planner}?study=${encodeURIComponent(id)}`);
        }
      }}
    >
      <label className="uf-label" htmlFor={inputId}>
        Re-open a study by id
      </label>
      <div className="planner-open__row">
        <input
          id={inputId}
          className="uf-input"
          type="text"
          placeholder="Study id"
          spellCheck={false}
          autoComplete="off"
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
          }}
        />
        <button
          type="submit"
          className="pb-btn pb-secondary"
          disabled={!ID_PATTERN.test(id)}
        >
          <FolderOpen size={15} aria-hidden="true" />
          Open
        </button>
      </div>
    </form>
  );
}

export function PlannerPage() {
  const search = useSearch();
  const raw = new URLSearchParams(search).get("study");
  const studyId = raw && ID_PATTERN.test(raw) ? raw : null;
  const [setupCheck, setSetupCheck] = useState<Check>(CHECKING);
  const [study, setStudy] = useState<{
    record?: StudyRecord;
    error?: string;
  }>({});
  const onStudyState = useCallback(
    (record: StudyRecord | undefined, error?: string) => {
      setStudy({ record, error });
    },
    [],
  );

  const stages = studyId
    ? studyStages(study.record, study.error)
    : setupStages(setupCheck);

  return (
    <div className="guided-page planner">
      <header className="guided-intro planner-intro">
        <div className="planner-intro__text">
          <p className="guided-eyebrow">Plan</p>
          <h1 id="planner-title">Plan a junction study</h1>
          <p>
            Compare control alternatives for one junction on the same simulated
            traffic and read the evidence. The planner reports differences and
            their uncertainty; it does not rank alternatives or recommend one.
          </p>
        </div>
        {!studyId && <OpenStudy />}
      </header>
      <PlannerFlow stages={stages} />
      {studyId ? (
        <StudyView key={studyId} studyId={studyId} onState={onStudyState} />
      ) : (
        <StudySetup onCheck={setSetupCheck} />
      )}
    </div>
  );
}

export default PlannerPage;
