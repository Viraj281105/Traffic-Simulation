import { useId } from "react";
import {
  ENTRY_QUEUE_CAPACITY_MAX,
  entryQueueEnabled,
  type EntryQueueSpec,
} from "../../scenario/scenarioTypes";
import { ENTRY_MODEL_INFO, ENTRY_POPULATIONS } from "../../metrics/entryModel";
import "./ScenarioBuilder.css";

/** Chooses the entry model for a scenario: hold arrivals back (the default,
 *  stored as no setting) or the point queue, with an optional per-road
 *  limit. */
export function EntryModelChoice({
  value,
  onChange,
  variant = "guided",
}: {
  value: EntryQueueSpec | null | undefined;
  onChange: (next: EntryQueueSpec | null) => void;
  /** "guided": the quick-setup cards; "builder": the junction builder. */
  variant?: "guided" | "builder";
}) {
  const name = useId();
  const headingId = useId();
  const capacityId = useId();
  // Each option is named by its title alone and described by its summary,
  // so its accessible name stays short (and distinct from other questions'
  // options, such as the demand level "Busy").
  const optionId = useId();
  const queued = entryQueueEnabled(value);
  const capacity = value?.capacity ?? null;
  const guided = variant === "guided";

  const option = (model: "suspend" | "queue") => {
    const selected = (model === "queue") === queued;
    const info = ENTRY_MODEL_INFO[model];
    return (
      <label
        key={model}
        className={
          guided
            ? `choice-card${selected ? " is-selected" : ""}`
            : `sb-radio${selected ? " is-active" : ""}`
        }
      >
        <input
          type="radio"
          name={name}
          value={model}
          checked={selected}
          aria-labelledby={`${optionId}-${model}-title`}
          aria-describedby={`${optionId}-${model}-summary`}
          onChange={() => {
            onChange(
              model === "queue" ? { enabled: true, capacity: null } : null,
            );
          }}
        />
        <span
          className={guided ? "choice-title" : "sb-radio-title"}
          id={`${optionId}-${model}-title`}
        >
          {info.label}
        </span>
        <span
          className={guided ? "choice-desc" : "sb-unit"}
          id={`${optionId}-${model}-summary`}
        >
          {info.summary}
        </span>
      </label>
    );
  };

  return (
    <div
      className={guided ? "q-subsection" : "sb-field"}
      role="radiogroup"
      aria-labelledby={headingId}
    >
      <span className={guided ? "q-subtitle" : "sb-field-label"} id={headingId}>
        When traffic cannot get in
      </span>
      <div className={guided ? "choice-grid" : "sb-radio-group"}>
        {option("suspend")}
        {option("queue")}
      </div>
      {queued && (
        <div className={guided ? "q-inline-field" : "sb-inline"}>
          <label htmlFor={capacityId}>Queue limit per road</label>
          <input
            id={capacityId}
            type="number"
            min={1}
            max={ENTRY_QUEUE_CAPACITY_MAX}
            step={1}
            placeholder="No limit"
            value={capacity ?? ""}
            onChange={(e) => {
              const raw = e.target.value;
              const n = Math.round(Number(raw));
              onChange({
                enabled: true,
                capacity:
                  raw === "" || !Number.isFinite(n)
                    ? null
                    : Math.min(ENTRY_QUEUE_CAPACITY_MAX, Math.max(1, n)),
              });
            }}
          />
          <span className={guided ? "q-help" : "sb-unit"}>
            vehicles. Leave empty for no limit beyond the run's vehicle cap;
            arrivals beyond a limit are counted as rejected.
          </span>
        </div>
      )}
      <details className={guided ? "q-details" : "sb-details"}>
        <summary>How vehicles are counted</summary>
        <dl className="entry-populations">
          {ENTRY_POPULATIONS.map((p) => (
            <div key={p.term}>
              <dt>{p.term}</dt>
              <dd>{p.meaning}</dd>
            </div>
          ))}
        </dl>
        <p>
          Arrivals = admitted + waiting outside + rejected, exactly, under both
          models. With arrivals held back, demand that never arrived is only
          estimated (“configured demand”). Results are model outputs, not field
          measurements.
        </p>
      </details>
    </div>
  );
}
