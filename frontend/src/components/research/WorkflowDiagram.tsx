import type { ReactNode } from "react";
import {
  ControlsArt,
  DemandArt,
  FindingsArt,
  MetricsArt,
  RunsArt,
  SetupArt,
  StatsArt,
} from "./WorkflowArt";

interface Stage {
  title: string;
  art: ReactNode;
  body: string;
  input: string;
  output: string;
}

/** The research workflow, in the order a study proceeds. Each stage's output
 *  is the next stage's input. */
const STAGES: Stage[] = [
  {
    title: "Junction setup",
    art: <SetupArt />,
    body: "Lanes and lane arrows on each road, road angles, signal timing or roundabout design.",
    input: "Your layout, or a preset",
    output: "One junction description",
  },
  {
    title: "Traffic demand",
    art: <DemandArt />,
    body: "How many vehicles arrive on each road, where they turn, and what kinds of vehicle they are.",
    input: "Demand and turning per road",
    output: "An arrival pattern, fixed by the seed",
  },
  {
    title: "Control strategies",
    art: <ControlsArt />,
    body: "Fixed-time signal, adaptive signal and roundabout, each built on the same junction.",
    input: "The junction",
    output: "One setup per control",
  },
  {
    title: "Simulation runs",
    art: <RunsArt />,
    body: "Every control is run on the same seeds, vehicle by vehicle, so the traffic is identical.",
    input: "Setups and seeds",
    output: "One run per control per seed",
  },
  {
    title: "Metrics",
    art: <MetricsArt />,
    body: "Each run is summarised after a warm-up: delay, vehicles served, queues, stops and more.",
    input: "A finished run",
    output: "Numbers for that run",
  },
  {
    title: "Statistical analysis",
    art: <StatsArt />,
    body: "Repeated seeds give a mean with an interval; paired differences compare the controls.",
    input: "Per-seed numbers",
    output: "Mean ± interval, and a reading per pair",
  },
  {
    title: "Findings",
    art: <FindingsArt />,
    body: "Each comparison reads as lower, about the same or inconclusive, with the conditions it holds under.",
    input: "Readings and the calibration note",
    output: "Evidence about this setup, not a verdict",
  },
];

export function WorkflowDiagram() {
  return (
    <ol className="rl-flow">
      {STAGES.map((stage, i) => (
        <li key={stage.title} className="rl-step">
          <div className="rl-step-head">
            <span className="rl-step-n" aria-hidden="true">
              {i + 1}
            </span>
            <h3>{stage.title}</h3>
          </div>
          {stage.art}
          <p>{stage.body}</p>
          <dl className="rl-io">
            <div>
              <dt>In</dt>
              <dd>{stage.input}</dd>
            </div>
            <div>
              <dt>Out</dt>
              <dd>{stage.output}</dd>
            </div>
          </dl>
        </li>
      ))}
    </ol>
  );
}
