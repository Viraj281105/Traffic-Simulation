/**
 * V2.0 planner: build a scenario, choose the alternatives to compare, see
 * how many simulations that is, run the study as a background job and read
 * the evidence (PlannerResults). The study id is kept in the URL
 * (``/app/planner?study=<id>``), so a reload or a shared link re-opens the
 * finished study from the server.
 *
 * Everything is checked and computed by /api/v2/planning; this page only
 * collects the request and shows what the server returns.
 */
import { useEffect, useId, useState } from "react";
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
import { PlannerResults } from "./PlannerResults";
import { buildStudyRequest, type AlternativeRow } from "./plannerRequest";
import { failureText, plainValidationError } from "./plannerText";
import "./Planner.css";

const POLL_MS = 1000;
const SCALE_CHOICES = [0.5, 0.75, 1, 1.25, 1.5, 2];
const ID_PATTERN = /^[A-Za-z0-9_-]{1,128}$/;

function asError(err: unknown): PlanningApiError {
  return err instanceof PlanningApiError
    ? err
    : new PlanningApiError(0, [String(err)]);
}

type Check =
  | { status: "checking" }
  | { status: "done"; result: ValidateResponse }
  | { status: "failed"; message: string };

/** The server's verdict on the study, a moment after the user stops editing. */
function useStudyValidation(
  request: PlanningStudyRequest,
  delayMs = 400,
): Check {
  const key = JSON.stringify(request);
  const [state, setState] = useState<{ key: string; value: Check }>({
    key: "",
    value: { status: "checking" },
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
  return state.key === key ? state.value : { status: "checking" };
}

// ── Setup ──────────────────────────────────────────────────────────────────

let nextKey = 1;
const row = (strategy: Strategy): AlternativeRow => ({
  key: nextKey++,
  strategy,
  label: "",
});

function StudySetup() {
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

  return (
    <div className="planner-setup">
      <section className="planner-block" aria-labelledby={`${formId}-scenario`}>
        <h2 id={`${formId}-scenario`}>1. Scenario</h2>
        <p>
          Start from a preset or build the junction yourself. Every alternative
          below runs on this junction with the same seeds.
        </p>
        <ScenarioBuilder
          value={scenario}
          onChange={setScenario}
          strategies={strategies}
          validation={scenarioCheck}
          junctionNote="In a planning study each alternative chooses its own control; the type here only sets the default view."
        />
      </section>

      <section className="planner-block" aria-labelledby={`${formId}-alts`}>
        <h2 id={`${formId}-alts`}>2. Alternatives and repetitions</h2>
        <label className="planner-field">
          Study name
          <input
            type="text"
            value={name}
            maxLength={120}
            onChange={(e) => {
              setName(e.target.value);
            }}
          />
        </label>

        <table className="planner-table">
          <caption>
            Alternatives to compare. The first is the baseline every other
            alternative is compared with.
          </caption>
          <thead>
            <tr>
              <th scope="col">Role</th>
              <th scope="col">Control</th>
              <th scope="col">Label (optional)</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {alternatives.map((alt, i) => (
              <tr key={alt.key}>
                <th scope="row">
                  {i === 0 ? "Baseline" : `Alternative ${i.toString()}`}
                </th>
                <td>
                  <select
                    aria-label={`Control for ${i === 0 ? "the baseline" : `alternative ${i.toString()}`}`}
                    value={alt.strategy}
                    onChange={(e) => {
                      update(alt.key, { strategy: e.target.value as Strategy });
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
                    type="text"
                    aria-label={`Label for ${i === 0 ? "the baseline" : `alternative ${i.toString()}`}`}
                    value={alt.label}
                    maxLength={120}
                    onChange={(e) => {
                      update(alt.key, { label: e.target.value });
                    }}
                  />
                </td>
                <td className="planner-row-actions">
                  {i > 0 && (
                    <button
                      type="button"
                      onClick={() => {
                        setAlternatives((rows) => [
                          alt,
                          ...rows.filter((r) => r.key !== alt.key),
                        ]);
                      }}
                    >
                      Make baseline
                    </button>
                  )}
                  <button
                    type="button"
                    disabled={alternatives.length <= 2}
                    onClick={() => {
                      setAlternatives((rows) =>
                        rows.filter((r) => r.key !== alt.key),
                      );
                    }}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <button
          type="button"
          disabled={alternatives.length >= PLANNING_LIMITS.maxAlternatives}
          onClick={() => {
            setAlternatives((rows) => [...rows, row("fixed_time")]);
          }}
        >
          Add alternative
        </button>

        <div className="planner-inline">
          <label className="planner-field">
            Seeds (repetitions per alternative, 1–
            {PLANNING_LIMITS.maxSeeds.toString()})
            <input
              type="number"
              min={1}
              max={PLANNING_LIMITS.maxSeeds}
              value={seeds}
              onChange={(e) => {
                setSeeds(Math.round(Number(e.target.value)) || 1);
              }}
            />
          </label>
          <fieldset className="planner-field">
            <legend>
              Demand levels (×current demand, up to{" "}
              {PLANNING_LIMITS.maxScales.toString()})
            </legend>
            {SCALE_CHOICES.map((s) => {
              const on = scales.includes(s);
              return (
                <label key={s} className="planner-check">
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
          </fieldset>
        </div>
      </section>

      <section className="planner-block" aria-labelledby={`${formId}-cost`}>
        <h2 id={`${formId}-cost`}>3. Check and run</h2>
        <div aria-live="polite">
          {check.status === "checking" && <p>Checking the study…</p>}
          {check.status === "failed" && (
            <p role="alert" className="planner-error">
              {check.message}
            </p>
          )}
          {check.status === "done" && check.result.valid && (
            <>
              <p>
                This study runs{" "}
                <strong>
                  {String(check.result.simulations ?? "an unknown number of")}{" "}
                  simulations
                </strong>{" "}
                (alternatives × demand levels × seeds; the server allows at most{" "}
                {PLANNING_LIMITS.maxTotalRuns.toString()}).
              </p>
              <p className="planner-muted">
                Run time: no measured estimate is available for this server.
                Time grows with the number of simulations, the scenario duration
                and how busy the junction is.
              </p>
              {check.result.warnings.length > 0 && (
                <ul>
                  {check.result.warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              )}
            </>
          )}
          {check.status === "done" && !check.result.valid && (
            <div role="alert" className="planner-error">
              <p>The study cannot run yet:</p>
              <ul>
                {check.result.errors.map((e) => (
                  <li key={e}>{plainValidationError(e)}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <button
          type="button"
          className="planner-primary"
          disabled={!ready}
          onClick={start}
        >
          {starting ? "Starting…" : "Run study"}
        </button>
        {startError && (
          <p role="alert" className="planner-error">
            {startError}
          </p>
        )}
      </section>
    </div>
  );
}

// ── A submitted study ────────────────────────────────────────────────────

function StudyView({ studyId }: { studyId: string }) {
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

  return (
    <div className="planner-study">
      <p>
        <a
          href={VIEW_ROUTES.planner}
          onClick={(e) => {
            e.preventDefault();
            navigate(VIEW_ROUTES.planner);
          }}
        >
          Plan a new study
        </a>
      </p>
      <div aria-live="polite" role="status">
        {!record && !current.error && <p>Loading study {studyId}…</p>}
        {record &&
          (record.status === "queued" || record.status === "running") && (
            <div className="planner-progress">
              <p>
                {record.name}:{" "}
                {record.status === "queued" ? "queued" : "running"}
                {record.progress
                  ? ` — ${record.progress.completed.toString()} of ${record.progress.total.toString()} simulations finished`
                  : ""}
              </p>
              <progress
                max={1}
                value={record.progress?.fraction ?? undefined}
                aria-label="Study progress"
              />
              <p className="planner-muted">
                You can leave this page; the study keeps running and this link
                re-opens it.
              </p>
            </div>
          )}
      </div>
      {current.error && (
        <p role="alert" className="planner-error">
          {current.error}
        </p>
      )}
      {record?.status === "failed" && (
        <p role="alert" className="planner-error">
          The study failed on the server: {record.error ?? "no reason given"}
        </p>
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
      <label htmlFor={inputId}>Re-open a study by id</label>
      <input
        id={inputId}
        type="text"
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
        }}
      />
      <button type="submit" disabled={!ID_PATTERN.test(id)}>
        Open
      </button>
    </form>
  );
}

export function PlannerPage() {
  const search = useSearch();
  const raw = new URLSearchParams(search).get("study");
  const studyId = raw && ID_PATTERN.test(raw) ? raw : null;
  return (
    <div className="planner">
      <header className="planner-header">
        <h1 id="planner-title">Plan a junction study</h1>
        <p>
          Compare control alternatives for one junction on the same simulated
          traffic and read the evidence. The planner reports differences and
          their uncertainty; it does not rank alternatives or recommend one.
        </p>
        {!studyId && <OpenStudy />}
      </header>
      {studyId ? <StudyView studyId={studyId} /> : <StudySetup />}
    </div>
  );
}

export default PlannerPage;
