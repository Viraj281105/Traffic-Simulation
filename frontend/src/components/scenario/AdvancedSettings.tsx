import { type ScenarioDocument } from "../../scenario/scenarioTypes";
import { setEntryControl } from "../../scenario/scenarioModel";
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
  const isMetered = rb.entryControl === "metered_entry";
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
        <legend>Roundabout entry control</legend>
        <div className="sb-field">
          <span className="sb-field-label">Control mode</span>
          <div className="chip-row">
            <button
              type="button"
              className={`chip${!isMetered ? " is-active" : ""}`}
              aria-pressed={!isMetered}
              onClick={() => {
                update((d) => {
                  setEntryControl(d, "conventional");
                });
              }}
            >
              Uncontrolled (conventional)
            </button>
            <button
              type="button"
              className={`chip${isMetered ? " is-active" : ""}`}
              aria-pressed={isMetered}
              onClick={() => {
                update((d) => {
                  setEntryControl(d, "metered_entry");
                });
              }}
            >
              Metered entry (signals)
            </button>
          </div>
        </div>
        {isMetered && rb.entryMetering && (
          <>
            <p className="config-hint">
              Each phase gives a green to the roads in parentheses while the
              others wait at red. Roads in no phase are not metered.
            </p>
            {rb.entryMetering.phases.map((p, idx) => (
              <NumberField
                key={idx}
                label={`Phase ${String(idx + 1)} (${p.entries.join("/")}) green`}
                unit="s"
                value={p.green}
                min={6}
                max={120}
                step={1}
                onChange={(v) => {
                  update((d) => {
                    if (d.roundabout.entryMetering?.phases[idx]) {
                      d.roundabout.entryMetering.phases[idx].green = v;
                    }
                  });
                }}
              />
            ))}
            <NumberField
              label="Yellow clearance"
              unit="s"
              value={rb.entryMetering.yellow}
              min={2.5}
              max={8}
              step={0.5}
              onChange={(v) => {
                update((d) => {
                  if (d.roundabout.entryMetering) {
                    d.roundabout.entryMetering.yellow = v;
                  }
                });
              }}
            />
            <NumberField
              label="All-red clearance"
              unit="s"
              value={rb.entryMetering.allRed}
              min={0}
              max={5}
              step={0.5}
              onChange={(v) => {
                update((d) => {
                  if (d.roundabout.entryMetering) {
                    d.roundabout.entryMetering.allRed = v;
                  }
                });
              }}
            />
            <label className="sb-check">
              <input
                type="checkbox"
                checked={rb.entryMetering.spillbackGuard?.enabled ?? false}
                onChange={(e) => {
                  update((d) => {
                    if (d.roundabout.entryMetering) {
                      d.roundabout.entryMetering.spillbackGuard = {
                        enabled: e.target.checked,
                        stoppedThreshold:
                          d.roundabout.entryMetering.spillbackGuard
                            ?.stoppedThreshold ?? 2,
                        maxHold:
                          d.roundabout.entryMetering.spillbackGuard?.maxHold ??
                          10.0,
                      };
                    }
                  });
                }}
              />
              Downstream spillback guard (holds red on ring queue)
            </label>
            {rb.entryMetering.spillbackGuard?.enabled && (
              <>
                <NumberField
                  label="Spillback stopped threshold"
                  unit="veh"
                  value={rb.entryMetering.spillbackGuard.stoppedThreshold ?? 2}
                  min={1}
                  max={20}
                  step={1}
                  onChange={(v) => {
                    update((d) => {
                      if (d.roundabout.entryMetering?.spillbackGuard) {
                        d.roundabout.entryMetering.spillbackGuard.stoppedThreshold =
                          Math.round(v);
                      }
                    });
                  }}
                />
                <NumberField
                  label="Spillback max hold per cycle"
                  unit="s"
                  value={rb.entryMetering.spillbackGuard.maxHold ?? 10.0}
                  min={0}
                  max={60}
                  step={1}
                  onChange={(v) => {
                    update((d) => {
                      if (d.roundabout.entryMetering?.spillbackGuard) {
                        d.roundabout.entryMetering.spillbackGuard.maxHold = v;
                      }
                    });
                  }}
                />
              </>
            )}
            <label className="sb-check">
              <input
                type="checkbox"
                checked={rb.entryMetering.queueCap?.enabled ?? false}
                onChange={(e) => {
                  update((d) => {
                    if (d.roundabout.entryMetering) {
                      d.roundabout.entryMetering.queueCap = {
                        enabled: e.target.checked,
                        vehicles:
                          d.roundabout.entryMetering.queueCap?.vehicles ?? 8,
                      };
                    }
                  });
                }}
              />
              Approach queue cap (shortens red for long queue)
            </label>
            {rb.entryMetering.queueCap?.enabled && (
              <NumberField
                label="Queue cap vehicles"
                unit="veh"
                value={rb.entryMetering.queueCap.vehicles ?? 8}
                min={1}
                max={50}
                step={1}
                onChange={(v) => {
                  update((d) => {
                    if (d.roundabout.entryMetering?.queueCap) {
                      d.roundabout.entryMetering.queueCap.vehicles =
                        Math.round(v);
                    }
                  });
                }}
              />
            )}
            <p className="config-hint" role="note">
              Simulation assumption — signal timings are not calibrated to real
              sites; no claim that signalised roundabouts are better or safer in
              the real world.
            </p>
          </>
        )}
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
