import { useState } from "react";
import {
  PlanningApiError,
  fetchReport,
  reproduceStudy,
  type IndicatorGroup,
  type PlanningResult,
  type ReportFormat,
  type ReproduceResponse,
} from "../../services/v2/planning";
import { downloadText } from "../../metrics/catalog";
import {
  failureText,
  fieldCalibrationText,
  formatInterval,
  formatNumber,
  metricText,
  verdictText,
} from "./plannerText";

const INDICATOR_COLUMNS: {
  group: "performance" | "safety";
  key: string;
}[] = [
  { group: "performance", key: "averageDelay" },
  { group: "performance", key: "throughput" },
  { group: "performance", key: "averageQueueLength" },
  { group: "safety", key: "collisionCount" },
];

const GROUPS = [
  "performance",
  "safety",
  "environmental",
  "reliability",
] as const;

function scaleText(scale: number): string {
  return `×${scale.toString()} demand`;
}

function asError(err: unknown): PlanningApiError {
  return err instanceof PlanningApiError
    ? err
    : new PlanningApiError(0, [String(err)]);
}

/** Every indicator the study could not report, once per group, with why. */
function unavailableIndicators(result: PlanningResult) {
  const seen = new Map<string, string>();
  for (const row of result.results) {
    for (const group of GROUPS) {
      const g: IndicatorGroup | undefined = row[group];
      for (const u of g?.unavailable ?? []) {
        if (!seen.has(u.label)) seen.set(u.label, u.reason);
      }
    }
  }
  return [...seen.entries()];
}

