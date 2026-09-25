import React, { useEffect, useId, useState } from "react";
import "./HistoryDashboard.css";
import "./RunPages.css";
import { Loader } from "./ui/Loader";
import {
  ApiError,
  getReplay,
  getRunRecord,
  reproduceRun,
  runExportUrl,
  updateRunMetadata,
  type ReproductionResult,
  type RunRecord,
} from "../services/api";
import type { SavedReplay } from "./HistoryDashboard";
import { ComparisonSections, MetricSections } from "./MetricSections";
import { comparisonCsv, downloadText, singleRunCsv } from "../metrics/catalog";
import {
  capturedInWarmup,
  commitLabel,
  configLabel,
  formatSeconds,
  intersectionLabel,
  metricColumns,
  provenanceStatus,
  runDisplayName,
} from "../runs/savedRun";
import { VIEW_ROUTES, comparePath, followLink } from "../routing";
import { parseStoredTimestamp } from "../utils/time";

type LoadState =
  | { kind: "loading" }
  | { kind: "notFound" }
  | { kind: "error"; message: string }
  | { kind: "ready"; record: RunRecord };

function Timestamp({ value }: { value: string | null }) {
  if (!value) return <>—</>;
  const date = parseStoredTimestamp(value);
  if (Number.isNaN(date.getTime())) return <>{value}</>;
  return <time dateTime={date.toISOString()}>{date.toLocaleString()}</time>;
}

function BackToHistory() {
  return (
    <a
      className="run-back-link"
      href={VIEW_ROUTES.history}
      onClick={(event) => {
        followLink(event, VIEW_ROUTES.history);
      }}
    >
      ← Saved runs
    </a>
  );
}

