import React, { useCallback, useEffect, useRef, useState } from "react";
import "./HistoryDashboard.css";
import { deleteReplay, listReplays } from "../services/api";
import type { RunReproducibility } from "../services/api";
import { commitLabel, configLabel } from "../runs/savedRun";
import {
  MAX_COMPARE_RUNS,
  VIEW_ROUTES,
  comparePath,
  followLink,
  navigate,
  runPath,
} from "../routing";
import { Tags } from "./RunTags";
import "./RunPages.css";

import type { RunningMetrics } from "../types/simulation";
import type { SimulationConfigValues } from "../types/config";
import { parseStoredTimestamp } from "../utils/time";
import { LoaderMark } from "./ui/Loader";
import { StatusState } from "./ui/StatusState";
import { strategyName } from "../strategies/strategyCatalog";

export interface SavedReplay {
  id: string;
  name: string;
  config: {
    /** Exact dashboard configuration (saves made since this was added). */
    ui?: SimulationConfigValues;
    simulation?: { duration?: number; randomSeed?: number; elapsed?: number };
    geometry?: { intersectionType?: string; laneWidth?: number };
    roads?: {
      lanesPerApproach?: {
        north?: number;
        south?: number;
        east?: number;
        west?: number;
      };
    };
    traffic?: { arrivalRate?: number };
  };
  metrics: {
    signal?: RunningMetrics;
    roundabout?: RunningMetrics;
  } & Partial<RunningMetrics>;
  created_at: string;
  /** Null for saves that have no run record (older saves). */
  reproducibility?: RunReproducibility | null;
}

interface HistoryDashboardProps {
  onReplay: (replay: SavedReplay) => void;
}

function num(v: number | undefined, decimals: number): string {
  return v === undefined || !Number.isFinite(v) ? "—" : v.toFixed(decimals);
}

/** The per-strategy metrics of a strategy comparison, in run order. */
function strategiesOf(
  r: SavedReplay,
): [string, Partial<RunningMetrics>][] | null {
  const byStrategy = (r.metrics as Record<string, unknown>).strategies;
  if (!byStrategy || typeof byStrategy !== "object") return null;
  return Object.entries(byStrategy as Record<string, Partial<RunningMetrics>>);
}

function kindOf(r: SavedReplay): "comparative" | "roundabout" | "signal" {
  if (
    strategiesOf(r) ||
    (r.metrics.signal !== undefined && r.metrics.roundabout !== undefined)
  ) {
    return "comparative";
  }
  return r.config.geometry?.intersectionType === "roundabout"
    ? "roundabout"
    : "signal";
}

/** The recorded seed, falling back to the one older saves kept in their
 *  config; "—" when neither recorded one. */
function seedOf(r: SavedReplay): string {
  const seed = r.reproducibility?.seed ?? r.config.simulation?.randomSeed;
  return seed === undefined ? "—" : String(seed);
}

const KIND_LABEL = {
  comparative: "Comparison",
  roundabout: "Roundabout",
  signal: "Signal",
} as const;

/** One value per strategy ("a / b / …", in run order) for a comparison,
 *  the single value otherwise. */
function pair(
  r: SavedReplay,
  pick: (m: Partial<RunningMetrics>) => number | undefined,
  decimals: number,
): string {
  const byStrategy = strategiesOf(r);
  if (byStrategy) {
    return byStrategy.map(([, m]) => num(pick(m), decimals)).join(" / ");
  }
  if (r.metrics.signal && r.metrics.roundabout) {
    return `${num(pick(r.metrics.signal), decimals)} / ${num(pick(r.metrics.roundabout), decimals)}`;
  }
  return num(pick(r.metrics), decimals);
}

