import "./research/ResearchLab.css";
import { ResearchLink } from "./research/LabSection";
import { ScenarioStudy } from "./scenario/ScenarioStudy";
import { VIEW_ROUTES } from "../routing";

const HELD_SAME = [
  "Geometry",
  "Lanes",
  "Traffic",
  "Vehicles",
  "Duration",
  "Seeds",
];

/** Research lab: the controlled study of a user's own junction, on its own
 *  page like the other research tools. The study itself is ScenarioStudy;
 *  this supplies the page frame and a short orientation. */
export function JunctionStudyPage() {
  return (
    <div className="guided-page junction-study">
      <header className="guided-intro">
        <p className="guided-eyebrow">Research lab</p>
        <h1>Your own junction: a controlled study</h1>
        <p>
          Build any junction the model supports, or import one, then run it
          under the controls you choose.
        </p>
      </header>

      <div className="rl-held">
        <div>
          <p className="rl-small-label">Same in every control</p>
          <ul>
            {HELD_SAME.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div className="is-differs">
          <p className="rl-small-label">Only this differs</p>
          <ul>
            <li>The control</li>
          </ul>
        </div>
      </div>

      <details className="rl-more">
        <summary>How the study is built</summary>
        <p>
          You set lanes and lane arrows per approach, demand and turning per
          road, the vehicle mix, timing and roundabout design. Every control is
          compiled from the same scenario document, so geometry, lanes, traffic,
          vehicles, duration and seeds are identical; only the control differs.
          The exact engine configuration of each control can be inspected before
          running and is exported with the result.
        </p>
        <p>
          <ResearchLink to={VIEW_ROUTES.threeWay}>
            How readings are decided: three-way study
          </ResearchLink>
        </p>
      </details>

      <ScenarioStudy />
    </div>
  );
}
