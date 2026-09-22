import { useState, useEffect, useId, useLayoutEffect } from "react";
import type { MouseEvent, ReactNode } from "react";
import { useWebSocketSnapshot } from "./hooks/useWebSocketSnapshot";
import { useSimulationPolling } from "./hooks/useSimulationPolling";
import { IntersectionMap } from "./components/IntersectionMap";
import { RoundaboutMap } from "./components/RoundaboutMap";
import { MetricsSidebar } from "./components/MetricsSidebar";
import {
  ComparativeDashboard,
  ComparisonPanel,
} from "./components/ComparativeDashboard";
import { PlaybackControls } from "./components/PlaybackControls";
import { HistoryDashboard, SavedReplay } from "./components/HistoryDashboard";
import { VolumeAnalysisDashboard } from "./components/VolumeAnalysisDashboard";
import { ValidationDashboard } from "./components/ValidationDashboard";
import { ConfigurationSidebar } from "./components/ConfigurationSidebar";
import { Sun, Moon } from "lucide-react";
import type { SimulationConfigValues } from "./types/config";
import { DEFAULT_CONFIG_VALUES } from "./types/config";
import { saveReplay, updateSimulationConfig } from "./services/api";
import type {
  LiveSnapshot,
  DualSnapshot,
  SimulationStatus,
} from "./types/simulation";
import {
  VIEW_ROUTES,
  navigate,
  resolveRoute,
  usePathname,
  type RoutedView,
} from "./routing";
import "./App.css";

type ViewMode = RoutedView | "single";

/**
 * Router shell. The URL is the source of truth for which view is shown, so a
 * refresh, a direct link or back/forward all land on the same view. The
 * dashboard stays mounted across view changes, keeping its configuration and
 * live stream exactly as when views were plain React state.
 */
export function App() {
  const route = resolveRoute(usePathname());
  const redirectTo = route.kind === "redirect" ? route.to : null;

  useLayoutEffect(() => {
    if (redirectTo) navigate(redirectTo, { replace: true });
  }, [redirectTo]);

  if (route.kind === "notFound") return <NotFound path={route.path} />;
  if (route.kind === "redirect") return null;
  return <Dashboard viewMode={route.view} />;
}

const SIMULATION_VIEWS: ReadonlySet<ViewMode> = new Set([
  "signal",
  "roundabout",
  "comparative",
  "single",
]);

const newSeed = () => Math.floor(Math.random() * 1000000) + 1;

/** Restores the exact UI configuration a run was saved with, falling back to
 *  the legacy fields older saves carry. */
function configFromReplay(
  replay: SavedReplay,
  current: SimulationConfigValues,
): SimulationConfigValues {
  if (replay.config.ui) return { ...DEFAULT_CONFIG_VALUES, ...replay.config.ui };
  const lanes = replay.config.roads?.lanesPerApproach?.north ?? current.lanes;
  return {
    ...current,
    lanes,
    laneWidth: replay.config.geometry?.laneWidth ?? current.laneWidth,
    arrivalRate: replay.config.traffic?.arrivalRate ?? current.arrivalRate,
    duration: replay.config.simulation?.duration ?? current.duration,
    randomSeed: replay.config.simulation?.randomSeed ?? current.randomSeed,
  };
}