/** First-class page for one stored run: /app/runs/:runId. */
export function RunPage({
  runId,
  onOpenInSimulator,
}: {
  runId: string;
  onOpenInSimulator: (replay: SavedReplay) => void;
}) {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getRunRecord(runId)
      .then((record) => {
        if (!cancelled) setState({ kind: "ready", record });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (
          err instanceof ApiError &&
          (err.status === 404 || err.status === 400)
        ) {
          setState({ kind: "notFound" });
        } else {
          console.error("Failed to load run:", err);
          setState({
            kind: "error",
            message:
              "This run could not be loaded. Check that the backend is running.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [runId, attempt]);

  if (state.kind === "loading") {
    return (
      <div className="uf-page uf-page--wide history-dashboard run-page">
        <BackToHistory />
        <Loader label="Loading run" />
      </div>
    );
  }
  if (state.kind === "notFound") {
    return (
      <div className="uf-page uf-page--wide history-dashboard run-page">
        <BackToHistory />
        <header className="history-header">
          <h1>Run not found</h1>
          <p>
            No saved run has the ID <code>{runId}</code>. It may have been
            deleted, or the link may be incomplete.
          </p>
        </header>
      </div>
    );
  }
  if (state.kind === "error") {
    return (
      <div className="uf-page uf-page--wide history-dashboard run-page">
        <BackToHistory />
        <div className="history-status error" role="alert">
          <p>{state.message}</p>
          <button
            type="button"
            className="pb-btn pb-secondary"
            onClick={() => {
              setState({ kind: "loading" });
              setAttempt((n) => n + 1);
            }}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }
  return (
    <RunDetails
      record={state.record}
      onRecordChange={(record) => {
        setState({ kind: "ready", record });
      }}
      onOpenInSimulator={onOpenInSimulator}
    />
  );
}

function RunDetails({
  record,
  onRecordChange,
  onOpenInSimulator,
}: {
  record: RunRecord;
  onRecordChange: (record: RunRecord) => void;
  onOpenInSimulator: (replay: SavedReplay) => void;
}) {
  const [openError, setOpenError] = useState<string | null>(null);
  const status = provenanceStatus(record);
  const commit = commitLabel(record.gitCommitHash);
  const config = configLabel(record);
  const columns = metricColumns(record);
  const warmup = capturedInWarmup(record.timing, record.config);
  const hasMetrics = columns.some((c) => c.ctx.metrics);
  const name = runDisplayName(record);

  const openInSimulator = () => {
    setOpenError(null);
    getReplay<SavedReplay>(record.runId)
      .then(onOpenInSimulator)
      .catch((err: unknown) => {
        console.error("Failed to load saved settings:", err);
        setOpenError("The saved settings could not be loaded. Try again.");
      });
  };

  const exportMetricsCsv = () => {
    const header = [
      `Run ${record.runId} — ${name}`,
      `Saved: ${record.createdAt ?? "not recorded"}`,
      `Seed: ${record.seed === null ? "not recorded" : String(record.seed)}`,
      `Git commit: ${record.gitCommitHash ?? "not recorded"}`,
      `Simulated time when saved: ${formatSeconds(record.timing.elapsed)}`,
    ];
    const csv =
      columns.length === 2
        ? comparisonCsv(columns[0].ctx, columns[1].ctx, header)
        : singleRunCsv(columns[0].ctx, header);
    downloadText(
      `run_${record.runId}_metrics.csv`,
      csv,
      "text/csv;charset=utf-8",
    );
  };

  return (
    <div className="uf-page uf-page--wide history-dashboard run-page">
      <BackToHistory />
      <header className="history-header run-header">
        <NameEditor record={record} onSaved={onRecordChange} />
        <p className="run-subtitle">
          <span className="mono" title={record.runId}>
            {record.runId}
          </span>
          {" · "}
          {intersectionLabel(record.intersectionType)}
        </p>
      </header>

      <section className="run-card" aria-labelledby="run-actions-title">
        <h2 id="run-actions-title" className="run-card-title">
          Re-run and export
        </h2>
        <div className="run-actions">
          <button
            type="button"
            className="pb-btn pb-primary"
            onClick={openInSimulator}
            disabled={!record.savedReplay}
          >
            Open in simulator
          </button>
          <a
            className="pb-btn pb-secondary"
            href={comparePath([record.runId])}
            onClick={(event) => {
              followLink(event, comparePath([record.runId]));
            }}
          >
            Compare with other runs
          </a>
          <a
            className="pb-btn pb-secondary"
            href={runExportUrl(record.runId, "json")}
            download={`run_${record.runId}.json`}
          >
            Export JSON
          </a>
          <a
            className="pb-btn pb-secondary"
            href={runExportUrl(record.runId, "csv")}
            download={`run_${record.runId}.csv`}
          >
            Export CSV
          </a>
          <button
            type="button"
            className="pb-btn pb-secondary"
            onClick={exportMetricsCsv}
            disabled={!hasMetrics}
            title="Every catalog metric with its label and unit"
          >
            Metrics table (CSV)
          </button>
        </div>
        <p className="run-hint">
          {record.savedReplay
            ? "Open in simulator restores this run's settings and seed; press Play to run it again and Save to History to keep the new run separately. This run is never changed."
            : "This run was not saved from the dashboard, so its settings cannot be loaded into the dashboard controls. Headless reproduction below re-runs its stored configuration."}
        </p>
        {openError && (
          <p className="history-status error" role="alert">
            {openError}
          </p>
        )}
        <p className="run-hint">
          Export JSON / CSV contain the full record: identity, seed, provenance,
          timing, stored configuration and stored metrics (raw backend keys).
          The metrics table adds catalog labels and units.
        </p>
      </section>

      <section className="run-card" aria-labelledby="run-repro-title">
        <h2 id="run-repro-title" className="run-card-title">
          Reproducibility
        </h2>
        <p className={`run-status${record.exactConfig ? " is-exact" : ""}`}>
          <strong>{status.label}.</strong> {status.detail}
        </p>
        <dl className="run-facts">
          <Fact label="Run ID">
            <span className="mono">{record.runId}</span>
          </Fact>
          <Fact label="Saved">
            <Timestamp value={record.createdAt} />
          </Fact>
          <Fact label="Intersection">
            {intersectionLabel(record.intersectionType)}
          </Fact>
          <Fact label="Seed">
            <span className="mono">
              {record.seed === null ? "—" : String(record.seed)}
            </span>
          </Fact>
          <Fact label="Git commit">
            <span className="mono" title={commit.title}>
              {record.gitCommitHash && record.gitCommitHash !== "unknown"
                ? record.gitCommitHash
                : commit.text}
            </span>
          </Fact>
          <Fact label="Python">{record.pythonVersion ?? "—"}</Fact>
          <Fact label="Configuration">
            <span title={config.title}>{config.text}</span>
          </Fact>
          <Fact label="Run type">
            {record.runMode === "dual"
              ? "Signal and roundabout in lockstep, same seed"
              : record.runMode === "single"
                ? "Single intersection"
                : "—"}
          </Fact>
          <Fact label="Time step">{formatSeconds(record.timing.timeStep)}</Fact>
          <Fact label="Duration">{formatSeconds(record.timing.duration)}</Fact>
          <Fact label="Warm-up">{formatSeconds(record.timing.warmupTime)}</Fact>
          <Fact label="Simulated time when saved">
            {formatSeconds(record.timing.elapsed)}
          </Fact>
        </dl>
        <Reproduction record={record} />
      </section>

      <MetadataEditor record={record} onSaved={onRecordChange} />

      <section className="run-card" aria-labelledby="run-metrics-title">
        <h2 id="run-metrics-title" className="run-card-title">
          Stored metrics
        </h2>
        {warmup === true && (
          <p className="warmup-notice">
            Saved during the warm-up period: metrics that accumulate after
            warm-up had no values yet and are shown as —.
          </p>
        )}
        {warmup === null && hasMetrics && (
          <p className="run-hint">
            This run did not record its timing, so it cannot be told whether its
            values were captured before warm-up ended.
          </p>
        )}
        {!hasMetrics ? (
          <p className="history-status empty">
            No metrics were stored with this run.
          </p>
        ) : columns.length === 2 ? (
          <ComparisonSections
            signal={columns[0].ctx}
            roundabout={columns[1].ctx}
            collapsed={[]}
          />
        ) : (
          <MetricSections ctx={columns[0].ctx} collapsed={[]} />
        )}
      </section>

      <section className="run-card" aria-labelledby="run-config-title">
        <h2 id="run-config-title" className="run-card-title">
          Stored configuration
        </h2>
        {record.config ? (
          <>
            <p className="run-hint">
              {record.exactConfig
                ? "The configuration the engine ran with, with the recorded seed pinned."
                : "As stored with the run. It is the dashboard's summary, not the engine's exact configuration."}
            </p>
            <pre className="run-config" tabIndex={0}>
              {JSON.stringify(record.config, null, 2)}
            </pre>
          </>
        ) : (
          <p className="history-status empty">
            No configuration was recorded for this run.
          </p>
        )}
      </section>
    </div>
  );
}

function Fact({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="run-fact">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function NameEditor({
  record,
  onSaved,
}: {
  record: RunRecord;
  onSaved: (record: RunRecord) => void;
}) {
  const inputId = useId();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  if (!editing) {
    return (
      <div className="run-title-row">
        <h1>{runDisplayName(record)}</h1>
        <button
          type="button"
          className="pb-btn pb-secondary"
          onClick={() => {
            setDraft(record.name ?? "");
            setError(null);
            setEditing(true);
          }}
        >
          Rename
        </button>
      </div>
    );
  }
  const save = (event: React.SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    const name = draft.trim();
    if (!name) {
      setError("Enter a name.");
      return;
    }
    setSaving(true);
    updateRunMetadata(record.runId, { name })
      .then((updated) => {
        onSaved(updated);
        setEditing(false);
      })
      .catch((err: unknown) => {
        console.error("Failed to rename run:", err);
        setError("The name could not be saved. Try again.");
      })
      .finally(() => {
        setSaving(false);
      });
  };
  return (
    <form className="run-title-row" onSubmit={save}>
      <label htmlFor={inputId} className="sr-only">
        Run name
      </label>
      <input
        id={inputId}
        className="run-input"
        value={draft}
        maxLength={120}
        onChange={(e) => {
          setDraft(e.target.value);
        }}
        autoFocus
      />
      <button type="submit" className="pb-btn pb-primary" disabled={saving}>
        Save
      </button>
      <button
        type="button"
        className="pb-btn pb-secondary"
        onClick={() => {
          setEditing(false);
        }}
      >
        Cancel
      </button>
      {error && (
        <p className="run-field-error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}

/** Tags are typed comma-separated; the backend trims and de-duplicates. */
function parseTags(text: string): string[] {
  return text
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
}

function MetadataEditor({
  record,
  onSaved,
}: {
  record: RunRecord;
  onSaved: (record: RunRecord) => void;
}) {
  const notesId = useId();
  const tagsId = useId();
  const [notes, setNotes] = useState(record.notes ?? "");
  const [tags, setTags] = useState(record.tags.join(", "));
  const [message, setMessage] = useState<{
    kind: "ok" | "error";
    text: string;
  } | null>(null);
  const [saving, setSaving] = useState(false);

  const save = (event: React.SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    const tagList = parseTags(tags);
    if (tagList.length > 20 || tagList.some((t) => t.length > 32)) {
      setMessage({
        kind: "error",
        text: "Use at most 20 tags of up to 32 characters each.",
      });
      return;
    }
    setSaving(true);
    setMessage(null);
    updateRunMetadata(record.runId, {
      notes: notes.trim() || null,
      tags: tagList,
    })
      .then((updated) => {
        onSaved(updated);
        setNotes(updated.notes ?? "");
        setTags(updated.tags.join(", "));
        setMessage({ kind: "ok", text: "Notes and tags saved." });
      })
      .catch((err: unknown) => {
        console.error("Failed to save notes/tags:", err);
        setMessage({
          kind: "error",
          text: "Notes and tags could not be saved. Try again.",
        });
      })
      .finally(() => {
        setSaving(false);
      });
  };

  return (
    <section className="run-card" aria-labelledby="run-notes-title">
      <h2 id="run-notes-title" className="run-card-title">
        Notes and tags
      </h2>
      <form className="run-metadata" onSubmit={save}>
        <label htmlFor={tagsId}>Tags (comma-separated)</label>
        <input
          id={tagsId}
          className="run-input"
          value={tags}
          onChange={(e) => {
            setTags(e.target.value);
          }}
          placeholder="e.g. baseline, peak hour"
        />
        <label htmlFor={notesId}>Notes</label>
        <textarea
          id={notesId}
          className="run-input run-notes"
          value={notes}
          maxLength={4000}
          rows={4}
          onChange={(e) => {
            setNotes(e.target.value);
          }}
        />
        <div className="run-actions">
          <button type="submit" className="pb-btn pb-primary" disabled={saving}>
            Save notes and tags
          </button>
          {message && (
            <span
              className={
                message.kind === "error" ? "run-field-error" : "run-hint"
              }
              role={message.kind === "error" ? "alert" : "status"}
            >
              {message.text}
            </span>
          )}
        </div>
      </form>
    </section>
  );
}

function Reproduction({ record }: { record: RunRecord }) {
  const [state, setState] = useState<
    | { kind: "idle" }
    | { kind: "running" }
    | { kind: "done"; result: ReproductionResult }
    | { kind: "error"; message: string }
  >({ kind: "idle" });

  if (!record.configAvailable) {
    return (
      <p className="run-hint">
        Headless reproduction needs a stored configuration, which this run does
        not have.
      </p>
    );
  }

  const run = () => {
    setState({ kind: "running" });
    reproduceRun(record.runId)
      .then((result) => {
        setState({ kind: "done", result });
      })
      .catch((err: unknown) => {
        console.error("Reproduction failed:", err);
        setState({
          kind: "error",
          message: "The reproduction could not be run. Try again.",
        });
      });
  };

  return (
    <div className="run-repro">
      <div className="run-actions">
        <button
          type="button"
          className="pb-btn pb-secondary"
          onClick={run}
          disabled={state.kind === "running"}
        >
          {state.kind === "running"
            ? "Re-running…"
            : "Verify reproduction (headless)"}
        </button>
        <span className="run-hint">
          Re-runs the stored configuration and seed on the server up to the
          saved simulated time and compares average delay and vehicles served.
          The stored run is not changed.
        </span>
      </div>
      {state.kind === "error" && (
        <p className="history-status error" role="alert">
          {state.message}
        </p>
      )}
      {state.kind === "done" && (
        <ReproductionResultView result={state.result} />
      )}
    </div>
  );
}

function ReproductionResultView({ result }: { result: ReproductionResult }) {
  const verdict =
    result.isDeterministic === null
      ? "Not assessed — nothing stored to compare against."
      : result.isDeterministic
        ? `Matched within tolerance (delay ±${result.tolerances.averageDelaySeconds.toString()} s, vehicles served ±${result.tolerances.throughputVehicles.toString()}).`
        : "Did not match within tolerance.";
  return (
    <div className="run-repro-result" role="status">
      <p>
        <strong>{verdict}</strong> Re-run to{" "}
        {formatSeconds(result.reproducedElapsed)} of simulated time with seed{" "}
        <span className="mono">{result.seed}</span> on commit{" "}
        <span className="mono" title={result.provenance.gitCommitHash}>
          {commitLabel(result.provenance.gitCommitHash).text}
        </span>
        .
      </p>
      {result.comparedMetrics.length > 0 && (
        <p className="run-hint">
          Compared: {result.comparedMetrics.join(", ")}.
        </p>
      )}
      {result.discrepancies.length > 0 && (
        <ul className="run-list">
          {result.discrepancies.map((d) => (
            <li key={d}>{d}</li>
          ))}
        </ul>
      )}
      {result.limitations.length > 0 && (
        <>
          <p className="run-hint">Limitations:</p>
          <ul className="run-list">
            {result.limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
