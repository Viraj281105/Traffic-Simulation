/**
 * V1.1 vehicle classes and V1.2 lanes on the frontend: mix utilities, the
 * dashboard payload contract, config equality, the map legend and the guided
 * setup question.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  DEFAULT_CONFIG_VALUES,
  dashboardPayload,
  sameConfigValues,
} from "../types/config";
import {
  MIX_PRESETS,
  describeMix,
  hasLongVehicles,
  mixPresetFor,
  normalizeMix,
  sameMix,
} from "../vehicles/vehicleClasses";
import { VehicleLegend, VehicleMixBar } from "../components/VehicleLegend";
import { ScenarioSetup } from "../components/guided/ScenarioSetup";
import type { LiveSnapshot, SnapshotVehicle } from "../types/simulation";

const city = MIX_PRESETS.find((p) => p.id === "city")?.mix ?? null;

describe("vehicle mix utilities", () => {
  it("normalises shares to exactly 1", () => {
    const mix = normalizeMix({
      car: 3,
      suv: 1,
      bus: 1,
      truck: 0,
      motorcycle: 1,
    });
    expect(mix).not.toBeNull();
    const total = Object.values(mix ?? {}).reduce((a, b) => a + b, 0);
    expect(total).toBeCloseTo(1, 9);
    // Three 1/6 shares round up; the remainder comes off the largest.
    expect(mix?.car).toBeCloseTo(0.5, 2);
    expect(
      normalizeMix({ car: 0, suv: 0, bus: 0, truck: 0, motorcycle: 0 }),
    ).toBeNull();
  });

  it("presets sum to 1 and are recognised", () => {
    for (const preset of MIX_PRESETS) {
      if (preset.mix) {
        const total = Object.values(preset.mix).reduce((a, b) => a + b, 0);
        expect(total).toBeCloseTo(1, 9);
      }
      expect(mixPresetFor(preset.mix)?.id).toBe(preset.id);
    }
    expect(mixPresetFor(null)?.id).toBe("cars");
  });

  it("describes and classifies mixes", () => {
    expect(describeMix(null)).toBe("cars only");
    expect(describeMix(city)).toMatch(/^60% car, 20% suv/);
    expect(hasLongVehicles(city)).toBe(true);
    expect(hasLongVehicles(null)).toBe(false);
    expect(sameMix(city, city ? { ...city } : null)).toBe(true);
    expect(sameMix(city, null)).toBe(false);
  });
});

describe("dashboard payload", () => {
  it("is unchanged for cars only with lane changing on", () => {
    const payload = dashboardPayload(
      DEFAULT_CONFIG_VALUES,
      "fixed_time_signal",
    );
    expect(payload).not.toHaveProperty("vehicleMix");
    expect(payload).not.toHaveProperty("laneChanging");
  });

  it("carries a mix and a disabled lane-change switch", () => {
    const payload = dashboardPayload(
      { ...DEFAULT_CONFIG_VALUES, vehicleMix: city, laneChanging: false },
      "roundabout",
    );
    expect(payload.vehicleMix).toEqual(city);
    expect(payload.laneChanging).toBe(false);
  });

  it("uses side-street lanes only when asked, and only for a signal", () => {
    const config = { ...DEFAULT_CONFIG_VALUES, lanes: 2, lanesEastWest: 1 };
    const comparison = dashboardPayload(config, "fixed_time_signal");
    expect([comparison.lanesEast, comparison.lanesWest]).toEqual([2, 2]);
    const signalOnly = dashboardPayload(config, "fixed_time_signal", true);
    expect([signalOnly.lanesNorth, signalOnly.lanesSouth]).toEqual([2, 2]);
    expect([signalOnly.lanesEast, signalOnly.lanesWest]).toEqual([1, 1]);
    const roundabout = dashboardPayload(config, "roundabout", true);
    expect(roundabout.lanesEast).toBe(2);
  });
});

describe("config equality", () => {
  it("compares mixes by value and treats absent lane changing as on", () => {
    const a = { ...DEFAULT_CONFIG_VALUES, vehicleMix: city };
    const b = {
      ...DEFAULT_CONFIG_VALUES,
      vehicleMix: city ? { ...city } : null,
    };
    expect(sameConfigValues(a, b)).toBe(true);
    expect(sameConfigValues(a, DEFAULT_CONFIG_VALUES)).toBe(false);
    expect(
      sameConfigValues(DEFAULT_CONFIG_VALUES, {
        ...DEFAULT_CONFIG_VALUES,
        laneChanging: true,
      }),
    ).toBe(true);
  });
});

function vehicle(
  id: string,
  vehicleType: SnapshotVehicle["vehicleType"],
  laneChange: SnapshotVehicle["laneChange"] = null,
): SnapshotVehicle {
  return {
    id,
    x: 0,
    y: 0,
    speed: 5,
    acceleration: 0,
    heading: 0,
    length: 4.5,
    width: 2,
    state: "approaching",
    laneId: "n_in_0",
    direction: "north",
    turnIntent: "straight",
    waitTime: 0,
    stopCount: 0,
    spawnTime: 0,
    exitTime: null,
    distanceTraveled: 0,
    vehicleType,
    laneChange,
  };
}

function snapshotWith(
  vehicles: SnapshotVehicle[],
  inProgress = 0,
): LiveSnapshot {
  return {
    vehicles,
    laneModel: {
      laneChanges: inProgress,
      laneChangesInProgress: inProgress,
      missedTurns: 0,
    },
  } as unknown as LiveSnapshot;
}

describe("map legend", () => {
  it("is hidden for cars-only traffic", () => {
    const { container } = render(
      <VehicleLegend snapshot={snapshotWith([vehicle("a", "car")])} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("lists the classes on the road with counts, and lane changes", () => {
    render(
      <VehicleLegend
        snapshot={snapshotWith(
          [
            vehicle("a", "car"),
            vehicle("b", "bus"),
            vehicle("c", "bus", "left"),
            vehicle("d", "motorcycle"),
          ],
          1,
        )}
      />,
    );
    const legend = screen.getByLabelText("Map legend");
    expect(legend).toHaveTextContent("Car1");
    expect(legend).toHaveTextContent("Bus2");
    expect(legend).toHaveTextContent("Motorcycle / bike1");
    expect(legend).toHaveTextContent("Changing lanes1");
    expect(legend).not.toHaveTextContent("Truck");
  });

  it("describes a mix bar for screen readers", () => {
    render(<VehicleMixBar mix={city} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "60% car, 20% suv, 5% bus, 5% truck, 10% motorcycle / bike",
    );
  });
});

describe("guided setup", () => {
  it("asks what traffic uses the junction and runs with the chosen mix", async () => {
    const onRun = vi.fn();
    render(
      <ScenarioSetup
        config={DEFAULT_CONFIG_VALUES}
        onRun={onRun}
        runInProgress={false}
      />,
    );
    expect(
      screen.getByText("What traffic uses the junction?"),
    ).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Cars only/ })).toBeChecked();
    await userEvent.click(
      screen.getByRole("radio", { name: /Bus & freight route/ }),
    );
    expect(
      screen.getByText(/the junction is laid out for them/),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: /Run the comparison/ }),
    );
    expect(onRun).toHaveBeenCalledWith(
      expect.objectContaining({
        vehicleMix: MIX_PRESETS.find((p) => p.id === "freight")?.mix,
      }),
    );
  });
});

describe("reliability notes", () => {
  it("flag mixed traffic as indicative", async () => {
    const { trustNotes } = await import("../metrics/plainLanguage");
    const base = {
      seed: 1,
      lanes: 1,
      warmupSeconds: 30,
      measuredSeconds: 270,
      complete: true,
      collisions: 0,
      lowReliabilitySample: false,
    };
    const text = (mixed: boolean) =>
      trustNotes({ ...base, mixedTraffic: mixed })
        .map((n) => n.text)
        .join(" ");
    expect(text(true)).toMatch(/Cars only is the calibrated comparison/);
    expect(text(false)).not.toMatch(/Cars only is the calibrated comparison/);
  });
});
