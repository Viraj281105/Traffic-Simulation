import type { StrategyId } from "./sceneData";

/** One colour per control strategy, the same on every chart on the page.
 *  Signal is amber and the roundabout teal, as everywhere in UrbanFlow. */
export const STRATEGY_COLOUR: Record<StrategyId, string> = {
  fixed_time: "var(--series-signal)",
  adaptive: "var(--color-accent)",
  roundabout: "var(--series-roundabout)",
  metered_entry_roundabout: "var(--brand-green)",
};

export const STRATEGY_SHORT: Record<StrategyId, string> = {
  fixed_time: "Fixed-time",
  adaptive: "Adaptive",
  roundabout: "Roundabout",
  metered_entry_roundabout: "Metered entry",
};

/** The metrics the recorded runs report, with how to read each. */
export const METRIC_VIEW = [
  {
    key: "averageDelay",
    label: "Average delay",
    unit: "s",
    digits: 1,
    better: "lower",
  },
  {
    key: "throughput",
    label: "Vehicles served",
    unit: "",
    digits: 0,
    better: "higher",
  },
  {
    key: "maxQueueLength",
    label: "Longest queue",
    unit: "veh",
    digits: 0,
    better: "lower",
  },
  {
    key: "averageStopsPerVehicle",
    label: "Stops per vehicle",
    unit: "",
    digits: 2,
    better: "lower",
  },
] as const;

/** The same colours as text: the darker "ink" variants where the theme has
 *  them, so a label stays readable on the light stage. */
export const STRATEGY_INK: Record<StrategyId, string> = {
  fixed_time: "var(--series-signal-ink)",
  adaptive: "var(--color-accent)",
  roundabout: "var(--series-roundabout-ink)",
  metered_entry_roundabout: "var(--brand-green-ink)",
};
