import { useId, useState } from "react";
import { GapPlot } from "./GapPlot";
import {
  CONFIDENCE_LEVEL,
  EXAMPLE_TWO,
  pairedReading,
  readingWords,
} from "./evidence";

const RUN_COUNTS = [3, 10] as const;
type RunCount = (typeof RUN_COUNTS)[number];

const X0 = 44;
const X1 = 340;
const Y0 = 128;
const Y1 = 16;
const yOf = (v: number) => Y0 - ((v - 20) / 30) * (Y0 - Y1);

const fix = (v: number) => v.toFixed(1);

/** Why one run is not enough, drawn with made-up numbers. */
export function ComparisonExplainer() {
  const [runs, setRuns] = useState<RunCount>(3);
  const group = useId();
  const a = EXAMPLE_TWO.a.slice(0, runs);
  const b = EXAMPLE_TWO.b.slice(0, runs);
  const diffs = a.map((v, i) => v - b[i]);
  const result = pairedReading(a, b);
  const xOf = (i: number) => X0 + ((i + 0.5) / runs) * (X1 - X0);
  const level = Math.round(CONFIDENCE_LEVEL * 100);

  return (
    <figure className="rl-compare">
      <div className="rl-compare-bar">
        <div role="group" aria-labelledby={group} className="rl-seg">
          <span id={group} className="sr-only">
            Number of runs shown
          </span>
          {RUN_COUNTS.map((n) => (
            <button
              key={n}
              type="button"
              aria-pressed={runs === n}
              onClick={() => {
                setRuns(n);
              }}
            >
              After {n} runs
            </button>
          ))}
        </div>
        <span className="uf-badge rl-example-badge">
          Example data, not an UrbanFlow result
        </span>
      </div>

      <div className="rl-compare-plots">
        <div>
          <p className="rl-small-label">Each run varies</p>
          <svg
            className="rl-svg rl-plot"
            viewBox="0 0 360 160"
            role="img"
            aria-label={`Example average delay for Control A and Control B in each of ${String(runs)} runs. Control A averages ${fix(result.meanA)} s and Control B ${fix(result.meanB)} s, but the runs scatter and in run 3 Control A had the lower delay.`}
          >
            {[20, 30, 40, 50].map((t) => (
              <g key={t}>
                <line
                  className="rl-grid"
                  x1={X0}
                  y1={yOf(t)}
                  x2={X1}
                  y2={yOf(t)}
                />
                <text
                  className="rl-tick-label"
                  x={X0 - 6}
                  y={yOf(t) + 3}
                  textAnchor="end"
                >
                  {t}
                </text>
              </g>
            ))}
            <line
              className="rl-mean-line"
              x1={X0}
              y1={yOf(result.meanA)}
              x2={X1}
              y2={yOf(result.meanA)}
            />
            <line
              className="rl-mean-line is-b"
              x1={X0}
              y1={yOf(result.meanB)}
              x2={X1}
              y2={yOf(result.meanB)}
            />
            {a.map((v, i) => (
              <g key={i}>
                <circle className="rl-dot is-a" cx={xOf(i)} cy={yOf(v)} r="4" />
                <rect
                  className="rl-dot is-b"
                  x={xOf(i) - 3.5}
                  y={yOf(b[i]) - 3.5}
                  width="7"
                  height="7"
                  transform={`rotate(45 ${String(xOf(i))} ${String(yOf(b[i]))})`}
                />
                <text
                  className="rl-tick-label"
                  x={xOf(i)}
                  y="144"
                  textAnchor="middle"
                >
                  {i + 1}
                </text>
              </g>
            ))}
            <text className="rl-note" x="190" y="157" textAnchor="middle">
              Run (each has its own random arrivals)
            </text>
            <text className="rl-note" x={X0} y="9">
              Delay (s)
            </text>
          </svg>
          <ul className="rl-legend">
            <li>
              <span className="rl-key is-a" aria-hidden="true" /> Control A,
              mean {fix(result.meanA)} s
            </li>
            <li>
              <span className="rl-key is-b" aria-hidden="true" /> Control B,
              mean {fix(result.meanB)} s
            </li>
          </ul>
        </div>
        <div>
          <p className="rl-small-label">The gap, with its uncertainty</p>
          <GapPlot
            diffs={diffs}
            mean={result.meanDifference}
            low={result.ciLow}
            high={result.ciHigh}
            domain={[-10, 20]}
            label={`Example gap in average delay, A minus B, after ${String(runs)} runs: mean ${fix(result.meanDifference)} s with a ${String(level)} % interval from ${fix(result.ciLow)} to ${fix(result.ciHigh)} s.`}
          />
          <p className="rl-reading" role="status">
            <strong>
              {readingWords(result.reading, "Control A", "Control B")}.
            </strong>{" "}
            Average gap {fix(result.meanDifference)} s, {String(level)} %
            interval {fix(result.ciLow)} to {fix(result.ciHigh)} s
            {result.ciLow <= 0 && result.ciHigh >= 0
              ? ": it includes 0, so these runs cannot separate the controls."
              : ": it excludes 0."}
          </p>
        </div>
      </div>

      <figcaption>
        <ol className="rl-points">
          <li>
            <strong>Runs differ.</strong> Each dot is one run. In run 3 Control
            A had the lower delay, though its average delay is higher.
          </li>
          <li>
            <strong>A gap needs an interval.</strong> The shaded diamond is the
            average gap; the bar is the range the {String(level)} % interval
            allows.
          </li>
          <li>
            <strong>More runs narrow it.</strong> The same example is
            inconclusive after 3 runs and separated after 10.
          </li>
        </ol>
      </figcaption>
    </figure>
  );
}
