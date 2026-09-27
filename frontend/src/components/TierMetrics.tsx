import { useId, useState } from "react";
import type { RunningMetrics } from "../types/simulation";
import { ComparisonSections } from "./MetricSections";

export interface TierMetricsRun {
  arrivalRate: number;
  hourlyVolumeVehPerHour: number;
  signal: { metrics?: RunningMetrics };
  roundabout: { metrics?: RunningMetrics };
}

/** Every backend metric for one demand tier of a volume sweep — the same set
 *  and presentation as the live comparison, including safety measures. */
export function TierMetrics({ runs }: { runs: TierMetricsRun[] }) {
  const withMetrics = runs.filter(
    (r) => r.signal.metrics !== undefined && r.roundabout.metrics !== undefined,
  );
  const [index, setIndex] = useState(0);
  const id = useId();
  if (withMetrics.length === 0) return null;
  const run = withMetrics[Math.min(index, withMetrics.length - 1)];

  return (
    <section className="tier-metrics" aria-labelledby={`${id}-title`}>
      <div className="tier-metrics-head">
        <h4 id={`${id}-title`}>All metrics for one tier</h4>
        <label htmlFor={id}>Demand tier</label>
        <select
          id={id}
          value={Math.min(index, withMetrics.length - 1)}
          onChange={(e) => {
            setIndex(Number(e.target.value));
          }}
        >
          {withMetrics.map((r, i) => (
            <option key={r.arrivalRate} value={i}>
              {r.arrivalRate.toFixed(2)} veh/s (≈
              {r.hourlyVolumeVehPerHour.toLocaleString()} veh/h)
            </option>
          ))}
        </select>
      </div>
      <ComparisonSections
        signal={{
          metrics: run.signal.metrics,
          geometry: "fixed_time_signal",
          inWarmup: false,
        }}
        roundabout={{
          metrics: run.roundabout.metrics,
          geometry: "roundabout",
          inWarmup: false,
        }}
        collapsed={["diagnostic"]}
      />
    </section>
  );
}
