import {
  useState,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
} from "react";
import type { ReactNode } from "react";
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
import { RunPage } from "./components/RunPage";
import { ComparePage } from "./components/ComparePage";
import { ResearchHub } from "./components/ResearchHub";
import { ScenarioSetup } from "./components/guided/ScenarioSetup";
import { LiveGuide } from "./components/guided/LiveGuide";
import { ResultsReport } from "./components/guided/ResultsReport";
import {
  contextsOf,
  sessionRunFrom,
  type SessionRun,
} from "./components/guided/comparisonRun";
import { StepNav, type GuidedStage } from "./components/guided/StepNav";
import "./components/guided/Guided.css";
import { Sun, Moon, SlidersHorizontal } from "lucide-react";
import type { SimulationConfigValues } from "./types/config";
import { DEFAULT_CONFIG_VALUES, dashboardPayload } from "./types/config";
import { saveReplay, updateSimulationConfig } from "./services/api";
import { hasResults, sideSummary } from "./metrics/plainLanguage";
import type {
  LiveSnapshot,
  DualSnapshot,
  SimulationStatus,
} from "./types/simulation";
import {
  VIEW_ROUTES,
  followLink,
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
  // Saved-run pages belong to the History section. They render inside the
  // same Dashboard element as every view, so moving between them and the
  // simulation keeps its configuration and live stream mounted.
  if (route.kind === "run") {
    return (
      <Dashboard viewMode="history" page={{ kind: "run", runId: route.runId }} />
    );
  }
  if (route.kind === "compare") {
    return <Dashboard viewMode="history" page={{ kind: "compare" }} />;
  }
  return <Dashboard viewMode={route.view} />;
}

const SIMULATION_VIEWS: ReadonlySet<ViewMode> = new Set([
  "signal",
  "roundabout",
  "comparative",
  "single",
]);

/** Single-control views: specialist tools with the full live metric panel,
 *  display toggles and scenario settings in the header. */
const SINGLE_VIEWS: ReadonlySet<ViewMode> = new Set([
  "signal",
  "roundabout",
  "single",
]);

/** The three places in the product. Compare is the guided path everyone
 *  starts on; Saved holds kept comparisons; the Research lab gathers every
 *  specialist tool. */
type Section = "compare" | "saved" | "research";

const RESEARCH_VIEWS: ReadonlySet<ViewMode> = new Set([
  "research",
  "volume",
  "validation",
  "signal",
  "roundabout",
  "single",
]);

function sectionOf(view: ViewMode): Section {
  if (view === "history") return "saved";
  if (RESEARCH_VIEWS.has(view)) return "research";
  return "compare";
}

const RESEARCH_TABS: { view: RoutedView; label: string }[] = [
  { view: "research", label: "Overview" },
  { view: "volume", label: "Traffic-level sweep" },
  { view: "validation", label: "Statistical validation" },
  { view: "signal", label: "Signal on its own" },
  { view: "roundabout", label: "Roundabout on its own" },
];

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

function sameConfig(a: SimulationConfigValues, b: SimulationConfigValues) {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]) as Set<
    keyof SimulationConfigValues
  >;
  return [...keys].every((k) => (a[k] ?? null) === (b[k] ?? null));
}

type HistoryPage = { kind: "run"; runId: string } | { kind: "compare" };

