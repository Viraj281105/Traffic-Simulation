import { useId, useState } from "react";
import "../netcommon/network.css";
import { NumberField } from "../netcommon/NumberField";
import {
  INCIDENT_TYPES,
  MAX_EVENTS,
  WEATHER_KINDS,
  isEmptyScenario,
  newIncident,
  newSurge,
  newWeather,
} from "./scenario";
import type { Incident, Scenario, Surge, WeatherWindow } from "./types";

function TextField({
  label,
  value,
  placeholder,
  onCommit,
}: {
  label: string;
  value: string;
  placeholder?: string;
  onCommit: (value: string) => void;
}) {
  const id = useId();
  const [draft, setDraft] = useState<string | null>(null);
  return (
    <div className="uf-field">
      <label className="uf-label" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        className="uf-input"
        type="text"
        placeholder={placeholder}
        value={draft ?? value}
        onChange={(e) => {
          setDraft(e.target.value);
          onCommit(e.target.value);
        }}
        onBlur={() => {
          setDraft(null);
        }}
      />
    </div>
  );
}

function SelectField<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { id: T; label: string }[];
  onChange: (value: T) => void;
}) {
  const id = useId();
  return (
    <div className="uf-field">
      <label className="uf-label" htmlFor={id}>
        {label}
      </label>
      <select
        id={id}
        className="uf-select"
        value={value}
        onChange={(e) => {
          onChange(e.target.value as T);
        }}
      >
        {options.map((o) => (
          <option key={o.id} value={o.id}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function replaceAt<T>(list: T[], index: number, item: T): T[] {
  return list.map((x, i) => (i === index ? item : x));
}

const SPLIT_LINKS = (text: string) =>
  text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

/** The incident, weather and surge form. Each list is edited as rows; the
 *  limits are those of backend/src/incidents/model.py. */
export function ScenarioEditor({
  value,
  onChange,
}: {
  value: Scenario;
  onChange: (next: Scenario) => void;
}) {
  const rerouteId = useId();
  const setIncident = (i: number, item: Incident) => {
    onChange({ ...value, incidents: replaceAt(value.incidents, i, item) });
  };
  const setWeather = (i: number, item: WeatherWindow) => {
    onChange({ ...value, weather: replaceAt(value.weather, i, item) });
  };
  const setSurge = (i: number, item: Surge) => {
    onChange({ ...value, surges: replaceAt(value.surges, i, item) });
  };
  return (
    <div className="nw-stack">
      <fieldset className="nw-stack">
        <legend className="uf-label">Incidents and closures</legend>
        {value.incidents.map((inc, i) => (
          <div
            className="nw-form"
            key={i}
            role="group"
            aria-label={`Incident ${String(i + 1)}`}
          >
            <SelectField
              label={`Incident ${String(i + 1)} type`}
              value={inc.type}
              options={INCIDENT_TYPES}
              onChange={(type) => {
                setIncident(i, { ...inc, type });
              }}
            />
            <TextField
              label={`Incident ${String(i + 1)} links`}
              value={inc.links.join(", ")}
              placeholder="J1>J2, J2>J1"
              onCommit={(text) => {
                setIncident(i, { ...inc, links: SPLIT_LINKS(text) });
              }}
            />
            <NumberField
              label={`Incident ${String(i + 1)} start (s)`}
              value={inc.start}
              min={0}
              max={86400}
              onChange={(start) => {
                setIncident(i, { ...inc, start });
              }}
            />
            <NumberField
              label={`Incident ${String(i + 1)} length (s)`}
              value={inc.duration}
              min={1}
              max={86400}
              onChange={(duration) => {
                setIncident(i, { ...inc, duration });
              }}
            />
            {inc.type !== "closure" && (
              <NumberField
                label={`Incident ${String(i + 1)} lanes lost`}
                value={inc.lanesBlocked}
                min={1}
                max={8}
                onChange={(lanesBlocked) => {
                  setIncident(i, {
                    ...inc,
                    lanesBlocked: Math.round(lanesBlocked),
                  });
                }}
              />
            )}
            <button
              type="button"
              className="nw-btn"
              onClick={() => {
                onChange({
                  ...value,
                  incidents: value.incidents.filter((_, k) => k !== i),
                });
              }}
            >
              Remove incident {i + 1}
            </button>
          </div>
        ))}
        <div>
          <button
            type="button"
            className="nw-btn"
            disabled={value.incidents.length >= MAX_EVENTS}
            onClick={() => {
              onChange({
                ...value,
                incidents: [...value.incidents, newIncident()],
              });
            }}
          >
            Add an incident
          </button>
        </div>
      </fieldset>

      <fieldset className="nw-stack">
        <legend className="uf-label">Weather</legend>
        {value.weather.map((w, i) => (
          <div
            className="nw-form"
            key={i}
            role="group"
            aria-label={`Weather ${String(i + 1)}`}
          >
            <SelectField
              label={`Weather ${String(i + 1)} kind`}
              value={w.kind}
              options={WEATHER_KINDS}
              onChange={(kind) => {
                setWeather(i, { ...w, kind });
              }}
            />
            <NumberField
              label={`Weather ${String(i + 1)} severity (0 to 1)`}
              value={w.severity}
              min={0}
              max={1}
              step={0.1}
              onChange={(severity) => {
                setWeather(i, { ...w, severity });
              }}
            />
            <NumberField
              label={`Weather ${String(i + 1)} start (s)`}
              value={w.start}
              min={0}
              max={86400}
              onChange={(start) => {
                setWeather(i, { ...w, start });
              }}
            />
            <NumberField
              label={`Weather ${String(i + 1)} length (s)`}
              value={w.duration}
              min={1}
              max={86400}
              onChange={(duration) => {
                setWeather(i, { ...w, duration });
              }}
            />
            <button
              type="button"
              className="nw-btn"
              onClick={() => {
                onChange({
                  ...value,
                  weather: value.weather.filter((_, k) => k !== i),
                });
              }}
            >
              Remove weather {i + 1}
            </button>
          </div>
        ))}
        <div>
          <button
            type="button"
            className="nw-btn"
            disabled={value.weather.length >= MAX_EVENTS}
            onClick={() => {
              onChange({ ...value, weather: [...value.weather, newWeather()] });
            }}
          >
            Add weather
          </button>
        </div>
      </fieldset>

      <fieldset className="nw-stack">
        <legend className="uf-label">Demand surges</legend>
        {value.surges.map((s, i) => (
          <div
            className="nw-form"
            key={i}
            role="group"
            aria-label={`Surge ${String(i + 1)}`}
          >
            <TextField
              label={`Surge ${String(i + 1)} from (node, blank for any)`}
              value={s.origin ?? ""}
              placeholder="GW1"
              onCommit={(text) => {
                setSurge(i, { ...s, origin: text.trim() || null });
              }}
            />
            <TextField
              label={`Surge ${String(i + 1)} to (node, blank for any)`}
              value={s.destination ?? ""}
              placeholder="GE1"
              onCommit={(text) => {
                setSurge(i, { ...s, destination: text.trim() || null });
              }}
            />
            <NumberField
              label={`Surge ${String(i + 1)} multiplier`}
              value={s.multiplier}
              min={0}
              max={10}
              step={0.1}
              onChange={(multiplier) => {
                setSurge(i, { ...s, multiplier });
              }}
            />
            <NumberField
              label={`Surge ${String(i + 1)} start (s)`}
              value={s.start}
              min={0}
              max={86400}
              onChange={(start) => {
                setSurge(i, { ...s, start });
              }}
            />
            <NumberField
              label={`Surge ${String(i + 1)} length (s)`}
              value={s.duration}
              min={1}
              max={86400}
              onChange={(duration) => {
                setSurge(i, { ...s, duration });
              }}
            />
            <button
              type="button"
              className="nw-btn"
              onClick={() => {
                onChange({
                  ...value,
                  surges: value.surges.filter((_, k) => k !== i),
                });
              }}
            >
              Remove surge {i + 1}
            </button>
          </div>
        ))}
        <div>
          <button
            type="button"
            className="nw-btn"
            disabled={value.surges.length >= MAX_EVENTS}
            onClick={() => {
              onChange({ ...value, surges: [...value.surges, newSurge()] });
            }}
          >
            Add a surge
          </button>
        </div>
      </fieldset>

      <div className="uf-field">
        <label htmlFor={rerouteId}>
          <input
            id={rerouteId}
            type="checkbox"
            checked={value.reroute}
            onChange={(e) => {
              onChange({ ...value, reroute: e.target.checked });
            }}
          />{" "}
          Vehicles detour around a fully blocked link when a path exists
        </label>
      </div>
      {isEmptyScenario(value) && (
        <p className="nw-alert" role="status">
          This scenario has no disruption yet. Add an incident, weather or a
          surge before running it.
        </p>
      )}
    </div>
  );
}