function Dashboard({ viewMode: routedView }: { viewMode: RoutedView }) {
  const viewMode = routedView as ViewMode;
  const setViewMode = (view: RoutedView) => {
    navigate(VIEW_ROUTES[view]);
  };
  const [activeReplay, setActiveReplay] = useState<SavedReplay | null>(null);
  const [showAnalyticsModal, setShowAnalyticsModal] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isLight, setIsLight] = useState(
    () => sessionStorage.getItem("signals-theme") === "light",
  );

  useEffect(() => {
    document.documentElement.classList.toggle("light", isLight);
    document.documentElement.classList.toggle("dark", !isLight);
    sessionStorage.setItem("signals-theme", isLight ? "light" : "dark");
  }, [isLight]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage(null);
    }, 3000);
  };

  const mode = viewMode === "comparative" ? "dual" : "single";
  const {
    snapshot,
    connectionStatus,
    isPlaying,
    error: wsError,
    play,
    pause,
    stop,
  } = useWebSocketSnapshot(mode);

  const {
    vehicle: singleVehicle,
    status: singleStatus,
    isLoading: singleIsLoading,
    error: singleError,
    start: singleStart,
    stop: singleStop,
    reset: singleReset,
  } = useSimulationPolling();

  // The live stream is the only source of displayed metrics: a completed or
  // paused run keeps showing its final values (the backend keeps streaming
  // them), while a reset or reconfiguration shows the fresh run rather than
  // the previous run's numbers next to a reset map.
  const dualSnapshot = snapshot && "signal" in snapshot ? snapshot : null;
  const singleSnapshot = snapshot && !("signal" in snapshot) ? snapshot : null;

  // Simulation configuration. The dashboard starts from the same values that
  // "Reset defaults" restores, with a fresh random seed.
  const [configValues, setConfigValues] = useState<SimulationConfigValues>(
    () => ({ ...DEFAULT_CONFIG_VALUES, randomSeed: newSeed() }),
  );
  const [showStopLines, setShowStopLines] = useState(true);
  const [debug, setDebug] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);

  const {
    lanes,
    laneWidth,
    arrivalRate,
    duration,
    randomSeed,
    greenDuration,
    yellowDuration,
    allRedDuration,
    criticalGap,
    followUpTime,
    nsGreenDuration,
    ewGreenDuration,
  } = configValues;

  const randomizeSeed = () => {
    setActiveReplay(null);
    setConfigValues((prev) => ({ ...prev, randomSeed: newSeed() }));
  };

  const intersectionSize = lanes * laneWidth * 2 + 4.0;
  const isDual = viewMode === "comparative";
  const isSimulationView = SIMULATION_VIEWS.has(viewMode);

  // Sync config with backend on change
  useEffect(() => {
    const intersectionType =
      viewMode === "roundabout" ? "roundabout" : "fixed_time_signal";
    updateSimulationConfig({
      intersectionType,
      intersectionSize,
      laneWidth,
      lanesNorth: lanes,
      lanesSouth: lanes,
      lanesEast: lanes,
      lanesWest: lanes,
      arrivalRate,
      duration,
      randomSeed,
      greenDuration,
      yellowDuration,
      allRedDuration,
      criticalGap,
      followUpTime,
      ...(nsGreenDuration !== null && nsGreenDuration !== undefined
        ? { nsGreenDuration }
        : {}),
      ...(ewGreenDuration !== null && ewGreenDuration !== undefined
        ? { ewGreenDuration }
        : {}),
    }).catch((err: unknown) => {
      console.error("Failed to update backend config:", err);
    });
  }, [
    viewMode,
    lanes,
    intersectionSize,
    laneWidth,
    arrivalRate,
    duration,
    randomSeed,
    greenDuration,
    yellowDuration,
    allRedDuration,
    criticalGap,
    followUpTime,
    nsGreenDuration,
    ewGreenDuration,
  ]);

  const handleApplyConfig = (newConfig: SimulationConfigValues) => {
    setActiveReplay(null);
    setConfigValues(newConfig);
    showToast("Scenario applied — the simulation was reset with it.");
  };

  // Map controls to appropriate hooks based on the active view mode
  const activeIsPlaying =
    viewMode === "single" ? singleStatus === "running" : isPlaying;
  const activeError = viewMode === "single" ? singleError : wsError;
  const activeConnectionStatus =
    viewMode === "single"
      ? singleError
        ? "error"
        : singleIsLoading
          ? "connecting"
          : "connected"
      : connectionStatus;

  const handlePlay = () => {
    setActiveReplay(null);
    if (viewMode === "single") {
      singleStart().catch(() => {});
    } else {
      play().catch(() => {});
    }
  };

  const handlePause = () => {
    if (viewMode === "single") {
      singleStop().catch(() => {});
    } else {
      pause().catch(() => {});
    }
  };

  const handleStop = () => {
    randomizeSeed();
    setActiveReplay(null);
    if (viewMode === "single") {
      singleReset().catch(() => {});
    } else {
      stop().catch(() => {});
    }
  };

  // Construct a compatible envelope object for the playback bar in polling mode
  const singlePlaybackEnvelope = {
    timestamp: singleVehicle?.sim_time ?? 0,
    tick: singleVehicle?.tick ?? 0,
    samplingFrequency: 10,
    simulationStatus: (singleStatus === "running"
      ? "running"
      : "stopped") as SimulationStatus,
  };

  const playbackEnvelope =
    viewMode === "single"
      ? (singlePlaybackEnvelope as unknown as LiveSnapshot)
      : dualSnapshot
        ? ({
            timestamp: dualSnapshot.elapsed,
            tick: dualSnapshot.tick,
            samplingFrequency: dualSnapshot.signal.samplingFrequency,
            simulationStatus: dualSnapshot.signal.simulationStatus,
          } as unknown as LiveSnapshot)
        : singleSnapshot;

  // A run can be saved once it has produced data and is not running.
  const liveTimestamp = isDual
    ? (dualSnapshot?.elapsed ?? 0)
    : (singleSnapshot?.timestamp ?? 0);
  const canSave = !activeIsPlaying && activeReplay === null && liveTimestamp > 0;

  const handleSaveHistory = () => {
    const geometryType =
      viewMode === "roundabout" ? "roundabout" : "fixed_time_signal";
    const configToSave: SavedReplay["config"] = {
      // Everything needed to re-run the same scenario from History.
      ui: configValues,
      simulation: { duration, randomSeed, elapsed: liveTimestamp },
      geometry: { intersectionType: geometryType, laneWidth },
      roads: {
        lanesPerApproach: {
          north: lanes,
          south: lanes,
          east: lanes,
          west: lanes,
        },
      },
      traffic: { arrivalRate },
    };

    let metricsToSave: Record<string, unknown> = {};
    if (isDual && dualSnapshot) {
      metricsToSave = {
        signal: dualSnapshot.signal.metrics,
        roundabout: dualSnapshot.roundabout.metrics,
      };
    } else if (singleSnapshot) {
      metricsToSave = { ...singleSnapshot.metrics };
    }

    const label =
      viewMode === "comparative"
        ? "Comparison"
        : viewMode === "roundabout"
          ? "Roundabout"
          : "Signal";
    const payload = {
      name: `${label} · seed ${String(randomSeed)} · ${liveTimestamp.toFixed(0)} s`,
      config: configToSave,
      metrics: metricsToSave,
      mode: isDual ? ("dual" as const) : ("single" as const),
    };

    saveReplay(payload)
      .then((saved: { runId?: string } | undefined) => {
        const runId = saved?.runId;
        showToast(
          runId
            ? `Run ${runId.slice(0, 8)} saved to History.`
            : "Run saved to History.",
        );
      })
      .catch((e: unknown) => {
        console.error(e);
        showToast("Could not save the run — is the backend reachable?");
      });
  };

  const handleReplay = (replay: SavedReplay) => {
    setActiveReplay(replay);
    setConfigValues((prev) => configFromReplay(replay, prev));

    const replayIsDual =
      replay.metrics.signal !== undefined &&
      replay.metrics.roundabout !== undefined;
    if (replayIsDual) {
      setViewMode("comparative");
    } else {
      const type = replay.config.geometry?.intersectionType;
      setViewMode(type === "roundabout" ? "roundabout" : "signal");
    }
  };

  const replayDual: DualSnapshot | null =
    activeReplay?.metrics.signal && activeReplay.metrics.roundabout
      ? ({
          signal: { metrics: activeReplay.metrics.signal },
          roundabout: { metrics: activeReplay.metrics.roundabout },
        } as unknown as DualSnapshot)
      : null;
  const replaySingle: LiveSnapshot | null =
    activeReplay && "averageWaitTime" in activeReplay.metrics
      ? ({ metrics: activeReplay.metrics } as unknown as LiveSnapshot)
      : null;

  return (
    <div className="app">
      {/* ── Header ────────────────────────────────────────────────────── */}
      <header className="app-header">
        <div className="header-left">
          <a className="brand" href="/" data-testid="link-brand">
            <span className="brand-mark" aria-hidden="true" />
            <span className="brand-name">URBANFLOW</span>
            <span className="sr-only">Home</span>
          </a>
        </div>

        {/* View Mode Tabs */}
        <nav className="header-tabs" aria-label="Views">
          <ViewTab view="signal" active={viewMode}>
            🚦 Fixed-Time Signal Only
          </ViewTab>
          <ViewTab view="roundabout" active={viewMode}>
            🔄 Roundabout Only
          </ViewTab>
          <ViewTab view="comparative" active={viewMode}>
            📊 Comparative View
          </ViewTab>
          <ViewTab view="history" active={viewMode}>
            📚 History
          </ViewTab>
          <ViewTab view="volume" active={viewMode}>
            📈 Volume Analysis
          </ViewTab>
          <ViewTab view="validation" active={viewMode}>
            🔬 Validation
          </ViewTab>
        </nav>

        <div className="header-right">
          {isSimulationView && (
            <button
              type="button"
              className={`config-toggle-btn ${configOpen ? "active" : ""}`}
              onClick={() => {
                setConfigOpen((v) => !v);
              }}
              aria-expanded={configOpen}
              aria-haspopup="dialog"
              aria-label="Scenario settings"
              title="Demand, geometry, signal timings and gap acceptance"
            >
              <span aria-hidden="true">⚙️</span>
              <span className="label-text" aria-hidden="true">
                {" "}
                Scenario settings
              </span>
            </button>
          )}
          <button
            className="theme-button"
            type="button"
            onClick={() => {
              setIsLight((c) => !c);
            }}
            aria-label={
              isLight ? "Switch to dark mode" : "Switch to light mode"
            }
            data-testid="button-theme-toggle"
          >
            {isLight ? <Moon size={15} /> : <Sun size={15} />}
          </button>
        </div>
      </header>

      {/* ── Map display toggles & seed ───────────────────────────────── */}
      {isSimulationView && (
        <div className="quick-toggles-bar">
          {viewMode !== "roundabout" && (
            <>
              <ConfigToggle
                label="Stop lines"
                value={showStopLines}
                onChange={setShowStopLines}
              />
              <ConfigToggle
                label="Queue labels"
                value={debug}
                onChange={setDebug}
              />
            </>
          )}
          <div className="quick-seed-group">
            <span className="seed-badge" title="Random seed of the next run">
              <span aria-hidden="true">🎲 </span>Seed:{" "}
              <strong>{randomSeed}</strong>
            </span>
            <button
              type="button"
              className="pb-btn pb-secondary re-roll-btn"
              onClick={randomizeSeed}
              title="Pick a new random seed (resets the simulation)"
            >
              Re-roll
            </button>
          </div>
        </div>
      )}

      {/* ── Interactive Configuration Sidebar ────────────────────────── */}
      {isSimulationView && (
        <ConfigurationSidebar
          isOpen={configOpen}
          onClose={() => {
            setConfigOpen(false);
          }}
          config={configValues}
          onApply={handleApplyConfig}
          mode={
            viewMode === "roundabout"
              ? "roundabout"
              : viewMode === "comparative"
                ? "comparative"
                : "signal"
          }
        />
      )}

      {/* ── Main content ──────────────────────────────────────────────── */}
      {viewMode === "comparative" ? (
        <main className="app-main comparison-layout">
          <h1 className="sr-only">Comparative view: signal vs roundabout</h1>
          <div className="comparison-maps-row">
            <section
              className="comparison-column"
              aria-labelledby="col-signal-title"
            >
              <div className="column-header">
                <h2 className="column-title" id="col-signal-title">
                  <span aria-hidden="true">🚦 </span>Fixed-time signal
                </h2>
              </div>
              <div className="canvas-wrapper">
                <IntersectionMap
                  snapshot={dualSnapshot?.signal ?? null}
                  lanesNorth={lanes}
                  lanesSouth={lanes}
                  lanesEast={lanes}
                  lanesWest={lanes}
                  laneWidth={laneWidth}
                  showCrosswalks={true}
                  showStopLines={showStopLines}
                  debug={debug}
                />
              </div>
            </section>
            <section
              className="comparison-column"
              aria-labelledby="col-roundabout-title"
            >
              <div className="column-header">
                <h2 className="column-title" id="col-roundabout-title">
                  <span aria-hidden="true">🔄 </span>Modern roundabout
                </h2>
              </div>
              <div className="canvas-wrapper">
                <RoundaboutMap
                  snapshot={dualSnapshot?.roundabout ?? null}
                  laneWidth={laneWidth}
                  lanes={lanes}
                  showCrosswalks={false}
                  debug={debug}
                />
              </div>
            </section>
          </div>
          <ComparisonPanel
            snapshot={replayDual ?? dualSnapshot}
            connectionStatus={activeConnectionStatus}
            replayName={replayDual ? (activeReplay?.name ?? null) : null}
            canSave={canSave}
            onSave={handleSaveHistory}
            onOpenDetails={() => {
              setShowAnalyticsModal(true);
            }}
          />
          {showAnalyticsModal && (
            <ComparativeDashboard
              snapshot={replayDual ?? dualSnapshot}
              replayName={replayDual ? (activeReplay?.name ?? null) : null}
              onClose={() => {
                setShowAnalyticsModal(false);
              }}
            />
          )}
        </main>
      ) : viewMode === "history" ? (
        <main className="app-main full-screen page-scroll">
          <HistoryDashboard onReplay={handleReplay} />
        </main>
      ) : viewMode === "volume" ? (
        <main className="app-main full-screen page-scroll">
          <VolumeAnalysisDashboard />
        </main>
      ) : viewMode === "validation" ? (
        <main className="app-main full-screen page-scroll">
          <ValidationDashboard />
        </main>
      ) : (
        <main className="app-main">
          <h1 className="sr-only">
            {viewMode === "roundabout"
              ? "Roundabout simulation"
              : "Fixed-time signal simulation"}
          </h1>
          <div className="canvas-wrapper">
            {viewMode === "roundabout" ? (
              <RoundaboutMap
                snapshot={singleSnapshot}
                laneWidth={laneWidth}
                lanes={lanes}
                showCrosswalks={false}
                debug={debug}
              />
            ) : (
              <IntersectionMap
                snapshot={singleSnapshot}
                lanesNorth={lanes}
                lanesSouth={lanes}
                lanesEast={lanes}
                lanesWest={lanes}
                laneWidth={laneWidth}
                showCrosswalks={true}
                showStopLines={showStopLines}
                debug={debug}
              />
            )}
          </div>
          <div className="single-side-column">
            <MetricsSidebar
              snapshot={replaySingle ?? singleSnapshot}
              connectionStatus={activeConnectionStatus}
              geometry={
                viewMode === "roundabout" ? "roundabout" : "fixed_time_signal"
              }
              replayName={replaySingle ? (activeReplay?.name ?? null) : null}
            />
            {!replaySingle && (
              <div className="save-bar">
                <button
                  type="button"
                  className="pb-btn pb-primary"
                  onClick={handleSaveHistory}
                  disabled={!canSave}
                  title={
                    canSave
                      ? "Save this run to History"
                      : "Pause or finish the run (after it has started) to save it"
                  }
                >
                  Save to History
                </button>
              </div>
            )}
          </div>
        </main>
      )}

      {/* ── Playback controls (live simulation views only) ───────────── */}
      {isSimulationView && (
        <footer className="app-footer">
          <PlaybackControls
            snapshot={playbackEnvelope}
            isPlaying={activeIsPlaying}
            onPlay={handlePlay}
            onPause={handlePause}
            onStop={handleStop}
          />
          {activeError && (
            <div className="error-banner" role="alert">
              ⚠ {activeError}
            </div>
          )}
        </footer>
      )}

      {/* ── Toast Notification ────────────────────────────────────────── */}
      <div className="toast-region" role="status" aria-live="polite">
        {toastMessage && (
          <div className="toast-notification">{toastMessage}</div>
        )}
      </div>
    </div>
  );
}

