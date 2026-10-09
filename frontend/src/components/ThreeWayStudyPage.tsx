import "./research/ResearchLab.css";
import { LabSection, ResearchLink } from "./research/LabSection";
import { MatchedSeedsDiagram } from "./research/MatchedSeedsDiagram";
import { PairedExample } from "./research/PairedExample";
import { CONFIDENCE_LEVEL, TIE, T_95 } from "./research/evidence";
import { ControlComparisonStudy } from "./ControlComparisonStudy";
import { ADAPTIVE_DEFAULTS } from "../types/config";
import { VIEW_ROUTES } from "../routing";

const level = Math.round(CONFIDENCE_LEVEL * 100);
const tiePercent = Math.round(TIE.rel * 100);

/** Research lab: the three-way study and the method behind it. The method
 *  comes first, drawn; the run controls and results are at the bottom, where
 *  they grow as a study is run. */
export function ThreeWayStudyPage() {
  return (
    <div className="guided-page three-way">
      <header className="guided-intro rl-hero">
        <p className="guided-eyebrow">Research lab</p>
        <h1>Three-way study</h1>
        <p>
          Fixed-time signal, adaptive signal and roundabout, run on the same
          junction and the same traffic at six demand levels. This page shows
          how the comparison is made, then lets you run it.
        </p>
        <nav className="rl-actions" aria-label="On this page">
          <a className="pb-btn pb-secondary" href="#method">
            How the comparison works
          </a>
          <a className="pb-btn pb-primary" href="#run">
            Run the study
          </a>
        </nav>
      </header>

      <LabSection
        id="compared"
        title="What is compared"
        lede="Three controls on one junction. Everything else is held the same."
      >
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
        <details className="rl-more" id="adaptive">
          <summary>How the adaptive signal decides</summary>
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
                  <td>
                    A green never ends earlier, so a standing queue starts.
                  </td>
                  <td>
                    <code>minGreen</code> ({ADAPTIVE_DEFAULTS.minGreen} s)
                  </td>
                </tr>
                <tr>
                  <th scope="row">Extension / gap-out</th>
                  <td>
                    Each passing vehicle restarts a gap timer; the green ends
                    when it expires while another phase is calling.
                  </td>
                  <td>
                    <code>extensionStep</code> (
                    {ADAPTIVE_DEFAULTS.extensionStep} s)
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
                    phases without demand are skipped whole. Every change
                    between approaches runs the configured yellow and all-red;
                    the conflict manager and collision checks still decide who
                    may enter.
                  </td>
                  <td>—</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p>
            Live decisions (status, detections per approach, greens ended by a
            gap or at the maximum, skipped phases, recent decisions) are in the
            snapshot’s <code>controller.adaptive</code>; green-time use for both
            signals is in <code>metrics.signalTiming</code> (phase changes, mean
            green, green shown to an empty road while others waited).
          </p>
        </details>
      </LabSection>

      <LabSection
        id="method"
        title="Matched seeds"
        lede="A seed fixes which vehicles arrive and when. Running every control on the same seed makes the comparison fair."
      >
        <figure className="rl-figure">
          <MatchedSeedsDiagram />
          <figcaption>
            For one seed the three runs share the geometry, lanes, vehicles,
            arrival sequence, duration and warm-up. The two signals also share
            one phase plan, yellow and all-red: only how a green ends differs.
            Nothing is tuned per control. Seeds are consecutive whole numbers,
            starting at 1 unless a study sets another base seed.
          </figcaption>
        </figure>
      </LabSection>

      <LabSection
        id="paired"
        title="From seeds to a reading"
        lede="Compare the controls seed by seed, then average the gaps."
        links={
          <ResearchLink to={VIEW_ROUTES.validation}>
            Compare with the unpaired Welch test: statistical validation
          </ResearchLink>
        }
      >
        <PairedExample />
        <p className="rl-small-note">
          An individual run says what happened under one arrival pattern. Only
          the mean gap, with its interval, speaks for the comparison.
        </p>
      </LabSection>

      <LabSection
        id="rule"
        title="How the conclusion is classified"
        lede="Three possible readings for every pair of controls at every demand level, decided in this order."
      >
        <ol className="rl-decision">
          <li>
            <div className="rl-decision-q">
              <span className="rl-step-n" aria-hidden="true">
                1
              </span>
              <p>
                Do the two mean delays differ by no more than the tie tolerance?
              </p>
            </div>
            <div className="rl-decision-a">
              <span className="rl-outcome is-tie">Yes: about the same</span>
              <span className="rl-small-note">No: go to 2</span>
            </div>
          </li>
          <li>
            <div className="rl-decision-q">
              <span className="rl-step-n" aria-hidden="true">
                2
              </span>
              <p>Does the {level} % interval of the per-seed gaps exclude 0?</p>
            </div>
            <div className="rl-decision-a">
              <span className="rl-outcome is-lower">
                Yes: lower, for the control with the smaller mean delay
              </span>
              <span className="rl-outcome is-open">No: inconclusive</span>
            </div>
          </li>
        </ol>
        <dl className="rl-defs">
          <div>
            <dt>Tie tolerance</dt>
            <dd>
              {TIE.abs} s, or {tiePercent} % of the larger mean, whichever is
              larger. It is a presentation tolerance, not a significance test:
              it stops a fraction of a second being reported as a win. It is
              checked first, on the two means.
            </dd>
          </div>
          <div>
            <dt>Interval</dt>
            <dd>
              mean gap ± t(n − 1) × s ÷ √n, a two-sided Student-t interval at{" "}
              {level} %. The multiplier is {T_95[2]} with 3 seeds, {T_95[4]}{" "}
              with 5 and {T_95[9]} with 10. If the interval includes 0, these
              seeds cannot separate the two controls.
            </dd>
          </div>
          <div>
            <dt>Inconclusive</dt>
            <dd>
              The means differ by more than the tolerance, but the interval
              includes 0. It is not evidence of “no difference”; more seeds
              might separate them.
            </dd>
          </div>
        </dl>
      </LabSection>

      <LabSection
        id="limits"
        title="Assumptions and limits"
        lede="What the method rests on, as implemented."
        links={
          <ResearchLink to={VIEW_ROUTES.research}>
            What the evidence can and cannot say
          </ResearchLink>
        }
      >
        <ul className="rl-bullets">
          <li>
            <strong>Student-t intervals</strong> assume the per-seed gaps are
            roughly bell-shaped. With 3 to 10 seeds that cannot be checked, so
            read intervals as indicative.
          </li>
          <li>
            <strong>Many readings, no correction.</strong> Six demand levels and
            three pairs give 18 readings per study, read without
            multiple-comparison correction.
          </li>
          <li>
            <strong>Delay only.</strong> The reading is about mean delay. Other
            measures are reported with their intervals but are not classified.
          </li>
          <li>
            <strong>Adaptive settings are the defaults</strong> (min green{" "}
            {ADAPTIVE_DEFAULTS.minGreen} s, max {ADAPTIVE_DEFAULTS.maxGreen} s),
            not tuned for any demand level.
          </li>
          <li>
            <strong>Calibration.</strong> The calibrated comparison is one lane
            per approach with cars only; anything else is exploratory. Every
            result carries its calibration note.
          </li>
          <li>
            <strong>No verdict.</strong> A reading holds for this junction,
            these demand levels and this duration, not for every junction.
          </li>
        </ul>
      </LabSection>

      <LabSection
        id="run"
        title="Run the study"
        lede="The same method, run for real. Results appear below with their intervals."
      >
        <ControlComparisonStudy />
      </LabSection>
    </div>
  );
}
