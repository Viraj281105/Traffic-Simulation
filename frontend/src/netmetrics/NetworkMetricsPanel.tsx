import { useId, useState } from "react";
import "../netcommon/network.css";
import { StatGrid, StatTile } from "../components/dashboard/Dashboard";
import { LineChart } from "../netcommon/LineChart";
import { isNum, num, withUnit } from "../netcommon/format";
import type {
  FundamentalDiagram,
  LinkMetrics,
  NetworkMetrics,
  SeriesBucket,
} from "./types";

const W = 520;
const H = 300;
const PAD = { left: 56, right: 16, top: 12, bottom: 44 };

/** Fundamental diagram: one dot per time bucket, density across and flow up.
 *  The busiest bucket is marked. */
export function FundamentalDiagramChart({
  diagram,
}: {
  diagram: FundamentalDiagram;
}) {
  const pts = diagram.points;
  if (pts.length === 0) {
    return <p className="nw-muted">There are no points to plot.</p>;
  }
  const maxX = Math.max(...pts.map((p) => p.densityVehPerKmLane), 1e-9);
  const maxY = Math.max(...pts.map((p) => p.flowVehPerHourLane), 1e-9);
  const pw = W - PAD.left - PAD.right;
  const ph = H - PAD.top - PAD.bottom;
  const sx = (v: number) => PAD.left + (v / maxX) * pw;
  const sy = (v: number) => PAD.top + ph - (v / maxY) * ph;
  const peak = diagram.peakFlow;
  const marks = [0, 0.5, 1];
  return (
    <svg
      className="nw-svg"
      viewBox={`0 0 ${String(W)} ${String(H)}`}
      role="img"
      aria-label={`Fundamental diagram: flow against density, ${String(pts.length)} points${
        peak
          ? `; highest flow ${num(peak.flowVehPerHourLane, 0)} vehicles per hour per lane at ${num(peak.densityVehPerKmLane, 1)} vehicles per kilometre per lane`
          : ""
      }`}
    >
      {marks.map((m) => (
        <g key={m}>
          <line
            className="nw-svg__grid"
            x1={PAD.left}
            x2={W - PAD.right}
            y1={sy(m * maxY)}
            y2={sy(m * maxY)}
          />
          <text
            className="nw-svg__tick"
            x={PAD.left - 6}
            y={sy(m * maxY) + 4}
            textAnchor="end"
          >
            {num(m * maxY, 0)}
          </text>
          <text
            className="nw-svg__tick"
            x={sx(m * maxX)}
            y={H - PAD.bottom + 16}
            textAnchor="middle"
          >
            {num(m * maxX, 1)}
          </text>
        </g>
      ))}
      <line
        className="nw-svg__axis"
        x1={PAD.left}
        x2={W - PAD.right}
        y1={PAD.top + ph}
        y2={PAD.top + ph}
      />
      <line
        className="nw-svg__axis"
        x1={PAD.left}
        x2={PAD.left}
        y1={PAD.top}
        y2={PAD.top + ph}
      />
      <text
        className="nw-svg__tick"
        x={PAD.left + pw / 2}
        y={H - 6}
        textAnchor="middle"
      >
        Density (vehicles per km per lane)
      </text>
      <text
        className="nw-svg__tick"
        transform={`translate(12 ${String(PAD.top + ph / 2)}) rotate(-90)`}
        textAnchor="middle"
      >
        Flow (vehicles per hour per lane)
      </text>
      {pts.map((p) => {
        const isPeak =
          peak?.flowVehPerHourLane === p.flowVehPerHourLane &&
          peak.densityVehPerKmLane === p.densityVehPerKmLane;
        return (
          <circle
            key={p.tStart}
            className={`nw-dot${isPeak ? " is-peak" : ""}`}
            cx={sx(p.densityVehPerKmLane)}
            cy={sy(p.flowVehPerHourLane)}
            r={isPeak ? 6 : 4.5}
          >
            <title>
              {`From ${num(p.tStart, 0)} s: ${num(p.densityVehPerKmLane, 2)} veh/km/lane, ${num(p.flowVehPerHourLane, 0)} veh/h/lane`}
            </title>
          </circle>
        );
      })}
    </svg>
  );
}

type SortKey = keyof LinkMetrics | "id";

const COLUMNS: { key: SortKey; label: string; digits: number }[] = [
  { key: "id", label: "Link", digits: 0 },
  { key: "flowVph", label: "Flow (veh/h)", digits: 0 },
  { key: "meanOccupancyRatio", label: "Average fullness", digits: 2 },
  { key: "meanQueue", label: "Average queue", digits: 1 },
  { key: "peakQueue", label: "Peak queue", digits: 0 },
  { key: "densityVehPerKmLane", label: "Density (veh/km/lane)", digits: 2 },
  { key: "blockedSeconds", label: "Blocked (s)", digits: 0 },
];

