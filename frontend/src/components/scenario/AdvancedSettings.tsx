import { type ScenarioDocument } from "../../scenario/scenarioTypes";
import { NumberField } from "./fields";

export function AdvancedSettings({
  value,
  update,
}: {
  value: ScenarioDocument;
  update: (mutate: (d: ScenarioDocument) => void) => void;
}) {
  const sig = value.signal;
  const rb = value.roundabout;
  return (
    <div className="sb-advanced-grid">
      <fieldset>
        <legend>Signal timing (both signals)</legend>
        <NumberField
          label="Green (both roads)"
          unit="s"
          value={sig.greenTime}
          min={6}
          max={120}
          onChange={(v) => {
            update((d) => {
              d.signal.greenTime = v;
            });
          }}
        />
        <NumberField
          label="North–south green"
          unit="s"
          placeholder="same"
          value={sig.nsGreenTime}
          min={6}
          max={120}
          onChange={(v) => {
            update((d) => {
              d.signal.nsGreenTime = v;
            });
          }}
        />
        <NumberField
          label="East–west green"
          unit="s"
          placeholder="same"
          value={sig.ewGreenTime}
          min={6}
          max={120}
          onChange={(v) => {
            update((d) => {
              d.signal.ewGreenTime = v;
            });
          }}
        />
        <NumberField
          label="Yellow"
          unit="s"
          value={sig.yellowTime}
          min={2.5}
          max={8}
          step={0.5}
          onChange={(v) => {
            update((d) => {
              d.signal.yellowTime = v;
            });
          }}
        />
        <NumberField
          label="All-red"
          unit="s"
          value={sig.allRedTime}
          min={0}
          max={5}
          step={0.5}
          onChange={(v) => {
            update((d) => {
              d.signal.allRedTime = v;
            });
          }}
        />
        {(sig.nsGreenTime != null || sig.ewGreenTime != null) && (
          <button
            type="button"
            className="link-btn"
            onClick={() => {
              update((d) => {
                d.signal.nsGreenTime = null;
                d.signal.ewGreenTime = null;
              });
            }}
          >
            Same green for both roads
          </button>
        )}
      </fieldset>
      <fieldset>
        <legend>Adaptive signal</legend>
        <NumberField
          label="Minimum green"
          unit="s"
          value={sig.adaptive.minGreen}
          min={5}
          max={60}
          onChange={(v) => {
            update((d) => {
              d.signal.adaptive.minGreen = v;
            });
          }}
        />
        <NumberField
          label="Maximum green"
          unit="s"
          value={sig.adaptive.maxGreen}
          min={10}
          max={180}
          onChange={(v) => {
            update((d) => {
              d.signal.adaptive.maxGreen = v;
            });
          }}
        />
        <NumberField
          label="Passage time"
          unit="s"
          value={sig.adaptive.extensionStep}
          min={0.5}
          max={10}
          step={0.5}
          onChange={(v) => {
            update((d) => {
              d.signal.adaptive.extensionStep = v;
            });
          }}
        />
        <NumberField
          label="Detection zone"
          unit="m"
          value={sig.adaptive.detectionDistance}
          min={5}
          max={200}
          onChange={(v) => {
            update((d) => {
              d.signal.adaptive.detectionDistance = v;
            });
          }}
        />
        <NumberField
          label="Vehicles to call"
          value={sig.adaptive.demandThreshold}
          min={1}
          max={20}
          onChange={(v) => {
            update((d) => {
              d.signal.adaptive.demandThreshold = Math.round(v);
            });
          }}
        />
      </fieldset>
      <fieldset>
        <legend>Roundabout design</legend>
        <div className="sb-field">
          <span className="sb-field-label">Circulating lanes</span>
          <div className="chip-row">
            {([null, 1, 2] as const).map((n) => (
              <button
                key={String(n)}
                type="button"
                className={`chip${(rb.circulatingLanes ?? null) === n ? " is-active" : ""}`}
                aria-pressed={(rb.circulatingLanes ?? null) === n}
                onClick={() => {
                  update((d) => {
                    d.roundabout.circulatingLanes = n;
                  });
                }}
              >
                {n === null ? "Automatic" : String(n)}
              </button>
            ))}
          </div>
        </div>
        <NumberField
          label="Island radius"
          unit="m"
          value={rb.innerRadius}
          min={6}
          max={50}
          step={0.5}
          onChange={(v) => {
            update((d) => {
              d.roundabout.innerRadius = v;
            });
          }}
        />
        <NumberField
          label="Outer radius"
          unit="m"
          value={rb.outerRadius}
          min={8}
          max={80}
          step={0.5}
          onChange={(v) => {
            update((d) => {
              d.roundabout.outerRadius = v;
            });
          }}
        />
        <NumberField
          label="Critical gap"
          unit="s"
          value={rb.criticalGap}
          min={1}
          max={10}
          step={0.1}
          onChange={(v) => {
            update((d) => {
              d.roundabout.criticalGap = v;
            });
          }}
        />
        <NumberField
          label="Follow-up time"
          unit="s"
          value={rb.followUpTime}
          min={0.5}
          max={10}
          step={0.1}
          onChange={(v) => {
            update((d) => {
              d.roundabout.followUpTime = v;
            });
          }}
        />
        <NumberField
          label="Entry speed"
          unit="m/s"
          value={rb.entrySpeed}
          min={1}
          max={15}
          step={0.5}
          onChange={(v) => {
            update((d) => {
              d.roundabout.entrySpeed = v;
            });
          }}
        />
        <NumberField
          label="Circulating speed"
          unit="m/s"
          value={rb.circulatingSpeed}
          min={2}
          max={15}
          step={0.5}
          onChange={(v) => {
            update((d) => {
              d.roundabout.circulatingSpeed = v;
            });
          }}
        />
      </fieldset>
      <fieldset>
        <legend>Roads</legend>
        <NumberField
          label="Lane width"
          unit="m"
          value={value.roads.laneWidth}
          min={2.6}
          max={5}
          step={0.1}
          onChange={(v) => {
            update((d) => {
              d.roads.laneWidth = v;
            });
          }}
        />
        <NumberField
          label="Speed limit"
          unit="km/h"
          value={Math.round(value.roads.speedLimit * 3.6)}
          min={10}
          max={108}
          step={5}
          onChange={(v) => {
            update((d) => {
              d.roads.speedLimit = Math.round((v / 3.6) * 100) / 100;
            });
          }}
        />
        <label className="sb-check">
          <input
            type="checkbox"
            checked={value.roads.laneChanging}
            onChange={(e) => {
              update((d) => {
                d.roads.laneChanging = e.target.checked;
              });
            }}
          />
          Drivers change lanes on multi-lane approaches
        </label>
      </fieldset>
    </div>
  );
}
