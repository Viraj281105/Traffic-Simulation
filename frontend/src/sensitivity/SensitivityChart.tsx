import { useMemo } from "react";
import { ListOrdered } from "lucide-react";
import "../insights/Insights.css";
import { EmptyHint, Panel, Skeleton } from "../components/dashboard/Dashboard";
import { IntervalPlot } from "../insights/IntervalPlot";
import { isNum, num, percent } from "../insights/format";
import { useRemote } from "../insights/useRemote";
import { getSensitivity } from "./api";
import { rankInputs } from "./rank";
import type { SensitivityResult } from "./types";

export function SensitivityView({ result }: { result: SensitivityResult }) {
  const ranked = rankInputs(result.inputs);
  const top = ranked.length > 0 ? ranked[0] : null;
  return (
    <div className="ins-stack">
      {top && (
        <p>
          <strong>{top.label}</strong> changes{" "}
          {result.metric.label.toLowerCase()} the most: on its own it explains
          about {percent(top.firstOrder)} of the variation.
        </p>
      )}
      <IntervalPlot
        rows={ranked.map((input) => ({
          id: input.id,
          label: input.label,
          value: input.firstOrder,
          ci: input.ci,
        }))}
        unit=""
        ariaLabel={`Share of the variation in ${result.metric.label.toLowerCase()} explained by each input, most influential first`}
      />
      <div className="uf-table-wrap">
        <table className="uf-table">
          <caption>
            Share of the variation in {result.metric.label.toLowerCase()}{" "}
            explained by each input. First effect: the input alone. Total
            effect: including its interactions with other inputs.
          </caption>
          <thead>
            <tr>
              <th scope="col">Rank</th>
              <th scope="col">Input</th>
              <th scope="col">First effect</th>
              <th scope="col">Total effect</th>
            </tr>
          </thead>
          <tbody>
            {ranked.map((input, i) => (
              <tr key={input.id}>
                <td>{i + 1}</td>
                <th scope="row">{input.label}</th>
                <td>
                  {isNum(input.firstOrder)
                    ? percent(input.firstOrder)
                    : "Not available"}
                </td>
                <td>
                  {isNum(input.total) ? percent(input.total) : "Not available"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="ins-muted">
        Method: {result.method.name}, {num(result.method.samples, 0)} samples,
        seed {result.method.seed} (the same seed gives the same ranking).
        {result.method.note ? ` ${result.method.note}` : ""}
      </p>
    </div>
  );
}

/** Which input changes the answer most. */
export function SensitivityChart({
  experimentId,
  metric,
}: {
  experimentId: string;
  metric?: string;
}) {
  const load = useMemo(
    () => () => getSensitivity(experimentId, { metric }),
    [experimentId, metric],
  );
  const state = useRemote(
    load,
    "The sensitivity analysis could not be loaded.",
  );
  return (
    <Panel
      id="ins-sensitivity"
      title="What changes the answer most?"
      subtitle="Inputs ranked by how much of the outcome they explain."
    >
      {state.status === "loading" && <Skeleton lines={4} />}
      {state.status === "notFound" && (
        <EmptyHint icon={<ListOrdered size={22} />} title="No sensitivity yet">
          This experiment has no sensitivity analysis yet.
        </EmptyHint>
      )}
      {state.status === "error" && <p role="alert">{state.message}</p>}
      {state.status === "ready" && <SensitivityView result={state.data} />}
    </Panel>
  );
}
