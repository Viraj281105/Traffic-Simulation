import "../netcommon/network.css";
import { PageHero } from "../components/dashboard/Dashboard";
import { IncidentsTab } from "../incidents/IncidentsTab";
import { ResilienceTab } from "../incidents/ResilienceTab";
import { JobsPanel } from "../jobs/JobsPanel";
import { PriorityTab } from "../priority/PriorityTab";
import { VIEW_ROUTES, navigate, useSearch } from "../routing";
import { TenancyPanel } from "../tenancy/TenancyPanel";
import { V2xTab } from "../v2x/V2xTab";
import { TABS, isTab, type TabId } from "./tabs";

function hrefFor(tab: TabId): string {
  return `${VIEW_ROUTES.resilience}?tab=${tab}`;
}

/** Resilience: incidents and weather, strategy resilience, emergency and
 *  transit priority, connected vehicles, and the account and job queue, as
 *  tabs of one page. The tab lives in the query string (?tab=). */
export function ResiliencePage() {
  const search = useSearch();
  const param = new URLSearchParams(search).get("tab");
  const tab: TabId = isTab(param) ? param : "incidents";
  return (
    <div className="nw-page">
      <PageHero eyebrow="Experiments" title="Resilience">
        Disrupt a network and see how signal strategies cope, what priority for
        emergency vehicles and buses costs and saves, and how much connected
        vehicles help. Every result is inside the model only.
      </PageHero>
      <div className="nw-tabs" role="tablist" aria-label="Resilience sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`res-tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls="res-tabpanel"
            className="nw-tab"
            onClick={() => {
              navigate(hrefFor(t.id));
            }}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div
        id="res-tabpanel"
        role="tabpanel"
        aria-labelledby={`res-tab-${tab}`}
        className="nw-stack"
      >
        {tab === "incidents" && <IncidentsTab />}
        {tab === "resilience" && <ResilienceTab />}
        {tab === "priority" && <PriorityTab />}
        {tab === "cooperation" && <V2xTab />}
        {tab === "account" && (
          <>
            <TenancyPanel />
            <JobsPanel />
          </>
        )}
      </div>
    </div>
  );
}
