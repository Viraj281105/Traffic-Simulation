import type { LiveSnapshot } from "../../types/simulation";

interface VehiclesFlowVisualizerProps {
  signal: LiveSnapshot | undefined;
  roundabout: LiveSnapshot | undefined;
  compact?: boolean;
}

export function VehiclesFlowVisualizer({
  signal,
  roundabout,
  compact = false,
}: VehiclesFlowVisualizerProps) {
  const sigCounts = signal?.vehicleCounts ?? {
    active: 0,
    approaching: 0,
    waiting: 0,
    crossing: 0,
    inRoundabout: 0,
    exited: 0,
  };

  const rndCounts = roundabout?.vehicleCounts ?? {
    active: 0,
    approaching: 0,
    waiting: 0,
    crossing: 0,
    inRoundabout: 0,
    exited: 0,
  };

  const sigInJunction = sigCounts.crossing;
  const rndInJunction = rndCounts.crossing + rndCounts.inRoundabout;

  const stages = [
    {
      id: "active",
      label: "In Network",
      sublabel: "Active vehicles",
      sigVal: sigCounts.active,
      rndVal: rndCounts.active,
      unit: "veh",
      icon: "🚗",
    },
    {
      id: "waiting",
      label: "Waiting",
      sublabel: "Speed < 0.5 m/s",
      sigVal: sigCounts.waiting,
      rndVal: rndCounts.waiting,
      unit: "veh",
      icon: "⏳",
    },
    {
      id: "junction",
      label: "In Junction",
      sublabel: "Crossing / circulating",
      sigVal: sigInJunction,
      rndVal: rndInJunction,
      unit: "veh",
      icon: "🔀",
    },
    {
      id: "exited",
      label: "Exited (whole run)",
      sublabel: "Includes warm-up; differs from Vehicles served",
      sigVal: sigCounts.exited,
      rndVal: rndCounts.exited,
      unit: "veh",
      icon: "🏁",
    },
  ];

  // Proportions for the live flow bar
  const sigWaitingPct =
    sigCounts.active > 0 ? (sigCounts.waiting / sigCounts.active) * 100 : 0;
  const sigJunctionPct =
    sigCounts.active > 0 ? (sigInJunction / sigCounts.active) * 100 : 0;
  const sigMovingPct = Math.max(0, 100 - sigWaitingPct - sigJunctionPct);

  const rndWaitingPct =
    rndCounts.active > 0 ? (rndCounts.waiting / rndCounts.active) * 100 : 0;
  const rndJunctionPct =
    rndCounts.active > 0 ? (rndInJunction / rndCounts.active) * 100 : 0;
  const rndMovingPct = Math.max(0, 100 - rndWaitingPct - rndJunctionPct);

  return (
    <div className={`vehicles-flow-container ${compact ? "compact" : ""}`}>
      {/* 4-Stage KPI Pipeline */}
      <div className="flow-pipeline-grid">
        {stages.map((stage, idx) => {
          const delta = stage.rndVal - stage.sigVal;
          return (
            <div className="flow-stage-card" key={stage.id}>
              <div className="stage-header">
                <span className="stage-icon">{stage.icon}</span>
                <div className="stage-meta">
                  <span className="stage-name">{stage.label}</span>
                  {!compact && (
                    <span className="stage-sublabel">{stage.sublabel}</span>
                  )}
                </div>
                {idx < stages.length - 1 && (
                  <span className="stage-flow-arrow" aria-hidden="true">
                    →
                  </span>
                )}
              </div>

              <div className="stage-values">
                <div className="stage-val-item signal-val">
                  <span className="control-dot signal-dot" title="Signal" />
                  <span className="val-number">{stage.sigVal}</span>
                  <span className="val-unit">{stage.unit}</span>
                </div>
                <div className="stage-val-item roundabout-val">
                  <span
                    className="control-dot roundabout-dot"
                    title="Roundabout"
                  />
                  <span className="val-number">{stage.rndVal}</span>
                  <span className="val-unit">{stage.unit}</span>
                </div>
                <div className="stage-val-delta">
                  <span className="delta-label">Δ</span>
                  <span
                    className={`delta-val ${delta > 0 ? "positive" : delta < 0 ? "negative" : "zero"}`}
                  >
                    {delta > 0
                      ? `+${String(delta)}`
                      : delta === 0
                        ? "0"
                        : `−${String(Math.abs(delta))}`}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Visual Flow Distribution Bars */}
      {!compact && (
        <div className="flow-distribution-section">
          <div className="flow-dist-header">
            <span className="flow-dist-title">
              In-Network Vehicle State Distribution
            </span>
            <div className="flow-legend">
              <span className="legend-item waiting">
                <span className="legend-box wait-box" /> Waiting
              </span>
              <span className="legend-item junction">
                <span className="legend-box junc-box" /> In Junction
              </span>
              <span className="legend-item moving">
                <span className="legend-box move-box" /> Cruising / Approaching
              </span>
            </div>
          </div>

          <div className="flow-bars-wrapper">
            <div className="flow-bar-row">
              <span className="control-tag signal-tag">🚦 Signal</span>
              <div
                className="flow-bar-track"
                title={`Waiting: ${sigWaitingPct.toFixed(1)}%, Junction: ${sigJunctionPct.toFixed(1)}%, Cruising: ${sigMovingPct.toFixed(1)}%`}
              >
                <div
                  className="flow-bar-seg seg-waiting"
                  style={{ width: `${String(sigWaitingPct)}%` }}
                />
                <div
                  className="flow-bar-seg seg-junction"
                  style={{ width: `${String(sigJunctionPct)}%` }}
                />
                <div
                  className="flow-bar-seg seg-moving"
                  style={{ width: `${String(sigMovingPct)}%` }}
                />
              </div>
              <span className="flow-total-badge">
                {sigCounts.active} active
              </span>
            </div>

            <div className="flow-bar-row">
              <span className="control-tag roundabout-tag">🔄 Roundabout</span>
              <div
                className="flow-bar-track"
                title={`Waiting: ${rndWaitingPct.toFixed(1)}%, Junction: ${rndJunctionPct.toFixed(1)}%, Cruising: ${rndMovingPct.toFixed(1)}%`}
              >
                <div
                  className="flow-bar-seg seg-waiting"
                  style={{ width: `${String(rndWaitingPct)}%` }}
                />
                <div
                  className="flow-bar-seg seg-junction"
                  style={{ width: `${String(rndJunctionPct)}%` }}
                />
                <div
                  className="flow-bar-seg seg-moving"
                  style={{ width: `${String(rndMovingPct)}%` }}
                />
              </div>
              <span className="flow-total-badge">
                {rndCounts.active} active
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
