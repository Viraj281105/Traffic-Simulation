import { useId } from "react";
import {
  meteringCoverage,
  rebuildEntryMeteringPhases,
  setEntryControl,
} from "../../scenario/scenarioModel";
import {
  isMeteredEntry,
  type ScenarioDocument,
} from "../../scenario/scenarioTypes";
import { cap } from "./builderOptions";

const MODES = [
  {
    id: "conventional",
    title: "Conventional roundabout",
    body: "No signal: drivers give way to circulating traffic and enter at gaps. This is the default.",
  },
  {
    id: "metered_entry",
    title: "Metered entry (signals)",
    body: "A signal on the entries can hold vehicles back with a red. Gap acceptance still applies, so a green never forces a vehicle in, and nothing is signalled inside the ring.",
  },
] as const;

const list = (arms: string[]) => arms.map(cap).join(", ");

/**
 * Step 1: how vehicles enter the roundabout. The choice is the same document
 * field the Advanced section edits; the phase timings, spillback guard and
 * queue cap stay there, so the default path stays short.
 */
export function EntryControlChoice({
  value,
  update,
}: {
  value: ScenarioDocument;
  update: (mutate: (d: ScenarioDocument) => void) => void;
}) {
  const name = useId();
  const metered = isMeteredEntry(value);
  const { metered: signalled, unmetered, missing } = meteringCoverage(value);
  return (
    <fieldset className="sb-entry-control">
      <legend className="sb-field-label">
        How do vehicles enter the roundabout?
      </legend>
      <div className="choice-grid">
        {MODES.map((m) => {
          const selected = (m.id === "metered_entry") === metered;
          return (
            <label
              key={m.id}
              className={`choice-card${selected ? " is-selected" : ""}`}
            >
              <input
                type="radio"
                name={name}
                checked={selected}
                onChange={() => {
                  update((d) => {
                    setEntryControl(d, m.id);
                  });
                }}
              />
              <span className="choice-title">{m.title}</span>
              <span className="choice-desc">{m.body}</span>
            </label>
          );
        })}
      </div>
      {metered && (
        <>
          <p className="q-help">
            The roundabout in this run has signals on{" "}
            {signalled.length ? list(signalled) : "no road"}.{" "}
            {unmetered.length > 0 &&
              `${list(unmetered)} ${unmetered.length > 1 ? "are" : "is"} not in any phase, so ${unmetered.length > 1 ? "they enter" : "it enters"} as at a conventional roundabout. `}
            Phase timings, spillback guard and queue cap are under Advanced.
            Timings are simulation assumptions, not calibrated to real sites.
          </p>
          {missing.length > 0 && (
            <p className="q-note is-caution" role="alert">
              The signal phases still name {list(missing)}, which this junction
              no longer has.{" "}
              <button
                type="button"
                className="link-btn"
                onClick={() => {
                  update(rebuildEntryMeteringPhases);
                }}
              >
                Rebuild phases for the current roads
              </button>{" "}
              (greens return to their defaults).
            </p>
          )}
        </>
      )}
    </fieldset>
  );
}
