import { Check, Minus, X } from "lucide-react";
import type {
  AlternativeAnalysis,
  ExperimentResult,
  Proportion,
} from "../../services/v3/experiments";
import {
  BASIS_TEXT,
  CLASS_TEXT,
  boundsText,
  criterionLabel,
  criterionStatus,
  distributionText,
  exclusionText,
  factorLabel,
  indicatorText,
  percent,
  percentInterval,
  seconds,
  secondsInterval,
  toleranceText,
} from "./experimentText";

/** A server detail string as a sentence: first letter capitalised. */
function sentence(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const NO_COMPARISON = "No valid condition to compare.";

function Share({ value, of }: { value: Proportion; of: number }) {
  return (
    <>
      {percent(value.p)}
      <span className="experiment-ci">
        {" "}
        ({value.count.toString()} of {of.toString()}) · 95 % interval{" "}
        {percentInterval(value.ci)}
      </span>
    </>
  );
}

function StatusIcon({ passed }: { passed: boolean | null }) {
  const Icon = passed === true ? Check : passed === false ? X : Minus;
  return <Icon className="experiment-criterion-icon" aria-hidden="true" />;
}

/** The finished experiment: limitations first, then what was run, whether it
 *  may be called robust, and the tables. Table first; there are no charts. */
export function ExperimentResultView({ result }: { result: ExperimentResult }) {
  const a = result.analysis;
  const labels = new Map(
    result.alternatives.map((x) => [x.id, x.label || x.id]),
  );
  const label = (id: string) => labels.get(id) ?? id;
  const indicator = indicatorText(a.primaryIndicator);
  const valid = a.counts.validConditions;
  const others = Object.entries(a.alternatives).filter(
    ([, alt]) => !alt.isBaseline,
  );
  const all = Object.entries(a.alternatives);
  const verdict = CLASS_TEXT[a.eligibility.class];

  return (
    <div className="experiment-result">
      <section className="experiment-banner" aria-labelledby="exp-limits-title">
        <h2 id="exp-limits-title">Read this first</h2>
        <p className="experiment-validity">
          <strong>Real-world validity: {a.realWorldValidity}</strong>
        </p>
        <p>
          Every input range below is an assumption, and this simulation is not
          calibrated to observed traffic. The results describe how the
          alternatives compare under those assumptions.
        </p>
        <ul>
          {a.limitations.map((text) => (
            <li key={text}>{text}</li>
          ))}
        </ul>
      </section>

      <section className="experiment-block" aria-labelledby="exp-run-title">
        <h2 id="exp-run-title">What was run</h2>
        <dl className="experiment-facts">
          <div>
            <dt>Sampled conditions</dt>
            <dd>{a.counts.conditions.toString()}</dd>
          </div>
          <div>
            <dt>Replications per condition</dt>
            <dd>{a.counts.replications.toString()}</dd>
          </div>
          <div>
            <dt>Alternatives</dt>
            <dd>{a.counts.alternatives.toString()}</dd>
          </div>
          <div>
            <dt>Total simulation runs</dt>
            <dd>{a.counts.totalRuns.toString()}</dd>
          </div>
          <div>
            <dt>Valid conditions</dt>
            <dd>{valid.toString()}</dd>
          </div>
          <div>
            <dt>Excluded conditions</dt>
            <dd>
              {a.exclusions.excluded.toString()} (
              {exclusionText(a.exclusions.byReason)})
            </dd>
          </div>
        </dl>
        <p>
          {a.counts.conditions.toString()} conditions ×{" "}
          {a.counts.alternatives.toString()} alternatives ×{" "}
          {a.counts.replications.toString()} replications ={" "}
          {a.counts.totalRuns.toString()} runs. The unit of inference is the
          condition: what this experiment says about uncertainty rests on{" "}
          {valid.toString()} valid conditions, not on{" "}
          {a.counts.totalRuns.toString()} runs.
        </p>
        <p className="experiment-muted">
          Every alternative ran the same scenario with the same random numbers
          in each condition, so the comparison is paired. Compared on{" "}
          {indicator} (lower is better); {toleranceText(a.tolerance)}.
        </p>
      </section>

      <section
        className="experiment-block"
        aria-labelledby="exp-eligibility-title"
      >
        <h2 id="exp-eligibility-title">Can this be called robust?</h2>
        <p className="experiment-class">
          <strong>{verdict.label}.</strong> {verdict.explanation}
        </p>
        <ul className="experiment-criteria">
          {a.eligibility.criteria.map((c) => (
            <li key={c.id}>
              <StatusIcon passed={c.passed} />
              <span>
                <strong>{criterionLabel(c.id)}:</strong>{" "}
                {criterionStatus(c.passed)}. {sentence(c.detail)}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="experiment-block" aria-labelledby="exp-compare-title">
        <h2 id="exp-compare-title">
          Comparison with the baseline ({label(a.baseline)})
        </h2>
        <table className="experiment-table">
          <caption>
            Share of the {valid.toString()} valid conditions in which each
            alternative has a lower (better), similar (tie) or higher (worse){" "}
            {indicator} than the baseline. A tie is a result, and it counts in
            every share. These are descriptive comparisons, not a ranking and
            not a test of significance.
          </caption>
          <thead>
            <tr>
              <th scope="col">Alternative</th>
              <th scope="col">Better (win)</th>
              <th scope="col">About the same (tie)</th>
              <th scope="col">Worse (loss)</th>
              <th scope="col">Mean difference</th>
              <th scope="col">Median difference</th>
            </tr>
          </thead>
          <tbody>
            {others.map(([id, alt]: [string, AlternativeAnalysis]) =>
              alt.comparison ? (
                <tr key={id}>
                  <th scope="row">{label(id)}</th>
                  <td>
                    <Share value={alt.comparison.win} of={valid} />
                  </td>
                  <td>
                    <Share value={alt.comparison.tie} of={valid} />
                  </td>
                  <td>
                    <Share value={alt.comparison.loss} of={valid} />
                  </td>
                  <td>
                    {seconds(alt.comparison.difference.mean.value)}
                    <span className="experiment-ci">
                      {" "}
                      95 % interval{" "}
                      {secondsInterval(alt.comparison.difference.mean.ci)}
                    </span>
                  </td>
                  <td>
                    {seconds(alt.comparison.difference.median.value)}
                    <span className="experiment-ci">
                      {" "}
                      95 % interval{" "}
                      {secondsInterval(alt.comparison.difference.median.ci)}
                    </span>
                  </td>
                </tr>
              ) : (
                <tr key={id}>
                  <th scope="row">{label(id)}</th>
                  <td colSpan={5}>{NO_COMPARISON}</td>
                </tr>
              ),
            )}
          </tbody>
        </table>
        <p className="experiment-muted">
          Difference = the alternative minus the baseline, in seconds; negative
          means the alternative had less {indicator}. The intervals treat the
          conditions as exchangeable draws and are approximate with stratified
          sampling.
        </p>
      </section>

      <section className="experiment-block" aria-labelledby="exp-regret-title">
        <h2 id="exp-regret-title">Regret and preference share</h2>
        <table className="experiment-table">
          <caption>
            Regret is how much worse an alternative is than the best alternative
            in the same condition (never negative). Preference share is the
            share of conditions in which an alternative is within the tie
            tolerance of the best. Shares are not ranked and can add up to more
            than 100 %. Both depend on which alternatives were compared:{" "}
            {all.map(([id]) => label(id)).join(", ")}.
          </caption>
          <thead>
            <tr>
              <th scope="col">Alternative</th>
              <th scope="col">Mean {indicator}</th>
              <th scope="col">Mean regret</th>
              <th scope="col">95th-percentile regret</th>
              <th scope="col">Largest regret in this sample</th>
              <th scope="col">Preference share</th>
            </tr>
          </thead>
          <tbody>
            {all.map(([id, alt]) => (
              <tr key={id}>
                <th scope="row">
                  {label(id)}
                  {alt.isBaseline ? " (baseline)" : ""}
                </th>
                <td>{seconds(alt.meanOutcome)}</td>
                <td>{seconds(alt.regret?.mean)}</td>
                <td>{seconds(alt.regret?.p95)}</td>
                <td>{seconds(alt.regret?.sampleMax)}</td>
                <td>{percent(alt.preferenceShare)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section
        className="experiment-block"
        aria-labelledby="exp-assumptions-title"
      >
        <h2 id="exp-assumptions-title">Assumptions behind these numbers</h2>
        <table className="experiment-table">
          <caption>
            Each factor was drawn from the range shown, with conditions spread
            evenly across it. Unless the basis says otherwise, the range is the
            analyst's assumption, not a measurement.
          </caption>
          <thead>
            <tr>
              <th scope="col">Factor</th>
              <th scope="col">Distribution</th>
              <th scope="col">Range</th>
              <th scope="col">Basis</th>
              <th scope="col">Why</th>
            </tr>
          </thead>
          <tbody>
            {result.assumptions.map((s) => (
              <tr key={s.id}>
                <th scope="row">{factorLabel(s.kind)}</th>
                <td>{distributionText(s)}</td>
                <td>{boundsText(s.bounds)}</td>
                <td>{BASIS_TEXT[s.basis]}</td>
                <td>{s.rationale || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section
        className="experiment-block"
        aria-labelledby="exp-provenance-title"
      >
        <h2 id="exp-provenance-title">Provenance</h2>
        <dl className="experiment-facts experiment-facts--wide">
          <div>
            <dt>Scenario</dt>
            <dd>
              {result.scenario.name} ·{" "}
              <code>{result.scenario.fingerprint}</code>
            </dd>
          </div>
          <div>
            <dt>Specification fingerprint</dt>
            <dd>
              <code>{result.specFingerprint}</code>
            </dd>
          </div>
          <div>
            <dt>Result fingerprint</dt>
            <dd>
              <code>{result.resultFingerprint}</code>
            </dd>
          </div>
          <div>
            <dt>Code version</dt>
            <dd>
              <code>{result.provenance.gitCommit.slice(0, 12)}</code> · Python{" "}
              {result.provenance.pythonVersion}
            </dd>
          </div>
          <div>
            <dt>Sampling</dt>
            <dd>{result.provenance.sampling}</dd>
          </div>
          <div>
            <dt>Wall time</dt>
            <dd>
              {result.execution.wallSeconds.toString()} s on{" "}
              {result.execution.workers.toString()} worker
              {result.execution.workers === 1 ? "" : "s"} (this does not affect
              the result)
            </dd>
          </div>
        </dl>
        <p className="experiment-muted">
          The same specification, scenario and seed give the same result
          fingerprint. {result.provenance.note}
        </p>
      </section>
    </div>
  );
}
