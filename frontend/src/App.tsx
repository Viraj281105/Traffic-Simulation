import { useState, useEffect } from "react";
import { useWebSocketSnapshot } from "./hooks/useWebSocketSnapshot";
import { useSimulationPolling } from "./hooks/useSimulationPolling";
import { IntersectionMap } from "./components/IntersectionMap";
import { RoundaboutMap } from "./components/RoundaboutMap";
import { MetricsSidebar } from "./components/MetricsSidebar";
import {
  ComparativeDashboard,
  CompactVehicleStatePanel,
} from "./components/ComparativeDashboard";
import { PlaybackControls } from "./components/PlaybackControls";
import { HistoryDashboard, SavedReplay } from "./components/HistoryDashboard";
import { updateSimulationConfig } from "./services/api";
import type {
  LiveSnapshot,
  DualSnapshot,
  SimulationStatus,
} from "./types/simulation";
import "./App.css";

export function App() {
  const [viewMode, setViewMode] = useState<
    "signal" | "roundabout" | "comparative" | "single" | "history"
  >("comparative");
  const [activeReplay, setActiveReplay] = useState<SavedReplay | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => { setToastMessage(null); }, 3000);
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

  const [lastCompletedSnapshotDual, setLastCompletedSnapshotDual] =
    useState<DualSnapshot | null>(null);
  const [lastCompletedSnapshotSingle, setLastCompletedSnapshotSingle] =
    useState<LiveSnapshot | null>(null);
  const [prevDual, setPrevDual] = useState<DualSnapshot | null>(null);
  const [prevSingle, setPrevSingle] = useState<LiveSnapshot | null>(null);
  const [prevConfigKey, setPrevConfigKey] = useState("");

  const dualSnapshot = snapshot && "signal" in snapshot ? snapshot : null;
  const singleSnapshot = snapshot && !("signal" in snapshot) ? snapshot : null;

  // Capture the last snapshot with valid metrics/vehicles to display when initialized/stopped
  if (dualSnapshot !== prevDual) {
    setPrevDual(dualSnapshot);
    if (
      dualSnapshot &&
      (dualSnapshot.signal.simulationStatus === "running" ||
        dualSnapshot.signal.simulationStatus === "completed" ||
        dualSnapshot.signal.simulationStatus === "paused")
    ) {
      setLastCompletedSnapshotDual(dualSnapshot);
    }
  }

  if (singleSnapshot !== prevSingle) {
    setPrevSingle(singleSnapshot);
    if (
      singleSnapshot &&
      (singleSnapshot.simulationStatus === "running" ||
        singleSnapshot.simulationStatus === "completed" ||
        singleSnapshot.simulationStatus === "paused")
    ) {
      setLastCompletedSnapshotSingle(singleSnapshot);
    }
  }

  // Canvas config state
  const [lanes, setLanes] = useState(2);
  const [showStopLines, setShowStopLines] = useState(true);
  const [debug, setDebug] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);

  // Extra configurations
  const [arrivalRate, setArrivalRate] = useState(0.3);
  const [duration, setDuration] = useState(300);
  const [randomSeed, setRandomSeed] = useState<number>(
    () => Math.floor(Math.random() * 1000000) + 1,
  );

  const randomizeSeed = () => {
    setActiveReplay(null);
    setRandomSeed(Math.floor(Math.random() * 1000000) + 1);
  };

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

  // Determine displayed snapshot for metrics
  let metricsSnapshotDual: DualSnapshot | null = dualSnapshot;
  if (dualSnapshot) {
    if (
      (dualSnapshot.signal.simulationStatus === "initialized" ||
        dualSnapshot.signal.simulationStatus === "stopped") &&
      lastCompletedSnapshotDual
    ) {
      metricsSnapshotDual = lastCompletedSnapshotDual;
    }
  } else if (lastCompletedSnapshotDual) {
    metricsSnapshotDual = lastCompletedSnapshotDual;
  }

  let metricsSnapshotSingle: LiveSnapshot | null = singleSnapshot;
  if (singleSnapshot) {
    if (
      (singleSnapshot.simulationStatus === "initialized" ||
        singleSnapshot.simulationStatus === "stopped") &&
      lastCompletedSnapshotSingle
    ) {
      metricsSnapshotSingle = lastCompletedSnapshotSingle;
    }
  } else if (lastCompletedSnapshotSingle) {
    metricsSnapshotSingle = lastCompletedSnapshotSingle;
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
      : isDual && snapshot && "signal" in snapshot
        ? ({
            timestamp: snapshot.elapsed,
            tick: snapshot.tick,
            samplingFrequency: 10,
            simulationStatus: snapshot.signal.simulationStatus,
          } as unknown as LiveSnapshot)
        : (snapshot as LiveSnapshot | null);

  const handleSaveHistory = () => {
    let currentDuration = duration;
    if (viewMode === "comparative" && metricsSnapshotDual) {
      currentDuration = metricsSnapshotDual.elapsed || metricsSnapshotDual.signal.timestamp;
    } else if (viewMode !== "comparative" && metricsSnapshotSingle) {
      currentDuration = metricsSnapshotSingle.timestamp;
    } else if (playbackEnvelope?.timestamp) {
      currentDuration = playbackEnvelope.timestamp;
    }
    // Safeguard: if it's 0 for some reason, use the config duration
    if (!currentDuration) {
      currentDuration = duration;
    }

    const configToSave = {
      simulation: { duration: currentDuration, randomSeed },
      geometry: { intersectionType: viewMode === "roundabout" ? "roundabout" : "fixed_time_signal" },
      roads: { lanesPerApproach: { north: lanesNorth, south: lanesSouth, east: lanesEast, west: lanesWest } },
      traffic: { arrivalRate }
    };
    
    let metricsToSave: Record<string, unknown> = {};
    if (viewMode === "comparative" && metricsSnapshotDual) {
      metricsToSave = {
        signal: metricsSnapshotDual.signal.metrics,
        roundabout: metricsSnapshotDual.roundabout.metrics
      };
    } else if (viewMode !== "comparative" && metricsSnapshotSingle) {
      metricsToSave = (metricsSnapshotSingle as unknown as { metrics: Record<string, unknown> }).metrics;
    }

    const payload = {
      name: `${viewMode.toUpperCase()} Run - ${new Date().toLocaleTimeString()}`,
      config: configToSave,
      metrics: metricsToSave
    };

    fetch("http://localhost:8000/api/v1/replays", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
    .then(r => r.json())
    .then(() => {
      showToast("✅ Simulation saved to history!");
    })
    .catch((e: unknown) => { console.error(e); });
  };

  const handleReplay = (replay: SavedReplay) => {
    setActiveReplay(replay);
    setLanes(replay.config.roads?.lanesPerApproach?.north || 2);
    setArrivalRate(replay.config.traffic?.arrivalRate || 0.3);
    setDuration(replay.config.simulation?.duration || 300);
    setRandomSeed(replay.config.simulation?.randomSeed || 42);
    
    const isDual = replay.metrics.signal !== undefined && replay.metrics.roundabout !== undefined;
    if (isDual) {
      setViewMode("comparative");
    } else {
      const type = replay.config.geometry?.intersectionType;
      setViewMode(type === "roundabout" ? "roundabout" : "signal");
    }
  };

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
          <button
            className={`tab-btn ${viewMode === "history" ? "active" : ""}`}
            onClick={() => {
              setViewMode("history");
            }}
          >
            📚 History
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
            <div className="config-item">
              <label className="config-label">Random Seed</label>
              <div className="config-input-row">
                <input
                  type="number"
                  value={randomSeed}
                  onChange={(e) => {
                    setRandomSeed(parseInt(e.target.value, 10) || 1);
                  }}
                  className="config-num-input"
                  style={{
                    width: "90px",
                    padding: "4px 8px",
                    borderRadius: "4px",
                    border: "1px solid #444",
                    background: "#222",
                    color: "#fff",
                  }}
                />
                <button
                  type="button"
                  onClick={randomizeSeed}
                  className="pb-btn pb-secondary"
                  style={{
                    padding: "4px 8px",
                    fontSize: "12px",
                    marginLeft: "6px",
                  }}
                  title="Generate new random seed"
                >
                  🎲 Re-roll
                </button>
              </div>
            </div>
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
        <main
          className="app-main comparison-container"
          style={{ flexDirection: "column" }}
        >
          <div
            className="comparison-maps-row"
            style={{ display: "flex", flex: 1.2, minHeight: 0 }}
          >
            {/* Left Column: Fixed-Time Signal */}
            <div className="comparison-column" style={{ flex: 1 }}>
              <div className="column-header">
                <span className="column-title">
                  🚦 Fixed-Time Signal Control
                </span>
              </div>
              <div
                className="canvas-wrapper"
                style={{
                  display: "flex",
                  flexDirection: "row",
                  alignItems: "flex-start",
                  gap: "16px",
                  padding: "0 16px",
                }}
              >
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
                {metricsSnapshotDual && (
                  <CompactVehicleStatePanel
                    counts={metricsSnapshotDual.signal.vehicleCounts}
                  />
                )}
              </div>
            </div>

            {/* Right Column: Roundabout */}
            <div className="comparison-column" style={{ flex: 1 }}>
              <div className="column-header">
                <span className="column-title">🔄 Modern Roundabout</span>
              </div>
              <div
                className="canvas-wrapper"
                style={{
                  display: "flex",
                  flexDirection: "row",
                  alignItems: "flex-start",
                  gap: "16px",
                  padding: "0 16px",
                }}
              >
                <RoundaboutMap
                  snapshot={dualSnapshot?.roundabout ?? null}
                  laneWidth={laneWidth}
                  showCrosswalks={false}
                  debug={debug}
                  width={600}
                  height={450}
                />
                {metricsSnapshotDual && (
                  <CompactVehicleStatePanel
                    counts={{
                      ...metricsSnapshotDual.roundabout.vehicleCounts,
                      crossing:
                        metricsSnapshotDual.roundabout.vehicleCounts.crossing +
                        metricsSnapshotDual.roundabout.vehicleCounts
                          .inRoundabout,
                    }}
                  />
                )}
              </div>
            </div>
          </div>

          <div
            className="comparison-metrics-row"
            style={{
              flex: 1,
              minHeight: 0,
              borderTop: "1px solid var(--border)",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div style={{ padding: "8px 16px", display: "flex", justifyContent: "flex-end" }}>
              <button 
                className="pb-btn pb-primary" 
                onClick={handleSaveHistory}
                disabled={activeIsPlaying || activeReplay !== null}
                title={activeReplay ? "Cannot save a replay" : "Save this simulation to history"}
              >
                💾 Save to History
              </button>
            </div>
            <ComparativeDashboard
              snapshot={
                (activeReplay && activeReplay.metrics.signal && activeReplay.metrics.roundabout)
                  ? ({
                      signal: { metrics: activeReplay.metrics.signal },
                      roundabout: { metrics: activeReplay.metrics.roundabout },
                    } as unknown as DualSnapshot)
                  : metricsSnapshotDual
              }
              connectionStatus={activeConnectionStatus}
            />
          </div>
        </main>
      ) : viewMode === "history" ? (
        <main className="app-main" style={{ overflow: "hidden" }}>
          <HistoryDashboard onReplay={handleReplay} />
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
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div style={{ padding: "8px 16px", display: "flex", justifyContent: "flex-end" }}>
              <button 
                className="pb-btn pb-primary" 
                onClick={handleSaveHistory}
                disabled={activeIsPlaying || activeReplay !== null}
                title={activeReplay ? "Cannot save a replay" : "Save this simulation to history"}
              >
                💾 Save to History
              </button>
            </div>
            <MetricsSidebar
              snapshot={
                (activeReplay && viewMode !== "comparative" && "averageWaitTime" in activeReplay.metrics)
                  ? ({ metrics: activeReplay.metrics } as unknown as LiveSnapshot)
                  : metricsSnapshotSingle
              }
              connectionStatus={activeConnectionStatus}
            />
          </div>
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

      {/* ── Toast Notification ────────────────────────────────────────── */}
      {toastMessage && (
        <div className="toast-notification">
          {toastMessage}
        </div>
      )}
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
