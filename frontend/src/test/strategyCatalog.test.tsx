/**
 * The strategy catalog (strategies/strategyCatalog.ts): what the comparison
 * offers is what the backend registry says it can run. A strategy added to
 * the registry later appears as one more card with no change here, and one
 * the live comparison cannot run is never offered.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { STRATEGY_CATALOG } from "./strategyCatalogFixture";
import {
  catalogFrom,
  strategyInfo,
  type CatalogState,
} from "../strategies/strategyCatalog";
import { StrategyPicker } from "../strategies/StrategyPicker";
import type { StrategyCatalogDto } from "../services/api";

const WITH_FUTURE: StrategyCatalogDto = {
  ...STRATEGY_CATALOG,
  strategies: [
    ...STRATEGY_CATALOG.strategies,
    {
      id: "bus_priority_signal",
      name: "Bus-Priority Signal",
      status: "experimental",
      description: "A signal that gives buses an early green.",
      family: "signal",
      controlPolicy: "fixed_time_phase_plan",
      adaptation: "none",
      notModelled: [],
      liveComparison: true,
    },
    {
      id: "study_only_strategy",
      name: "Study-Only Strategy",
      status: "experimental",
      description: "Registered, but not derivable for the live comparison.",
      family: "roundabout",
      controlPolicy: "uncontrolled",
      adaptation: "none",
      notModelled: [],
      liveComparison: false,
    },
  ],
  liveComparison: { ...STRATEGY_CATALOG.liveComparison, maxStrategies: 5 },
};

const ready = (
  dto: StrategyCatalogDto,
): CatalogState & { retry: () => void } => ({
  status: "ready",
  catalog: catalogFrom(dto),
  retry: () => undefined,
});

describe("strategy catalog", () => {
  it("offers exactly the strategies the live comparison can run", () => {
    const ids = catalogFrom(WITH_FUTURE).strategies.map((s) => s.id);
    expect(ids).toEqual([
      "fixed_time_signal",
      "adaptive_signal",
      "conventional_roundabout",
      "metered_entry_roundabout",
      "bus_priority_signal",
    ]);
  });

  it("presents a strategy it has no entry for from the registry", () => {
    const future = catalogFrom(WITH_FUTURE).strategies[4];
    expect(future).toMatchObject({
      name: "Bus-Priority Signal",
      summary: "A signal that gives buses an early green.",
      family: "signal",
      glyph: "signal",
      color: "var(--series-5)",
      live: true,
    });
  });

  it("names legacy saved-run strategy ids canonically", () => {
    expect(strategyInfo("adaptive").id).toBe("adaptive_signal");
    expect(strategyInfo("roundabout").name).toBe("Roundabout");
    expect(strategyInfo("signalised_roundabout").name).toBe(
      "Metered roundabout",
    );
  });

  it("gives a new strategy its own card in the same picker", async () => {
    const onChange = vi.fn();
    render(
      <StrategyPicker
        catalog={ready(WITH_FUTURE)}
        value={["fixed_time_signal", "conventional_roundabout"]}
        onChange={onChange}
      />,
    );
    const group = screen.getByRole("group", {
      name: /which strategies should we compare/i,
    });
    expect(within(group).getAllByRole("checkbox")).toHaveLength(5);
    expect(group).toHaveTextContent(/2 of 5 selected/);
    expect(
      within(group).queryByRole("checkbox", { name: /study-only/i }),
    ).toBeNull();

    await userEvent.click(
      within(group).getByRole("checkbox", { name: "Bus-Priority Signal" }),
    );
    // Added in catalog order, whatever order cards are ticked in.
    expect(onChange).toHaveBeenCalledWith([
      "fixed_time_signal",
      "conventional_roundabout",
      "bus_priority_signal",
    ]);
  });

  it("stops adding at the most the comparison can run", () => {
    render(
      <StrategyPicker
        catalog={ready({
          ...STRATEGY_CATALOG,
          liveComparison: {
            ...STRATEGY_CATALOG.liveComparison,
            maxStrategies: 2,
          },
        })}
        value={["fixed_time_signal", "conventional_roundabout"]}
        onChange={() => undefined}
      />,
    );
    expect(
      screen.getByRole("checkbox", { name: "Adaptive signal" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("checkbox", { name: "Fixed-time signal" }),
    ).toBeEnabled();
  });
});
