import "../netcommon/network.css";
import { UNAVAILABLE, isNum, num, percent } from "../netcommon/format";
import type { CalibrationReport, FitSide, Recalibration } from "./types";

function side(label: string, s: FitSide) {
  const m = s.metrics;
  return {
    label,
    rmse: isNum(m.rmseVph) ? `${num(m.rmseVph, 1)} veh/h` : UNAVAILABLE,
    mape: isNum(m.mapePercent) ? `${num(m.mapePercent, 1)}%` : UNAVAILABLE,
    r2: isNum(m.r2) ? num(m.r2, 2) : UNAVAILABLE,
    geh: isNum(m.meanGeh) ? num(m.meanGeh, 2) : UNAVAILABLE,
    fraction: isNum(s.gCal.gehFraction)
      ? `${percent(s.gCal.gehFraction)} (${String(s.gCal.linksPassingGeh)} of ${String(s.gCal.linksChecked)})`
      : UNAVAILABLE,
    gate: s.gCal.passed ? "Pass" : "Fail",
  };
}

export function GCalBadge({ status }: { status: "PASS" | "FAIL" }) {
  return (
    <span
      className={`nw-badge is-${status === "PASS" ? "pass" : "fail"}`}
      role="status"
      aria-label={`Gate G-CAL: ${status}`}
    >
      G-CAL {status}
    </span>
  );
}

/** What changed since the last calibration: parameters that moved more than
 *  the drift threshold are flagged, which is the cue to recalibrate. */
