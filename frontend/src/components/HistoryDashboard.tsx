import React, { useCallback, useEffect, useState } from "react";
import "./HistoryDashboard.css";
import { deleteReplay, listReplays } from "../services/api";
import type { RunReproducibility } from "../services/api";
import { commitLabel, configLabel } from "../runs/savedRun";
import {
  MAX_COMPARE_RUNS,
  comparePath,
  followLink,
  navigate,
  runPath,
} from "../routing";
import { Tags } from "./RunTags";
import "./RunPages.css";
import { Loader } from "./ui/Loader";
import { useDelayedFlag } from "../hooks/useDelayedFlag";
import { Overlay } from "./ui/Overlay";
import { PageHeader } from "./ui/PageHeader";

import type { RunningMetrics } from "../types/simulation";
import type { SimulationConfigValues } from "../types/config";
import { parseStoredTimestamp } from "../utils/time";

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

function kindOf(r: SavedReplay): "comparative" | "roundabout" | "signal" {
  if (r.metrics.signal !== undefined && r.metrics.roundabout !== undefined) {
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

/** "S / R" for a comparison, the single value otherwise. */
function pair(
  r: SavedReplay,
  pick: (m: Partial<RunningMetrics>) => number | undefined,
  decimals: number,
): string {
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
  const showLoader = useDelayedFlag(loading);

  return (
    <div className="uf-page uf-page--wide history-dashboard">
      <PageHeader
        eyebrow="Saved"
        title="Saved runs"
        lead={
          <p>
            Each saved run keeps its run ID, seed and code commit. Select a name
            for its page (configuration, provenance, notes, exports). Opening a
            run restores its settings and shows the metrics recorded when it was
            saved; press Play to run it again.
          </p>
        }
      />

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
        showLoader ? (
          <Loader label="Loading saved runs" />
        ) : (
          <p className="sr-only" role="status">
            Loading saved runs
          </p>
        )
      ) : loadError ? (
        <div
          className="uf-callout uf-callout--danger history-status"
          role="alert"
        >
          <p>{loadError}</p>
          <button type="button" className="uf-btn uf-btn--sm" onClick={retry}>
            Retry
          </button>
        </div>
      ) : replays.length === 0 ? (
        <div className="uf-empty">
          <p className="uf-empty__title">No saved runs yet</p>
          <p className="uf-empty__text">
            Run a comparison, pause it or let it finish, then choose “Save to
            History”.
          </p>
        </div>
      ) : (
        <div className="history-table-wrap">
          <table className="history-table">
            <caption className="sr-only">
              Saved runs. For comparisons, values read signal / roundabout.
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
                    <td>{KIND_LABEL[kind]}</td>
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

      {deletingId && (
        <Overlay
          role="alertdialog"
          narrow
          title="Delete this run?"
          description={`“${deleting?.name ?? "This run"}” will be removed permanently.`}
          closeLabel="Cancel"
          onClose={() => {
            setDeletingId(null);
          }}
          footer={
            <>
              <button
                type="button"
                className="uf-btn"
                data-autofocus
                onClick={() => {
                  setDeletingId(null);
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="uf-btn uf-btn--danger"
                onClick={() => {
                  confirmDelete(deletingId);
                }}
              >
                Delete
              </button>
            </>
          }
        >
          <p className="uf-help">
            The run record, its notes and tags are deleted. This cannot be
            undone.
          </p>
        </Overlay>
      )}
    </div>
  );
};
