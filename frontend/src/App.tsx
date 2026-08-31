import { useState, useEffect } from "react";
import { useWebSocketSnapshot } from "./hooks/useWebSocketSnapshot";
import { useSimulationPolling } from "./hooks/useSimulationPolling";
import { IntersectionMap } from "./components/IntersectionMap";
import { RoundaboutMap } from "./components/RoundaboutMap";
import { MetricsSidebar } from "./components/MetricsSidebar";
import { PlaybackControls } from "./components/PlaybackControls";
import { updateSimulationConfig } from "./services/api";
import type { LiveSnapshot, DualSnapshot, SimulationStatus } from "./types/simulation";
import "./App.css";

export function App() {
  const [viewMode, setViewMode] = useState<
    "signal" | "roundabout" | "comparative"
  >("comparative");

  const mode = viewMode === "comparative" ? "dual" : "single";
  const { snapshot, connectionStatus, isPlaying, error: wsError, play, pause, stop } =
    useWebSocketSnapshot(mode);

  const {
    vehicle: singleVehicle,
    status: singleStatus,
    isLoading: singleIsLoading,
    error: singleError,
    start: singleStart,
    stop: singleStop,
    reset: singleReset,
  } = useSimulationPolling();

  const [lastCompletedSnapshotDual, setLastCompletedSnapshotDual] =
    useState<DualSnapshot | null>(null);
  const [lastCompletedSnapshotSingle, setLastCompletedSnapshotSingle] =
    useState<LiveSnapshot | null>(null);
  const [prevSnapshot, setPrevSnapshot] = useState<
    LiveSnapshot | DualSnapshot | null
  >(null);
  const [prevConfigKey, setPrevConfigKey] = useState("");

  const dualSnapshot = snapshot && "signal" in snapshot ? snapshot : null;
  const singleSnapshot = snapshot && !("signal" in snapshot) ? snapshot : null;

  // Canvas config state
  const [lanes, setLanes] = useState(2);
  const [showStopLines, setShowStopLines] = useState(true);
  const [debug, setDebug] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);

  // Extra configurations
  const [arrivalRate, setArrivalRate] = useState(0.3);
  const [duration, setDuration] = useState(300);
  const [randomSeed, setRandomSeed] = useState(42);

  // Dynamically compute width and intersection proportionally based on lanes count
  const lanesNorth = lanes;
  const lanesSouth = lanes;
  const lanesEast = lanes;
  const lanesWest = lanes;
  const laneWidth = 3.0 + (lanes - 1) * 0.5;
  const intersectionSize = lanes * laneWidth * 2 + 4.0;

  const isDual = viewMode === "comparative";

  // Adjust state during render to avoid useEffect warnings
  const configKey = lanes.toString();

  if (configKey !== prevConfigKey) {
    setPrevConfigKey(configKey);
    setLastCompletedSnapshotDual(null);
    setLastCompletedSnapshotSingle(null);
  }

  if (snapshot !== prevSnapshot) {
    setPrevSnapshot(snapshot);
    if (snapshot) {
      if ("signal" in snapshot) {
        if (snapshot.signal.simulationStatus === "completed") {
          setLastCompletedSnapshotDual(snapshot);
        }
      } else {
        if (snapshot.simulationStatus === "completed") {
          setLastCompletedSnapshotSingle(snapshot);
        }
      }
    }
  }

  // Determine displayed snapshot for metrics
  let metricsSnapshotDual: DualSnapshot | null = dualSnapshot;
  if (dualSnapshot) {
    if (
      dualSnapshot.signal.simulationStatus === "initialized" &&
      lastCompletedSnapshotDual
    ) {
      metricsSnapshotDual = lastCompletedSnapshotDual;
    }
  }

  let metricsSnapshotSingle: LiveSnapshot | null = singleSnapshot;
  if (singleSnapshot) {
    if (
      singleSnapshot.simulationStatus === "initialized" &&
      lastCompletedSnapshotSingle
    ) {
      metricsSnapshotSingle = lastCompletedSnapshotSingle;
    }
  }

  // Sync config with backend on change (debounced to prevent flooding)
  useEffect(() => {
    const intersectionType =
      viewMode === "roundabout" ? "roundabout" : "fixed_time_signal";
    updateSimulationConfig({
      intersectionType,
      intersectionSize,
      laneWidth,
      lanesNorth,
      lanesSouth,
      lanesEast,
      lanesWest,
      arrivalRate,
      duration,
      randomSeed,
    }).catch((err: unknown) => {
      console.error("Failed to update backend config:", err);
    });
  }, [
    viewMode,
    lanes,
    intersectionSize,
    laneWidth,
    lanesNorth,
    lanesSouth,
    lanesEast,
    lanesWest,
    arrivalRate,
    duration,
    randomSeed,
  ]);

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
      : isDual && snapshot
        ? ({
            timestamp: (snapshot as DualSnapshot).elapsed,
            tick: (snapshot as DualSnapshot).tick,
            samplingFrequency: 10,
            simulationStatus: (snapshot as DualSnapshot).signal
              .simulationStatus,
          } as unknown as LiveSnapshot)
        : (snapshot as LiveSnapshot | null);

  return (
    <div className="app">
      {/* ── Header ────────────────────────────────────────────────────── */}
      <header className="app-header">
        <div className="header-left">
          <div className="header-logo">
            <span className="logo-icon">🚦</span>
            <div>
              <h1 className="header-title">Traffic Simulation Comparison</h1>
              <p className="header-sub">
                Fixed-Time Signal vs. Modern Roundabout
              </p>
            </div>
          </div>
        </div>

        {/* View Mode Tabs */}
        <div className="header-tabs">
          <button
            className={`tab-btn ${viewMode === "signal" ? "active" : ""}`}
            onClick={() => {
              setViewMode("signal");
            }}
          >
            🚦 Fixed-Time Signal Only
          </button>
          <button
            className={`tab-btn ${viewMode === "roundabout" ? "active" : ""}`}
            onClick={() => {
              setViewMode("roundabout");
            }}
          >
            🔄 Roundabout Only
          </button>
          <button
            className={`tab-btn ${viewMode === "comparative" ? "active" : ""}`}
            onClick={() => {
              setViewMode("comparative");
            }}
          >
            📊 Comparative View
          </button>
        </div>

        <div className="header-right">
          <button
            className="config-toggle-btn"
            onClick={() => {
              setConfigOpen((v) => !v);
            }}
          >
            ⚙ Map Config
          </button>
        </div>
      </header>

      {/* ── Config panel (collapsible) ────────────────────────────────── */}
      {configOpen && (
        <div className="config-panel">
          <div className="config-grid">
            <ConfigSlider
              label="Lanes"
              value={lanes}
              min={1}
              max={5}
              step={1}
              onChange={setLanes}
            />
            <ConfigSlider
              label="Arrival Rate"
              value={arrivalRate}
              min={0.1}
              max={1.0}
              step={0.05}
              onChange={setArrivalRate}
            />
            <ConfigSlider
              label="Duration (s)"
              value={duration}
              min={60}
              max={900}
              step={10}
              onChange={setDuration}
            />
            <ConfigSlider
              label="Random Seed"
              value={randomSeed}
              min={1}
              max={100}
              step={1}
              onChange={setRandomSeed}
            />
            <ConfigToggle
              label="Stop Lines"
              value={showStopLines}
              onChange={setShowStopLines}
            />
            <ConfigToggle
              label="Debug Queues"
              value={debug}
              onChange={setDebug}
            />
          </div>
        </div>
      )}

      {/* ── Main content ──────────────────────────────────────────────── */}
      {viewMode === "comparative" ? (
        <main className="app-main comparison-container">
          {/* Left Column: Fixed-Time Signal */}
          <div className="comparison-column">
            <div className="column-header">
              <span className="column-title">🚦 Fixed-Time Signal Control</span>
            </div>
            <div className="canvas-wrapper">
              <IntersectionMap
                snapshot={dualSnapshot?.signal ?? null}
                lanesNorth={lanesNorth}
                lanesSouth={lanesSouth}
                lanesEast={lanesEast}
                lanesWest={lanesWest}
                laneWidth={laneWidth}
                intersectionSize={intersectionSize}
                showCrosswalks={true}
                showStopLines={showStopLines}
                debug={debug}
                width={600}
                height={450}
              />
            </div>
            <div className="sidebar-container">
              <MetricsSidebar
                snapshot={metricsSnapshotDual?.signal ?? null}
                connectionStatus={activeConnectionStatus}
                hideHeader={true}
              />
            </div>
          </div>

          {/* Right Column: Roundabout */}
          <div className="comparison-column">
            <div className="column-header">
              <span className="column-title">🔄 Modern Roundabout</span>
            </div>
            <div className="canvas-wrapper">
              <RoundaboutMap
                snapshot={dualSnapshot?.roundabout ?? null}
                laneWidth={laneWidth}
                showCrosswalks={false}
                debug={debug}
                width={600}
                height={450}
              />
            </div>
            <div className="sidebar-container">
              <MetricsSidebar
                snapshot={metricsSnapshotDual?.roundabout ?? null}
                connectionStatus={activeConnectionStatus}
                hideHeader={true}
              />
            </div>
          </div>
        </main>
      ) : (
        <main className="app-main">
          <div className="canvas-wrapper">
            {viewMode === "roundabout" ? (
              <RoundaboutMap
                snapshot={singleSnapshot}
                laneWidth={laneWidth}
                showCrosswalks={false}
                debug={debug}
              />
            ) : (
              <IntersectionMap
                snapshot={singleSnapshot}
                lanesNorth={lanesNorth}
                lanesSouth={lanesSouth}
                lanesEast={lanesEast}
                lanesWest={lanesWest}
                laneWidth={laneWidth}
                intersectionSize={intersectionSize}
                showCrosswalks={true}
                showStopLines={showStopLines}
                debug={debug}
              />
            )}
          </div>
          <MetricsSidebar
            snapshot={metricsSnapshotSingle}
            connectionStatus={activeConnectionStatus}
          />
        </main>
      )}

      {/* ── Playback controls ─────────────────────────────────────────── */}
      <footer className="app-footer">
        <PlaybackControls
          snapshot={playbackEnvelope}
          isPlaying={activeIsPlaying}
          onPlay={handlePlay}
          onPause={handlePause}
          onStop={handleStop}
        />
        {activeError && <div className="error-banner">⚠ {activeError}</div>}
      </footer>
    </div>
  );
}

// ── Config helpers ─────────────────────────────────────────────────────────

function ConfigSlider({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="config-item">
      <label className="config-label">{label}</label>
      <div className="config-input-row">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => {
            onChange(parseFloat(e.target.value));
          }}
          className="config-range"
        />
        <span className="config-val">{value}</span>
      </div>
    </div>
  );
}

function ConfigToggle({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="config-item config-toggle-item">
      <label className="config-label">{label}</label>
      <button
        className={`toggle-btn ${value ? "toggle-on" : "toggle-off"}`}
        onClick={() => {
          onChange(!value);
        }}
      >
        {value ? "ON" : "OFF"}
      </button>
    </div>
  );
}
