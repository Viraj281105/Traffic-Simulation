import type {
  Incident,
  IncidentType,
  PresetScenario,
  Scenario,
  Surge,
  WeatherKind,
  WeatherWindow,
} from "./types";

/** Bounds of the request models (backend/src/incidents/model.py). */
export const INCIDENT_TYPES: { id: IncidentType; label: string }[] = [
  { id: "crash", label: "Crash" },
  { id: "blocked_lane", label: "Blocked lane" },
  { id: "closure", label: "Closure" },
];
export const WEATHER_KINDS: { id: WeatherKind; label: string }[] = [
  { id: "rain", label: "Rain" },
  { id: "fog", label: "Fog" },
  { id: "snow", label: "Snow" },
  { id: "ice", label: "Ice" },
];
export const MAX_EVENTS = 20;

export function newIncident(): Incident {
  return {
    type: "crash",
    links: [],
    start: 200,
    duration: 240,
    lanesBlocked: 1,
    policy: "drain",
  };
}
export function newWeather(): WeatherWindow {
  return { kind: "rain", severity: 1, start: 200, duration: 300 };
}
export function newSurge(): Surge {
  return {
    origin: null,
    destination: null,
    start: 200,
    duration: 300,
    multiplier: 1.5,
  };
}

/** A catalogue preset's scenario with the model's defaults filled in, so the
 *  form can edit every field. */
export function scenarioFromPreset(s: PresetScenario): Scenario {
  return {
    incidents: (s.incidents ?? []).map((i) => ({ ...newIncident(), ...i })),
    weather: (s.weather ?? []).map((w) => ({ ...newWeather(), ...w })),
    surges: (s.surges ?? []).map((u) => ({ ...newSurge(), ...u })),
    reroute: s.reroute ?? true,
  };
}

export function isEmptyScenario(s: Scenario): boolean {
  return !s.incidents.length && !s.weather.length && !s.surges.length;
}
