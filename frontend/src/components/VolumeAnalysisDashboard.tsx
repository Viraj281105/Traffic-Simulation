import { BookOpen, ChartSpline, Microscope, TriangleAlert } from "lucide-react";
import React, { useState, useEffect, useCallback, useMemo } from "react";
import { getSweep, listSweeps } from "../services/api";
import { STUDY_JOB_ROUTES } from "../services/studyJobs";
import { useStudyJob } from "../hooks/useStudyJob";
import "./VolumeAnalysisDashboard.css";
import { LoaderMark } from "./ui/Loader";
import { StudyProgress } from "./ui/StudyProgress";
import { AdvancedConfigDrawer } from "./volume/AdvancedConfigDrawer";
import { CurvesTab, type MetricView } from "./volume/CurvesTab";
import { DemandScrubber } from "./volume/DemandScrubber";
import { EmptySweepHero } from "./volume/EmptySweepHero";
import { InsightsTab } from "./volume/InsightsTab";
import { MatrixTab, type WinnerFilter } from "./volume/MatrixTab";
import { SavedSweepsDrawer } from "./volume/SavedSweepsDrawer";
import { SweepHeader } from "./volume/SweepHeader";
import { SweepOverview } from "./volume/SweepOverview";
import type { XAxisMode } from "./volume/SweepTooltip";
import {
  DEFAULT_SWEEP_CONFIG,
  buildChartData,
  closestRun,
  defaultScrubberVolume,
  parseSweepSession,
  sweepCsv,
  sweepCustomConfig,
  sweepTierRates,
  tierTally,
  type SavedSweep,
  type SweepConfig,
  type SweepSession,
} from "./volumeSweepModel";

type StudioTab = "curves" | "matrix" | "insights";

// ── Main Component ──────────────────────────────────────────────────────────
//
// Owns the sweep form, the job, the loaded session and every view toggle (so
// a tab keeps its settings when the user switches away and back). The
// sections it renders live in ./volume/ and the data transforms in
// ./volumeSweepModel.

