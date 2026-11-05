import "../netcommon/network.css";
import { PairedChart } from "../rescommon/PairedChart";
import {
  DroppedNote,
  SafetyBadges,
  StatTable,
  Verdict,
} from "./ComparisonParts";
import type { EmergencyComparison } from "./types";

/** Emergency pre-emption on versus off: the headline verdict, the per-seed
 *  paired chart, the cost to other vehicles and the safety audit. */
export function EmergencyResult({ result }: { result: EmergencyComparison }) {
  const c = result.comparison;
  const on = result.perSeed.withPreemption;
  const off = result.perSeed.baseline;
  return (
    <div className="nw-stack">
      <Verdict stat={c.emergencyTravelTime} />
      <PairedChart
        seeds={result.seeds}
        baseline={off.travelTime}
        treated={on.travelTime}
        baselineLabel="Without pre-emption"
        treatedLabel="With pre-emption"
        unit="Emergency vehicle travel time (s)"
        ariaLabel="Emergency vehicle travel time for each seed, without and with pre-emption"
      />
      <h3 className="nw-headline">Cost to everyone else</h3>
      <Verdict stat={c.collateralDelay} />
      <PairedChart
        seeds={result.seeds}
        baseline={off.collateralDelay}
        treated={on.collateralDelay}
        baselineLabel="Without pre-emption"
        treatedLabel="With pre-emption"
        unit="Mean time lost by other vehicles (s)"
        ariaLabel="Collateral delay of other vehicles for each seed, without and with pre-emption"
      />
      <StatTable stats={Object.values(c)} withLabel="With pre-emption" />
      <h3 className="nw-headline">Safety audit</h3>
      <ul className="nw-list">
        <SafetyBadges
          name="With pre-emption"
          safety={result.safety.withPreemption}
        />
        <SafetyBadges name="Without" safety={result.safety.baseline} />
      </ul>
      <DroppedNote dropped={result.droppedSeeds} />
      <p className="nw-muted">{result.label}</p>
    </div>
  );
}
