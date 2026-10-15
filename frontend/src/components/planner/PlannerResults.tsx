import { useState } from "react";
import {
  Check,
  CircleAlert,
  FileJson,
  FileText,
  RotateCcw,
  ShieldAlert,
  Sheet,
} from "lucide-react";
import {
  PlanningApiError,
  fetchReport,
  reproduceStudy,
  type BaselineComparison,
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
  splitCaveats,
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

const REPORTS: { format: ReportFormat; label: string; icon: typeof Sheet }[] = [
  { format: "json", label: "Download JSON", icon: FileJson },
  { format: "md", label: "Download Markdown", icon: FileText },
  { format: "csv", label: "Download CSV", icon: Sheet },
];

function scaleText(scale: number): string {
  return `×${scale.toString()} demand`;
}

/** A difference with its sign, so "+20.00" and "-6.66" read alike. */
function signed(value: number | null | undefined): string {
  const text = formatNumber(value);
  return typeof value === "number" && Number.isFinite(value) && value > 0
    ? `+${text}`
    : text;
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

/** Comparisons grouped by alternative, in the order the server sent them. */
function byAlternative(rows: BaselineComparison[]) {
  const groups = new Map<string, BaselineComparison[]>();
  for (const c of rows) {
    const list = groups.get(c.alternativeId) ?? [];
    list.push(c);
    groups.set(c.alternativeId, list);
  }
  return [...groups.entries()];
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
  const [downloading, setDownloading] = useState<ReportFormat | null>(null);

  const titleOf = new Map(
    result.alternatives.map((a) => [a.id, a.label || a.strategyTitle]),
  );
  const scales = result.summary.scales;
  const missing = unavailableIndicators(result);
  const confidence = Math.round(result.reliability.confidenceLevel * 100);
  const caveats = splitCaveats(result.findings);
  const baselineTitle =
    titleOf.get(result.comparison.baselineId) ?? result.comparison.baselineId;

  const download = (format: ReportFormat) => {
    setDownloadError(null);
    setDownloading(format);
    fetchReport(studyId, format)
      .then((r) => {
        downloadText(r.filename, r.content, r.type);
      })
      .catch((err: unknown) => {
        setDownloadError(failureText(asError(err)));
      })
      .finally(() => {
        setDownloading((cur) => (cur === format ? null : cur));
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
      className="planner-results uf-reveal"
      aria-labelledby="planner-results-title"
    >
      <header className="planner-results__head">
        <h2 id="planner-results-title" className="planner-results__title">
          Evidence: {result.name}
        </h2>
        <p className="uf-panel__desc">
          Scenario: {result.scenario.name}. Every alternative ran the same
          seeds; each figure is a mean with its {confidence.toString()}%
          interval.
        </p>
      </header>

      <dl className="planner-facts">
        <div>
          <dt>Baseline</dt>
          <dd>{baselineTitle}</dd>
        </div>
        <div>
          <dt>Alternatives</dt>
          <dd>{result.summary.alternatives.toString()}</dd>
        </div>
        <div>
          <dt>Demand levels</dt>
          <dd>{scales.map((s) => `×${s.toString()}`).join("  ")}</dd>
        </div>
        <div>
          <dt>Seeds per alternative</dt>
          <dd>{result.summary.seeds.toString()}</dd>
        </div>
        <div>
          <dt>Interval</dt>
          <dd>{confidence.toString()}%</dd>
        </div>
      </dl>

      <div
        className="uf-callout uf-callout--warning planner-validity"
        role="note"
        aria-label="Validity"
      >
        <ShieldAlert size={18} aria-hidden="true" />
        <div className="uf-callout__body">
          <p className="uf-callout__title">
            {fieldCalibrationText(result.validity.fieldCalibration)}
          </p>
          {result.validity.exploratory && (
            <p>
              Exploratory results: they describe this simulated scenario at
              these demand levels and do not transfer to other junctions.
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
            <ul className="uf-list">
              {result.validity.caveats.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {scales.map((scale) => {
        const rows = result.results.filter((r) => r.demandScale === scale);
        const comparisons = result.comparison.vsBaseline.filter(
          (c) => c.demandScale === scale,
        );
        const headingId = `planner-scale-${scale.toString().replace(".", "_")}`;
        return (
          <section
            key={scale}
            className="uf-panel planner-scale"
            aria-labelledby={headingId}
          >
            <div className="uf-panel__head">
              <h3 id={headingId} className="uf-panel__title">
                {scaleText(scale)}
              </h3>
              <span className="uf-badge planner-vph">
                {formatNumber(rows[0]?.demandVph, 0)} veh/h
              </span>
            </div>

            <div className="uf-table-wrap">
              <table className="uf-table planner-indicators">
                <caption>
                  Indicators per alternative: mean across{" "}
                  {result.summary.seeds.toString()} seeds, with its {confidence}
                  % interval
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Alternative</th>
                    {INDICATOR_COLUMNS.map((c) => (
                      <th scope="col" key={c.key} className="is-num">
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
                        {row.alternativeId === result.comparison.baselineId && (
                          <span className="planner-tag">Baseline</span>
                        )}
                      </th>
                      {INDICATOR_COLUMNS.map((c) => {
                        const v = row[c.group]?.values[c.key];
                        const known = !!v && v.mean !== null;
                        return (
                          <td key={c.key} className="is-num">
                            <span
                              className={
                                known ? "planner-mean" : "planner-mean is-na"
                              }
                            >
                              {formatNumber(v?.mean)}
                            </span>
                            {known && (
                              <span className="planner-ci">
                                <span className="sr-only">interval </span>
                                {formatInterval(v.ciLow, v.ciHigh)}
                              </span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="uf-table-wrap">
              <table className="uf-table planner-paired">
                <caption>
                  Paired difference from the baseline (alternative minus
                  baseline, same seeds)
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Alternative</th>
                    <th scope="col">Indicator</th>
                    <th scope="col" className="is-num">
                      Baseline
                    </th>
                    <th scope="col" className="is-num">
                      Alternative
                    </th>
                    <th scope="col" className="is-num">
                      Difference
                    </th>
                    <th scope="col" className="is-num">
                      Interval
                    </th>
                    <th scope="col">Reading</th>
                  </tr>
                </thead>
                {byAlternative(comparisons).map(([alternativeId, group]) => (
                  <tbody key={alternativeId} className="planner-paired__group">
                    {group.map((c, i) => (
                      <tr key={`${c.alternativeId}-${c.metric}`}>
                        {i === 0 && (
                          <th scope="rowgroup" rowSpan={group.length}>
                            {titleOf.get(alternativeId) ?? alternativeId}
                          </th>
                        )}
                        <td>{metricText(c.metric)}</td>
                        <td className="is-num">
                          {formatNumber(c.baselineMean)}
                        </td>
                        <td className="is-num">
                          {formatNumber(c.alternativeMean)}
                        </td>
                        <td className="is-num planner-delta">
                          {signed(c.delta)}
                        </td>
                        <td className="is-num planner-interval">
                          {formatInterval(c.ciLow, c.ciHigh)}
                        </td>
                        <td data-verdict={c.verdict}>
                          <span className={`planner-verdict is-${c.verdict}`}>
                            {verdictText(c)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                ))}
              </table>
            </div>
          </section>
        );
      })}

      <div className="planner-results__grid">
        <section
          className="uf-panel planner-findings-panel"
          aria-labelledby="planner-findings-title"
        >
          <div>
            <h3 id="planner-findings-title" className="uf-panel__title">
              Findings
            </h3>
            <p className="uf-panel__desc">
              Each finding names the results it is read from (its evidence).
            </p>
          </div>
          {caveats.shared.length > 0 && (
            <div className="planner-shared">
              <p className="uf-subhead">Caveats on several findings</p>
              <ol className="uf-list planner-shared__list">
                {caveats.shared.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ol>
            </div>
          )}
          <ol className="planner-findings">
            {result.findings.map((f) => {
              const own = caveats.own.get(f.id) ?? [];
              const refs = caveats.refs.get(f.id) ?? [];
              return (
                <li key={f.id} className="planner-finding">
                  <p className="planner-finding__statement">{f.statement}</p>
                  <div className="planner-finding__meta">
                    <span
                      className={`uf-badge planner-confidence is-${f.confidence}`}
                    >
                      Confidence: {f.confidence}
                    </span>
                    {refs.length > 0 && (
                      <span className="uf-hint">
                        See shared caveat
                        {refs.length > 1 ? "s" : ""}{" "}
                        {refs.map((i) => (i + 1).toString()).join(", ")}
                      </span>
                    )}
                  </div>
                  {own.length > 0 && (
                    <ul className="uf-list">
                      {own.map((c) => (
                        <li key={c}>{c}</li>
                      ))}
                    </ul>
                  )}
                  <details className="planner-evidence">
                    <summary>Evidence ({f.evidence.length.toString()})</summary>
                    <ul>
                      {f.evidence.map((e) => (
                        <li key={e.path}>
                          <code>{e.path}</code>
                        </li>
                      ))}
                    </ul>
                  </details>
                </li>
              );
            })}
          </ol>
        </section>

        <div className="planner-results__side">
          <section
            className="uf-panel"
            aria-labelledby="planner-reliability-title"
          >
            <h3 id="planner-reliability-title" className="uf-panel__title">
              Reliability and limitations
            </h3>
            <p className="planner-sample">
              Sample: {result.reliability.repetitions.toString()} repetitions (
              {result.reliability.sampleAdequacy}).
            </p>
            <ul className="uf-list">
              {result.reliability.flags.map((f, i) => (
                <li key={`${f.code}-${i.toString()}`}>{f.message}</li>
              ))}
              {result.limitations.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </section>

          {missing.length > 0 && (
            <section
              className="uf-panel"
              aria-labelledby="planner-missing-title"
            >
              <h3 id="planner-missing-title" className="uf-panel__title">
                Not available in this study
              </h3>
              <ul className="uf-list">
                {missing.map(([label, reason]) => (
                  <li key={label}>
                    {label}: not available — {reason}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>

      <div className="planner-results__end">
        <section className="uf-panel" aria-labelledby="planner-report-title">
          <div>
            <h3 id="planner-report-title" className="uf-panel__title">
              Report
            </h3>
            <p className="uf-panel__desc">
              The server writes each file from this study's stored result.
            </p>
          </div>
          <div className="planner-actions">
            {REPORTS.map(({ format, label, icon: Icon }) => (
              <button
                key={format}
                type="button"
                className="pb-btn pb-secondary"
                aria-busy={downloading === format}
                onClick={() => {
                  download(format);
                }}
              >
                {downloading === format ? (
                  <span className="uf-spinner" aria-hidden="true" />
                ) : (
                  <Icon size={15} aria-hidden="true" />
                )}
                {label}
              </button>
            ))}
          </div>
          {downloadError && (
            <div
              role="alert"
              className="uf-callout uf-callout--danger uf-reveal"
            >
              <CircleAlert size={17} aria-hidden="true" />
              <div className="uf-callout__body">
                <p>{downloadError}</p>
              </div>
            </div>
          )}
        </section>

        <section className="uf-panel" aria-labelledby="planner-reproduce-title">
          <div>
            <h3 id="planner-reproduce-title" className="uf-panel__title">
              Reproducibility
            </h3>
            <p className="uf-panel__desc">
              Re-running the study on the server should give the same result
              fingerprint.
            </p>
          </div>
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
          <div>
            <button
              type="button"
              className="pb-btn pb-secondary"
              onClick={runReproduce}
              disabled={reproduce.state === "running"}
            >
              {reproduce.state === "running" ? (
                <>
                  <span className="uf-spinner" aria-hidden="true" />
                  Re-running…
                </>
              ) : (
                <>
                  <RotateCcw size={15} aria-hidden="true" />
                  Reproduce
                </>
              )}
            </button>
          </div>
          <div aria-live="polite">
            {reproduce.state === "done" &&
              (reproduce.outcome.reproduced ? (
                <div className="uf-callout uf-callout--success uf-reveal">
                  <Check size={17} aria-hidden="true" />
                  <div className="uf-callout__body">
                    <p>
                      Reproduced: the re-run gave the same result fingerprint (
                      <code>{reproduce.outcome.rerunResultFingerprint}</code>).
                    </p>
                  </div>
                </div>
              ) : (
                <div className="uf-callout uf-callout--warning uf-reveal">
                  <CircleAlert size={17} aria-hidden="true" />
                  <div className="uf-callout__body">
                    <p>
                      Not reproduced: the re-run gave{" "}
                      <code>{reproduce.outcome.rerunResultFingerprint}</code>{" "}
                      instead of{" "}
                      <code>{reproduce.outcome.originalResultFingerprint}</code>
                      {reproduce.outcome.gitCommitOriginal !==
                        reproduce.outcome.gitCommitRerun &&
                        " (the server now runs a different commit)"}
                      .
                    </p>
                  </div>
                </div>
              ))}
            {reproduce.state === "failed" && (
              <div
                role="alert"
                className="uf-callout uf-callout--danger uf-reveal"
              >
                <CircleAlert size={17} aria-hidden="true" />
                <div className="uf-callout__body">
                  <p>{reproduce.message}</p>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>
    </section>
  );
}