// ── Navigation ─────────────────────────────────────────────────────────────

/** Client-side navigation for a same-document link, leaving modified clicks
 *  (new tab/window) to the browser. */
function followLink(event: MouseEvent<HTMLAnchorElement>, to: string) {
  if (
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  ) {
    return;
  }
  event.preventDefault();
  navigate(to);
}

function ViewTab({
  view,
  active,
  children,
}: {
  view: RoutedView;
  active: ViewMode;
  children: ReactNode;
}) {
  const href = VIEW_ROUTES[view];
  const isActive = view === active;
  return (
    <a
      href={href}
      className={`tab-btn ${isActive ? "active" : ""}`}
      aria-current={isActive ? "page" : undefined}
      onClick={(event) => {
        followLink(event, href);
      }}
    >
      {children}
    </a>
  );
}

function NotFound({ path }: { path: string }) {
  useEffect(() => {
    const isLight = sessionStorage.getItem("signals-theme") === "light";
    document.documentElement.classList.toggle("light", isLight);
    document.documentElement.classList.toggle("dark", !isLight);
  }, []);

  const home = VIEW_ROUTES.comparative;
  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <a className="brand" href="/" data-testid="link-brand">
            <span className="brand-mark" aria-hidden="true" />
            <span className="brand-name">URBANFLOW</span>
          </a>
        </div>
      </header>
      <main className="app-main full-screen not-found" role="main">
        <h1>Page not found</h1>
        <p>
          There is no page at <code>{path}</code>.
        </p>
        <p className="not-found-links">
          <a
            href={home}
            className="pb-btn pb-primary"
            onClick={(event) => {
              followLink(event, home);
            }}
          >
            Open the simulation dashboard
          </a>
          <a href="/" className="pb-btn pb-secondary">
            Back to the landing page
          </a>
        </p>
      </main>
    </div>
  );
}

// ── Config helpers ─────────────────────────────────────────────────────────

function ConfigToggle({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  const id = useId();
  return (
    <div className="config-item config-toggle-item">
      <span className="config-label" id={id}>
        {label}
      </span>
      <button
        type="button"
        className={`toggle-btn ${value ? "toggle-on" : "toggle-off"}`}
        aria-pressed={value}
        aria-labelledby={id}
        onClick={() => {
          onChange(!value);
        }}
      >
        {value ? "On" : "Off"}
      </button>
    </div>
  );
}
