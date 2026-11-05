import { useMemo } from "react";
import { CircleCheck, Scale } from "lucide-react";
import "../insights/Insights.css";
import {
  EmptyHint,
  Panel,
  Pill,
  Skeleton,
  type Tone,
} from "../components/dashboard/Dashboard";
import { IntervalPlot } from "../insights/IntervalPlot";
import { useRemote } from "../insights/useRemote";
import { getComparison } from "./api";
import { ELIGIBILITY_WORDS, describeComparison } from "./comparisonText";
import type { ComparisonResult } from "./types";

const ELIGIBILITY_TONE: Record<ComparisonResult["eligibility"], Tone> = {
  eligible: "good",
  indicative: "warn",
  exploratory: "neutral",
};

/** The comparison itself, from data already in hand. */
export function ComparisonView({ result }: { result: ComparisonResult }) {
  const words = describeComparison(result);
  const eligibility = ELIGIBILITY_WORDS[result.eligibility];
  return (
    <div className="ins-stack">
      <p className="ins-headline">
        <CircleCheck size={20} aria-hidden="true" />
        {words.headline}
      </p>
      <p>{words.sentence}</p>
      <IntervalPlot
        rows={[
          {
            id: "gap",
            label: `${result.a.label} minus ${result.b.label}`,
            value: result.meanDifference,
            ci: result.ci,
            tone: result.verdict === "no_clear_difference" ? "muted" : "good",
          },
        ]}
        unit={result.metric.unit}
        reference={0}
        referenceLabel="no difference"
        ariaLabel={`Gap in ${result.metric.label.toLowerCase()} between ${result.a.label} and ${result.b.label}, with its confidence interval`}
      />
      <ul className="ins-facts">
        <li>{words.confidence}</li>
        <li>{words.pValue}</li>
        <li>{words.method}</li>
      </ul>
      <p className="ins-muted">
        <Pill tone={ELIGIBILITY_TONE[result.eligibility]}>
          {eligibility.label}
        </Pill>{" "}
        {eligibility.text}
      </p>
    </div>
  );
}

/** The "A beats B" block of the results page: loads the comparison for an
 *  experiment and states it in plain words. */
export function ComparisonBlock({
  experimentId,
  a,
  b,
  metric,
}: {
  experimentId: string;
  a?: string;
  b?: string;
  metric?: string;
}) {
  const load = useMemo(
    () => () => getComparison(experimentId, { a, b, metric }),
    [experimentId, a, b, metric],
  );
  const state = useRemote(load, "The comparison could not be loaded.");
  return (
    <Panel
      id="ins-comparison"
      title="Which option is better?"
      subtitle="Paired comparison with its uncertainty."
    >
      {state.status === "loading" && <Skeleton lines={4} />}
      {state.status === "notFound" && (
        <EmptyHint icon={<Scale size={22} />} title="No comparison yet">
          This experiment has no comparison result yet.
        </EmptyHint>
      )}
      {state.status === "error" && <p role="alert">{state.message}</p>}
      {state.status === "ready" && <ComparisonView result={state.data} />}
    </Panel>
  );
}
