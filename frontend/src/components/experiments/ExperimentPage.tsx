import { useEffect, useState } from "react";
import "./Experiments.css";
import {
  ExperimentsApiError,
  getExperiment,
  getExperimentResult,
  isActive,
  type ExperimentResult,
  type ExperimentStatus,
} from "../../services/v3/experiments";
import { VIEW_ROUTES, followLink } from "../../routing";
import { parseStoredTimestamp } from "../../utils/time";
import { LoaderMark } from "../ui/Loader";
import { StatusState } from "../ui/StatusState";
import { ExperimentResultView } from "./ExperimentResultView";

/** How often a queued or running experiment is asked for its progress. */
export const POLL_MS = 2000;

type LoadState =
  | { kind: "loading" }
  | { kind: "notFound" }
  | { kind: "error"; message: string }
  | { kind: "active"; status: ExperimentStatus }
  | { kind: "failed"; status: ExperimentStatus }
  | { kind: "ready"; status: ExperimentStatus; result: ExperimentResult };

function BackToPlanner() {
  return (
    <a
      className="experiment-back-link"
      href={VIEW_ROUTES.planner}
      onClick={(event) => {
        followLink(event, VIEW_ROUTES.planner);
      }}
    >
      ← Planner
    </a>
  );
}

function Created({ value }: { value: string }) {
  const date = parseStoredTimestamp(value);
  if (Number.isNaN(date.getTime())) return <>{value}</>;
  return <time dateTime={date.toISOString()}>{date.toLocaleString()}</time>;
}

const STATE_WORD: Record<ExperimentStatus["status"], string> = {
  queued: "Waiting to start",
  running: "Running",
  completed: "Finished",
  failed: "Failed",
};

/** First-class page for one Robustness Lab experiment: /app/experiments/:id.
 *  Follows a queued or running experiment until it ends, then shows its
 *  result. Everything shown comes from the server. */
export function ExperimentPage({
  experimentId,
  pollMs = POLL_MS,
}: {
  experimentId: string;
  pollMs?: number;
}) {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const fail = (err: unknown) => {
      if (cancelled) return;
      if (
        err instanceof ExperimentsApiError &&
        (err.status === 404 || err.status === 400)
      ) {
        setState({ kind: "notFound" });
        return;
      }
      console.error("Failed to load experiment:", err);
      setState({
        kind: "error",
        message:
          err instanceof ExperimentsApiError && err.status !== 0
            ? err.message
            : "This experiment could not be loaded. Check that the backend is running.",
      });
    };

    const load = () => {
      getExperiment(experimentId)
        .then((status) => {
          if (cancelled) return;
          if (isActive(status.status)) {
            setState({ kind: "active", status });
            timer = setTimeout(load, pollMs);
            return;
          }
          if (status.status === "failed" || !status.resultAvailable) {
            setState({ kind: "failed", status });
            return;
          }
          return getExperimentResult(experimentId).then((result) => {
            if (!cancelled) setState({ kind: "ready", status, result });
          });
        })
        .catch(fail);
    };
    load();

    return () => {
      cancelled = true;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [experimentId, attempt, pollMs]);

  if (state.kind === "loading") {
    return (
      <div className="experiment-page">
        <BackToPlanner />
        <p className="experiment-status is-loading" role="status">
          <LoaderMark />
          Loading experiment…
        </p>
      </div>
    );
  }
  if (state.kind === "notFound") {
    return (
      <div className="experiment-page">
        <BackToPlanner />
        <header className="experiment-header">
          <h1>Experiment not found</h1>
          <p>
            No experiment of yours has the ID <code>{experimentId}</code>. It
            may have been deleted, it may belong to someone else, or the link
            may be incomplete.
          </p>
        </header>
      </div>
    );
  }
  if (state.kind === "error") {
    return (
      <div className="experiment-page">
        <BackToPlanner />
        <StatusState
          tone="error"
          role="alert"
          headingLevel={1}
          title="Could not load this experiment"
          actions={
            <button
              type="button"
              className="experiment-retry"
              onClick={() => {
                setState({ kind: "loading" });
                setAttempt((n) => n + 1);
              }}
            >
              Try again
            </button>
          }
        >
          {state.message}
        </StatusState>
      </div>
    );
  }

  const status = state.status;
  return (
    <div className="experiment-page">
      <BackToPlanner />
      <header className="experiment-header">
        <h1>{status.name}</h1>
        <p className="experiment-meta">
          <span className={`experiment-chip is-${status.status}`}>
            {STATE_WORD[status.status]}
          </span>{" "}
          Submitted <Created value={status.createdAt} />
          {status.specFingerprint ? (
            <>
              {" "}
              · specification <code>{status.specFingerprint}</code>
            </>
          ) : null}
        </p>
      </header>

      {state.kind === "active" ? (
        <section className="experiment-block" aria-labelledby="exp-progress">
          <h2 id="exp-progress">Progress</h2>
          <p role="status">
            {status.status === "queued"
              ? "Waiting for a free worker."
              : progressText(status)}
          </p>
          {status.counts ? (
            <p className="experiment-muted">
              {status.counts.conditions.toString()} conditions ×{" "}
              {status.counts.alternatives.toString()} alternatives ×{" "}
              {status.counts.replications.toString()} replications ={" "}
              {status.counts.totalRuns.toString()} runs. Results appear here
              when it finishes; you can leave this page open or come back later.
            </p>
          ) : null}
          {status.progress && status.progress.total > 0 ? (
            <progress
              value={status.progress.completed}
              max={status.progress.total}
              aria-label="Simulations finished"
            />
          ) : null}
        </section>
      ) : null}

      {state.kind === "failed" ? (
        <StatusState
          tone="error"
          role="alert"
          title="This experiment did not produce a result"
        >
          {status.error ??
            "It ended without a result and the server gave no reason."}
        </StatusState>
      ) : null}

      {state.kind === "ready" ? (
        <ExperimentResultView result={state.result} />
      ) : null}
    </div>
  );
}

function progressText(status: ExperimentStatus): string {
  const p = status.progress;
  if (!p) return "Running.";
  const phase = p.phase === "simulating" ? "Simulating" : "Preparing";
  if (p.total > 0) {
    return `${phase}: ${p.completed.toString()} of ${p.total.toString()} simulations finished (${Math.round(p.fraction * 100).toString()} %), ${Math.round(p.elapsedSeconds).toString()} s elapsed.`;
  }
  return `${phase}…`;
}
