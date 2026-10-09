import { useId, useState } from "react";
import { GapPlot } from "./GapPlot";
import {
  CONFIDENCE_LEVEL,
  CONTROL_NAME,
  EXAMPLE_PAIRS,
  EXAMPLE_THREE,
  T_95,
  pairedReading,
  readingWords,
} from "./evidence";
import type { ExampleControl } from "./evidence";

const CONTROLS: ExampleControl[] = ["fixed_time", "adaptive", "roundabout"];
const fix = (v: number) => v.toFixed(1);
const signed = (v: number) => (v > 0 ? `+${fix(v)}` : fix(v));
const mean = (xs: readonly number[]) =>
  xs.reduce((s, x) => s + x, 0) / xs.length;

/**
 * Five matched seeds, three controls, made-up delays: how per-seed gaps
 * become a mean gap, an interval and a reading. The reading is computed by
 * the same rule the backend applies (evidence.ts), so the example can never
 * teach a different rule from the one implemented.
 */
export function PairedExample() {
  const [pairIndex, setPairIndex] = useState(0);
  const group = useId();
  const pair = EXAMPLE_PAIRS[pairIndex];
  const a = EXAMPLE_THREE[pair.a];
  const b = EXAMPLE_THREE[pair.b];
  const diffs = a.map((v, i) => v - b[i]);
  const result = pairedReading(a, b);
  const nameA = CONTROL_NAME[pair.a];
  const nameB = CONTROL_NAME[pair.b];
  const level = Math.round(CONFIDENCE_LEVEL * 100);
  const n = a.length;
  const gap = Math.abs(result.meanA - result.meanB);
  const tied = result.reading === "tie";

  return (
    <figure className="rl-paired">
      <div className="rl-compare-bar">
        <div role="group" aria-labelledby={group} className="rl-seg">
          <span id={group} className="sr-only">
            Pair of controls to compare
          </span>
          {EXAMPLE_PAIRS.map((p, i) => (
            <button
              key={p.key}
              type="button"
              aria-pressed={pairIndex === i}
              onClick={() => {
                setPairIndex(i);
              }}
            >
              {CONTROL_NAME[p.a]} vs {CONTROL_NAME[p.b]}
            </button>
          ))}
        </div>
        <span className="uf-badge rl-example-badge">
          Illustrative numbers, not a study result
        </span>
      </div>

      <div className="rl-paired-grid">
        <div className="multi-run-scroll">
          <table className="plain-table rl-paired-table">
            <caption>
              Average delay per vehicle (s), one run per seed and control
            </caption>
            <thead>
              <tr>
                <th scope="col">Seed</th>
                {CONTROLS.map((c) => (
                  <th
                    scope="col"
                    key={c}
                    className={c === pair.a || c === pair.b ? "is-picked" : ""}
                  >
                    {CONTROL_NAME[c]}
                  </th>
                ))}
                <th scope="col" className="is-gap">
                  Gap: {nameA} − {nameB}
                </th>
              </tr>
            </thead>
            <tbody>
              {EXAMPLE_THREE.seeds.map((seed, i) => (
                <tr key={seed}>
                  <th scope="row">{seed}</th>
                  {CONTROLS.map((c) => (
                    <td
                      key={c}
                      className={
                        c === pair.a || c === pair.b ? "is-picked" : ""
                      }
                    >
                      {EXAMPLE_THREE[c][i]}
                    </td>
                  ))}
                  <td className="is-gap">{signed(diffs[i])}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th scope="row">Mean</th>
                {CONTROLS.map((c) => (
                  <td
                    key={c}
                    className={c === pair.a || c === pair.b ? "is-picked" : ""}
                  >
                    {fix(mean(EXAMPLE_THREE[c]))}
                  </td>
                ))}
                <td className="is-gap">{signed(result.meanDifference)}</td>
              </tr>
            </tfoot>
          </table>
        </div>

        <div>
          <p className="rl-small-label">
            Mean gap and its {String(level)} % interval
          </p>
          <GapPlot
            diffs={diffs}
            mean={result.meanDifference}
            low={result.ciLow}
            high={result.ciHigh}
            domain={[-10, 20]}
            tieBand={result.tieBand}
            label={`Example gap, ${nameA} minus ${nameB}, over ${String(n)} matched seeds: mean ${fix(result.meanDifference)} s with a ${String(level)} % interval from ${fix(result.ciLow)} to ${fix(result.ciHigh)} s. The shaded band is the tie tolerance, plus or minus ${fix(result.tieBand)} s.`}
          />
          <p className="rl-small-note">
            Shaded band: the tie tolerance for these two means (±{" "}
            {fix(result.tieBand)} s).
          </p>
        </div>
      </div>

      <ol className="rl-working" role="status">
        <li>
          <strong>Tie check first.</strong> The means differ by {fix(gap)} s;
          the tolerance is {fix(result.tieBand)} s, so{" "}
          {tied ? "they count as about the same." : "this is not a tie."}
        </li>
        <li>
          <strong>Then the interval.</strong> Mean gap{" "}
          {signed(result.meanDifference)} s ± {fix(result.half)} s (t ={" "}
          {String(T_95[n - 1])} × {fix(result.sd)} ÷ √{n}), so{" "}
          {fix(result.ciLow)} to {fix(result.ciHigh)} s, which{" "}
          {result.ciLow <= 0 && result.ciHigh >= 0 ? "includes" : "excludes"} 0.
        </li>
        <li>
          <strong>
            Reading: {readingWords(result.reading, nameA, nameB)}.
          </strong>{" "}
          {tied
            ? "The tie rule decides before the interval is consulted."
            : result.reading === "inconclusive"
              ? "The gap is larger than the tolerance, but these seeds cannot separate the controls."
              : "The interval excludes 0 and the gap is larger than the tolerance."}
        </li>
      </ol>
    </figure>
  );
}
