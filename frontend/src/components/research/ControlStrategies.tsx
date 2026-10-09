import type { ReactNode } from "react";
import { JunctionPreview } from "../scenario/JunctionPreview";
import { DEFAULT_SCENARIO } from "../../scenario/scenarioModel";
import { ADAPTIVE_DEFAULTS, DEFAULT_CONFIG_VALUES } from "../../types/config";
import { AdaptiveArt, FixedTimeArt, RoundaboutArt } from "./StrategyArt";

const {
  greenDuration,
  yellowDuration,
  allRedDuration,
  criticalGap,
  followUpTime,
} = DEFAULT_CONFIG_VALUES;
const { minGreen, maxGreen, extensionStep, detectionDistance } =
  ADAPTIVE_DEFAULTS;

interface Strategy {
  id: string;
  name: string;
  tone: "signal" | "adaptive" | "roundabout";
  art: ReactNode;
  how: string;
  params: string[];
}

const STRATEGIES: Strategy[] = [
  {
    id: "fixed",
    name: "Fixed-time signal",
    tone: "signal",
    art: <FixedTimeArt />,
    how: "Greens follow a timetable, whether or not anyone is waiting.",
    params: [
      `Green ${String(greenDuration)} s`,
      `Yellow ${String(yellowDuration)} s`,
      `All-red ${String(allRedDuration)} s`,
    ],
  },
  {
    id: "adaptive",
    name: "Adaptive signal",
    tone: "adaptive",
    art: <AdaptiveArt />,
    how: "Same phases, but detectors at the stop lines decide when each green ends.",
    params: [
      `Min green ${String(minGreen)} s`,
      `Max green ${String(maxGreen)} s`,
      `Passage ${String(extensionStep)} s`,
      `Detection zone ${String(detectionDistance)} m`,
    ],
  },
  {
    id: "roundabout",
    name: "Roundabout",
    tone: "roundabout",
    art: <RoundaboutArt />,
    how: "No signal: drivers give way to circulating traffic and enter at an accepted gap.",
    params: [
      `Critical gap ${criticalGap.toFixed(1)} s`,
      `Follow-up ${String(followUpTime)} s`,
      "Ring design (lanes, radii)",
    ],
  },
];

/** The three controls side by side, with what they share and what they do
 *  not. Defaults shown are the engine's own. */
export function ControlStrategies() {
  return (
    <div className="rl-strategies">
      <div className="rl-same">
        <div className="rl-same-plans">
          <figure>
            <JunctionPreview scenario={DEFAULT_SCENARIO} view="signal" />
            <figcaption>As a signal</figcaption>
          </figure>
          <figure>
            <JunctionPreview scenario={DEFAULT_SCENARIO} view="roundabout" />
            <figcaption>As a roundabout</figcaption>
          </figure>
        </div>
        <div className="rl-same-text">
          <h3>The same in every comparison</h3>
          <p>
            Geometry, lanes, traffic, vehicles, duration and seeds. Plans drawn
            by the scenario builder; only the control changes.
          </p>
        </div>
      </div>
      <div className="rl-strategy-grid">
        {STRATEGIES.map((s) => (
          <article key={s.id} className={`rl-strategy is-${s.tone}`}>
            <h3>
              <span className="rl-swatch" aria-hidden="true" />
              {s.name}
            </h3>
            {s.art}
            <p>{s.how}</p>
            <div>
              <p className="rl-small-label">Settings of this control</p>
              <ul className="rl-params">
                {s.params.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
