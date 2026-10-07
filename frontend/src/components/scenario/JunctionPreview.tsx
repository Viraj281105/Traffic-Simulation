import {
  APPROACHES,
  SLOT_BEARING,
  type ApproachName,
  type Movement,
  type ScenarioDocument,
} from "../../scenario/scenarioTypes";
import {
  armBearing,
  armLaneWidth,
  presentArms,
  ringLanes,
  signalLaneUse,
  stopLineDistances,
} from "../../scenario/scenarioModel";
import type { StrategyDesign } from "../../scenario/scenarioTypes";

const GLYPH: Record<Movement, string> = {
  uturn: "↶",
  left: "↰",
  straight: "↑",
  right: "↱",
};

const SPLITTER = 1.5;
const VIEW = 64;

/** SVG rotation (degrees) of an arm's local frame, in which incoming traffic
 *  drives "up" the screen towards the junction: a south arm (bearing 180)
 *  needs none, and a larger bearing turns the arm clockwise on the map. */
function rotation(bearing: number): number {
  return (((bearing - 180) % 360) + 360) % 360;
}

/** Point ``along`` m out from the centre on an arm and ``lateral`` m to its
 *  exit side, in SVG coordinates (y down). */
function armPoint(
  bearing: number,
  along: number,
  lateral: number,
): [number, number] {
  const rad = (bearing * Math.PI) / 180;
  const ux = Math.sin(rad);
  const uy = -Math.cos(rad); // north is up on screen
  // Exit side: the outward axis turned 90° clockwise on the map.
  const nx = -uy;
  const ny = ux;
  return [along * ux + lateral * nx, along * uy + lateral * ny];
}

