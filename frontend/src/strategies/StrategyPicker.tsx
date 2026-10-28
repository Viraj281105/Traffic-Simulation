import type { ReactNode } from "react";
import { Check, RotateCcw } from "lucide-react";
import { StrategyGlyph } from "./StrategyGlyph";
import type { CatalogState } from "./strategyCatalog";
import { StatusState } from "../components/ui/StatusState";
import { LoaderMark } from "../components/ui/Loader";
import "./Strategies.css";

/** The strategies to compare, one card each, any combination. Every
 *  strategy the live comparison can run is shown; ticking a card adds it,
 *  and the count and the run button follow the selection. */
export function StrategyPicker({
  catalog,
  value,
  onChange,
  details,
  heading = "Which strategies should we compare?",
  number,
}: {
  catalog: CatalogState & { retry: () => void };
  value: string[];
  onChange: (next: string[]) => void;
  /** A line of this scenario's settings per strategy (its timetable, its
   *  gap acceptance), shown on the card. */
  details?: Record<string, ReactNode>;
  heading?: string;
  number?: number;
}) {
  if (catalog.status === "loading") {
    return (
      <section className="guided-question strategy-picker" aria-busy="true">
        <PickerHeading heading={heading} number={number} />
        <p className="strategy-picker__loading" role="status">
          <LoaderMark />
          Loading the available strategies…
        </p>
      </section>
    );
  }
  if (catalog.status === "error") {
    return (
      <section className="guided-question strategy-picker">
        <PickerHeading heading={heading} number={number} />
        <StatusState
          tone="unavailable"
          role="alert"
          title={catalog.message}
          actions={
            <button
              type="button"
              className="pb-btn pb-secondary"
              onClick={catalog.retry}
            >
              <RotateCcw size={14} aria-hidden="true" />
              Try again
            </button>
          }
        />
      </section>
    );
  }

  const { strategies, maxStrategies, defaultSelection } = catalog.catalog;
  const chosen = new Set(value);
  const atMax = value.length >= maxStrategies;
  const toggle = (id: string) => {
    if (chosen.has(id)) {
      onChange(value.filter((v) => v !== id));
    } else if (!atMax) {
      // Keep the catalog's order, whatever order the cards were ticked in.
      onChange(
        strategies.map((s) => s.id).filter((s) => chosen.has(s) || s === id),
      );
    }
  };
  const allIds = strategies.slice(0, maxStrategies).map((s) => s.id);
  const isAll = allIds.every((id) => chosen.has(id));
  const isDefault =
    value.length === defaultSelection.length &&
    defaultSelection.every((id) => chosen.has(id));

  return (
    <fieldset className="guided-question strategy-picker">
      <legend>
        {number !== undefined && <span className="q-number">{number}</span>}{" "}
        {heading}
      </legend>
      <div className="strategy-picker__bar">
        <p className="strategy-picker__count" aria-live="polite">
          <strong>{value.length}</strong> of {strategies.length} selected
          {value.length === 1 && " · add another to compare"}
        </p>
        <div className="strategy-picker__shortcuts">
          <button
            type="button"
            className="strategy-chip"
            aria-pressed={isAll}
            onClick={() => {
              onChange(allIds);
            }}
          >
            All {allIds.length}
          </button>
          <button
            type="button"
            className="strategy-chip"
            aria-pressed={isDefault}
            onClick={() => {
              onChange(defaultSelection);
            }}
          >
            Signal vs roundabout
          </button>
        </div>
      </div>
      <div className="strategy-grid">
        {strategies.map((s) => {
          const on = chosen.has(s.id);
          const disabled = !on && atMax;
          return (
            <label
              key={s.id}
              className={`strategy-card${on ? " is-selected" : ""}${disabled ? " is-disabled" : ""}`}
              style={{ "--strategy-color": s.color } as React.CSSProperties}
            >
              <input
                type="checkbox"
                className="strategy-card__input"
                checked={on}
                disabled={disabled}
                aria-label={s.name}
                aria-describedby={`strategy-${s.id}-summary`}
                onChange={() => {
                  toggle(s.id);
                }}
              />
              <span className="strategy-card__top">
                <StrategyGlyph strategy={s} />
                <span className="strategy-card__check" aria-hidden="true">
                  <Check size={14} strokeWidth={3} />
                </span>
              </span>
              <span className="strategy-card__family">
                {s.family === "signal" ? "Signalised junction" : "Roundabout"}
              </span>
              <span className="strategy-card__name">{s.name}</span>
              <span
                className="strategy-card__summary"
                id={`strategy-${s.id}-summary`}
              >
                {s.summary}
              </span>
              {details?.[s.id] && (
                <span className="strategy-card__detail">{details[s.id]}</span>
              )}
            </label>
          );
        })}
      </div>
      <p className="q-help">
        Every strategy you pick runs at the same time on exactly the same
        vehicles, so the only difference between them is how the junction is
        controlled.
        {value.length === 0 && (
          <strong className="strategy-picker__need"> Pick at least one.</strong>
        )}
      </p>
    </fieldset>
  );
}

function PickerHeading({
  heading,
  number,
}: {
  heading: string;
  number?: number;
}) {
  return (
    <h2 className="as-legend">
      {number !== undefined && <span className="q-number">{number}</span>}{" "}
      {heading}
    </h2>
  );
}
