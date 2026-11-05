import "../netcommon/network.css";
import { PairedChart } from "../rescommon/PairedChart";
import {
  DroppedNote,
  SafetyBadges,
  StatTable,
  Verdict,
} from "./ComparisonParts";
import type { TransitComparison } from "./types";

/** Transit priority on versus off: person delay and bus lateness first. */
export function TransitResult({ result }: { result: TransitComparison }) {
  const c = result.comparison;
  const on = result.perSeed.withPriority;
  const off = result.perSeed.baseline;
  return (
    <div className="nw-stack">
      <Verdict stat={c.personDelayPerPerson} />
      <PairedChart
        seeds={result.seeds}
        baseline={off.personDelayPerPerson}
        treated={on.personDelayPerPerson}
        baselineLabel="Without priority"
        treatedLabel="With priority"
        unit="Person delay (s per person)"
        ariaLabel="Person delay for each seed, without and with transit priority"
      />
      <Verdict stat={c.busScheduleLateness} />
      <PairedChart
        seeds={result.seeds}
        baseline={off.busScheduleLateness}
        treated={on.busScheduleLateness}
        baselineLabel="Without priority"
        treatedLabel="With priority"
        unit="Bus lateness at the stop line (s)"
        ariaLabel="Bus lateness for each seed, without and with transit priority"
      />
      <StatTable stats={Object.values(c)} withLabel="With priority" />
      <h3 className="nw-headline">Safety audit</h3>
      <ul className="nw-list">
        <SafetyBadges
          name="With priority"
          safety={result.safety.withPriority}
        />
        <SafetyBadges name="Without" safety={result.safety.baseline} />
      </ul>
      <DroppedNote dropped={result.droppedSeeds} />
      <p className="nw-muted">{result.label}</p>
    </div>
  );
}