export function PlannerResults({
  studyId,
  result,
}: {
  studyId: string;
  result: PlanningResult;
}) {
  const [reproduce, setReproduce] = useState<
    | { state: "idle" }
    | { state: "running" }
    | { state: "done"; outcome: ReproduceResponse }
    | { state: "failed"; message: string }
  >({ state: "idle" });
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const titleOf = new Map(
    result.alternatives.map((a) => [a.id, a.label || a.strategyTitle]),
  );
  const scales = result.summary.scales;
  const missing = unavailableIndicators(result);

  const download = (format: ReportFormat) => {
    setDownloadError(null);
    fetchReport(studyId, format)
      .then((r) => {
        downloadText(r.filename, r.content, r.type);
      })
      .catch((err: unknown) => {
        setDownloadError(failureText(asError(err)));
      });
  };

  const runReproduce = () => {
    setReproduce({ state: "running" });
    reproduceStudy(studyId)
      .then((outcome) => {
        setReproduce({ state: "done", outcome });
      })
      .catch((err: unknown) => {
        setReproduce({ state: "failed", message: failureText(asError(err)) });
      });
  };

  return (
    <section
      className="planner-results"
      aria-labelledby="planner-results-title"
    >
      <h2 id="planner-results-title">Evidence: {result.name}</h2>

      <div className="planner-banner" role="note" aria-label="Validity">
        <p>
          <strong>
            {fieldCalibrationText(result.validity.fieldCalibration)}
          </strong>
        </p>
        {result.validity.exploratory && (
          <p>
            Exploratory results: they describe this simulated scenario at these
            demand levels and do not transfer to other junctions.
          </p>
        )}
        {result.validity.vehicleLimitReached && (
          <p>
            The simulation reached its vehicle limit in at least one run, so
            some figures understate the real load.
          </p>
        )}
        <p>{result.summary.recommendationBasis}</p>
        {result.validity.caveats.length > 0 && (
          <ul>
            {result.validity.caveats.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        )}
      </div>

      {scales.map((scale) => {
        const rows = result.results.filter((r) => r.demandScale === scale);
        const comparisons = result.comparison.vsBaseline.filter(
          (c) => c.demandScale === scale,
        );
        return (
          <div key={scale} className="planner-scale">
            <h3>
              {scaleText(scale)} ({formatNumber(rows[0]?.demandVph, 0)} veh/h)
            </h3>
            <table className="planner-table">
              <caption>
                Indicators per alternative: mean across{" "}
                {result.summary.seeds.toString()} seeds, with its{" "}
                {Math.round(result.reliability.confidenceLevel * 100)}% interval
              </caption>
              <thead>
                <tr>
                  <th scope="col">Alternative</th>
                  {INDICATOR_COLUMNS.map((c) => (
                    <th scope="col" key={c.key}>
                      {metricText(c.key)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.alternativeId}>
                    <th scope="row">
                      {titleOf.get(row.alternativeId) ?? row.alternativeId}
                      {row.alternativeId === result.comparison.baselineId &&
                        " (baseline)"}
                    </th>
                    {INDICATOR_COLUMNS.map((c) => {
                      const v = row[c.group]?.values[c.key];
                      return (
                        <td key={c.key}>
                          {formatNumber(v?.mean)}
                          {v && v.mean !== null && (
                            <span className="planner-ci">
                              {" "}
                              ({formatInterval(v.ciLow, v.ciHigh)})
                            </span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>

            <table className="planner-table">
              <caption>
                Paired difference from the baseline (alternative minus baseline,
                same seeds)
              </caption>
              <thead>
                <tr>
                  <th scope="col">Alternative</th>
                  <th scope="col">Indicator</th>
                  <th scope="col">Baseline</th>
                  <th scope="col">Alternative</th>
                  <th scope="col">Difference</th>
                  <th scope="col">Interval</th>
                  <th scope="col">Reading</th>
                </tr>
              </thead>
              <tbody>
                {comparisons.map((c) => (
                  <tr key={`${c.alternativeId}-${c.metric}`}>
                    <th scope="row">
                      {titleOf.get(c.alternativeId) ?? c.alternativeId}
                    </th>
                    <td>{metricText(c.metric)}</td>
                    <td>{formatNumber(c.baselineMean)}</td>
                    <td>{formatNumber(c.alternativeMean)}</td>
                    <td>{formatNumber(c.delta)}</td>
                    <td>{formatInterval(c.ciLow, c.ciHigh)}</td>
                    <td data-verdict={c.verdict}>{verdictText(c)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}

      {missing.length > 0 && (
        <div className="planner-block">
          <h3>Not available in this study</h3>
          <ul>
            {missing.map(([label, reason]) => (
              <li key={label}>
                {label}: not available — {reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="planner-block">
        <h3>Findings</h3>
        <ol className="planner-findings">
          {result.findings.map((f) => (
            <li key={f.id}>
              <p>
                {f.statement}{" "}
                <span className="planner-confidence">
                  (confidence: {f.confidence})
                </span>
              </p>
              <p className="planner-evidence">
                Evidence:{" "}
                {f.evidence.map((e, i) => (
                  <span key={e.path}>
                    {i > 0 && ", "}
                    <code>{e.path}</code>
                  </span>
                ))}
              </p>
              {f.caveats.length > 0 && (
                <ul>
                  {f.caveats.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ol>
      </div>

      <div className="planner-block">
        <h3>Reliability and limitations</h3>
        <p>
          Sample: {result.reliability.repetitions.toString()} repetitions (
          {result.reliability.sampleAdequacy}).
        </p>
        <ul>
          {result.reliability.flags.map((f, i) => (
            <li key={`${f.code}-${i.toString()}`}>{f.message}</li>
          ))}
          {result.limitations.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </div>

      <div className="planner-block">
        <h3>Report</h3>
        <div className="planner-actions">
          <button
            type="button"
            onClick={() => {
              download("json");
            }}
          >
            Download JSON
          </button>
          <button
            type="button"
            onClick={() => {
              download("md");
            }}
          >
            Download Markdown
          </button>
          <button
            type="button"
            onClick={() => {
              download("csv");
            }}
          >
            Download CSV
          </button>
        </div>
        {downloadError && (
          <p role="alert" className="planner-error">
            {downloadError}
          </p>
        )}
      </div>

      <div className="planner-block">
        <h3>Reproducibility</h3>
        <dl className="planner-provenance">
          <dt>Study id</dt>
          <dd>
            <code>{studyId}</code>
          </dd>
          <dt>Scenario fingerprint</dt>
          <dd>
            <code>{result.meta.scenarioFingerprint}</code>
          </dd>
          <dt>Input fingerprint</dt>
          <dd>
            <code>{result.meta.inputFingerprint}</code>
          </dd>
          <dt>Result fingerprint</dt>
          <dd>
            <code>{result.meta.resultFingerprint}</code>
          </dd>
          <dt>Source commit</dt>
          <dd>
            <code>{result.meta.gitCommit}</code>
          </dd>
          <dt>Seeds</dt>
          <dd>{result.meta.seeds.join(", ")}</dd>
        </dl>
        <button
          type="button"
          onClick={runReproduce}
          disabled={reproduce.state === "running"}
        >
          {reproduce.state === "running" ? "Re-running…" : "Reproduce"}
        </button>
        <div aria-live="polite">
          {reproduce.state === "done" &&
            (reproduce.outcome.reproduced ? (
              <p className="planner-ok">
                Reproduced: the re-run gave the same result fingerprint (
                <code>{reproduce.outcome.rerunResultFingerprint}</code>).
              </p>
            ) : (
              <p className="planner-error">
                Not reproduced: the re-run gave{" "}
                <code>{reproduce.outcome.rerunResultFingerprint}</code> instead
                of <code>{reproduce.outcome.originalResultFingerprint}</code>
                {reproduce.outcome.gitCommitOriginal !==
                  reproduce.outcome.gitCommitRerun &&
                  " (the server now runs a different commit)"}
                .
              </p>
            ))}
          {reproduce.state === "failed" && (
            <p role="alert" className="planner-error">
              {reproduce.message}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