export function DriftTable({
  recalibration: r,
}: {
  recalibration: Recalibration;
}) {
  const d = r.drift;
  return (
    <div className="nw-stack">
      <p className={d.drifted ? "nw-alert" : undefined}>
        {d.drifted
          ? `Recalibrate: ${num(d.flagged.length, 0)} parameter${d.flagged.length === 1 ? "" : "s"} moved by more than ${percent(d.threshold)} (${d.flagged.join(", ")}). `
          : `No parameter moved by more than ${percent(d.threshold)}; the previous calibration still holds. `}
        {r.previousParametersGCalPassed
          ? "The previous parameters still pass G-CAL on the newest counts."
          : "The previous parameters no longer pass G-CAL on the newest counts."}
      </p>
      <div className="uf-table-wrap nw-scroll">
        <table className="uf-table">
          <caption>
            Parameter drift over the last {num(r.windowIntervals, 0)} count
            intervals
            {r.windowFirstIntervalStart && r.windowLastIntervalStart
              ? ` (${r.windowFirstIntervalStart} to ${r.windowLastIntervalStart})`
              : ""}
            .
          </caption>
          <thead>
            <tr>
              <th scope="col">Parameter</th>
              <th scope="col">Previous</th>
              <th scope="col">Now</th>
              <th scope="col">Change</th>
              <th scope="col">Flag</th>
            </tr>
          </thead>
          <tbody>
            {d.parameters.map((p) => (
              <tr key={p.name}>
                <th scope="row">{p.name}</th>
                <td className="nw-num">{num(p.previous, 3)}</td>
                <td className="nw-num">{num(p.current, 3)}</td>
                <td className="nw-num">
                  {isNum(p.relativeChange)
                    ? `${p.relativeChange > 0 ? "+" : ""}${num(p.relativeChange * 100, 1)}%`
                    : UNAVAILABLE}
                </td>
                <td>{p.flag ? "Drifted" : "Steady"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** One calibration report: did the model reach the counts (gate G-CAL), what
 *  the fit changed, where it still misses, and where the numbers came from. */
export function CalibrationReportView({
  report: r,
}: {
  report: CalibrationReport;
}) {
  const before = side("Before", r.before);
  const after = side("After", r.after);
  const limit = r.thresholds.gCal.geh_limit;
  const need = percent(r.thresholds.gCal.min_fraction);
  return (
    <div className="nw-stack">
      <p className="nw-headline">
        <GCalBadge status={r.status} />{" "}
        {r.status === "PASS"
          ? `The model matches the counts: GEH is below ${num(limit, 0)} on ${after.fraction}.`
          : `The model does not yet match the counts well enough: ${need} of links need GEH below ${num(limit, 0)}.`}
      </p>
      {r.after.gCal.reasons.length > 0 && (
        <ul className="nw-facts" aria-label="Why the gate failed">
          {r.after.gCal.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}

      <h3 className="nw-headline">Error before and after</h3>
      <div className="uf-table-wrap nw-scroll">
        <table className="uf-table">
          <caption>
            Fit of the simulated link flows to the counted flows, before and
            after calibration.
          </caption>
          <thead>
            <tr>
              <th scope="col">Measure</th>
              <th scope="col">Before</th>
              <th scope="col">After</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">Root mean square error</th>
              <td className="nw-num">{before.rmse}</td>
              <td className="nw-num">{after.rmse}</td>
            </tr>
            <tr>
              <th scope="row">Mean absolute percentage error</th>
              <td className="nw-num">{before.mape}</td>
              <td className="nw-num">{after.mape}</td>
            </tr>
            <tr>
              <th scope="row">R-squared</th>
              <td className="nw-num">{before.r2}</td>
              <td className="nw-num">{after.r2}</td>
            </tr>
            <tr>
              <th scope="row">Average GEH</th>
              <td className="nw-num">{before.geh}</td>
              <td className="nw-num">{after.geh}</td>
            </tr>
            <tr>
              <th scope="row">Links with GEH below {num(limit, 0)}</th>
              <td className="nw-num">{before.fraction}</td>
              <td className="nw-num">{after.fraction}</td>
            </tr>
            <tr>
              <th scope="row">Gate G-CAL</th>
              <td>{before.gate}</td>
              <td>{after.gate}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <h3 className="nw-headline">What the fit changed</h3>
      <div className="uf-table-wrap nw-scroll">
        <table className="uf-table">
          <caption>
            Scale factors found by the search (1 means unchanged), with the
            range it was allowed to use.
          </caption>
          <thead>
            <tr>
              <th scope="col">Parameter</th>
              <th scope="col">Start</th>
              <th scope="col">Fitted</th>
              <th scope="col">Allowed range</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(r.parameters.fitted).map(([name, value]) => {
              const range = r.parameters.bounds[name] as
                [number, number] | undefined;
              return (
                <tr key={name}>
                  <th scope="row">{name}</th>
                  <td className="nw-num">{num(r.parameters.start[name], 3)}</td>
                  <td className="nw-num">{num(value, 3)}</td>
                  <td className="nw-num">
                    {range
                      ? `${num(range[0], 2)} to ${num(range[1], 2)}`
                      : UNAVAILABLE}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <h3 className="nw-headline">Link by link</h3>
      <div className="uf-table-wrap nw-scroll">
        <table className="uf-table">
          <caption>
            Residual = simulated minus counted flow (veh/h). A GEH of{" "}
            {num(limit, 0)} or more is marked as a miss.
          </caption>
          <thead>
            <tr>
              <th scope="col">Link</th>
              <th scope="col">Counted</th>
              <th scope="col">Simulated before</th>
              <th scope="col">Residual before</th>
              <th scope="col">GEH before</th>
              <th scope="col">Simulated after</th>
              <th scope="col">Residual after</th>
              <th scope="col">GEH after</th>
              <th scope="col">Error after</th>
            </tr>
          </thead>
          <tbody>
            {r.perLink.map((l) => (
              <tr key={l.linkId}>
                <th scope="row">{l.linkId}</th>
                <td className="nw-num">{num(l.observedVph, 0)}</td>
                <td className="nw-num">{num(l.before.simulatedVph, 0)}</td>
                <td className="nw-num">{num(l.before.residualVph, 0)}</td>
                <td className="nw-num">
                  {num(l.before.geh, 1)}
                  {l.before.geh >= limit ? " (miss)" : ""}
                </td>
                <td className="nw-num">{num(l.after.simulatedVph, 0)}</td>
                <td className="nw-num">{num(l.after.residualVph, 0)}</td>
                <td className="nw-num">
                  {num(l.after.geh, 1)}
                  {l.after.geh >= limit ? " (miss)" : ""}
                </td>
                <td className="nw-num">
                  {isNum(l.after.percentError)
                    ? `${num(l.after.percentError, 1)}%`
                    : "Count too small"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {r.recalibration && (
        <>
          <h3 className="nw-headline">Recalibration and drift</h3>
          <DriftTable recalibration={r.recalibration} />
        </>
      )}

      <h3 className="nw-headline">Where this came from</h3>
      <ul className="nw-facts" aria-label="Provenance">
        <li>
          Counts: {r.provenance.counts.source},{" "}
          {num(r.provenance.counts.rows, 0)} rows on{" "}
          {num(r.provenance.counts.links, 0)} links,{" "}
          {num(r.provenance.counts.intervals, 0)} intervals of{" "}
          {num(r.provenance.counts.intervalSeconds, 0)} s
          {r.provenance.counts.intervalSecondsInferred
            ? " (length inferred)"
            : ""}
          {r.provenance.counts.firstIntervalStart
            ? `, ${r.provenance.counts.firstIntervalStart} to ${r.provenance.counts.lastIntervalStart ?? ""}`
            : ""}
          .
        </li>
        <li>
          Counts file fingerprint (SHA-256):{" "}
          <code>{r.provenance.counts.sha256}</code>
        </li>
        <li>
          Network: {r.provenance.network.name},{" "}
          {num(r.provenance.network.nodes, 0)} nodes,{" "}
          {num(r.provenance.network.links, 0)} links.{" "}
          {num(r.provenance.countedLinks, 0)} links had counts;{" "}
          {num(r.provenance.linksWithoutCounts, 0)} had none.
        </li>
        <li>
          Search: {r.optimiser.method}, {num(r.optimiser.evaluations, 0)} of{" "}
          {num(r.optimiser.budget, 0)} runs used, stopped because{" "}
          {r.optimiser.stopReason}. Each run simulated{" "}
          {num(r.simulation.duration, 0)} s (seed {num(r.simulation.seed, 0)}).
        </li>
        <li>
          Inputs fingerprint: <code>{r.manifest.hash}</code>. The same inputs
          and code give the same report.
        </li>
        <li>{r.thresholds.gehNote}</li>
        {r.provenance.counts.warnings.map((w) => (
          <li key={w}>{w}</li>
        ))}
        {r.notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>
    </div>
  );
}
