import React from "react";
import type { DualSnapshot, LiveSnapshot } from "../types/simulation";
import type { ConnectionStatus } from "../services/websocket";
import "./ComparativeDashboard.css";

interface ComparativeDashboardProps {
  snapshot: DualSnapshot | null;
  connectionStatus: ConnectionStatus;
}

function fmt(val: number | undefined, decimals = 1): string {
  if (val === undefined) return "—";
  return val.toFixed(decimals);
}

export const ComparativeDashboard: React.FC<ComparativeDashboardProps> = ({
  snapshot,
}) => {
  if (!snapshot || !snapshot.signal || !snapshot.roundabout) {
    return (
      <div className="comparative-dashboard empty">
        <p>Waiting for simulation data...</p>
      </div>
    );
  }

  const mSignal = snapshot.signal.metrics;
  const mRound = snapshot.roundabout.metrics;
  const vcSignal = snapshot.signal.vehicleCounts;
  const vcRound = snapshot.roundabout.vehicleCounts;

  const handleDownloadReport = () => {
    if (mSignal && mRound) {
      let csv = "Metric Name,Fixed-Time Signal,Roundabout,Winner,Delta (%)\n";
      const addRow = (
        label: string,
        valA: number,
        valB: number,
        lowerIsBetter = true,
      ) => {
        const winner =
          valA === valB
            ? "Tie"
            : lowerIsBetter
              ? valA < valB
                ? "Signal"
                : "Roundabout"
              : valA > valB
                ? "Signal"
                : "Roundabout";
        const delta = valA === 0 ? 0 : ((valB - valA) / valA) * 100;
        csv += `"${label}",${valA.toFixed(2)},${valB.toFixed(2)},${winner},${delta.toFixed(1)}%\n`;
      };
      addRow("Average Wait Time", mSignal.averageWaitTime, mRound.averageWaitTime, true);
      addRow("Throughput", mSignal.throughput, mRound.throughput, false);
      addRow("Throughput Rate", mSignal.throughputRate, mRound.throughputRate, false);
      addRow("Average Queue Length", mSignal.averageQueueLength ?? 0, mRound.averageQueueLength ?? 0, true);
      addRow("Max Queue Length", mSignal.maxQueueLength, mRound.maxQueueLength, true);
      addRow("Average Stops per Vehicle", mSignal.averageStopsPerVehicle, mRound.averageStopsPerVehicle, true);
      addRow("Speed Variance Index", mSignal.speedVarianceIndex, mRound.speedVarianceIndex, true);
      addRow("Travel Time Reliability", mSignal.travelTimeReliability, mRound.travelTimeReliability, true);
      addRow("Directional Fairness", mSignal.directionalFairnessIndex, mRound.directionalFairnessIndex, false);
      addRow("Idle Opportunity Loss", mSignal.idleOpportunityLoss, mRound.idleOpportunityLoss, true);

      const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.setAttribute("href", url);
      link.setAttribute(
        "download",
        `comparative_report_${Date.now().toString()}.csv`,
      );
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  return (
    <div className="comparative-dashboard">
      <div className="dashboard-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
        <div className="dashboard-insights">
           <h3 style={{ margin: 0, fontSize: "14px", color: "var(--text-primary)" }}>Performance Insights</h3>
           <p style={{ margin: "4px 0 0 0", fontSize: "12px", color: "var(--text-secondary)" }}>
             Observe how the Roundabout typically reduces Average Wait Time and Queues during low-to-medium traffic, 
             while the Fixed-Time Signal may offer better fairness or throughput under heavy, directional loads.
           </p>
        </div>
        <button
          className="pb-btn pb-primary"
          onClick={handleDownloadReport}
          style={{ padding: "8px 12px", fontSize: "12px", borderRadius: "4px", whiteSpace: "nowrap" }}
        >
          📥 Export CSV
        </button>
      </div>

      <table className="comparison-table">
        <thead>
          <tr>
            <th>Performance Metric</th>
            <th>🚦 Fixed-Time Signal</th>
            <th>🔄 Modern Roundabout</th>
            <th>Difference (Roundabout vs Signal)</th>
          </tr>
        </thead>
        <tbody>
          <ComparisonRow
            label="Avg Wait Time (s)"
            valA={mSignal.averageWaitTime}
            valB={mRound.averageWaitTime}
            lowerIsBetter={true}
            formatter={(v) => fmt(v)}
          />
          <ComparisonRow
            label="Throughput (veh)"
            valA={mSignal.throughput}
            valB={mRound.throughput}
            lowerIsBetter={false}
            formatter={(v) => fmt(v, 0)}
          />
          <ComparisonRow
            label="Speed Variance"
            valA={mSignal.speedVarianceIndex}
            valB={mRound.speedVarianceIndex}
            lowerIsBetter={true}
            formatter={(v) => fmt(v)}
          />
          <ComparisonRow
            label="Average Queue"
            valA={mSignal.averageQueueLength ?? 0}
            valB={mRound.averageQueueLength ?? 0}
            lowerIsBetter={true}
            formatter={(v) => fmt(v)}
          />
          <ComparisonRow
            label="Max Queue Length"
            valA={mSignal.maxQueueLength}
            valB={mRound.maxQueueLength}
            lowerIsBetter={true}
            formatter={(v) => fmt(v, 0)}
          />
          <ComparisonRow
            label="Active Vehicles"
            valA={vcSignal.active}
            valB={vcRound.active}
            lowerIsBetter={true}
            formatter={(v) => fmt(v, 0)}
          />
          <ComparisonRow
            label="Approaching"
            valA={vcSignal.approaching}
            valB={vcRound.approaching}
            lowerIsBetter={true}
            formatter={(v) => fmt(v, 0)}
          />
          <ComparisonRow
            label="Waiting"
            valA={vcSignal.waiting}
            valB={vcRound.waiting}
            lowerIsBetter={true}
            formatter={(v) => fmt(v, 0)}
          />
          <ComparisonRow
            label="Crossing"
            valA={vcSignal.crossing}
            valB={vcRound.crossing + vcRound.inRoundabout}
            lowerIsBetter={true}
            formatter={(v) => fmt(v, 0)}
          />
          <ComparisonRow
            label="Exited"
            valA={vcSignal.exited}
            valB={vcRound.exited}
            lowerIsBetter={false}
            formatter={(v) => fmt(v, 0)}
          />
        </tbody>
      </table>
    </div>
  );
};

function ComparisonRow({
  label,
  valA,
  valB,
  lowerIsBetter,
  formatter,
}: {
  label: string;
  valA: number;
  valB: number;
  lowerIsBetter: boolean;
  formatter: (v: number) => string;
}) {
  const diff = valB - valA;
  const pct = valA === 0 ? 0 : (diff / valA) * 100;
  
  let winner = "";
  if (valA !== valB) {
    if (lowerIsBetter) winner = valA < valB ? "sig" : "round";
    else winner = valA > valB ? "sig" : "round";
  }

  const isBetterDiff = lowerIsBetter ? diff < 0 : diff > 0;
  const diffColorClass = diff === 0 ? "neutral" : (isBetterDiff ? "good" : "bad");

  return (
    <tr>
      <td className="metric-name">{label}</td>
      <td className={winner === "sig" ? "winner-cell" : ""}>{formatter(valA)}</td>
      <td className={winner === "round" ? "winner-cell" : ""}>{formatter(valB)}</td>
      <td className="diff-cell">
        <span className={`diff-badge ${diffColorClass}`}>
          {diff > 0 ? "+" : ""}{formatter(diff)} ({pct > 0 ? "+" : ""}{fmt(pct)}%)
        </span>
      </td>
    </tr>
  );
}