/**
 * Plan view of the scenario as it is being built: every arm on its own
 * bearing with its own lanes, lane width and lane arrows, how busy each road
 * is, and the junction itself — a signal area whose stop lines sit where the
 * engine puts them, or the ring with its circulating lanes. Slots without an
 * arm are left empty. Drawn from the document (and, once the server has
 * checked it, from the geometry the engine will build), so it changes the
 * moment a setting does; click an arm to edit it.
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
  /** The engine's resolved design for this view's strategy, when known. */
  design?: StrategyDesign;
}) {
  const roundabout = view === "roundabout";
  const gap = roundabout ? SPLITTER : 0;
  const arms = presentArms(scenario);
  const rings = ringLanes(scenario);
  const inner = scenario.roundabout.innerRadius;
  const outer = scenario.roundabout.outerRadius;
  const local = stopLineDistances(scenario, roundabout);
  const stopOf = (a: ApproachName): number =>
    design?.geometry?.[a]?.stopLineDistance ?? local[a] ?? 0;
  const standard =
    arms.length === 4 &&
    arms.every(
      ([a, arm]) => arm.bearing == null || arm.bearing === SLOT_BEARING[a],
    ) &&
    arms.every(([, arm]) => arm.laneWidth == null);
  const maxVph = Math.max(300, ...arms.map(([, arm]) => arm.vehiclesPerHour));

  const laneUseFor = (a: ApproachName): Movement[][] => {
    const arm = scenario.approaches[a];
    if (!arm) return [];
    if (roundabout) {
      const resolved = design?.laneUse[a];
      if (resolved && resolved.length === arm.lanes) return resolved;
      const own = arm.roundaboutLaneUse;
      if (own && own.length === arm.lanes) return own;
    }
    const resolved = design?.laneUse[a];
    if (!roundabout && resolved && resolved.length === arm.lanes)
      return resolved;
    return signalLaneUse(arm);
  };

  // The signal's conflict area: the V1.0 square box for the standard
  // junction, otherwise the polygon through every arm's stop-line corners.
  const box = Math.max(...arms.map(([a]) => stopOf(a)), 0);
  const area = arms
    .map(([a, arm]) => ({ a, arm, b: armBearing(a, arm) }))
    .sort((x, y) => x.b - y.b)
    .flatMap(({ a, arm, b }) => {
      const half = arm.lanes * armLaneWidth(scenario, arm);
      return [armPoint(b, stopOf(a), -half), armPoint(b, stopOf(a), half)];
    });

  return (
    <svg
      className="junction-preview"
      viewBox={`${String(-VIEW)} ${String(-VIEW)} ${String(2 * VIEW)} ${String(2 * VIEW)}`}
      role="img"
      aria-label={`Plan of the ${String(arms.length)}-arm junction as a ${roundabout ? "roundabout" : "signal"}`}
    >
      {arms.map(([a, arm]) => {
        const lw = armLaneWidth(scenario, arm);
        const stop = stopOf(a);
        const half = arm.lanes * lw + gap;
        const isSelected = selected === a;
        const demand = arm.vehiclesPerHour / maxVph;
        const use = laneUseFor(a);
        const bearing = armBearing(a, arm);
        return (
          <g
            key={a}
            transform={`rotate(${String(rotation(bearing))})`}
            className={`jp-arm${isSelected ? " is-selected" : ""}${onSelect ? " is-clickable" : ""}`}
            onClick={() => onSelect?.(a)}
          >
            <title>{`${a}: ${String(arm.lanes)} lane${arm.lanes === 1 ? "" : "s"} of ${String(lw)} m, bearing ${String(bearing)}°, ${String(Math.round(arm.vehiclesPerHour))} veh/h`}</title>
            {/* Local frame: this arm runs from the junction (y = stop) down
                to the edge (y = VIEW); incoming lanes are on the right
                (x > 0) and drive up. */}
            <rect
              className="jp-road"
              x={-half}
              y={stop - 1}
              width={2 * half}
              height={VIEW * 1.5 - stop + 1}
            />
            {gap > 0 && (
              <rect
                className="jp-island"
                x={-gap}
                y={stop + 1}
                width={2 * gap}
                height={VIEW * 1.5 - stop}
              />
            )}
            {Array.from({ length: arm.lanes - 1 }, (_, i) => {
              const x = (i + 1) * lw + gap;
              return (
                <g key={i}>
                  <line
                    className="jp-lane-line"
                    x1={x}
                    y1={stop}
                    x2={x}
                    y2={VIEW * 1.5}
                  />
                  <line
                    className="jp-lane-line"
                    x1={-x}
                    y1={stop}
                    x2={-x}
                    y2={VIEW * 1.5}
                  />
                </g>
              );
            })}
            {!roundabout && (
              <line
                className="jp-centre-line"
                x1={0}
                y1={stop}
                x2={0}
                y2={VIEW * 1.5}
              />
            )}
            <line
              className="jp-stop-line"
              x1={gap}
              y1={stop + 0.6}
              x2={half}
              y2={stop + 0.6}
            />
            {use.map((turns, i) => (
              <text
                key={i}
                className="jp-arrows"
                x={(i + 0.5) * lw + gap}
                y={stop + 6}
                textAnchor="middle"
              >
                {turns.map((t) => GLYPH[t]).join("")}
              </text>
            ))}
            {/* How busy this road is: a bar beside the incoming lanes. */}
            <rect
              className="jp-demand"
              x={half + 1.2}
              y={VIEW - 4 - demand * Math.max(4, VIEW - stop - 12)}
              width={1.6}
              height={Math.max(0.5, demand * Math.max(4, VIEW - stop - 12))}
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
      ) : standard ? (
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
      ) : (
        <g>
          <polygon
            className="jp-road"
            points={area.map(([x, y]) => `${String(x)},${String(y)}`).join(" ")}
          />
          <polygon
            className="jp-box"
            points={area.map(([x, y]) => `${String(x)},${String(y)}`).join(" ")}
          />
        </g>
      )}

      {APPROACHES.map((a) => {
        const arm = scenario.approaches[a];
        if (!arm) return null;
        const [x, y] = armPoint(armBearing(a, arm), (VIEW - 6) * 0.97, 0);
        return (
          <text
            key={`label-${a}`}
            className={`jp-label${selected === a ? " is-selected" : ""}`}
            x={x}
            y={y}
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