/** Every link's numbers, sortable by any column. */
export function PerLinkTable({
  perLink,
}: {
  perLink: Record<string, LinkMetrics>;
}) {
  const uid = useId();
  const [sort, setSort] = useState<SortKey>("meanOccupancyRatio");
  const rows = Object.entries(perLink).sort(([ia, a], [ib, b]) => {
    if (sort === "id") return ia.localeCompare(ib);
    return b[sort] - a[sort] || ia.localeCompare(ib);
  });
  return (
    <div className="nw-stack">
      <div className="uf-field" style={{ maxWidth: 260 }}>
        <label className="uf-label" htmlFor={`${uid}-sort`}>
          Sort links by
        </label>
        <select
          id={`${uid}-sort`}
          className="uf-select"
          value={sort}
          onChange={(e) => {
            setSort(e.target.value as SortKey);
          }}
        >
          {COLUMNS.map((c) => (
            <option key={c.key} value={c.key}>
              {c.label}
            </option>
          ))}
        </select>
      </div>
      <div className="uf-table-wrap nw-scroll">
        <table className="uf-table">
          <caption>
            Per-link results, {sort === "id" ? "by name" : "highest first"}.
          </caption>
          <thead>
            <tr>
              {COLUMNS.map((c) => (
                <th key={c.key} scope="col">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(([id, m]) => (
              <tr key={id}>
                <th scope="row">{id}</th>
                {COLUMNS.slice(1).map((c) => (
                  <td key={c.key} className="nw-num">
                    {num(m[c.key as keyof LinkMetrics], c.digits)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function seriesChart(series: SeriesBucket[]) {
  return (
    <LineChart
      xLabel="Time (s)"
      yLabel="Vehicles"
      ariaLabel="Vehicles in the network and queued vehicles over time"
      series={[
        {
          id: "in",
          label: "Vehicles in the network",
          tone: "a",
          points: series.map((b) => ({ x: b.tStart, y: b.vehiclesInNetwork })),
        },
        {
          id: "queued",
          label: "Queued vehicles",
          tone: "b",
          points: series.map((b) => ({ x: b.tStart, y: b.queuedVehicles })),
        },
      ]}
    />
  );
}

/** Network-wide results of one run: KPI cards, vehicles over time, the
 *  fundamental diagram and a per-link table. */
export function NetworkMetricsPanel({ metrics }: { metrics: NetworkMetrics }) {
  const n = metrics.network;
  const delayed = isNum(n.meanDelaySeconds);
  return (
    <div className="nw-stack">
      <StatGrid>
        <StatTile
          label="Throughput"
          value={num(n.throughputVph, 0)}
          unit="veh/h"
          hint={`${num(n.completed, 0)} vehicles finished their trip`}
        />
        <StatTile
          label="Mean delay"
          value={delayed ? num(n.meanDelaySeconds, 1) : "Not available"}
          unit={delayed ? "s" : undefined}
          hint="Finished trips only"
        />
        <StatTile
          label="Mean travel time"
          value={
            isNum(n.meanTravelSeconds)
              ? num(n.meanTravelSeconds, 1)
              : "Not available"
          }
          unit={isNum(n.meanTravelSeconds) ? "s" : undefined}
        />
        <StatTile
          label="Vehicles in the network"
          value={num(n.meanVehiclesInNetwork, 1)}
          hint="Average over the run"
        />
        <StatTile
          label="Queued vehicles"
          value={num(n.meanQueuedVehicles, 1)}
          hint="Average over the run"
          tone={
            n.meanQueuedVehicles > 0.2 * n.meanVehiclesInNetwork
              ? "warn"
              : "neutral"
          }
        />
        <StatTile
          label="Blocked link time"
          value={num(n.blockedLinkSeconds, 0)}
          unit="link-s"
          hint="Time links could not release vehicles"
          tone={n.blockedLinkSeconds > 0 ? "warn" : "good"}
        />
      </StatGrid>
      <p>
        {num(n.generated, 0)} vehicles were generated: {num(n.entered, 0)}{" "}
        entered, {num(n.blockedAtEntry, 0)} could not enter,{" "}
        {num(n.completed, 0)} finished and {num(n.active, 0)} were still
        travelling at the end
        {n.unroutable > 0 ? `; ${num(n.unroutable, 0)} had no route` : ""}.{" "}
        {n.conserved
          ? "Every vehicle is accounted for."
          : "The vehicle count did not balance; treat this run with care."}
      </p>
      <h3 className="nw-headline">Vehicles over time</h3>
      {seriesChart(metrics.series)}
      <h3 className="nw-headline">Fundamental diagram</h3>
      <FundamentalDiagramChart diagram={metrics.fundamentalDiagram} />
      <p className="nw-muted">
        One dot per {num(metrics.fundamentalDiagram.bucketSeconds, 0)} s of the
        run, over all lanes of all links.
        {metrics.fundamentalDiagram.peakFlow
          ? ` Highest flow: ${withUnit(metrics.fundamentalDiagram.peakFlow.flowVehPerHourLane, "veh/h per lane", 0)} at ${withUnit(metrics.fundamentalDiagram.peakFlow.densityVehPerKmLane, "veh/km per lane", 1)} (red dot).`
          : ""}
      </p>
      <h3 className="nw-headline">Links</h3>
      <PerLinkTable perLink={metrics.perLink} />
      {metrics.notes.length > 0 && (
        <ul className="nw-facts">
          {metrics.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
