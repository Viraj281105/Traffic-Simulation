import { useState, useEffect } from "react";
import { useWebSocketSnapshot } from "./hooks/useWebSocketSnapshot";
import { useSimulationPolling } from "./hooks/useSimulationPolling";
import { IntersectionMap } from "./components/IntersectionMap";
import { RoundaboutMap } from "./components/RoundaboutMap";
import { IntersectionCanvas } from "./components/IntersectionCanvas";
import { MetricsSidebar } from "./components/MetricsSidebar";
import { PlaybackControls } from "./components/PlaybackControls";
import { updateSimulationConfig } from "./services/api";
import type {
  LiveSnapshot,
  DualSnapshot,
  SimulationStatus,
} from "./types/simulation";
import "./App.css";

export function App() {
  const [viewMode, setViewMode] = useState<"sandbox" | "single" | "comparison">(
    "sandbox",
  );

  // Determine path for WebSocket snapshot based on mode
  const wsPath =
    viewMode === "comparison" ? "/ws/simulation/dual" : "/ws/simulation/live";

  // WebSocket Live / Comparison Hook
  const {
    snapshot,
    connectionStatus,
    isPlaying,
    error: wsError,
    play,
    pause,
    stop,
  } = useWebSocketSnapshot(wsPath);

  // REST Polling Hook for Single Vehicle tracking
  const {
    vehicle: singleVehicle,
    status: singleStatus,
    isLoading: singleIsLoading,
    error: singleError,
    start: singleStart,
    stop: singleStop,
    reset: singleReset,
  } = useSimulationPolling();

  const [lastCompletedSnapshot, setLastCompletedSnapshot] = useState<
    LiveSnapshot | DualSnapshot | null
  >(null);
  const [prevSnapshot, setPrevSnapshot] = useState<
    LiveSnapshot | DualSnapshot | null
  >(null);
  const [prevConfigKey, setPrevConfigKey] = useState("");

  // Canvas and traffic config state
  const [lanesNorth, setLanesNorth] = useState(2);
  const [lanesSouth, setLanesSouth] = useState(2);
  const [lanesEast, setLanesEast] = useState(2);
  const [lanesWest, setLanesWest] = useState(2);
  const [laneWidth, setLaneWidth] = useState(3.5);
  const [intersectionSize, setIntersectionSize] = useState(15);
  const [showCrosswalks, setShowCrosswalks] = useState(true);
  const [showStopLines, setShowStopLines] = useState(true);
  const [debug, setDebug] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);
  const [intersectionType, setIntersectionType] = useState("fixed_time_signal");

  // Extra configurations
  const [arrivalRate, setArrivalRate] = useState(0.3);
  const [duration, setDuration] = useState(300);
  const [randomSeed, setRandomSeed] = useState(42);

  // Adjust state during render to avoid useEffect warnings
  const configKey = `${intersectionType}-${intersectionSize.toString()}-${laneWidth.toString()}-${lanesNorth.toString()}-${lanesSouth.toString()}-${lanesEast.toString()}-${lanesWest.toString()}-${arrivalRate.toString()}-${duration.toString()}-${randomSeed.toString()}`;

  if (configKey !== prevConfigKey) {
    setPrevConfigKey(configKey);
    setLastCompletedSnapshot(null);
  }

  if (snapshot !== prevSnapshot) {
    setPrevSnapshot(snapshot);
    const status =
      snapshot !== null
        ? "signal" in snapshot
          ? snapshot.signal.simulationStatus
          : snapshot.simulationStatus
        : null;
    if (snapshot && status === "completed") {
      setLastCompletedSnapshot(snapshot);
    }
  }

  const isDual = viewMode === "comparison";
  const status =
    snapshot !== null
      ? "signal" in snapshot
        ? snapshot.signal.simulationStatus
        : snapshot.simulationStatus
      : null;
  const metricsSnapshot =
    snapshot && status === "initialized" && lastCompletedSnapshot
      ? lastCompletedSnapshot
      : snapshot;

  // Sync config with backend on change (debounced to prevent flooding)
  useEffect(() => {
    const timer = setTimeout(() => {
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
    }, 500);
    return () => {
      clearTimeout(timer);
    };
  }, [
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
              <h1 className="header-title">Traffic Simulation</h1>
              <p className="header-sub">
                Fixed-Time Signal vs. Modern Roundabout
              </p>
            </div>
          </div>
        </div>

        {/* View Mode Switching Tabs */}
        <div className="view-mode-tabs" style={{ display: "flex", gap: "8px" }}>
          <button
            className={`tab-btn ${viewMode === "sandbox" ? "active" : ""}`}
            onClick={() => {
              setViewMode("sandbox");
            }}
            style={{
              background:
                viewMode === "sandbox" ? "var(--bg-hover)" : "transparent",
              color:
                viewMode === "sandbox"
                  ? "var(--text-primary)"
                  : "var(--text-secondary)",
              border: "1px solid var(--border)",
              borderBottom:
                viewMode === "sandbox"
                  ? "2px solid var(--accent-blue)"
                  : "1px solid var(--border)",
              borderRadius: "4px 4px 0 0",
              padding: "6px 14px",
              cursor: "pointer",
              fontSize: "12px",
              fontWeight: 600,
              transition: "all 0.15s",
            }}
          >
            Sandbox View
          </button>
          <button
            className={`tab-btn ${viewMode === "single" ? "active" : ""}`}
            onClick={() => {
              setViewMode("single");
            }}
            style={{
              background:
                viewMode === "single" ? "var(--bg-hover)" : "transparent",
              color:
                viewMode === "single"
                  ? "var(--text-primary)"
                  : "var(--text-secondary)",
              border: "1px solid var(--border)",
              borderBottom:
                viewMode === "single"
                  ? "2px solid var(--accent-blue)"
                  : "1px solid var(--border)",
              borderRadius: "4px 4px 0 0",
              padding: "6px 14px",
              cursor: "pointer",
              fontSize: "12px",
              fontWeight: 600,
              transition: "all 0.15s",
            }}
          >
            Single Vehicle Track
          </button>
          <button
            className={`tab-btn ${viewMode === "comparison" ? "active" : ""}`}
            onClick={() => {
              setViewMode("comparison");
            }}
            style={{
              background:
                viewMode === "comparison" ? "var(--bg-hover)" : "transparent",
              color:
                viewMode === "comparison"
                  ? "var(--text-primary)"
                  : "var(--text-secondary)",
              border: "1px solid var(--border)",
              borderBottom:
                viewMode === "comparison"
                  ? "2px solid var(--accent-blue)"
                  : "1px solid var(--border)",
              borderRadius: "4px 4px 0 0",
              padding: "6px 14px",
              cursor: "pointer",
              fontSize: "12px",
              fontWeight: 600,
              transition: "all 0.15s",
            }}
          >
            Dual Comparison
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
              label="Lanes North"
              value={lanesNorth}
              min={1}
              max={5}
              step={1}
              onChange={setLanesNorth}
            />
            <ConfigSlider
              label="Lanes South"
              value={lanesSouth}
              min={1}
              max={5}
              step={1}
              onChange={setLanesSouth}
            />
            <ConfigSlider
              label="Lanes East"
              value={lanesEast}
              min={1}
              max={5}
              step={1}
              onChange={setLanesEast}
            />
            <ConfigSlider
              label="Lanes West"
              value={lanesWest}
              min={1}
              max={5}
              step={1}
              onChange={setLanesWest}
            />
            <ConfigSlider
              label="Lane Width (m)"
              value={laneWidth}
              min={2}
              max={5}
              step={0.5}
              onChange={setLaneWidth}
            />
            <ConfigSlider
              label="Intersection (m)"
              value={intersectionSize}
              min={10}
              max={30}
              step={1}
              onChange={setIntersectionSize}
            />

            {/* Added Extra Parameters */}
            <ConfigSlider
              label="Arrival Rate (veh/s)"
              value={arrivalRate}
              min={0.1}
              max={2.0}
              step={0.1}
              onChange={setArrivalRate}
            />
            <ConfigSlider
              label="Duration (s)"
              value={duration}
              min={30}
              max={600}
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

            <div className="config-item">
              <label className="config-label">Intersection Type</label>
              <select
                className="config-select"
                value={intersectionType}
                onChange={(e) => {
                  setIntersectionType(e.target.value);
                }}
                disabled={viewMode === "comparison"} // Fixed in comparison
                style={{
                  background: "#2b2b2b",
                  color: "#fff",
                  border: "1px solid #444",
                  borderRadius: "4px",
                  padding: "6px 8px",
                  width: "100%",
                }}
              >
                <option value="fixed_time_signal">🚦 Fixed-Time Signal</option>
                <option value="roundabout">🔄 Roundabout</option>
              </select>
            </div>
            <ConfigToggle
              label="Crosswalks"
              value={showCrosswalks}
              onChange={setShowCrosswalks}
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
      <main className="app-main">
        {/* Render appropriate canvas based on the view mode */}
        <div className="canvas-wrapper">
          {viewMode === "single" ? (
            <IntersectionCanvas
              vehicle={singleVehicle}
              width={800}
              height={680}
            />
          ) : viewMode === "comparison" ? (
            <div className="dual-canvas-container">
              <div className="canvas-column">
                <h3>Fixed-Time Signal</h3>
                <IntersectionMap
                  snapshot={
                    isDual && snapshot
                      ? (snapshot as DualSnapshot).signal
                      : null
                  }
                  lanesNorth={lanesNorth}
                  lanesSouth={lanesSouth}
                  lanesEast={lanesEast}
                  lanesWest={lanesWest}
                  laneWidth={laneWidth}
                  intersectionSize={intersectionSize}
                  showCrosswalks={showCrosswalks}
                  showStopLines={showStopLines}
                  debug={debug}
                />
              </div>
              <div className="canvas-column">
                <h3>Roundabout</h3>
                <RoundaboutMap
                  snapshot={
                    isDual && snapshot
                      ? (snapshot as DualSnapshot).roundabout
                      : null
                  }
                  laneWidth={laneWidth}
                  showCrosswalks={showCrosswalks}
                  debug={debug}
                />
              </div>
            </div>
          ) : snapshot !== null &&
            "controller" in snapshot &&
            snapshot.controller.type === "roundabout" ? (
            <RoundaboutMap
              snapshot={snapshot}
              laneWidth={laneWidth}
              showCrosswalks={showCrosswalks}
              debug={debug}
            />
          ) : (
            <IntersectionMap
              snapshot={snapshot as LiveSnapshot | null}
              lanesNorth={lanesNorth}
              lanesSouth={lanesSouth}
              lanesEast={lanesEast}
              lanesWest={lanesWest}
              laneWidth={laneWidth}
              intersectionSize={intersectionSize}
              showCrosswalks={showCrosswalks}
              showStopLines={showStopLines}
              debug={debug}
            />
          )}
        </div>

        {/* Sidebar */}
        <MetricsSidebar
          snapshot={metricsSnapshot}
          connectionStatus={activeConnectionStatus}
        />
      </main>

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
