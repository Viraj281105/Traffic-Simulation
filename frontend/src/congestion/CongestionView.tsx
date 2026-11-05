import "../netcommon/network.css";
import { num } from "../netcommon/format";
import { CongestionHeatmap } from "./CongestionHeatmap";
import { spreadSummary } from "./spreadText";
import type { CongestionResult } from "./types";

const DIRECTION_TEXT = {
  upstream: "Backwards along the road",
  downstream: "Forwards along the road",
  lateral: "Sideways (a neighbouring road)",
} as const;

/** One congestion run: the spread in words, the links-by-time heatmap, the
 *  spillback events and the per-link onsets. */
export function CongestionView({ result }: { result: CongestionResult }) {
  const events = result.spillback.events;
  return (
    <div className="nw-stack">
      <div className="nw-stack" aria-label="Spread summary" role="group">
        {spreadSummary(result).map((line) => (
          <p key={line}>{line}</p>
        ))}
      </div>
      <h3 className="nw-headline">Congestion over time</h3>
      <CongestionHeatmap heatmap={result.heatmap} />
      <h3 className="nw-headline">Links in the order they congested</h3>
      <div className="uf-table-wrap nw-scroll">
        <table className="uf-table">
          <caption>
            When each link became congested (more than{" "}
            {num(result.threshold * 100, 0)}% full for{" "}
            {num(result.minHoldSeconds, 0)} s) and how full it got.
          </caption>
          <thead>
            <tr>
              <th scope="col">Order</th>
              <th scope="col">Link</th>
              <th scope="col">Onset (s)</th>
              <th scope="col">Peak fullness</th>
              <th scope="col">Spread from</th>
              <th scope="col">Direction</th>
              <th scope="col">Front speed (m/s)</th>
            </tr>
          </thead>
          <tbody>
            {result.links.map((l) => {
              const step = result.spread.order.find((s) => s.link === l.id);
              return (
                <tr key={l.id}>
                  <td className="nw-num">{l.rank ?? "Never"}</td>
                  <th scope="row">{l.id}</th>
                  <td className="nw-num">
                    {l.onsetSeconds === null
                      ? "Not congested"
                      : num(l.onsetSeconds, 0)}
                  </td>
                  <td className="nw-num">
                    {num(l.peakOccupancyRatio * 100, 0)}%
                  </td>
                  <td>{step?.parent ?? "Start"}</td>
                  <td>
                    {step?.direction ? DIRECTION_TEXT[step.direction] : "Start"}
                  </td>
                  <td className="nw-num">{num(step?.speedMps, 1)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <h3 className="nw-headline">Spillback events</h3>
      {events.length === 0 ? (
        <p>No queue backed up into the link behind it.</p>
      ) : (
        <ul className="nw-list" aria-label="Spillback events">
          {events.map((ev) => (
            <li
              key={`${ev.link}-${String(ev.startSeconds)}`}
              className="nw-alert"
            >
              <strong>{ev.link}</strong> was blocked by{" "}
              <strong>{ev.blockedBy}</strong> from {num(ev.startSeconds, 0)} s
              to {num(ev.endSeconds, 0)} s ({num(ev.durationSeconds, 0)} s). It
              was {num(ev.peakOccupancyRatio * 100, 0)}% full
              {ev.chainLength > 1
                ? `, and the blockage reached back ${num(ev.chainLength, 0)} links.`
                : "."}
            </li>
          ))}
        </ul>
      )}
      <p className="nw-muted">
        Mesoscopic, uncalibrated model: use it to compare scenarios, not to
        predict a real network.
      </p>
    </div>
  );
}