export const HistoryDashboard: React.FC<HistoryDashboardProps> = ({
  onReplay,
}) => {
  const [replays, setReplays] = useState<SavedReplay[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  // Runs ticked for comparison, in the order they were ticked.
  const [selected, setSelected] = useState<string[]>([]);
  const cancelRef = useRef<HTMLButtonElement>(null);

  // State changes happen in the fetch callbacks, never synchronously in the
  // effect; `loading` starts true for the initial fetch.
  const fetchReplays = useCallback(() => {
    listReplays<SavedReplay[]>()
      .then((data) => {
        setReplays(data);
        setLoading(false);
      })
      .catch((err: unknown) => {
        console.error("Failed to load replays:", err);
        setLoadError(
          "Saved runs could not be loaded. Check that the backend is running.",
        );
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    fetchReplays();
  }, [fetchReplays]);

  const retry = () => {
    setLoading(true);
    setLoadError(null);
    fetchReplays();
  };

  useEffect(() => {
    if (!deletingId) return;
    cancelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDeletingId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, [deletingId]);

  const confirmDelete = (id: string) => {
    setDeleteError(null);
    deleteReplay(id)
      .then((data: { status: string }) => {
        if (data.status === "ok") {
          setReplays((prev) => prev.filter((r) => r.id !== id));
          setSelected((prev) => prev.filter((s) => s !== id));
        }
        setDeletingId(null);
      })
      .catch((err: unknown) => {
        console.error("Failed to delete replay:", err);
        setDeleteError("The run could not be deleted. Try again.");
        setDeletingId(null);
      });
  };

  const deleting = replays.find((r) => r.id === deletingId);

  return (
    <div className="history-dashboard">
      <header className="history-header">
        <p className="guided-eyebrow">Saved</p>
        <h1>Saved runs</h1>
        <p>
          Runs saved from the simulation views, each with its run ID, seed and
          the code commit it ran on. Select a name for the run&apos;s own page
          (configuration, provenance, notes, exports). Opening one restores its
          settings and seed and shows the metrics recorded when it was saved;
          press Play to run it again.
        </p>
      </header>

      {replays.length > 0 && (
        <div className="run-actions">
          <button
            type="button"
            className="pb-btn pb-primary"
            disabled={selected.length < 2}
            onClick={() => {
              navigate(comparePath(selected));
            }}
          >
            Compare selected ({selected.length})
          </button>
          <span className="run-hint">
            Tick 2 to {MAX_COMPARE_RUNS} runs to compare their stored metrics.
          </span>
        </div>
      )}

      {deleteError && (
        <p className="history-status error" role="alert">
          {deleteError}
        </p>
      )}

      {loading ? (
        <p className="history-status is-loading" role="status">
          <LoaderMark />
          Loading saved runs…
        </p>
      ) : loadError ? (
        <StatusState
          tone="unavailable"
          role="alert"
          className="history-state"
          title={loadError}
          actions={
            <button
              type="button"
              className="pb-btn pb-secondary"
              onClick={retry}
            >
              Retry
            </button>
          }
        />
      ) : replays.length === 0 ? (
        <StatusState
          tone="empty"
          className="history-state"
          title="No saved runs yet."
        >
          <p className="hint">
            Run a simulation, pause it or let it finish, then choose “Save run”
            (or “Save this comparison” on the results page).
          </p>
        </StatusState>
      ) : (
        <div className="history-table-wrap">
          <table className="history-table">
            <caption className="sr-only">
              Saved runs. For comparisons, values read one per strategy, in the
              order the Type column lists them.
            </caption>
            <thead>
              <tr>
                <th scope="col">
                  <span className="sr-only">Select for comparison</span>
                </th>
                <th scope="col">Saved</th>
                <th scope="col">Run ID</th>
                <th scope="col">Name</th>
                <th scope="col">Type</th>
                <th scope="col">Seed</th>
                <th scope="col" title="Git commit of the code that ran it">
                  Commit
                </th>
                <th scope="col" title="Stored configuration">
                  Config
                </th>
                <th scope="col" title="Simulated time when saved">
                  Sim time (s)
                </th>
                <th scope="col" title="Signal / roundabout for comparisons">
                  Avg delay (s)
                </th>
                <th scope="col" title="Signal / roundabout for comparisons">
                  Vehicles served
                </th>
                <th scope="col">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {replays.map((r) => {
                const saved = parseStoredTimestamp(r.created_at);
                const kind = kindOf(r);
                const commit = commitLabel(r.reproducibility?.gitCommitHash);
                const config = configLabel(r.reproducibility);
                const isSelected = selected.includes(r.id);
                return (
                  <tr key={r.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        disabled={
                          !isSelected && selected.length >= MAX_COMPARE_RUNS
                        }
                        onChange={() => {
                          setSelected((prev) =>
                            isSelected
                              ? prev.filter((s) => s !== r.id)
                              : [...prev, r.id],
                          );
                        }}
                        aria-label={`Select ${r.name} for comparison`}
                      />
                    </td>
                    <td>
                      {Number.isNaN(saved.getTime()) ? (
                        r.created_at
                      ) : (
                        <time dateTime={saved.toISOString()}>
                          {saved.toLocaleString()}
                        </time>
                      )}
                    </td>
                    <td className="mono" title={r.id}>
                      {r.id.slice(0, 8)}
                    </td>
                    <th scope="row" className="run-name">
                      <a
                        href={runPath(r.id)}
                        onClick={(event) => {
                          followLink(event, runPath(r.id));
                        }}
                      >
                        {r.name}
                      </a>
                      <Tags tags={r.reproducibility?.tags ?? []} />
                    </th>
                    <td>
                      {strategiesOf(r)
                        ? strategiesOf(r)
                            ?.map(([id]) => strategyName(id))
                            .join(" / ")
                        : KIND_LABEL[kind]}
                    </td>
                    <td className="mono">{seedOf(r)}</td>
                    <td className="mono" title={commit.title}>
                      {commit.text}
                    </td>
                    <td title={config.title}>{config.text}</td>
                    <td className="mono">
                      {num(
                        r.reproducibility?.timing.elapsed ??
                          r.config.simulation?.elapsed,
                        0,
                      )}
                    </td>
                    <td className="mono">
                      {pair(r, (m) => m.averageDelay, 1)}
                    </td>
                    <td className="mono">{pair(r, (m) => m.throughput, 0)}</td>
                    <td>
                      <div className="row-actions">
                        <button
                          type="button"
                          className="pb-btn pb-primary"
                          onClick={() => {
                            onReplay(r);
                          }}
                          aria-label={`Open ${r.name}`}
                        >
                          Open
                        </button>
                        <button
                          type="button"
                          className="pb-btn pb-danger"
                          onClick={() => {
                            setDeletingId(r.id);
                          }}
                          aria-label={`Delete ${r.name}`}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <SavedElsewhere />

      {deletingId && (
        <div className="modal-overlay">
          <div
            className="modal-content"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="delete-title"
            aria-describedby="delete-desc"
          >
            <h2 id="delete-title">Delete this run?</h2>
            <p id="delete-desc">
              “{deleting?.name ?? "This run"}” will be removed permanently.
            </p>
            <div className="modal-actions">
              <button
                ref={cancelRef}
                type="button"
                className="pb-btn pb-secondary"
                onClick={() => {
                  setDeletingId(null);
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="pb-btn pb-danger"
                onClick={() => {
                  confirmDelete(deletingId);
                }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/** Work that each tool keeps in its own list. Saved points to it rather
 *  than copying it, so there is one place each kind of work lives. */
const ELSEWHERE: { href: string; title: string; body: string }[] = [
  {
    href: VIEW_ROUTES.planner,
    title: "Planner studies",
    body: "Open one in the Planner by its study ID; a study’s address can be bookmarked and shared.",
  },
  {
    href: VIEW_ROUTES.scenarios,
    title: "Planning scenarios",
    body: "Saved baseline and intervention scenarios open from Scenario planning.",
  },
  {
    href: VIEW_ROUTES.copilot,
    title: "Experiments",
    body: "Each experiment has its own page, linked when you confirm a Copilot proposal.",
  },
  {
    href: VIEW_ROUTES.discovery,
    title: "Discovery searches",
    body: "Listed in the Discovery Lab with their results and packages.",
  },
  {
    href: VIEW_ROUTES.stress,
    title: "Stress and breakpoint jobs",
    body: "Listed in the Stress Lab with their results.",
  },
  {
    href: VIEW_ROUTES.volume,
    title: "Traffic-level sweeps",
    body: "Listed in the Traffic-level sweep, newest first.",
  },
];

function SavedElsewhere() {
  return (
    <aside
      className="related-tools is-inline"
      aria-labelledby="saved-elsewhere-title"
    >
      <h2 id="saved-elsewhere-title">Saved in other tools</h2>
      <ul>
        {ELSEWHERE.map((item) => (
          <li key={item.href}>
            <a
              href={item.href}
              onClick={(event) => {
                followLink(event, item.href);
              }}
            >
              <span className="related-tools__label">{item.title}</span>
              <span className="related-tools__body">{item.body}</span>
            </a>
          </li>
        ))}
      </ul>
    </aside>
  );
}
