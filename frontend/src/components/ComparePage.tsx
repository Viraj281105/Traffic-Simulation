import { useEffect, useId, useState } from "react";
import "./HistoryDashboard.css";
import "./RunPages.css";
import {
  ApiError,
  getRunRecord,
  listReplays,
  type RunRecord,
} from "../services/api";
import type { SavedReplay } from "./HistoryDashboard";
import { MultiRunSections } from "./MetricSections";
import { Tags } from "./RunTags";
import { downloadText, multiRunCsv } from "../metrics/catalog";
import {
  capturedInWarmup,
  commitLabel,
  configDifferences,
  configLabel,
  formatSeconds,
  intersectionLabel,
  metricColumns,
  runDisplayName,
  shortRunId,
  type RunColumn,
} from "../runs/savedRun";
import {
  MAX_COMPARE_RUNS,
  VIEW_ROUTES,
  comparePath,
  followLink,
  navigate,
  parseCompareRuns,
  runPath,
  useSearch,
} from "../routing";
import { LoaderMark } from "./ui/Loader";

type Loaded =
  | { kind: "ready"; record: RunRecord }
  | { kind: "notFound"; runId: string }
  | { kind: "error"; runId: string };

/** Comparison of stored runs: /app/compare?runs=<id>,<id>,… */
export function ComparePage() {
  const runIds = parseCompareRuns(useSearch());
  const key = runIds.join(",");
  const [loaded, setLoaded] = useState<{ key: string; runs: Loaded[] } | null>(
    null,
  );

  useEffect(() => {
    let cancelled = false;
    const ids = key ? key.split(",") : [];
    Promise.all(
      ids.map((runId) =>
        getRunRecord(runId).then(
          (record): Loaded => ({ kind: "ready", record }),
          (err: unknown): Loaded =>
            err instanceof ApiError && err.status === 404
              ? { kind: "notFound", runId }
              : { kind: "error", runId },
        ),
      ),
    )
      .then((runs) => {
        if (!cancelled) setLoaded({ key, runs });
      })
      .catch((err: unknown) => {
        console.error("Failed to load runs:", err);
      });
    return () => {
      cancelled = true;
    };
  }, [key]);

  const setRuns = (ids: string[]) => {
    navigate(comparePath(ids));
  };

  const current = loaded?.key === key ? loaded.runs : null;
  const records = (current ?? []).flatMap((r) =>
    r.kind === "ready" ? [r.record] : [],
  );
  const missing = (current ?? []).flatMap((r) =>
    r.kind === "ready" ? [] : [r],
  );

  return (
    <div className="history-dashboard run-page">
      <a
        className="run-back-link"
        href={VIEW_ROUTES.history}
        onClick={(event) => {
          followLink(event, VIEW_ROUTES.history);
        }}
      >
        ← Saved runs
      </a>
      <header className="history-header">
        <h1>Compare saved runs</h1>
        <p>
          Stored metrics of up to {MAX_COMPARE_RUNS} runs side by side, with
          each run&apos;s seed, code version and settings. Values a run did not
          record stay unavailable.
        </p>
      </header>

      <RunPicker runIds={runIds} onChange={setRuns} />

      {runIds.length > 0 && current === null ? (
        <p className="history-status is-loading" role="status">
          <LoaderMark />
          Loading runs…
        </p>
      ) : (
        <>
          {missing.length > 0 && (
            <div className="history-status error" role="alert">
              {missing.map((m) => (
                <p key={m.runId}>
                  {m.kind === "notFound"
                    ? `Run ${m.runId} was not found; it may have been deleted.`
                    : `Run ${m.runId} could not be loaded.`}{" "}
                  <button
                    type="button"
                    className="pb-btn pb-secondary"
                    onClick={() => {
                      setRuns(runIds.filter((id) => id !== m.runId));
                    }}
                  >
                    Remove
                  </button>
                </p>
              ))}
            </div>
          )}
          {records.length < 2 ? (
            <div className="history-status empty">
              <p>Choose at least two saved runs to compare.</p>
              <p className="hint">
                Add runs above, or tick runs in Saved runs and choose “Compare
                selected”.
              </p>
            </div>
          ) : (
            <Comparison
              records={records}
              onRemove={(runId) => {
                setRuns(runIds.filter((id) => id !== runId));
              }}
            />
          )}
        </>
      )}
    </div>
  );
}

