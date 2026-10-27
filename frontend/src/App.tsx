import { Suspense, lazy, useState, useLayoutEffect } from "react";
import { useWebSocketSnapshot } from "./hooks/useWebSocketSnapshot";
import { useSimulationPolling } from "./hooks/useSimulationPolling";
import { useAuthSession } from "./hooks/useAuthSession";
import { useLiveConfigSync } from "./hooks/useLiveConfigSync";
import { useToast } from "./hooks/useToast";
import { useThemeMode } from "./theme/mode";
import { IntersectionMap } from "./components/IntersectionMap";
import { RoundaboutMap } from "./components/RoundaboutMap";
import { AdaptiveSignalStatus } from "./components/AdaptiveSignalStatus";
import { MeteredRoundaboutStatus } from "./components/MeteredRoundaboutStatus";
import { VehicleLegend } from "./components/VehicleLegend";
import { MetricsSidebar } from "./components/MetricsSidebar";
import {
  ComparativeDashboard,
  ComparisonPanel,
} from "./components/ComparativeDashboard";
import { PlaybackControls } from "./components/PlaybackControls";
import type { SavedReplay } from "./components/HistoryDashboard";
import { ConfigurationSidebar } from "./components/ConfigurationSidebar";
import { ResearchHub } from "./components/ResearchHub";
import {
  ScenarioSetup,
  type GuidedRunRequest,
} from "./components/guided/ScenarioSetup";
import { LiveGuide } from "./components/guided/LiveGuide";
import { ResultsReport } from "./components/guided/ResultsReport";
import { ComparisonMaps } from "./components/guided/ComparisonMaps";
import {
  contextsOf,
  sessionRunFrom,
  type SessionRun,
} from "./components/guided/comparisonRun";
import { StepNav, type GuidedStage } from "./components/guided/StepNav";
import "./components/guided/Guided.css";
import { ConfigToggle } from "./components/shell/ConfigToggle";
import { LoginDialog } from "./components/shell/LoginDialog";
import { MainNav, PlanNav, ResearchNav } from "./components/shell/Navigation";
import { NotFound } from "./components/shell/NotFound";
import {
  SIMULATION_VIEWS,
  SINGLE_VIEWS,
  sectionOf,
  type ViewMode,
} from "./components/shell/sections";
import { DEV_AUTH_BYPASS } from "./auth/cognito";
import {
  Sun,
  Moon,
  Settings2,
  Dices,
  LogIn,
  LogOut,
  CircleAlert,
  CircleCheck,
} from "lucide-react";
import { UrbanFlowLockup } from "./components/ui/UrbanFlowLogo";
import { PageTransition } from "./components/ui/PageTransition";
import { UrbanFlowLoader } from "./components/ui/Loader";
import type { SimulationConfigValues } from "./types/config";
import {
  DEFAULT_CONFIG_VALUES,
  dashboardPayload,
  sameConfigValues,
} from "./types/config";
import {
  saveReplay,
  setSimulationSpeed,
  setDualSimulationSpeed,
  createSuite,
  enqueueSuiteBatch,
} from "./services/api";
import { approachLanes } from "./scenario/scenarioModel";
import { isMeteredEntry } from "./scenario/scenarioTypes";
import { hasResults, sideSummary } from "./metrics/plainLanguage";
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

// Views outside the guided comparison load when first opened (the route
// loader already covers the switch), keeping them and Recharts out of the
// dashboard's first download.
const HistoryDashboard = lazy(() =>
  import("./components/HistoryDashboard").then((m) => ({
    default: m.HistoryDashboard,
  })),
);
const RunPage = lazy(() =>
  import("./components/RunPage").then((m) => ({ default: m.RunPage })),
);
const ComparePage = lazy(() =>
  import("./components/ComparePage").then((m) => ({ default: m.ComparePage })),
);
const VolumeAnalysisDashboard = lazy(() =>
  import("./components/VolumeAnalysisDashboard").then((m) => ({
    default: m.VolumeAnalysisDashboard,
  })),
);
const ValidationDashboard = lazy(() =>
  import("./components/ValidationDashboard").then((m) => ({
    default: m.ValidationDashboard,
  })),
);
const JunctionStudyPage = lazy(() =>
  import("./components/JunctionStudyPage").then((m) => ({
    default: m.JunctionStudyPage,
  })),
);
const ThreeWayStudyPage = lazy(() =>
  import("./components/ThreeWayStudyPage").then((m) => ({
    default: m.ThreeWayStudyPage,
  })),
);
const ScenarioPlanningDashboard = lazy(() =>
  import("./components/planning/ScenarioPlanningDashboard").then((m) => ({
    default: m.ScenarioPlanningDashboard,
  })),
);
const DiscoveryPage = lazy(() =>
  import("./components/discovery/DiscoveryPage").then((m) => ({
    default: m.DiscoveryPage,
  })),
);
const CopilotPage = lazy(() =>
  import("./components/copilot/CopilotPage").then((m) => ({
    default: m.CopilotPage,
  })),
);
const AdminPanel = lazy(() =>
  import("./components/AdminPanel").then((m) => ({ default: m.AdminPanel })),
);
const ExperimentPage = lazy(() =>
  import("./components/experiments/ExperimentPage").then((m) => ({
    default: m.ExperimentPage,
  })),
);
const PlannerPage = lazy(() =>
  import("./components/planner/PlannerPage").then((m) => ({
    default: m.PlannerPage,
  })),
);
const viewLoading = <UrbanFlowLoader label="Loading…" />;

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
      <Dashboard
        viewMode="history"
        page={{ kind: "run", runId: route.runId }}
      />
    );
  }
  if (route.kind === "compare") {
    return <Dashboard viewMode="history" page={{ kind: "compare" }} />;
  }
  // Robustness Lab experiments belong to the Plan section.
  if (route.kind === "experiment") {
    return (
      <Dashboard
        viewMode="planner"
        page={{ kind: "experiment", experimentId: route.experimentId }}
      />
    );
  }
  return <Dashboard viewMode={route.view} />;
}

