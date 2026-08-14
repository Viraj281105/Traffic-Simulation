import { useState } from "react";
import { useSimulationPolling } from "./hooks/useSimulationPolling";
import { IntersectionCanvas } from "./components/IntersectionCanvas";
import { IntersectionMap } from "./components/IntersectionMap";
import "./App.css";

export function App() {
  const { vehicle, status, isLoading, error, start, stop, reset } =
    useSimulationPolling();
  const [canvasSize] = useState({ width: 800, height: 600 });

  // Config State
  const [viewMode, setViewMode] = useState<"map" | "canvas">("map");
  const [lanesNorth, setLanesNorth] = useState(2);
  const [lanesSouth, setLanesSouth] = useState(2);
  const [lanesEast, setLanesEast] = useState(2);
  const [lanesWest, setLanesWest] = useState(2);
  const [laneWidth, setLaneWidth] = useState(3.5);
  const [intersectionSize, setIntersectionSize] = useState(15);
  const [showCrosswalks, setShowCrosswalks] = useState(true);
  const [showStopLines, setShowStopLines] = useState(true);
  const [debug, setDebug] = useState(false);

  const handleStart = () => {
    start().catch((err: unknown) => {
      console.error("Failed to start simulation:", err);
    });
  };

  const handleStop = () => {
    stop().catch((err: unknown) => {
      console.error("Failed to stop simulation:", err);
    });
  };

  const handleReset = () => {
    reset().catch((err: unknown) => {
      console.error("Failed to reset simulation:", err);
    });
  };

  const activeVehicles = vehicle ? [vehicle] : [];

  return (
    <div className="app">
      <header className="app-header">
        <h1>Traffic Simulation</h1>
        <p>Single Vehicle at Signalized Intersection</p>
      </header>

      <main className="app-main">
        <div className="canvas-container">
          {viewMode === "map" ? (
            <IntersectionMap
              vehicles={activeVehicles}
              status={status}
              width={canvasSize.width}
              height={canvasSize.height}
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
          ) : (
            <IntersectionCanvas
              vehicle={vehicle}
              width={canvasSize.width}
              height={canvasSize.height}
            />
          )}
        </div>

        <div className="control-panel">
          <div className="status-section">
            <h2>Simulation Status</h2>
            <div className="status-info">
              <div className={`status-badge status-${status}`}>
                {status.toUpperCase()}
              </div>
              {vehicle && (
                <>
                  <p>
                    <strong>Sim Time:</strong> {vehicle.sim_time.toFixed(2)}s
                  </p>
                  <p>
                    <strong>Tick:</strong> {vehicle.tick}
                  </p>
                  <p>
                    <strong>Vehicle State:</strong> {vehicle.state}
                  </p>
                </>
              )}
            </div>
          </div>

          <div className="controls-section">
            <h2>Controls</h2>
            <div className="button-group">
              <button
                onClick={handleStart}
                disabled={status === "running" || isLoading}
                className="btn btn-primary"
              >
                {isLoading ? "Starting..." : "Start"}
              </button>
              <button
                onClick={handleStop}
                disabled={status === "stopped" || isLoading}
                className="btn btn-secondary"
              >
                Stop
              </button>
              <button
                onClick={handleReset}
                disabled={isLoading}
                className="btn btn-tertiary"
              >
                Reset
              </button>
            </div>
          </div>

          <div className="config-section">
            <h2>Map Configuration</h2>
            <div className="view-toggle">
              <button
                onClick={() => {
                  setViewMode("map");
                }}
                className={`btn ${viewMode === "map" ? "btn-primary" : "btn-tertiary"}`}
                style={{ flex: 1, padding: "8px" }}
              >
                Symmetrical Map
              </button>
              <button
                onClick={() => {
                  setViewMode("canvas");
                }}
                className={`btn ${viewMode === "canvas" ? "btn-primary" : "btn-tertiary"}`}
                style={{ flex: 1, padding: "8px" }}
              >
                Classic Canvas
              </button>
            </div>
            {viewMode === "map" && (
              <div className="config-group">
                <div className="config-item">
                  <label>Lanes North</label>
                  <input
                    type="number"
                    min={1}
                    max={5}
                    value={lanesNorth}
                    onChange={(e) => {
                      setLanesNorth(Math.max(1, parseInt(e.target.value) || 1));
                    }}
                  />
                </div>
                <div className="config-item">
                  <label>Lanes South</label>
                  <input
                    type="number"
                    min={1}
                    max={5}
                    value={lanesSouth}
                    onChange={(e) => {
                      setLanesSouth(Math.max(1, parseInt(e.target.value) || 1));
                    }}
                  />
                </div>
                <div className="config-item">
                  <label>Lanes East</label>
                  <input
                    type="number"
                    min={1}
                    max={5}
                    value={lanesEast}
                    onChange={(e) => {
                      setLanesEast(Math.max(1, parseInt(e.target.value) || 1));
                    }}
                  />
                </div>
                <div className="config-item">
                  <label>Lanes West</label>
                  <input
                    type="number"
                    min={1}
                    max={5}
                    value={lanesWest}
                    onChange={(e) => {
                      setLanesWest(Math.max(1, parseInt(e.target.value) || 1));
                    }}
                  />
                </div>
                <div className="config-item">
                  <label>Lane Width (m)</label>
                  <input
                    type="number"
                    step={0.1}
                    min={2}
                    max={5}
                    value={laneWidth}
                    onChange={(e) => {
                      setLaneWidth(
                        Math.max(2, parseFloat(e.target.value) || 3.5),
                      );
                    }}
                  />
                </div>
                <div className="config-item">
                  <label>Intersection Size (m)</label>
                  <input
                    type="number"
                    min={10}
                    max={30}
                    value={intersectionSize}
                    onChange={(e) => {
                      setIntersectionSize(
                        Math.max(10, parseInt(e.target.value) || 15),
                      );
                    }}
                  />
                </div>
                <div className="config-item">
                  <label>Show Crosswalks</label>
                  <input
                    type="checkbox"
                    checked={showCrosswalks}
                    onChange={(e) => {
                      setShowCrosswalks(e.target.checked);
                    }}
                  />
                </div>
                <div className="config-item">
                  <label>Show Stop Lines</label>
                  <input
                    type="checkbox"
                    checked={showStopLines}
                    onChange={(e) => {
                      setShowStopLines(e.target.checked);
                    }}
                  />
                </div>
                <div className="config-item">
                  <label>Debug Lane Queues</label>
                  <input
                    type="checkbox"
                    checked={debug}
                    onChange={(e) => {
                      setDebug(e.target.checked);
                    }}
                  />
                </div>
              </div>
            )}
          </div>

          {error && (
            <div className="error-section">
              <h3>Error</h3>
              <p className="error-message">{error}</p>
            </div>
          )}

          {vehicle && (
            <div className="vehicle-details-section">
              <h2>Vehicle Details</h2>
              <div className="details-grid">
                <div className="detail-item">
                  <span className="detail-label">Speed:</span>
                  <span className="detail-value">
                    {(vehicle.speed * 3.6).toFixed(1)} km/h
                  </span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Position:</span>
                  <span className="detail-value">
                    {vehicle.position.toFixed(1)} m
                  </span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Acceleration:</span>
                  <span className="detail-value">
                    {vehicle.acceleration.toFixed(2)} m/s²
                  </span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Lane:</span>
                  <span className="detail-value">{vehicle.lane_id}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Wait Time:</span>
                  <span className="detail-value">
                    {vehicle.wait_time.toFixed(1)}s
                  </span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Stops:</span>
                  <span className="detail-value">{vehicle.stop_count}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