function RunPicker({
  runIds,
  onChange,
}: {
  runIds: string[];
  onChange: (ids: string[]) => void;
}) {
  const selectId = useId();
  const [replays, setReplays] = useState<SavedReplay[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listReplays<SavedReplay[]>()
      .then((data) => {
        if (!cancelled) setReplays(data);
      })
      .catch((err: unknown) => {
        console.error("Failed to load saved runs:", err);
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const available = (replays ?? []).filter((r) => !runIds.includes(r.id));
  const full = runIds.length >= MAX_COMPARE_RUNS;
  return (
    <div className="run-picker">
      <label htmlFor={selectId}>Add a saved run</label>
      <select
        id={selectId}
        value=""
        disabled={full || replays === null || available.length === 0}
        onChange={(e) => {
          if (e.target.value) onChange([...runIds, e.target.value]);
        }}
      >
        <option value="">
          {failed
            ? "Saved runs could not be loaded"
            : replays === null
              ? "Loading…"
              : full
                ? `At most ${MAX_COMPARE_RUNS.toString()} runs`
                : available.length === 0
                  ? "No other saved runs"
                  : "Choose a run…"}
        </option>
        {available.map((r) => (
          <option key={r.id} value={r.id}>
            {r.name} ({shortRunId(r.id)})
          </option>
        ))}
      </select>
    </div>
  );
}

function valueOrDash(v: string | number | null | undefined): string {
  return v === null || v === undefined ? "—" : String(v);
}

function Comparison({
  records,
  onRemove,
}: {
  records: RunRecord[];
  onRemove: (runId: string) => void;
}) {
  const baselineId = useId();
  const columns: (RunColumn & { name: string })[] = records.flatMap((r) =>
    metricColumns(r).map((c) => ({ ...c, name: runDisplayName(r) })),
  );
  const [baselineKey, setBaselineKey] = useState(columns[0].key);
  const baselineIndex = Math.max(
    0,
    columns.findIndex((c) => c.key === baselineKey),
  );
  const columnLabel = (c: (typeof columns)[number]) =>
    c.side ? `${c.name} · ${c.label}` : c.name;

  const facts = describeDifferences(records);
  const configDiffs = configDifferences(records.map((r) => r.config));

  const exportCsv = () => {
    const header = [
      "Comparison of stored runs",
      ...records.map(
        (r) =>
          `${r.runId} — ${runDisplayName(r)}; seed ${valueOrDash(r.seed)}; commit ${valueOrDash(r.gitCommitHash)}; simulated time ${formatSeconds(r.timing.elapsed)}`,
      ),
      `Differences are column minus "${columnLabel(columns[baselineIndex])}", in each metric's unit (percentage points for %).`,
    ];
    downloadText(
      `comparison_${records.map((r) => shortRunId(r.runId)).join("_")}.csv`,
      multiRunCsv(
        columns.map((c) => ({ label: columnLabel(c), ctx: c.ctx })),
        header,
        baselineIndex,
      ),
      "text/csv;charset=utf-8",
    );
  };

  return (
    <>
      <section className="run-card" aria-labelledby="compare-runs-title">
        <h2 id="compare-runs-title" className="run-card-title">
          Runs
        </h2>
        <div className="history-table-wrap">
          <table className="history-table compare-runs-table">
            <thead>
              <tr>
                <th scope="col">Run</th>
                <th scope="col">Run ID</th>
                <th scope="col">Type</th>
                <th scope="col">Seed</th>
                <th scope="col">Commit</th>
                <th scope="col">Config</th>
                <th scope="col">Sim time</th>
                <th scope="col">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {records.map((r) => {
                const commit = commitLabel(r.gitCommitHash);
                const config = configLabel(r);
                return (
                  <tr key={r.runId}>
                    <th scope="row" className="run-name">
                      <a
                        href={runPath(r.runId)}
                        onClick={(event) => {
                          followLink(event, runPath(r.runId));
                        }}
                      >
                        {runDisplayName(r)}
                      </a>
                      <Tags tags={r.tags} />
                    </th>
                    <td className="mono" title={r.runId}>
                      {shortRunId(r.runId)}
                    </td>
                    <td>{intersectionLabel(r.intersectionType)}</td>
                    <td className="mono">{valueOrDash(r.seed)}</td>
                    <td className="mono" title={commit.title}>
                      {commit.text}
                    </td>
                    <td title={config.title}>{config.text}</td>
                    <td className="mono">{formatSeconds(r.timing.elapsed)}</td>
                    <td>
                      <button
                        type="button"
                        className="pb-btn pb-secondary"
                        onClick={() => {
                          onRemove(r.runId);
                        }}
                        aria-label={`Remove ${runDisplayName(r)} from the comparison`}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {facts.length > 0 && (
          <ul className="run-list compare-facts">
            {facts.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        )}
      </section>

      <section className="run-card" aria-labelledby="compare-config-title">
        <h2 id="compare-config-title" className="run-card-title">
          Settings that differ
        </h2>
        {configDiffs.length === 0 ? (
          <p className="run-hint">
            The stored configurations are identical (apart from anything a run
            did not store).
          </p>
        ) : (
          <div className="history-table-wrap">
            <table className="history-table">
              <thead>
                <tr>
                  <th scope="col">Setting</th>
                  {records.map((r) => (
                    <th scope="col" key={r.runId}>
                      {runDisplayName(r)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {configDiffs.map((row) => (
                  <tr key={row.path}>
                    <th scope="row" className="mono">
                      {row.path}
                    </th>
                    {row.values.map((v, i) => (
                      <td className="mono" key={records[i].runId}>
                        {v ?? "—"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="run-card" aria-labelledby="compare-metrics-title">
        <div className="run-card-head">
          <h2 id="compare-metrics-title" className="run-card-title">
            Stored metrics
          </h2>
          <div className="run-actions">
            <label htmlFor={baselineId} className="run-hint">
              Differences relative to
            </label>
            <select
              id={baselineId}
              value={columns[baselineIndex].key}
              onChange={(e) => {
                setBaselineKey(e.target.value);
              }}
            >
              {columns.map((c) => (
                <option key={c.key} value={c.key}>
                  {columnLabel(c)}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="pb-btn pb-secondary"
              onClick={exportCsv}
            >
              Export comparison (CSV)
            </button>
          </div>
        </div>
        <p className="run-hint">
          Δ = column value − baseline value, in the metric&apos;s unit
          (percentage points for %). It is left as — when either value is
          unavailable. Differences are descriptive; they do not say which run is
          better.
        </p>
        <MultiRunSections
          columns={columns.map((c) => ({
            key: c.key,
            heading: (
              <>
                {c.name}
                {c.side && <span className="column-side">{c.label}</span>}
              </>
            ),
            ctx: c.ctx,
          }))}
          baselineIndex={baselineIndex}
          collapsed={[]}
        />
      </section>
    </>
  );
}

/** Factual notes on what differs between the runs beyond their settings. */
function describeDifferences(records: RunRecord[]): string[] {
  const facts: string[] = [];
  const distinct = (values: unknown[]) =>
    new Set(values.map((v) => JSON.stringify(v ?? null))).size > 1;
  if (distinct(records.map((r) => r.seed))) {
    facts.push(
      "The runs use different random seeds, so their vehicle arrivals differ.",
    );
  }
  const commits = records.map((r) => r.gitCommitHash);
  if (commits.some((c) => !c || c === "unknown")) {
    facts.push("At least one run has no known code version.");
  } else if (distinct(commits)) {
    facts.push("The runs were recorded on different code versions.");
  }
  if (distinct(records.map((r) => r.timing.elapsed))) {
    facts.push(
      "The runs were saved at different simulated times; accumulated counts (vehicles served, stops, events) are not normalised for that.",
    );
  }
  if (records.some((r) => !r.exactConfig)) {
    facts.push(
      "Some runs store only dashboard settings or predate provenance, so their stored settings are not the engine's exact configuration.",
    );
  }
  if (records.some((r) => capturedInWarmup(r.timing, r.config) === true)) {
    facts.push(
      "Some runs were saved during warm-up; their post-warm-up metrics are unavailable.",
    );
  }
  return facts;
}