const newSeed = () => Math.floor(Math.random() * 1000000) + 1;

/** Restores the exact UI configuration a run was saved with, falling back to
 *  the legacy fields older saves carry. */
function configFromReplay(
  replay: SavedReplay,
  current: SimulationConfigValues,
): SimulationConfigValues {
  if (replay.config.ui)
    return { ...DEFAULT_CONFIG_VALUES, ...replay.config.ui };
  const lanes = replay.config.roads?.lanesPerApproach?.north ?? current.lanes;
  return {
    ...current,
    lanes,
    laneWidth: replay.config.geometry?.laneWidth ?? current.laneWidth,
    arrivalRate: replay.config.traffic?.arrivalRate ?? current.arrivalRate,
    duration: replay.config.simulation?.duration ?? current.duration,
    randomSeed: replay.config.simulation?.randomSeed ?? current.randomSeed,
    // Saves without the dashboard configuration predate V1.3, whose signals
    // all ran the fixed timetable.
    signalControl: undefined,
    adaptive: null,
  };
}

type HistoryPage =
  | { kind: "run"; runId: string }
  | { kind: "compare" }
  | { kind: "experiment"; experimentId: string };

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
  const {
    isAuthenticated,
    userProfile,
    isAdmin,
    showLogin,
    openLogin,
    closeLogin,
    requireAuth,
    handleLoginSuccess,
    signOut,
  } = useAuthSession();

  const [activeReplay, setActiveReplay] = useState<SavedReplay | null>(null);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [showAnalyticsModal, setShowAnalyticsModal] = useState(false);
  const { toast, showToast } = useToast();
  const { isLight, toggleTheme } = useThemeMode();

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
    lanesEastWest,
    signalControl,
    scenario,
  } = configValues;
  const armLanes = approachLanes(configValues);

  const randomizeSeed = () => {
    setActiveReplay(null);
    setConfigValues((prev) => ({ ...prev, randomSeed: newSeed() }));
  };

  const isDual = viewMode === "comparative";
  const isSimulationView = SIMULATION_VIEWS.has(viewMode);

  const { playAfterSync } = useLiveConfigSync(viewMode, configValues, play);

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

  const handleGuidedRun = ({ isBatch, ...next }: GuidedRunRequest) => {
    if (isBatch) {
      const payload = dashboardPayload(next, "fixed_time_signal");
      const arrivalRates = [0.1, 0.2, 0.4, 0.8, 1.2];
      createSuite({
        name: `Batch Experiment - ${new Date().toLocaleTimeString()}`,
        description: "Batch experiment generated from dashboard.",
        run_ids: [],
        config_variations: { arrivalRate: arrivalRates },
      })
        .then((suite) =>
          enqueueSuiteBatch(suite.id, {
            baseConfig: payload,
            sweepParameters: { arrivalRate: arrivalRates },
            numSeeds: 3,
          }),
        )
        .then((res) => {
          showToast(`Batch enqueued! Job ID: ${res.jobId}`);
          navigate(VIEW_ROUTES.history);
        })
        .catch((e: unknown) => {
          console.error(e);
          showToast("Failed to enqueue batch experiment", "error");
        });
      return;
    }
    recordCurrentRun();
    setActiveReplay(null);
    setStage("watch");
    if (sameConfigValues(next, configValues)) {
      if (!isPlaying) play().catch(() => {});
      return;
    }
    playAfterSync();
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
    setPlaybackSpeed(1);
    if (viewMode === "single") {
      singleReset().catch(() => {});
    } else {
      stop().catch(() => {});
    }
  };

  const handleSpeedChange = (speed: number) => {
    setPlaybackSpeed(speed);
    if (viewMode === "single") {
      setSimulationSpeed(speed).catch(() => {});
    } else {
      setDualSimulationSpeed(speed).catch(() => {});
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
  const canSave =
    !activeIsPlaying && activeReplay === null && liveTimestamp > 0;

  const handleSaveHistory = () => {
    requireAuth(() => {
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
          showToast(
            "Could not save the run — is the backend reachable?",
            "error",
          );
        });
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

  // Each page (and each guided step) enters with the shared transition.
  const pageKey = [
    viewMode,
    viewMode === "comparative" ? stage : "",
    page?.kind ?? "",
    page?.kind === "run" ? page.runId : "",
    page?.kind === "experiment" ? page.experimentId : "",
  ].join(":");

  return (
    <div className="app">
      {/* ── Header ────────────────────────────────────────────────────── */}
      <header className="app-header">
        <div className="header-left">
          <a className="brand" href="/" data-testid="link-brand">
            <UrbanFlowLockup size={30} />
            <span className="sr-only">Home</span>
          </a>
        </div>

        <MainNav
          section={section}
          requireAuth={requireAuth}
          isAdmin={isAdmin}
        />

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
              <Settings2 size={16} aria-hidden="true" />
              <span className="label-text" aria-hidden="true">
                Scenario settings
              </span>
            </button>
          )}
          <button
            className="theme-button"
            type="button"
            onClick={toggleTheme}
            aria-label={
              isLight ? "Switch to dark mode" : "Switch to light mode"
            }
            title={isLight ? "Dark mode" : "Light mode"}
            data-testid="button-theme-toggle"
          >
            <span className="theme-icon" key={isLight ? "moon" : "sun"}>
              {isLight ? <Moon size={16} /> : <Sun size={16} />}
            </span>
          </button>

          {!isAuthenticated ? (
            <button type="button" className="header-signin" onClick={openLogin}>
              <LogIn size={15} aria-hidden="true" />
              Sign In
            </button>
          ) : (
            <div className="user-chip">
              <span className="user-avatar" aria-hidden="true">
                {(userProfile?.name || "U").charAt(0).toUpperCase()}
              </span>
              <span className="user-meta">
                <span className="user-name">{userProfile?.name || "User"}</span>
                <span className="user-email">{userProfile?.email || ""}</span>
              </span>
              {DEV_AUTH_BYPASS ? (
                <span
                  className="uf-badge dev-auth-badge"
                  title="Local development session: authentication is bypassed on the dev server only"
                >
                  DEV AUTH
                </span>
              ) : (
                <button
                  type="button"
                  className="uf-icon-btn user-logout"
                  onClick={signOut}
                  aria-label="Logout"
                  title="Logout"
                >
                  <LogOut aria-hidden="true" />
                </button>
              )}
            </div>
          )}
        </div>
        <span className="route-progress" aria-hidden="true" />
      </header>

      {/* ── Section sub-navigation ───────────────────────────────────── */}
      {section === "research" && <ResearchNav viewMode={viewMode} />}
      {section === "plan" && <PlanNav viewMode={viewMode} />}
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
              <Dices size={13} aria-hidden="true" />
              Seed: <strong>{randomSeed}</strong>
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
          <PageTransition
            transitionKey={pageKey}
            className="app-main full-screen page-scroll"
          >
            <ScenarioSetup
              config={configValues}
              onRun={handleGuidedRun}
              runInProgress={
                !activeReplay && liveTimestamp > 0 && !dualComplete
              }
            />
          </PageTransition>
        ) : stage === "results" ? (
          <PageTransition
            transitionKey={pageKey}
            className="app-main full-screen page-scroll"
          >
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
          </PageTransition>
        ) : (
          <PageTransition
            transitionKey={pageKey}
            className="app-main comparison-layout"
          >
            <h1 className="sr-only">
              Watch the traffic signal and the roundabout run side by side
            </h1>
            <ComparisonMaps
              snapshot={dualSnapshot}
              signalControl={signalControl}
              armLanes={armLanes}
              lanes={lanes}
              laneWidth={laneWidth}
              showStopLines={showStopLines}
              debug={debug}
            />
            <LiveGuide
              snapshot={dualSnapshot}
              meteredEntry={scenario ? isMeteredEntry(scenario) : false}
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
          </PageTransition>
        )
      ) : viewMode === "history" ? (
        <PageTransition
          transitionKey={pageKey}
          className="app-main full-screen page-scroll"
        >
          <Suspense fallback={viewLoading}>
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
          </Suspense>
        </PageTransition>
      ) : viewMode === "research" ? (
        <PageTransition
          transitionKey={pageKey}
          className="app-main full-screen page-scroll"
        >
          <ResearchHub />
        </PageTransition>
      ) : viewMode === "volume" ? (
        <PageTransition
          transitionKey={pageKey}
          className="app-main full-screen page-scroll"
        >
          <Suspense fallback={viewLoading}>
            <VolumeAnalysisDashboard />
          </Suspense>
        </PageTransition>
      ) : viewMode === "validation" ? (
        <PageTransition
          transitionKey={pageKey}
          className="app-main full-screen page-scroll"
        >
          <Suspense fallback={viewLoading}>
            <ValidationDashboard />
          </Suspense>
        </PageTransition>
      ) : viewMode === "junction" ? (
        <PageTransition
          transitionKey={pageKey}
          className="app-main full-screen page-scroll"
        >
          <Suspense fallback={viewLoading}>
            <JunctionStudyPage />
          </Suspense>
        </PageTransition>
      ) : viewMode === "threeWay" ? (
        <PageTransition
          transitionKey={pageKey}
          className="app-main full-screen page-scroll"
        >
          <Suspense fallback={viewLoading}>
            <ThreeWayStudyPage />
          </Suspense>
        </PageTransition>
      ) : viewMode === "scenarios" ? (
        <PageTransition
          transitionKey={pageKey}
          className="app-main full-screen page-scroll"
        >
          <Suspense fallback={viewLoading}>
            <ScenarioPlanningDashboard />
          </Suspense>
        </PageTransition>
      ) : viewMode === "discovery" ? (
        <PageTransition
          transitionKey={pageKey}
          className="app-main full-screen page-scroll"
        >
          <Suspense fallback={viewLoading}>
            <DiscoveryPage />
          </Suspense>
        </PageTransition>
      ) : viewMode === "copilot" ? (
        <PageTransition
          transitionKey={pageKey}
          className="app-main full-screen page-scroll"
        >
          <Suspense fallback={viewLoading}>
            <CopilotPage />
          </Suspense>
        </PageTransition>
      ) : viewMode === "planner" ? (
        <PageTransition
          transitionKey={pageKey}
          className="app-main full-screen page-scroll"
        >
          <Suspense fallback={viewLoading}>
            {page?.kind === "experiment" ? (
              <ExperimentPage
                key={page.experimentId}
                experimentId={page.experimentId}
              />
            ) : (
              <PlannerPage />
            )}
          </Suspense>
        </PageTransition>
      ) : viewMode === "admin" ? (
        <PageTransition
          transitionKey={pageKey}
          className="app-main full-screen page-scroll"
        >
          <Suspense fallback={viewLoading}>
            <AdminPanel />
          </Suspense>
        </PageTransition>
      ) : (
        <PageTransition transitionKey={pageKey} className="app-main">
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
                lanesNorth={armLanes.north}
                lanesSouth={armLanes.south}
                lanesEast={scenario ? armLanes.east : (lanesEastWest ?? lanes)}
                lanesWest={scenario ? armLanes.west : (lanesEastWest ?? lanes)}
                laneWidth={laneWidth}
                showCrosswalks={true}
                showStopLines={showStopLines}
                debug={debug}
              />
            )}
            <VehicleLegend snapshot={singleSnapshot} />
            {viewMode === "roundabout" ? (
              <MeteredRoundaboutStatus snapshot={singleSnapshot} />
            ) : (
              <AdaptiveSignalStatus snapshot={singleSnapshot} />
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
              config={replaySingle ? null : configValues}
              onApply={replaySingle ? undefined : handleApplyConfig}
              isRunning={activeIsPlaying}
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
        </PageTransition>
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
            playbackSpeed={playbackSpeed}
            onSpeedChange={handleSpeedChange}
            simple={!isSingle}
            durationSeconds={duration}
          />
          {activeError && (
            <div className="error-banner" role="alert">
              <CircleAlert size={15} aria-hidden="true" />
              {activeError}
            </div>
          )}
        </footer>
      )}

      {/* ── Toast Notification ────────────────────────────────────────── */}
      <div className="toast-region" role="status" aria-live="polite">
        {toast && (
          <div
            className={`toast-notification is-${toast.tone}`}
            key={toast.message}
          >
            {toast.tone === "error" ? (
              <CircleAlert size={17} aria-hidden="true" />
            ) : (
              <CircleCheck size={17} aria-hidden="true" />
            )}
            {toast.message}
          </div>
        )}
      </div>

      {showLogin && (
        <LoginDialog onClose={closeLogin} onLogin={handleLoginSuccess} />
      )}
    </div>
  );
}
