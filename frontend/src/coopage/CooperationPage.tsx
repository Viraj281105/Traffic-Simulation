import "../netcommon/network.css";
import { PageHero } from "../components/dashboard/Dashboard";
import { AimTab } from "../aim/AimTab";
import { CostTab } from "../costing/CostTab";
import { GovernanceTab } from "../governance/GovernanceTab";
import { PlatoonTab } from "../platoon/PlatoonTab";
import { VIEW_ROUTES, navigate, useSearch } from "../routing";
import { TABS, isTab, type TabId } from "./tabs";

function hrefFor(tab: TabId): string {
  return `${VIEW_ROUTES.cooperation}?tab=${tab}`;
}

/** Cooperation: vehicle platoons, signal-free intersections, advisory
 *  recommendations with an audit log, and cost estimates, as tabs of one
 *  page. The tab lives in the query string (?tab=). */
export function CooperationPage() {
  const search = useSearch();
  const param = new URLSearchParams(search).get("tab");
  const tab: TabId = isTab(param) ? param : "platoons";
  return (
    <div className="nw-page">
      <PageHero eyebrow="Experiments" title="Cooperation">
        Try vehicle platoons and signal-free intersections, keep a reviewed
        record of recommendations, and estimate what runs cost. Every traffic
        result is an in-model estimate, not a field measurement.
      </PageHero>
      <div className="nw-tabs" role="tablist" aria-label="Cooperation sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`coop-tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls="coop-tabpanel"
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
        id="coop-tabpanel"
        role="tabpanel"
        aria-labelledby={`coop-tab-${tab}`}
        className="nw-stack"
      >
        {tab === "platoons" && <PlatoonTab />}
        {tab === "signal-free" && <AimTab />}
        {tab === "governance" && <GovernanceTab />}
        {tab === "cost" && <CostTab />}
      </div>
    </div>
  );
}