export const VolumeAnalysisDashboard: React.FC = () => {
  const [savedSweeps, setSavedSweeps] = useState<SavedSweep[]>([]);
  const [activeSession, setActiveSession] = useState<SweepSession | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Tab & View Controls
  const [activeTab, setActiveTab] = useState<StudioTab>("curves");
  const [showAdvancedDrawer, setShowAdvancedDrawer] = useState(false);
  const [showHistoryDrawer, setShowHistoryDrawer] = useState(false);

  // Sweep config form state: duration and seed in the header, the rest in
  // the advanced drawer
  const [config, setConfig] = useState<SweepConfig>(DEFAULT_SWEEP_CONFIG);
  const updateConfig = useCallback((patch: Partial<SweepConfig>) => {
    setConfig((prev) => ({ ...prev, ...patch }));
  }, []);

  // Scrubber volume override state
  const [scrubberVolumeOverride, setScrubberVolumeOverride] = useState<
    number | null
  >(null);

  // Interactive UI view controls
  const [metricView, setMetricView] = useState<MetricView>("delay");
  const [xAxisMode, setXAxisMode] = useState<XAxisMode>("volume");
  const [showUncertaintyBands, setShowUncertaintyBands] = useState(true);
  const [showDeltaTrend, setShowDeltaTrend] = useState(false);
  const [filterWinner, setFilterWinner] = useState<WinnerFilter>("all");

  const [isRunning, setIsRunning] = useState(false);
  const [sweepError, setSweepError] = useState<string | null>(null);
  const [loadingSession, setLoadingSession] = useState(false);
  const study = useStudyJob();

  const ratesConfig = useMemo(
    () => sweepTierRates(config.demandTierPreset, config.lanesCount),
    [config.demandTierPreset, config.lanesCount],
  );

  // Load a specific sweep session
  const loadSweep = useCallback((id: string) => {
    setSelectedId(id);
    setLoadingSession(true);
    setShowHistoryDrawer(false);
    setShowAdvancedDrawer(false);
    getSweep(id)
      .then((data) => {
        setActiveSession(
          parseSweepSession(data, {
            sessionId: id,
            name: "Saved Sweep",
            duration: 60,
            randomSeed: 42,
          }),
        );
        setScrubberVolumeOverride(null);
        setLoadingSession(false);
      })
      .catch(() => {
        setLoadingSession(false);
        setSweepError("Failed to load sweep results.");
      });
  }, []);

  // Fetch saved sweep list
  const fetchSweeps = useCallback(() => {
    listSweeps<SavedSweep[]>()
      .then((data) => {
        setSavedSweeps(data);
      })
      .catch(() => {
        setSavedSweeps([]);
      });
  }, []);

  useEffect(() => {
    fetchSweeps();
  }, [fetchSweeps]);

  // Trigger new sweep via API
  const runSweep = () => {
    setIsRunning(true);
    setSweepError(null);
    setShowAdvancedDrawer(false);
    setShowHistoryDrawer(false);

    study
      .run(STUDY_JOB_ROUTES.sweep, {
        duration: config.duration,
        randomSeed: config.randomSeed,
        arrivalRates: ratesConfig.rates,
        name: `Sweep (${ratesConfig.rates.length.toString()} tiers, ${config.duration.toString()}s)`,
        customConfig: sweepCustomConfig(config),
      })
      .then((data) => {
        const session = parseSweepSession(data, {
          sessionId: "session",
          name: "Completed Sweep",
          duration: config.duration,
          randomSeed: config.randomSeed,
        });
        setActiveSession(session);
        setSelectedId(session.sessionId);
        setScrubberVolumeOverride(null);
        setIsRunning(false);
        fetchSweeps();
      })
      .catch((e: unknown) => {
        setSweepError(e instanceof Error ? e.message : "Sweep failed");
        setIsRunning(false);
      });
  };

  // Export CSV helper
  const exportCSV = () => {
    if (!activeSession || !Array.isArray(activeSession.runs)) return;
    const csvContent =
      "data:text/csv;charset=utf-8," + sweepCsv(activeSession.runs);
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute(
      "download",
      `traffic_volume_sweep_${activeSession.sessionId.slice(0, 8)}.csv`,
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // The two drawers are mutually exclusive
  const toggleAdvancedDrawer = () => {
    setShowAdvancedDrawer((prev) => !prev);
    setShowHistoryDrawer(false);
  };
  const toggleHistoryDrawer = () => {
    setShowHistoryDrawer((prev) => !prev);
    setShowAdvancedDrawer(false);
  };

  const chartData = activeSession ? buildChartData(activeSession) : [];
  const crossover = activeSession?.curves.crossoverHourlyVolume ?? null;

  const runsList = useMemo(() => {
    if (activeSession && Array.isArray(activeSession.runs)) {
      return activeSession.runs;
    }
    return [];
  }, [activeSession]);

  const tally = tierTally(runsList);

  // Scrubber min/max & closest run computation
  const minVol = runsList[0]?.hourlyVolumeVehPerHour ?? 360;
  const maxVol = runsList[runsList.length - 1]?.hourlyVolumeVehPerHour ?? 2880;

  const currentScrubberVolume = useMemo(
    () =>
      scrubberVolumeOverride ?? defaultScrubberVolume(activeSession, runsList),
    [activeSession, scrubberVolumeOverride, runsList],
  );

  const currentScrubberRun = useMemo(
    () => closestRun(runsList, currentScrubberVolume),
    [runsList, currentScrubberVolume],
  );

  return (
    <div className="volume-dashboard">
      {/* ── Top Executive Header ───────────────────────── */}
      <SweepHeader
        config={config}
        onChange={updateConfig}
        onRun={runSweep}
        isRunning={isRunning}
        advancedOpen={showAdvancedDrawer}
        historyOpen={showHistoryDrawer}
        onToggleAdvanced={toggleAdvancedDrawer}
        onToggleHistory={toggleHistoryDrawer}
        savedCount={savedSweeps.length}
        canExport={activeSession !== null}
        onExport={exportCSV}
      />

      {/* ── Advanced Configuration Drawer ── */}
      {showAdvancedDrawer && (
        <AdvancedConfigDrawer
          config={config}
          onChange={updateConfig}
          tierCount={ratesConfig.rates.length}
          onReset={() => {
            setConfig(DEFAULT_SWEEP_CONFIG);
          }}
          onClose={() => {
            setShowAdvancedDrawer(false);
          }}
          onRun={runSweep}
          isRunning={isRunning}
        />
      )}

      {/* ── Saved Sweeps History Drawer ── */}
      {showHistoryDrawer && (
        <SavedSweepsDrawer
          sweeps={savedSweeps}
          selectedId={selectedId}
          onSelect={loadSweep}
          onClose={() => {
            setShowHistoryDrawer(false);
          }}
        />
      )}

      {/* ── Running / Status Feedback ── */}
      {isRunning && (
        <StudyProgress
          title={`Volume sweep · ${ratesConfig.rates.length.toString()} tiers × ${config.duration.toString()}s, signal and roundabout`}
          progress={study.progress}
        />
      )}

      {sweepError && (
        <div className="sweep-error-banner">
          <TriangleAlert size={14} aria-hidden="true" className="uf-glyph" />{" "}
          {sweepError}
        </div>
      )}

      {/* ── Loading indicator ──────────────────────────── */}
      {loadingSession && (
        <div className="sweep-loading">
          <LoaderMark />
          <span>Retrieving sweep curves and telemetry…</span>
        </div>
      )}

      {/* ── Empty State Hero (When No Active Session) ── */}
      {!activeSession && !loadingSession && !isRunning && (
        <EmptySweepHero
          tierCount={ratesConfig.rates.length}
          savedCount={savedSweeps.length}
          isRunning={isRunning}
          onRun={runSweep}
          onOpenAdvanced={() => {
            setShowAdvancedDrawer(true);
            setShowHistoryDrawer(false);
          }}
          onOpenHistory={() => {
            setShowHistoryDrawer(true);
            setShowAdvancedDrawer(false);
          }}
        />
      )}

      {/* ── Active Results View ───────────────────────── */}
      {activeSession && !loadingSession && (
        <>
          <SweepOverview
            session={activeSession}
            runs={runsList}
            crossover={crossover}
            tally={tally}
          />

          {/* ── Studio Navigation Tabs ─────────────────── */}
          <div className="studio-tabs-bar">
            <button
              type="button"
              className={`studio-tab-btn ${activeTab === "curves" ? "active" : ""}`}
              onClick={() => {
                setActiveTab("curves");
              }}
            >
              <ChartSpline size={14} aria-hidden="true" className="uf-glyph" />{" "}
              Interactive Curves & Crossover Studio
            </button>
            <button
              type="button"
              className={`studio-tab-btn ${activeTab === "matrix" ? "active" : ""}`}
              onClick={() => {
                setActiveTab("matrix");
              }}
            >
              <Microscope size={14} aria-hidden="true" className="uf-glyph" />{" "}
              Head-to-Head Volume Matrix
            </button>
            <button
              type="button"
              className={`studio-tab-btn ${activeTab === "insights" ? "active" : ""}`}
              onClick={() => {
                setActiveTab("insights");
              }}
            >
              <BookOpen size={14} aria-hidden="true" className="uf-glyph" /> How
              to read this sweep
            </button>
          </div>

          {/* ── Interactive Volume Scrubber Bar ───────── */}
          {activeTab !== "insights" && currentScrubberRun && (
            <DemandScrubber
              run={currentScrubberRun}
              volume={currentScrubberVolume}
              minVol={minVol}
              maxVol={maxVol}
              crossover={crossover}
              onVolumeChange={setScrubberVolumeOverride}
            />
          )}

          {/* ── TAB 1: Curves & Crossover Studio ───────── */}
          {activeTab === "curves" && (
            <CurvesTab
              chartData={chartData}
              crossover={crossover}
              metricView={metricView}
              onMetricViewChange={setMetricView}
              xAxisMode={xAxisMode}
              onXAxisModeChange={setXAxisMode}
              showUncertaintyBands={showUncertaintyBands}
              onShowUncertaintyBandsChange={setShowUncertaintyBands}
              showDeltaTrend={showDeltaTrend}
              onShowDeltaTrendChange={setShowDeltaTrend}
            />
          )}

          {/* ── TAB 2: Head-to-Head Volume Matrix ──────── */}
          {activeTab === "matrix" && (
            <MatrixTab
              session={activeSession}
              runs={runsList}
              tally={tally}
              filterWinner={filterWinner}
              onFilterWinnerChange={setFilterWinner}
            />
          )}

          {/* ── TAB 3: How to read this sweep ─ */}
          {activeTab === "insights" && (
            <InsightsTab
              session={activeSession}
              runs={runsList}
              crossover={crossover}
              tally={tally}
            />
          )}
        </>
      )}
    </div>
  );
};
