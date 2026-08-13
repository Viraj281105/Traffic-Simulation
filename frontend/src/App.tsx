import { useState } from 'react';
import { useSimulationPolling } from './hooks/useSimulationPolling';
import { IntersectionCanvas } from './components/IntersectionCanvas';
import './App.css';

export function App() {
  const { vehicle, status, isLoading, error, start, stop, reset } = useSimulationPolling();
  const [canvasSize] = useState({ width: 800, height: 600 });

  return (
    <div className="app">
      <header className="app-header">
        <h1>Traffic Simulation</h1>
        <p>Single Vehicle at Signalized Intersection</p>
      </header>

      <main className="app-main">
        <div className="canvas-container">
          <IntersectionCanvas
            vehicle={vehicle}
            width={canvasSize.width}
            height={canvasSize.height}
          />
        </div>

        <div className="control-panel">
          <div className="status-section">
            <h2>Simulation Status</h2>
            <div className="status-info">
              <div className={`status-badge status-${status}`}>{status.toUpperCase()}</div>
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
                onClick={start}
                disabled={status === 'running' || isLoading}
                className="btn btn-primary"
              >
                {isLoading ? 'Starting...' : 'Start'}
              </button>
              <button
                onClick={stop}
                disabled={status === 'stopped' || isLoading}
                className="btn btn-secondary"
              >
                Stop
              </button>
              <button onClick={reset} disabled={isLoading} className="btn btn-tertiary">
                Reset
              </button>
            </div>
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
                  <span className="detail-value">{(vehicle.speed * 3.6).toFixed(1)} km/h</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Position:</span>
                  <span className="detail-value">{vehicle.position.toFixed(1)} m</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Acceleration:</span>
                  <span className="detail-value">{vehicle.acceleration.toFixed(2)} m/s²</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Lane:</span>
                  <span className="detail-value">{vehicle.lane_id}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Wait Time:</span>
                  <span className="detail-value">{vehicle.wait_time.toFixed(1)}s</span>
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
