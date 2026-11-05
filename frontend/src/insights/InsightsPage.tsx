import { useState } from "react";
import "./Insights.css";
import { PageHero } from "../components/dashboard/Dashboard";
import { ComparisonBlock } from "../comparison/ComparisonBlock";
import { RunMetricsSection } from "../kpis/MetricPanels";
import { NetworkUpload } from "../network/NetworkUpload";
import { RoadImportPreview } from "../network/RoadImportPreview";
import { NightlyRegressionView } from "../regression/NightlyRegressionView";
import { ReportView } from "../reports/ReportView";
import { RlComparisonChart } from "../rlcompare/RlComparisonChart";
import { CompareRunsView } from "../runcompare/CompareRunsView";
import { SensitivityChart } from "../sensitivity/SensitivityChart";
import { TABS, isTab, type TabId } from "./tabs";
import { RUN_ID_PATTERN, VIEW_ROUTES, navigate, useSearch } from "../routing";

function hrefWith(params: Record<string, string>): string {
  return `${VIEW_ROUTES.insights}?${new URLSearchParams(params).toString()}`;
}

/** Asks for one id and puts it in the address, so the view can be shared. */
function IdPicker({
  label,
  param,
  value,
  tab,
  keep = {},
}: {
  label: string;
  param: string;
  value: string;
  tab: TabId;
  keep?: Record<string, string>;
}) {
  const [draft, setDraft] = useState(value);
  const valid = RUN_ID_PATTERN.test(draft);
  return (
    <form
      className="ins-row"
      onSubmit={(event) => {
        event.preventDefault();
        if (valid) navigate(hrefWith({ ...keep, tab, [param]: draft }));
      }}
    >
      <div className="uf-field">
        <label className="uf-label" htmlFor={`ins-id-${param}`}>
          {label}
        </label>
        <input
          id={`ins-id-${param}`}
          className="uf-input"
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value.trim());
          }}
        />
      </div>
      <button type="submit" className="ins-btn" disabled={!valid}>
        Show
      </button>
    </form>
  );
}

/** Trust and reports: the uncertainty, metric, run-comparison, regression,
 *  report, RL and network screens in one place. The tab and ids live in the
 *  query string. */
export function InsightsPage() {
  const search = useSearch();
  const params = new URLSearchParams(search);
  const tabParam = params.get("tab");
  const tab: TabId = isTab(tabParam) ? tabParam : "results";
  const get = (key: string) => {
    const value = params.get(key) ?? "";
    return RUN_ID_PATTERN.test(value) ? value : "";
  };
  const experiment = get("experiment");
  const run = get("run");
  const rl = get("rl");

  return (
    <div className="ins-page">
      <PageHero eyebrow="Experiments" title="Trust and reports">
        See how sure a result is, compare runs, check last night&apos;s
        regression, print a report, and bring in real road networks.
      </PageHero>
      <div className="ins-tabs" role="tablist" aria-label="Sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`ins-tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls="ins-tabpanel"
            className="ins-tab"
            onClick={() => {
              navigate(hrefWith({ tab: t.id }));
            }}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div
        id="ins-tabpanel"
        role="tabpanel"
        aria-labelledby={`ins-tab-${tab}`}
        className="ins-stack"
      >
        {tab === "results" && (
          <>
            <IdPicker
              label="Experiment ID"
              param="experiment"
              value={experiment}
              tab="results"
              keep={run ? { run } : {}}
            />
            {experiment && <ComparisonBlock experimentId={experiment} />}
            {experiment && <SensitivityChart experimentId={experiment} />}
            <IdPicker
              label="Run ID (for delay, safety and emissions)"
              param="run"
              value={run}
              tab="results"
              keep={experiment ? { experiment } : {}}
            />
            {run && <RunMetricsSection runId={run} />}
          </>
        )}
        {tab === "runs" && (
          <CompareRunsView initialA={get("a")} initialB={get("b")} />
        )}
        {tab === "nightly" && <NightlyRegressionView />}
        {tab === "report" && (
          <>
            <IdPicker
              label="Experiment ID"
              param="experiment"
              value={experiment}
              tab="report"
            />
            {experiment && <ReportView experimentId={experiment} />}
          </>
        )}
        {tab === "rl" && (
          <>
            <IdPicker label="RL comparison ID" param="rl" value={rl} tab="rl" />
            {rl && <RlComparisonChart comparisonId={rl} />}
          </>
        )}
        {tab === "network" && (
          <>
            <NetworkUpload />
            <RoadImportPreview />
          </>
        )}
      </div>
    </div>
  );
}
