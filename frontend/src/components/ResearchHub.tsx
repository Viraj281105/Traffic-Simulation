import {
  ArrowUpRight,
  ChartSpline,
  History,
  Orbit,
  Sigma,
  TrafficCone,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { VIEW_ROUTES, followLink } from "../routing";
import { PLAIN_METRIC_MAP, metricDef } from "../metrics/plainLanguage";
import { ADAPTIVE_DEFAULTS } from "../types/config";
import { ControlComparisonStudy } from "./ControlComparisonStudy";
import { ScenarioStudy } from "./scenario/ScenarioStudy";

const TOOLS: {
  href: string;
  title: string;
  body: string;
  use: string;
  icon: LucideIcon;
}[] = [
  {
    href: VIEW_ROUTES.volume,
    icon: ChartSpline,
    title: "Traffic-level sweep",
    body: "Runs both controls across a range of demand tiers, one random traffic pattern per tier, and plots delay, throughput and queue against volume, with where the lower-delay control changes and indicative level-of-service bands. Descriptive: use Statistical validation to test a difference.",
    use: "Where does the comparison change as traffic grows?",
  },
  {
    href: VIEW_ROUTES.validation,
    icon: Sigma,
    title: "Statistical validation",
    body: "Monte Carlo study on a configurable scenario: the same random patterns for both controls, Student-t confidence intervals, an unpaired Welch t-test, Cohen’s d, per-seed data and CSV export, plus model integrity checks on both geometries.",
    use: "Is a difference statistically robust for a study design?",
  },
  {
    href: VIEW_ROUTES.signal,
    icon: TrafficCone,
    title: "Signal on its own",
    body: "One signal — fixed-time or adaptive (Signal control in its settings) — with its live metric set, phase state, adaptive decisions, queue labels and stop-line display.",
    use: "How does the signal behave in detail?",
  },
  {
    href: VIEW_ROUTES.roundabout,
    icon: Orbit,
    title: "Roundabout on its own",
    body: "One roundabout with its live metric set, circulating and yielding counts.",
    use: "How does the roundabout behave in detail?",
  },
  {
    href: VIEW_ROUTES.history,
    icon: History,
    title: "Saved runs & reproducibility",
    body: "Every saved run with its exact configuration, seed, code version and metrics; re-run to check determinism, export JSON/CSV, compare up to six runs.",
    use: "Can this result be reproduced and audited?",
  },
];

/** Entry point for specialist tools. The guided comparison is the product's
 *  main path; these tools keep every research capability one click away. */
export function ResearchHub() {
  return (
    <div className="guided-page research-hub">
      <header className="guided-intro">
        <p className="guided-eyebrow">Research lab</p>
        <h1>Tools for deeper analysis</h1>
        <p>
          The guided comparison answers “how would a signal and a roundabout
          handle my junction?”. These tools are for going further: sweeping
          traffic levels, formal statistics, single-control detail and
          reproducibility. They use technical terms throughout.
        </p>
      </header>

      <div className="tool-grid">
        {TOOLS.map((tool) => (
          <a
            key={tool.href}
            className="tool-card"
            href={tool.href}
            onClick={(e) => {
              followLink(e, tool.href);
            }}
          >
            <span className="tool-card-top" aria-hidden="true">
              <span className="tool-icon">
                <tool.icon size={18} strokeWidth={1.9} />
              </span>
              <ArrowUpRight size={16} className="tool-arrow" />
            </span>
            <span className="tool-use">{tool.use}</span>
            <span className="tool-title">{tool.title}</span>
            <span className="tool-body">{tool.body}</span>
          </a>
        ))}
      </div>

      <section className="results-section" aria-labelledby="control-title">
        <h2 id="control-title">
          Signal control: fixed-time, adaptive and roundabout
        </h2>
        <dl className="control-defs">
          <div>
            <dt>Fixed-time signal</dt>
            <dd>
              Predetermined timings: every green runs its configured length (30
              s by default, paired north–south / east–west plan), whether or not
              anyone is there.
            </dd>
          </div>
          <div>
            <dt>Adaptive signal</dt>
            <dd>
              Responds to observed simulated demand: the same phase plan, yellow
              and all-red as the fixed-time signal, but each green is ended by
              stop-line detection (vehicle-actuated control).
            </dd>
          </div>
          <div>
            <dt>Roundabout</dt>
            <dd>
              No signal: drivers give way to circulating traffic and enter at an
              accepted gap.
            </dd>
          </div>
        </dl>
        <h3>How the adaptive signal decides</h3>
        <div className="multi-run-scroll">
          <table className="plain-table">
            <thead>
              <tr>
                <th scope="col">Rule</th>
                <th scope="col">What it does</th>
                <th scope="col">Setting (default)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Detection</th>
                <td>
                  Counts vehicles in the last metres before each stop line, on
                  the lanes a phase releases. A vehicle moving at ≥ 1 m/s is
                  “passing”; a standing one is demand but does not extend a
                  green.
                </td>
                <td>
                  <code>detectionDistance</code> (
                  {ADAPTIVE_DEFAULTS.detectionDistance} m)
                </td>
              </tr>
              <tr>
                <th scope="row">Minimum green</th>
                <td>A green never ends earlier, so a standing queue starts.</td>
                <td>
                  <code>minGreen</code> ({ADAPTIVE_DEFAULTS.minGreen} s)
                </td>
              </tr>
              <tr>
                <th scope="row">Extension / gap-out</th>
                <td>
                  Each passing vehicle restarts a gap timer; the green ends when
                  it expires while another phase is calling.
                </td>
                <td>
                  <code>extensionStep</code> ({ADAPTIVE_DEFAULTS.extensionStep}{" "}
                  s)
                </td>
              </tr>
              <tr>
                <th scope="row">Maximum green / max-out</th>
                <td>
                  Once another phase calls, the green ends within this time,
                  however busy it is.
                </td>
                <td>
                  <code>maxGreen</code> ({ADAPTIVE_DEFAULTS.maxGreen} s)
                </td>
              </tr>
              <tr>
                <th scope="row">Call</th>
                <td>
                  A phase calls when this many vehicles are detected on lanes
                  only it releases. Without a call elsewhere the green rests.
                </td>
                <td>
                  <code>demandThreshold</code> (
                  {ADAPTIVE_DEFAULTS.demandThreshold})
                </td>
              </tr>
              <tr>
                <th scope="row">Order and safety</th>
                <td>
                  The next phase is the first calling phase in plan order;
                  phases without demand are skipped whole. Every change between
                  approaches runs the configured yellow and all-red; the
                  conflict manager and collision checks still decide who may
                  enter.
                </td>
                <td>—</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p>
          Live decisions (status, detections per approach, greens ended by a gap
          or at the maximum, skipped phases, recent decisions) are in the
          snapshot’s <code>controller.adaptive</code>; green-time use for both
          signals is in <code>metrics.signalTiming</code> (phase changes, mean
          green, green shown to an empty road while others waited).
        </p>
        <h3>Three-way study</h3>
        <p>
          Every seed runs once under each control on the same junction, with the
          same arrivals, vehicles, duration and warm-up. Delays are compared
          pairwise per seed; a difference is called only when its interval
          excludes zero and it exceeds the tie tolerance.
        </p>
        <ControlComparisonStudy />
      </section>

      <section
        className="results-section"
        aria-labelledby="scenario-study-title"
      >
        <h2 id="scenario-study-title">Your own junction: a controlled study</h2>
        <p>
          Build any junction the model supports — lanes and lane arrows per
          approach, demand and turning per road, the vehicle mix, timing and
          roundabout design — or import one, then run it under the controls you
          choose. Every control is compiled from the same scenario document, so
          geometry, lanes, traffic, vehicles, duration and seeds are identical;
          only the control differs. The exact engine configuration of each
          control can be inspected before running and is exported with the
          result.
        </p>
        <ScenarioStudy />
      </section>

      <section className="results-section" aria-labelledby="map-title">
        <h2 id="map-title">How the guided results map to the metrics</h2>
        <p>
          The guided results translate a small set of catalog metrics into
          everyday questions. Every other metric remains in the “All
          measurements” table of each comparison and in exports.
        </p>
        <div className="multi-run-scroll">
          <table className="plain-table">
            <thead>
              <tr>
                <th scope="col">Everyday question</th>
                <th scope="col">What it shows</th>
                <th scope="col">Technical metrics</th>
              </tr>
            </thead>
            <tbody>
              {PLAIN_METRIC_MAP.map((row) => (
                <tr key={row.question}>
                  <th scope="row">{row.question}</th>
                  <td>{row.plain}</td>
                  <td>
                    {row.keys.map((key) => (
                      <span key={key} className="metric-key">
                        {metricDef(key).label} <code>{key}</code>
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
