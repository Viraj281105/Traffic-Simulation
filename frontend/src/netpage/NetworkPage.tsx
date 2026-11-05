import "../netcommon/network.css";
import { PageHero } from "../components/dashboard/Dashboard";
import { CalibrationTab } from "../calibration/CalibrationTab";
import { CongestionTab } from "../congestion/CongestionTab";
import { LoadTestTab } from "../loadtest/LoadTestTab";
import { MapTab } from "../mapview/MapTab";
import { MetricsTab } from "../netmetrics/MetricsTab";
import { NetworkRlTab } from "../netrl/NetworkRlTab";
import { VIEW_ROUTES, navigate, useSearch } from "../routing";
import { TwinTab } from "../twinview/TwinTab";
import { TABS, isTab, type TabId } from "./tabs";

function hrefFor(tab: TabId): string {
  return `${VIEW_ROUTES.network}?tab=${tab}`;
}

/** Multi-junction networks: map, congestion spread, network metrics,
 *  calibration, RL, the digital twin and load tests, as tabs of one page.
 *  The tab lives in the query string (?tab=). */
export function NetworkPage() {
  const search = useSearch();
  const param = new URLSearchParams(search).get("tab");
  const tab: TabId = isTab(param) ? param : "map";
  return (
    <div className="nw-page">
      <PageHero eyebrow="Experiments" title="Networks">
        See a whole road network at once: where it fills up, how congestion
        spreads, how well the model matches counts, how a learned controller
        compares, and how the digital twin is keeping up.
      </PageHero>
      <div className="nw-tabs" role="tablist" aria-label="Network sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`nw-tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls="nw-tabpanel"
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
        id="nw-tabpanel"
        role="tabpanel"
        aria-labelledby={`nw-tab-${tab}`}
        className="nw-stack"
      >
        {tab === "map" && <MapTab />}
        {tab === "congestion" && <CongestionTab />}
        {tab === "metrics" && <MetricsTab />}
        {tab === "calibration" && <CalibrationTab />}
        {tab === "rl" && <NetworkRlTab />}
        {tab === "twin" && <TwinTab />}
        {tab === "loadtests" && <LoadTestTab />}
      </div>
    </div>
  );
}
