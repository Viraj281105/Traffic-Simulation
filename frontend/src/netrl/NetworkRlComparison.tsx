import { useId, useState } from "react";
import "../netcommon/network.css";
import { IntervalPlot, type IntervalRow } from "../insights/IntervalPlot";
import { num } from "../netcommon/format";
import {
  WAIT_CAVEAT,
  metricLabel,
  metricUnit,
  outcome,
  seedValues,
  statsLine,
} from "./rlText";
import type { PairedComparisonRow, RlEvalDocument } from "./types";

function verdictClass(row: PairedComparisonRow): string {
  const o = outcome(row);
  return o === "better" ? "is-good" : o === "worse" ? "is-bad" : "is-neutral";
}

/** RL against the baselines on the network: the server's verdict for each
 *  pair, the interval and p-value, and the per-seed values behind them. */
export function NetworkRlComparison({ doc }: { doc: RlEvalDocument }) {
  const uid = useId();
  const compared = [...new Set(doc.paired_comparisons.map((r) => r.metric))];
  const [metric, setMetric] = useState(
    compared.length > 0
      ? compared[0]
      : doc.metrics.length > 0
        ? doc.metrics[0]
        : "",
  );
  const policies = Object.keys(doc.policies);
  const rows = doc.paired_comparisons.filter((r) => r.metric === metric);
  const unit = metricUnit(metric);
  const plot: IntervalRow[] = rows.map((r) => ({
    id: `${r.rl}-${r.baseline}`,
    label: `${r.rl} vs ${r.baseline}`,
    value: r.comparison.difference,
    ci: [r.comparison.ci_lower, r.comparison.ci_upper],
    tone:
      outcome(r) === "better"
        ? "good"
        : outcome(r) === "worse"
          ? "warn"
          : "muted",
  }));
  const level = `${String(Math.round(doc.confidence * 100))}%`;
  const showsWait = doc.metrics.includes("mean_wait_s");

  return (
    <div className="nw-stack">
      <p className="nw-muted">
        {num(doc.seeds.length, 0)} held-out seeds, the same for every policy
        (seeds {doc.seeds.join(", ")}); {num(doc.signal_nodes.length, 0)}{" "}
        signalised junctions; baseline fixed green{" "}
        {num(doc.baseline_fixed_green_s, 0)} s. Comparison:{" "}
        {doc.comparison_method}, {level} intervals.
      </p>
      {doc.cautions.length > 0 && (
        <ul className="nw-facts" aria-label="Cautions">
          {doc.cautions.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      )}
      {showsWait && <p className="nw-alert">{WAIT_CAVEAT}</p>}

      {compared.length > 0 ? (
        <div className="uf-field" style={{ maxWidth: 320 }}>
          <label className="uf-label" htmlFor={`${uid}-metric`}>
            Measure
          </label>
          <select
            id={`${uid}-metric`}
            className="uf-select"
            value={metric}
            onChange={(e) => {
              setMetric(e.target.value);
            }}
          >
            {compared.map((m) => (
              <option key={m} value={m}>
                {metricLabel(m)}
              </option>
            ))}
          </select>
        </div>
      ) : (
        <p>The document has no paired comparisons.</p>
      )}

      {rows.map((r) => (
        <p
          key={`${r.rl}-${r.baseline}`}
          className={`nw-verdict ${verdictClass(r)}`}
        >
          <strong>{r.verdict}</strong>
          <br />
          {statsLine(r)}
          {r.comparison.cautions.map((c) => (
            <span key={c}>
              <br />
              Caution: {c}
            </span>
          ))}
        </p>
      ))}

      {plot.length > 0 && (
        <IntervalPlot
          rows={plot}
          unit={unit}
          reference={0}
          referenceLabel="no difference"
          ariaLabel={`Difference in ${metricLabel(metric).toLowerCase()} between the RL policy and each baseline, with ${level} intervals`}
        />
      )}

      <h3 className="nw-headline">Each seed</h3>
      <div className="uf-table-wrap nw-scroll">
        <table className="uf-table">
          <caption>
            {metricLabel(metric)}
            {unit ? ` (${unit})` : ""} for each held-out seed. Rows with the
            same seed are paired.
          </caption>
          <thead>
            <tr>
              <th scope="col">Seed</th>
              {policies.map((p) => (
                <th key={p} scope="col">
                  {p}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {doc.seeds.map((seed, i) => (
              <tr key={seed}>
                <th scope="row">{seed}</th>
                {policies.map((p) => {
                  const values = seedValues(doc, p, metric);
                  return (
                    <td key={p} className="nw-num">
                      {values && i < values.length
                        ? num(values[i], 2)
                        : "Not available"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
