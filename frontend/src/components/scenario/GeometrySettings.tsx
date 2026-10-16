import {
  MAX_SLOT_DEVIATION,
  SLOT_BEARING,
  type ApproachSpec,
  type ScenarioDocument,
} from "../../scenario/scenarioTypes";
import { presentApproaches } from "../../scenario/scenarioModel";
import { cap } from "./builderOptions";
import { NumberField } from "./fields";

export function GeometrySettings({
  value,
  update,
}: {
  value: ScenarioDocument;
  update: (mutate: (d: ScenarioDocument) => void) => void;
}) {
  return (
    <fieldset className="sb-geometry">
      <legend>Junction geometry (real-world layout)</legend>
      <p className="q-help">
        The compass bearing each road leaves the junction on, and its own lane
        width. Each road may lie up to {MAX_SLOT_DEVIATION}° from its compass
        direction, so left, straight and right keep their meaning; a layout that
        cannot be represented is rejected with the reason, never bent to fit.
      </p>
      <div className="sb-geometry-rows">
        {presentApproaches(value).map((a) => {
          const arm = value.approaches[a] as ApproachSpec;
          return (
            <div key={a} className="sb-geometry-row">
              <span className="sb-field-label">{cap(a)}</span>
              <NumberField
                label="Bearing"
                unit="°"
                value={arm.bearing ?? SLOT_BEARING[a]}
                min={0}
                max={359.9}
                step={1}
                onChange={(v) => {
                  update((d) => {
                    const own = d.approaches[a];
                    if (own) own.bearing = ((v % 360) + 360) % 360;
                  });
                }}
              />
              <NumberField
                label="Lane width"
                unit="m"
                value={arm.laneWidth ?? value.roads.laneWidth}
                min={2.6}
                max={5}
                step={0.1}
                onChange={(v) => {
                  update((d) => {
                    const own = d.approaches[a];
                    if (own) own.laneWidth = v;
                  });
                }}
              />
              {(arm.bearing != null || arm.laneWidth != null) && (
                <button
                  type="button"
                  className="link-btn"
                  onClick={() => {
                    update((d) => {
                      const own = d.approaches[a];
                      if (own) {
                        own.bearing = null;
                        own.laneWidth = null;
                      }
                    });
                  }}
                >
                  Compass axis, junction lane width
                </button>
              )}
            </div>
          );
        })}
      </div>
    </fieldset>
  );
}
