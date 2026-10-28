/**
 * GET /api/strategies as the backend answers it with its four built-in
 * strategies (backend live/router.py list_strategies). Tests that render the
 * guided comparison mock services/api with this.
 */
import type { StrategyCatalogDto } from "../services/api";

export const STRATEGY_CATALOG: StrategyCatalogDto = {
  strategies: [
    {
      id: "fixed_time_signal",
      name: "Fixed-Time Signal",
      status: "stable",
      description: "Signal with a fixed phase plan.",
      family: "signal",
      controlPolicy: "fixed_time_phase_plan",
      adaptation: "none",
      notModelled: [],
      liveComparison: true,
    },
    {
      id: "adaptive_signal",
      name: "Adaptive (Actuated) Signal",
      status: "stable",
      description: "Signal that extends greens on detection.",
      family: "signal",
      controlPolicy: "fixed_time_phase_plan",
      adaptation: "gap_out_extension",
      notModelled: [],
      liveComparison: true,
    },
    {
      id: "conventional_roundabout",
      name: "Conventional Roundabout",
      status: "stable",
      description: "Unsignalised roundabout.",
      family: "roundabout",
      controlPolicy: "uncontrolled",
      adaptation: "none",
      notModelled: [],
      liveComparison: true,
    },
    {
      id: "metered_entry_roundabout",
      name: "Metered-Entry Signalised Roundabout",
      status: "stable",
      description: "Roundabout with metered entries.",
      family: "roundabout",
      controlPolicy: "metering",
      adaptation: "none",
      notModelled: [],
      liveComparison: true,
    },
  ],
  aliases: { adaptive: "adaptive_signal" },
  liveComparison: {
    defaultSelection: ["fixed_time_signal", "conventional_roundabout"],
    maxStrategies: 4,
  },
};
