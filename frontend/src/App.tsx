import { useState } from "react";
import { useWebSocketSnapshot } from "./hooks/useWebSocketSnapshot";
import { IntersectionMap } from "./components/IntersectionMap";
import { MetricsSidebar } from "./components/MetricsSidebar";
import { PlaybackControls } from "./components/PlaybackControls";
import "./App.css";

export function App() {
  const { snapshot, connectionStatus, isPlaying, error, play, pause } =
    useWebSocketSnapshot();

  // Canvas config state
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
        {/* Canvas */}
        <div className="canvas-wrapper">
          <IntersectionMap
            snapshot={snapshot}
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

        {/* Sidebar */}
        <MetricsSidebar
          snapshot={snapshot}
          connectionStatus={connectionStatus}
        />
      </main>

      {/* ── Playback controls ─────────────────────────────────────────── */}
      <footer className="app-footer">
        <PlaybackControls
          snapshot={snapshot}
          isPlaying={isPlaying}
          onPlay={() => {
            void play();
          }}
          onPause={() => {
            void pause();
          }}
        />
        {error && <div className="error-banner">⚠ {error}</div>}
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
