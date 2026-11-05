import { useMemo } from "react";
import { FileText, Printer } from "lucide-react";
import "../insights/Insights.css";
import { EmptyHint, Pill, Skeleton } from "../components/dashboard/Dashboard";
import { ComparisonView } from "../comparison/ComparisonBlock";
import { RunMetricsView } from "../kpis/MetricPanels";
import { SensitivityView } from "../sensitivity/SensitivityChart";
import { UNAVAILABLE, dateTime } from "../insights/format";
import { useRemote } from "../insights/useRemote";
import { getReport } from "./api";
import type { ReportDocument } from "./types";

/** The report as a printable document. Assumptions and limitations come
 *  first, then the findings with their uncertainty, then the reproducibility
 *  record. "Print or save as PDF" uses the browser's own print dialog. */
export function ReportDocumentView({
  report,
  onPrint = () => {
    window.print();
  },
}: {
  report: ReportDocument;
  onPrint?: () => void;
}) {
  const { manifest } = report;
  return (
    <>
      <div className="ins-row no-print">
        <button type="button" className="ins-btn" onClick={onPrint}>
          <Printer size={15} aria-hidden="true" />
          Print or save as PDF
        </button>
        <span className="ins-muted">
          In the print dialog choose &ldquo;Save as PDF&rdquo;.
        </span>
      </div>
      <article className="ins-report" aria-label={report.title}>
        <h1>{report.title}</h1>
        <p className="ins-muted">Generated {dateTime(report.generatedAt)}</p>

        <section aria-labelledby="rep-assumptions">
          <h2 id="rep-assumptions">Assumptions and limitations</h2>
          <h3 className="uf-subhead">Assumptions</h3>
          <ul className="ins-facts">
            {report.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
          <h3 className="uf-subhead">Limitations</h3>
          <ul className="ins-facts">
            {report.limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="rep-summary">
          <h2 id="rep-summary">Summary</h2>
          <p>{report.summary.text}</p>
          <p className="ins-muted">
            {report.summary.grounded ? (
              <Pill tone="good">Numbers checked</Pill>
            ) : (
              <Pill tone="warn">Numbers not checked</Pill>
            )}{" "}
            {report.summary.grounded
              ? "Every number in this summary was found in the computed results."
              : "The server could not confirm every number in this summary against the computed results."}
          </p>
        </section>

        {report.comparison && (
          <section aria-labelledby="rep-comparison">
            <h2 id="rep-comparison">Which option is better</h2>
            <ComparisonView result={report.comparison} />
          </section>
        )}
        {report.sensitivity && (
          <section aria-labelledby="rep-sensitivity">
            <h2 id="rep-sensitivity">What changes the answer most</h2>
            <SensitivityView result={report.sensitivity} />
          </section>
        )}
        {report.metrics && (
          <section aria-labelledby="rep-metrics">
            <h2 id="rep-metrics">Measures</h2>
            <RunMetricsView metrics={report.metrics} />
          </section>
        )}

        <section aria-labelledby="rep-repro">
          <h2 id="rep-repro">How to reproduce this</h2>
          <dl className="ins-facts">
            <dt>Seed</dt>
            <dd>{manifest.seed ?? UNAVAILABLE}</dd>
            <dt>Configuration</dt>
            <dd>{manifest.configHash ?? UNAVAILABLE}</dd>
            <dt>Code version</dt>
            <dd>{manifest.codeVersion ?? UNAVAILABLE}</dd>
            <dt>Input version</dt>
            <dd>{manifest.inputVersion ?? UNAVAILABLE}</dd>
          </dl>
        </section>
      </article>
    </>
  );
}

/** Loads the report for an experiment and shows it. */
export function ReportView({ experimentId }: { experimentId: string }) {
  const load = useMemo(() => () => getReport(experimentId), [experimentId]);
  const state = useRemote(load, "The report could not be loaded.");
  if (state.status === "loading") return <Skeleton lines={6} />;
  if (state.status === "notFound")
    return (
      <EmptyHint icon={<FileText size={22} />} title="No report yet">
        This experiment has no report yet.
      </EmptyHint>
    );
  if (state.status === "error") return <p role="alert">{state.message}</p>;
  if (state.status === "ready")
    return <ReportDocumentView report={state.data} />;
  return null;
}
