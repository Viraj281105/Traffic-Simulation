import React, { useCallback, useEffect, useRef, useState } from "react";
import "./HistoryDashboard.css";
import { deleteReplay, listReplays } from "../services/api";
import type { RunReproducibility } from "../services/api";

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

function commitCell(rep: RunReproducibility | null | undefined): {
  text: string;
  title: string;
} {
  const hash = rep?.gitCommitHash;
  if (!hash) {
    return { text: "—", title: "Not recorded for this run" };
  }
  if (hash === "unknown") {
    return {
      text: "unknown",
      title:
        "The backend could not read its git commit when this run was saved",
    };
  }
  return { text: hash.slice(0, 7), title: hash };
}

function configCell(rep: RunReproducibility | null | undefined): {
  text: string;
  title: string;
} {
  if (rep?.exactConfig) {
    return {
      text: "Exact",
      title: "The exact configuration the simulation ran with is stored",
    };
  }
  if (rep?.configAvailable) {
    return {
      text: "Settings",
      title: "Only the dashboard settings were stored for this run",
    };
  }
  return { text: "—", title: "No configuration recorded for this run" };
}

const KIND_LABEL = {
  comparative: "📊 Comparison",
  roundabout: "🔄 Roundabout",
  signal: "🚦 Signal",
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
        <h1>Saved runs</h1>
        <p>
          Runs saved from the simulation views, each with its run ID, seed and
          the code commit it ran on. Opening one restores its settings and seed
          and shows the metrics recorded when it was saved; press Play to run it
          again.
        </p>
      </header>

      {deleteError && (
        <p className="history-status error" role="alert">
          {deleteError}
        </p>
      )}

      {loading ? (
        <p className="history-status" role="status">
          Loading saved runs…
        </p>
      ) : loadError ? (
        <div className="history-status error" role="alert">
          <p>{loadError}</p>
          <button type="button" className="pb-btn pb-secondary" onClick={retry}>
            Retry
          </button>
        </div>
      ) : replays.length === 0 ? (
        <div className="history-status empty">
          <p>No saved runs yet.</p>
          <p className="hint">
            Run a simulation, pause it or let it finish, then choose “Save to
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
                const commit = commitCell(r.reproducibility);
                const config = configCell(r.reproducibility);
                return (
                  <tr key={r.id}>
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
                      {r.name}
                    </th>
                    <td>{KIND_LABEL[kind]}</td>
                    <td className="mono">{seedOf(r)}</td>
                    <td className="mono" title={commit.title}>
                      {commit.text}
                    </td>
                    <td title={config.title}>{config.text}</td>
                    <td className="mono">
                      {num(r.config.simulation?.elapsed, 0)}
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
