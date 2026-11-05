import "../netcommon/network.css";
import { num, pValueText } from "../netcommon/format";
import type { PriorityStat } from "../rescommon/types";
import type { DroppedSeed, Safety } from "./types";

/** A stat's verdict as a sentence block, coloured by who won. */
export function Verdict({ stat }: { stat: PriorityStat }) {
  const tone =
    stat.direction === "none"
      ? "is-neutral"
      : (stat.direction === "a_lower") === stat.lowerIsBetter
        ? "is-good"
        : "is-bad";
  return (
    <p className={`nw-verdict ${tone}`}>
      <strong>{stat.label}.</strong> {stat.verdict}
    </p>
  );
}

/** One row per paired metric: both means, the paired difference with its
 *  interval, the p-value and the percentage change. */
export function StatTable({
  stats,
  withLabel,
}: {
  stats: PriorityStat[];
  withLabel: string;
}) {
  return (
    <div className="uf-table-wrap nw-scroll">
      <table className="uf-table">
        <caption>Paired comparison over the seeds, with and without.</caption>
        <thead>
          <tr>
            <th scope="col">Measure</th>
            <th scope="col">Without</th>
            <th scope="col">{withLabel}</th>
            <th scope="col">Difference</th>
            <th scope="col">Interval</th>
            <th scope="col">Evidence</th>
            <th scope="col">Change</th>
          </tr>
        </thead>
        <tbody>
          {stats.map((s) => (
            <tr key={s.metric}>
              <th scope="row">{s.label}</th>
              <td className="nw-num">{num(s.meanBaseline)}</td>
              <td className="nw-num">{num(s.meanWithPriority)}</td>
              <td className="nw-num">{num(s.difference)}</td>
              <td className="nw-num">
                {num(s.ci_lower)} to {num(s.ci_upper)}
              </td>
              <td className="nw-num">{pValueText(s.p_value)}</td>
              <td className="nw-num">
                {s.changePercent === null
                  ? "Not available"
                  : `${num(s.changePercent, 1)}%`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Pass/fail badges from the safety audit of one arm. */
export function SafetyBadges({
  name,
  safety,
}: {
  name: string;
  safety: Safety;
}) {
  const collisions = safety.collisions.reduce((a, b) => a + b, 0);
  const badge = (ok: boolean, good: string, bad: string) => (
    <span className={`nw-badge ${ok ? "is-pass" : "is-fail"}`}>
      {ok ? good : bad}
    </span>
  );
  return (
    <li>
      <strong>{name}:</strong>{" "}
      {badge(
        collisions === 0,
        "No collisions",
        `${String(collisions)} collisions`,
      )}{" "}
      {badge(
        safety.signalAuditOk,
        "Signal audit passed",
        "Signal audit failed",
      )}{" "}
      {badge(
        safety.vehiclesConserved,
        "Vehicle count balanced",
        "Vehicle count off",
      )}
    </li>
  );
}

export function DroppedNote({ dropped }: { dropped: DroppedSeed[] }) {
  if (dropped.length === 0) return null;
  return (
    <p className="nw-alert" role="status">
      {dropped.length === 1
        ? "One seed was"
        : `${String(dropped.length)} seeds were`}{" "}
      left out of the comparison:{" "}
      {dropped.map((d) => `seed ${String(d.seed)} (${d.reason})`).join("; ")}.
    </p>
  );
}