function Dashboard({
  viewMode: routedView,
  page,
}: {
  viewMode: RoutedView;
  page?: HistoryPage;
}) {
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

  // A guided "Run the comparison" changes the config and must start playing
  // only once the backend holds it: a config update resets the simulation,
  // so playing first would run (and then lose) the old scenario.
  const syncVersion = useRef(0);
  const playAfterSync = useRef(false);
  const playRef = useRef(play);
  useEffect(() => {
    playRef.current = play;
  });

  // Sync config with backend on change
  useEffect(() => {
    const intersectionType =
      viewMode === "roundabout" ? "roundabout" : "fixed_time_signal";
    const version = ++syncVersion.current;
    updateSimulationConfig(
      dashboardPayload(
        {
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
        },
        intersectionType,
      ),
    )
      .then(() => {
        if (version === syncVersion.current && playAfterSync.current) {
          playAfterSync.current = false;
          playRef.current().catch(() => {});
        }
      })
      .catch((err: unknown) => {
        playAfterSync.current = false;
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

  // ── Guided comparison (the Compare section) ─────────────────────────────
  const [stage, setStage] = useState<GuidedStage>("setup");
  const [sessionRuns, setSessionRuns] = useState<SessionRun[]>([]);
  const currentRunId = JSON.stringify(configValues);
  const dualComplete = dualSnapshot?.signal.simulationStatus === "completed";
  const liveResultsReady = (() => {
    if (!dualSnapshot) return false;
    const { signal, roundabout } = contextsOf(dualSnapshot);
    return hasResults(sideSummary(signal), sideSummary(roundabout));
  })();
  const currentRun =
    dualSnapshot && liveResultsReady && !activeReplay
      ? sessionRunFrom(currentRunId, configValues, dualSnapshot, dualComplete)
      : null;
  const shownSessionRuns = [
    ...sessionRuns.filter((run) => run.id !== currentRunId),
    ...(currentRun ? [currentRun] : []),
  ];

  /** Keeps the comparison on screen in the session table before the next
   *  scenario replaces it. */
  const recordCurrentRun = () => {
    const run = currentRun;
    if (!run) return;
    setSessionRuns((prev) => [...prev.filter((r) => r.id !== run.id), run]);
  };

  const handleGuidedRun = (next: SimulationConfigValues) => {
    recordCurrentRun();
    setActiveReplay(null);
    setStage("watch");
    if (sameConfig(next, configValues)) {
      if (!isPlaying) play().catch(() => {});
      return;
    }
    playAfterSync.current = true;
    setConfigValues(next);
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
      setStage("results");
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

  const section = sectionOf(viewMode);
  const isSingle = SINGLE_VIEWS.has(viewMode);
  const guidedResultsAvailable = replayDual !== null || liveResultsReady;
  const warmupSeconds = dualSnapshot?.signal.warmupTime ?? null;

  const comparisonMaps = (
    <div className="comparison-maps-row">
      <section className="comparison-column" aria-labelledby="col-signal-title">
        <div className="column-header">
          <h2 className="column-title" id="col-signal-title">
            <span
              className="column-swatch column-swatch--signal"
              aria-hidden="true"
            />
            Traffic signal
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
            <span
              className="column-swatch column-swatch--roundabout"
              aria-hidden="true"
            />
            Roundabout
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
  );

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

        <nav className="header-tabs" aria-label="Main">
          <ViewTab view="comparative" current={section === "compare"}>
            Compare
          </ViewTab>
          <ViewTab view="history" current={section === "saved"}>
            Saved
          </ViewTab>
          <ViewTab view="research" current={section === "research"}>
            Research lab
          </ViewTab>
        </nav>

        <div className="header-right">
          {isSingle && (
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
              <SlidersHorizontal aria-hidden="true" />
              <span className="label-text" aria-hidden="true">
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

      {/* ── Section sub-navigation ───────────────────────────────────── */}
      {section === "research" && (
        <nav className="sub-nav" aria-label="Research tools">
          {RESEARCH_TABS.map((tab) => (
            <ViewTab
              key={tab.view}
              view={tab.view}
              current={tab.view === viewMode}
            >
              {tab.label}
            </ViewTab>
          ))}
        </nav>
      )}
      {section === "compare" && (
        <StepNav
          stage={stage}
          resultsAvailable={guidedResultsAvailable}
          onChange={(next) => {
            if (next !== "results") setActiveReplay(null);
            setStage(next);
          }}
        />
      )}

      {/* ── Map display toggles & seed (single-control tools) ────────── */}
      {isSingle && (
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
              Seed <strong>{randomSeed}</strong>
            </span>
            <button
              type="button"
              className="uf-btn uf-btn--sm re-roll-btn"
              onClick={randomizeSeed}
              title="Pick a new random seed (resets the simulation)"
            >
              Re-roll
            </button>
          </div>
        </div>
      )}

      {/* ── Scenario settings for the single-control tools ───────────── */}
      {isSingle && (
        <ConfigurationSidebar
          isOpen={configOpen}
          onClose={() => {
            setConfigOpen(false);
          }}
          config={configValues}
          onApply={handleApplyConfig}
          mode={viewMode === "roundabout" ? "roundabout" : "signal"}
        />
      )}

      {/* ── Main content ──────────────────────────────────────────────── */}
      {viewMode === "comparative" ? (
        stage === "setup" ? (
          <main className="app-main full-screen page-scroll">
            <ScenarioSetup
              config={configValues}
              onRun={handleGuidedRun}
              runInProgress={
                !activeReplay && liveTimestamp > 0 && !dualComplete
              }
            />
          </main>
        ) : stage === "results" ? (
          <main className="app-main full-screen page-scroll">
            <ResultsReport
              snapshot={replayDual ?? dualSnapshot}
              config={configValues}
              replayName={replayDual ? (activeReplay?.name ?? null) : null}
              complete={replayDual === null && dualComplete}
              running={replayDual === null && activeIsPlaying}
              warmupSeconds={replayDual ? null : warmupSeconds}
              elapsedSeconds={
                replayDual
                  ? (activeReplay?.config.simulation?.elapsed ?? null)
                  : (dualSnapshot?.elapsed ?? null)
              }
              canSave={canSave}
              onSave={handleSaveHistory}
              onWatch={() => {
                setActiveReplay(null);
                setStage("watch");
              }}
              onChangeScenario={() => {
                setActiveReplay(null);
                setStage("setup");
              }}
              onTryScenario={handleGuidedRun}
              onOpenAnalytics={() => {
                setShowAnalyticsModal(true);
              }}
              sessionRuns={shownSessionRuns}
              currentRunId={replayDual ? null : currentRunId}
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
        ) : (
          <main className="app-main comparison-layout">
            <h1 className="sr-only">
              Watch the traffic signal and the roundabout run side by side
            </h1>
            {comparisonMaps}
            <LiveGuide
              snapshot={dualSnapshot}
              durationSeconds={duration}
              connectionStatus={activeConnectionStatus}
              onSeeResults={() => {
                setStage("results");
              }}
              detailedPanel={
                <ComparisonPanel
                  snapshot={dualSnapshot}
                  connectionStatus={activeConnectionStatus}
                  replayName={null}
                  canSave={canSave}
                  onSave={handleSaveHistory}
                  onOpenDetails={() => {
                    setShowAnalyticsModal(true);
                  }}
                />
              }
            />
            {showAnalyticsModal && (
              <ComparativeDashboard
                snapshot={dualSnapshot}
                replayName={null}
                onClose={() => {
                  setShowAnalyticsModal(false);
                }}
              />
            )}
          </main>
        )
      ) : viewMode === "history" ? (
        <main className="app-main full-screen page-scroll">
          {page?.kind === "run" ? (
            <RunPage
              key={page.runId}
              runId={page.runId}
              onOpenInSimulator={handleReplay}
            />
          ) : page?.kind === "compare" ? (
            <ComparePage />
          ) : (
            <HistoryDashboard onReplay={handleReplay} />
          )}
        </main>
      ) : viewMode === "research" ? (
        <main className="app-main full-screen page-scroll">
          <ResearchHub />
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
      {isSimulationView && (isSingle || stage === "watch") && (
        <footer className="app-footer">
          <PlaybackControls
            snapshot={playbackEnvelope}
            isPlaying={activeIsPlaying}
            onPlay={handlePlay}
            onPause={handlePause}
            onStop={handleStop}
            simple={!isSingle}
            durationSeconds={duration}
          />
          {activeError && (
            <div className="error-banner" role="alert">
              {activeError}
            </div>
          )}
        </footer>
      )}

      {/* ── Toast Notification ────────────────────────────────────────── */}
      <div className="toast-region" role="status" aria-live="polite">
        {toastMessage && <div className="uf-toast">{toastMessage}</div>}
      </div>
    </div>
  );
}

// ── Navigation ─────────────────────────────────────────────────────────────

/** Client-side navigation for a same-document link, leaving modified clicks
 *  (new tab/window) to the browser. */
function ViewTab({
  view,
  current: isActive,
  children,
}: {
  view: RoutedView;
  current: boolean;
  children: ReactNode;
}) {
  const href = VIEW_ROUTES[view];
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
            Start a comparison
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
