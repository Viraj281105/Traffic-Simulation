import {
  APPROACHES,
  type ApproachName,
  type Movement,
  type ScenarioDocument,
} from "../../scenario/scenarioTypes";
import { ringLanes, signalLaneUse } from "../../scenario/scenarioModel";
import type { StrategyDesign } from "../../scenario/scenarioTypes";

/** Rotation (degrees, SVG) of each arm's local frame, in which incoming
 *  traffic drives "up" the screen towards the junction. */
const HEADING: Record<ApproachName, number> = {
  south: 0,
  west: 90,
  north: 180,
  east: 270,
};

const GLYPH: Record<Movement, string> = {
  left: "↰",
  straight: "↑",
  right: "↱",
};

const SPLITTER = 1.5;
const VIEW = 64;

/**
 * Plan view of the scenario as it is being built: every arm with its own
 * lanes and lane arrows, how busy each road is, and the junction itself —
 * a signal box, or the ring with its circulating lanes. Drawn from the
 * document, so it changes the moment a setting does; click an arm to edit it.
 */
export function JunctionPreview({
  scenario,
  view,
  selected,
  onSelect,
  design,
}: {
  scenario: ScenarioDocument;
  view: "signal" | "roundabout";
  selected?: ApproachName | null;
  onSelect?: (approach: ApproachName) => void;
  /** The roundabout's lane markings as the backend resolved them. */
  design?: StrategyDesign;
}) {
  const lw = scenario.roads.laneWidth;
  const roundabout = view === "roundabout";
  const gap = roundabout ? SPLITTER : 0;
  const widest = Math.max(
    ...APPROACHES.map((a) => scenario.approaches[a].lanes),
  );
  const rings = ringLanes(scenario);
  const inner = scenario.roundabout.innerRadius;
  const outer = scenario.roundabout.outerRadius;
  const box = roundabout ? outer + 4 : widest * lw + 3.5;
  const maxVph = Math.max(
    300,
    ...APPROACHES.map((a) => scenario.approaches[a].vehiclesPerHour),
  );

  const laneUseFor = (a: ApproachName): Movement[][] => {
    if (roundabout) {
      const resolved = design?.laneUse[a];
      if (resolved && resolved.length === scenario.approaches[a].lanes)
        return resolved;
      const own = scenario.approaches[a].roundaboutLaneUse;
      if (own && own.length === scenario.approaches[a].lanes) return own;
    }
    return signalLaneUse(scenario.approaches[a]);
  };

  return (
    <svg
      className="junction-preview"
      viewBox={`${String(-VIEW)} ${String(-VIEW)} ${String(2 * VIEW)} ${String(2 * VIEW)}`}
      role="img"
      aria-label={`Plan of the junction as a ${roundabout ? "roundabout" : "signal"}`}
    >
      {APPROACHES.map((a) => {
        const arm = scenario.approaches[a];
        const half = arm.lanes * lw + gap;
        const isSelected = selected === a;
        const demand = arm.vehiclesPerHour / maxVph;
        const use = laneUseFor(a);
        return (
          <g
            key={a}
            transform={`rotate(${String(HEADING[a])})`}
            className={`jp-arm${isSelected ? " is-selected" : ""}${onSelect ? " is-clickable" : ""}`}
            onClick={() => onSelect?.(a)}
          >
            <title>{`${a}: ${String(arm.lanes)} lane${arm.lanes === 1 ? "" : "s"}, ${String(Math.round(arm.vehiclesPerHour))} veh/h`}</title>
            {/* Local frame: this arm runs from the junction (y = box) down
                to the edge (y = VIEW); incoming lanes are on the right
                (x > 0) and drive up. */}
            <rect
              className="jp-road"
              x={-half}
              y={box - 1}
              width={2 * half}
              height={VIEW - box + 1}
            />
            {gap > 0 && (
              <rect
                className="jp-island"
                x={-gap}
                y={box + 1}
                width={2 * gap}
                height={VIEW - box}
              />
            )}
            {Array.from({ length: arm.lanes - 1 }, (_, i) => {
              const x = (i + 1) * lw + gap;
              return (
                <g key={i}>
                  <line
                    className="jp-lane-line"
                    x1={x}
                    y1={box}
                    x2={x}
                    y2={VIEW}
                  />
                  <line
                    className="jp-lane-line"
                    x1={-x}
                    y1={box}
                    x2={-x}
                    y2={VIEW}
                  />
                </g>
              );
            })}
            {!roundabout && (
              <line
                className="jp-centre-line"
                x1={0}
                y1={box}
                x2={0}
                y2={VIEW}
              />
            )}
            <line
              className="jp-stop-line"
              x1={gap}
              y1={box + 0.6}
              x2={half}
              y2={box + 0.6}
            />
            {use.map((turns, i) => (
              <text
                key={i}
                className="jp-arrows"
                x={(i + 0.5) * lw + gap}
                y={box + 6}
                textAnchor="middle"
              >
                {turns.map((t) => GLYPH[t]).join("")}
              </text>
            ))}
            {/* How busy this road is: a bar beside the incoming lanes. */}
            <rect
              className="jp-demand"
              x={half + 1.2}
              y={VIEW - 4 - demand * (VIEW - box - 12)}
              width={1.6}
              height={Math.max(0.5, demand * (VIEW - box - 12))}
              rx={0.8}
            />
          </g>
        );
      })}

      {roundabout ? (
        <g className="jp-ring">
          <circle className="jp-road" r={outer} />
          {Array.from({ length: rings - 1 }, (_, i) => (
            <circle
              key={i}
              className="jp-ring-line"
              r={inner + ((i + 1) * (outer - inner)) / rings}
            />
          ))}
          <circle className="jp-island" r={inner} />
          <text className="jp-ring-label" textAnchor="middle" y={1.5}>
            {rings} ring lane{rings === 1 ? "" : "s"}
          </text>
        </g>
      ) : (
        <g>
          <rect
            className="jp-road"
            x={-box}
            y={-box}
            width={2 * box}
            height={2 * box}
          />
          <rect
            className="jp-box"
            x={-box + 1}
            y={-box + 1}
            width={2 * box - 2}
            height={2 * box - 2}
            rx={1.5}
          />
        </g>
      )}

      {APPROACHES.map((a) => {
        const arm = scenario.approaches[a];
        const angle = ((HEADING[a] + 90) * Math.PI) / 180;
        const r = VIEW - 6;
        return (
          <text
            key={`label-${a}`}
            className={`jp-label${selected === a ? " is-selected" : ""}`}
            x={Math.cos(angle) * r * 0.97}
            y={Math.sin(angle) * r * 0.97}
            textAnchor="middle"
            dominantBaseline="middle"
            onClick={() => onSelect?.(a)}
          >
            {a[0].toUpperCase()} · {Math.round(arm.vehiclesPerHour)}
          </text>
        );
      })}
    </svg>
  );
}
