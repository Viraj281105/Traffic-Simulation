import { IntersectionMap } from "../IntersectionMap";
import { RoundaboutMap } from "../RoundaboutMap";
import { AdaptiveSignalStatus } from "../AdaptiveSignalStatus";
import { MeteredRoundaboutStatus } from "../MeteredRoundaboutStatus";
import { VehicleLegend } from "../VehicleLegend";
import type { DualSnapshot } from "../../types/simulation";
import type { SignalControl } from "../../types/config";

/** The live signal and roundabout maps, side by side, for the guided
 *  comparison's "watch" step. */
export function ComparisonMaps({
  snapshot,
  signalControl,
  armLanes,
  lanes,
  laneWidth,
  showStopLines,
  debug,
}: {
  snapshot: DualSnapshot | null;
  signalControl: SignalControl | undefined;
  armLanes: { north: number; south: number; east: number; west: number };
  lanes: number;
  laneWidth: number;
  showStopLines: boolean;
  debug: boolean;
}) {
  return (
    <div className="comparison-maps-row">
      <section className="comparison-column" aria-labelledby="col-signal-title">
        <div className="column-header">
          <h2 className="column-title" id="col-signal-title">
            <span className="series-dot is-signal" aria-hidden="true" />
            {signalControl === "adaptive"
              ? "Traffic signal · responds to traffic"
              : "Traffic signal"}
          </h2>
        </div>
        <div className="canvas-wrapper">
          <IntersectionMap
            snapshot={snapshot?.signal ?? null}
            lanesNorth={armLanes.north}
            lanesSouth={armLanes.south}
            lanesEast={armLanes.east}
            lanesWest={armLanes.west}
            laneWidth={laneWidth}
            showCrosswalks={true}
            showStopLines={showStopLines}
            debug={debug}
          />
          <VehicleLegend snapshot={snapshot?.signal} />
          <AdaptiveSignalStatus snapshot={snapshot?.signal} />
        </div>
      </section>
      <section
        className="comparison-column"
        aria-labelledby="col-roundabout-title"
      >
        <div className="column-header">
          <h2 className="column-title" id="col-roundabout-title">
            <span className="series-dot is-roundabout" aria-hidden="true" />
            Roundabout
          </h2>
        </div>
        <div className="canvas-wrapper">
          <RoundaboutMap
            snapshot={snapshot?.roundabout ?? null}
            laneWidth={laneWidth}
            lanes={lanes}
            showCrosswalks={false}
            debug={debug}
          />
          <VehicleLegend snapshot={snapshot?.roundabout} />
          <MeteredRoundaboutStatus snapshot={snapshot?.roundabout} />
        </div>
      </section>
    </div>
  );
}
