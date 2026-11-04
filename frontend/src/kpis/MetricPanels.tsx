import { useMemo, type ReactNode } from "react";
import { Clock, Fuel, ShieldAlert, Timer, Gauge } from "lucide-react";
import "../insights/Insights.css";
import {
  EmptyHint,
  Panel,
  Pill,
  Skeleton,
  StatGrid,
  StatTile,
} from "../components/dashboard/Dashboard";
import { UNAVAILABLE, interval, isNum, num } from "../insights/format";
import { useRemote } from "../insights/useRemote";
import { getRunMetrics } from "./api";
import type { MetricValue, RunMetrics } from "./types";

function Tile({
  label,
  metric,
  icon,
  digits = 1,
  tip,
}: {
  label: string;
  metric: MetricValue;
  icon: ReactNode;
  digits?: number;
  tip?: string;
}) {
  const known = isNum(metric.value);
  return (
    <StatTile
      label={label}
      icon={icon}
      value={known ? num(metric.value, digits) : UNAVAILABLE}
      unit={known ? metric.unit : undefined}
      tip={tip}
      hint={
        known && metric.ci
          ? `Interval: ${interval(metric.ci, metric.unit, digits)}`
          : undefined
      }
    />
  );
}

/** Delay and travel-time cards. */
export function FlowCards({ metrics }: { metrics: RunMetrics }) {
  return (
    <Panel
      id="kpi-flow"
      title="Delay and travel time"
      subtitle="How long vehicles waited and how long the trip took."
    >
      <StatGrid>
        <Tile
          label="Average delay"
          metric={metrics.delay.mean}
          icon={<Timer size={16} />}
          tip={metrics.delay.definition}
        />
        <Tile
          label="Delay, slowest 5%"
          metric={metrics.delay.p95}
          icon={<Timer size={16} />}
          tip="95th percentile: 95% of vehicles waited this long or less."
        />
        <Tile
          label="Average travel time"
          metric={metrics.travelTime.mean}
          icon={<Clock size={16} />}
          tip={metrics.travelTime.definition}
        />
        <Tile
          label="Travel time, slowest 5%"
          metric={metrics.travelTime.p95}
          icon={<Clock size={16} />}
          tip="95th percentile: 95% of trips took this long or less."
        />
      </StatGrid>
      {isNum(metrics.vehiclesCompleted) && (
        <p className="ins-muted">
          Based on {num(metrics.vehiclesCompleted, 0)} vehicles that completed
          their trip.
        </p>
      )}
    </Panel>
  );
}

/** Safety (time-to-collision) panel. Always labelled as a proxy. */
export function SafetyPanel({ metrics }: { metrics: RunMetrics }) {
  const { safety } = metrics;
  return (
    <Panel
      id="kpi-safety"
      title="Safety (time-to-collision)"
      subtitle={<Pill tone="warn">Proxy measure, not crash data</Pill>}
    >
      <StatGrid>
        <Tile
          label="Closest call"
          metric={safety.minTtc}
          icon={<ShieldAlert size={16} />}
          digits={2}
          tip="Smallest time-to-collision seen. Lower means a closer call."
        />
        <Tile
          label={`Encounters under ${num(safety.thresholdSeconds, 1)} s`}
          metric={safety.conflicts}
          icon={<ShieldAlert size={16} />}
          digits={0}
        />
      </StatGrid>
      <p className="ins-muted">
        {safety.definition} Time-to-collision is a stand-in for crash risk: it
        shows where close calls happen in the model, not how many crashes would
        occur.
      </p>
    </Panel>
  );
}

/** Emissions (fuel and CO2) panel. Always labelled as a model estimate. */
export function EmissionsPanel({ metrics }: { metrics: RunMetrics }) {
  const { emissions } = metrics;
  const version = emissions.model.version ? ` v${emissions.model.version}` : "";
  return (
    <Panel
      id="kpi-emissions"
      title="Fuel and CO2"
      subtitle={<Pill tone="warn">Model estimate, not a measurement</Pill>}
    >
      <StatGrid>
        <Tile
          label="Fuel used"
          metric={emissions.fuel}
          icon={<Fuel size={16} />}
        />
        <Tile label="CO2" metric={emissions.co2} icon={<Gauge size={16} />} />
        <Tile
          label="CO2 per vehicle"
          metric={emissions.co2PerVehicle}
          icon={<Gauge size={16} />}
        />
      </StatGrid>
      <p className="ins-muted">
        {emissions.definition} Model: {emissions.model.name}
        {version}. These are estimates from simulated driving, not measured
        emissions.
      </p>
      {metrics.notes && metrics.notes.length > 0 && (
        <ul className="ins-facts">
          {metrics.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

/** All three metric groups for one run. */
export function RunMetricsView({ metrics }: { metrics: RunMetrics }) {
  return (
    <div className="ins-stack">
      <FlowCards metrics={metrics} />
      <div className="ins-cols">
        <SafetyPanel metrics={metrics} />
        <EmissionsPanel metrics={metrics} />
      </div>
    </div>
  );
}

/** Loads a run's metrics and shows the cards and panels. */
export function RunMetricsSection({ runId }: { runId: string }) {
  const load = useMemo(() => () => getRunMetrics(runId), [runId]);
  const state = useRemote(load, "The run's metrics could not be loaded.");
  if (state.status === "loading") return <Skeleton lines={5} />;
  if (state.status === "notFound")
    return (
      <EmptyHint icon={<Gauge size={22} />} title="No metrics yet">
        This run has no metrics yet.
      </EmptyHint>
    );
  if (state.status === "error") return <p role="alert">{state.message}</p>;
  if (state.status === "ready") return <RunMetricsView metrics={state.data} />;
  return null;
}
