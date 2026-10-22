/**
 * @vitest-environment jsdom
 *
 * W3-T4: Strategy Summary UI & Strategy DNA Card Tests (ADR-014, W3-T4).
 *
 * Verifies:
 * 1. Rendering of the 6-layer Strategy DNA card across all 4 built-in strategies.
 * 2. Distinction between selected strategies and resolved defaults / parameter provenance.
 * 3. Dynamic live updates when scenario settings (junction type, metering, arms, parameters) change.
 * 4. Surfacing of compatibility and validation diagnostics (compat.* codes) and layer conflict highlighting.
 * 5. Candidate strategy inspection tabs in multi-strategy comparative contexts.
 * 6. Accessibility compliance (axe-core: 0 violations).
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { ScenarioBuilder } from "../components/scenario/ScenarioBuilder";
import { StrategySummaryCard } from "../components/scenario/StrategySummaryCard";
import type { ValidationState } from "../components/scenario/useScenarioValidation";
import { scenarioFromPreset, setEntryControl } from "../scenario/scenarioModel";
import type { ScenarioDocument, Strategy } from "../scenario/scenarioTypes";
import {
  BUILTIN_STRATEGY_DESCRIPTORS,
  evaluateStrategyCompatibility,
  resolveActiveStrategyId,
  resolveParameterProvenance,
  resolveStrategyLayers,
} from "../scenario/strategySummaryModel";
import { ADAPTIVE_DEFAULTS } from "../types/config";
import { axeViolations } from "./axe";

const READY_VALIDATION: ValidationState = {
  status: "done",
  result: {
    valid: true,
    errors: [],
    warnings: [],
    strategies: ["fixed_time", "roundabout"],
  },
};

function BuilderHarness({
  initial,
  strategies = ["fixed_time", "roundabout"],
  validation = READY_VALIDATION,
}: {
  initial: ScenarioDocument;
  strategies?: Strategy[];
  validation?: ValidationState;
}) {
  const [doc, setDoc] = useState(initial);
  return (
    <ScenarioBuilder
      value={doc}
      onChange={setDoc}
      strategies={strategies}
      validation={validation}
    />
  );
}

describe("Strategy DNA model and layer resolution", () => {
  it("ships all four built-in strategies with frozen 16-hex fingerprints", () => {
    expect(BUILTIN_STRATEGY_DESCRIPTORS.fixed_time_signal.fingerprint).toBe(
      "21b44f48677fff33",
    );
    expect(BUILTIN_STRATEGY_DESCRIPTORS.adaptive_signal.fingerprint).toBe(
      "9463e0b9e7a3619d",
    );
    expect(
      BUILTIN_STRATEGY_DESCRIPTORS.conventional_roundabout.fingerprint,
    ).toBe("b622164ad2527a01");
    expect(
      BUILTIN_STRATEGY_DESCRIPTORS.metered_entry_roundabout.fingerprint,
    ).toBe("32511c2e97ffc1bb");
  });

  it("resolves the primary strategy ID correctly from document junction and entry control", () => {
    const docSig = scenarioFromPreset("typical-urban");
    expect(resolveActiveStrategyId(docSig)).toBe("fixed_time_signal");

    docSig.junction.type = "adaptive_signal";
    expect(resolveActiveStrategyId(docSig)).toBe("adaptive_signal");

    const docRb = scenarioFromPreset("typical-urban");
    docRb.junction.type = "roundabout";
    expect(resolveActiveStrategyId(docRb)).toBe("conventional_roundabout");

    setEntryControl(docRb, "metered_entry");
    expect(resolveActiveStrategyId(docRb)).toBe("metered_entry_roundabout");
  });

  it("resolves all six structural layers for conventional roundabout", () => {
    const doc = scenarioFromPreset("typical-urban");
    doc.junction.type = "roundabout";
    const layers = resolveStrategyLayers("conventional_roundabout", doc);
    expect(layers).toHaveLength(6);

    expect(layers[0].layerTitle).toBe("Geometry Constraint");
    expect(layers[0].appliedValue).toContain("Roundabout · 4 arms");

    expect(layers[1].layerTitle).toBe("Movement Topology");
    expect(layers[1].appliedValue).toContain(
      "Zone-based circulatory conflicts",
    );

    expect(layers[2].layerTitle).toBe("Right-of-Way Rule");
    expect(layers[2].appliedValue).toContain(
      "Yield to ring (offside priority)",
    );

    expect(layers[3].layerTitle).toBe("Control Policy");
    expect(layers[3].appliedValue).toContain("Uncontrolled");

    expect(layers[4].layerTitle).toBe("Adaptation Logic");
    expect(layers[4].appliedValue).toContain("None");

    expect(layers[5].layerTitle).toBe("Priority Overlay");
    expect(layers[5].appliedValue).toContain("None");
  });

  it("resolves all six structural layers for metered-entry roundabout", () => {
    const doc = scenarioFromPreset("typical-urban");
    doc.junction.type = "roundabout";
    setEntryControl(doc, "metered_entry");

    const layers = resolveStrategyLayers("metered_entry_roundabout", doc);
    expect(layers).toHaveLength(6);
    expect(layers[2].appliedValue).toContain("Signal over yield");
    expect(layers[3].appliedValue).toContain("Entry metering");
  });

  it("tracks parameter provenance and detects factory defaults vs customizations", () => {
    // The preset carries the engine's own defaults: 30 s green, 4 s yellow, 2 s all-red.
    const doc = scenarioFromPreset("typical-urban");
    doc.signal.nsGreenTime = null;
    doc.signal.ewGreenTime = null;

    const p1 = resolveParameterProvenance("fixed_time_signal", doc);
    expect(p1.isAllDefault).toBe(true);
    expect(p1.customizedCount).toBe(0);

    // Customize green time
    doc.signal.greenTime = 42;
    const p2 = resolveParameterProvenance("fixed_time_signal", doc);
    expect(p2.isAllDefault).toBe(false);
    expect(p2.customizedCount).toBeGreaterThanOrEqual(1);
    expect(p2.parameters.find((p) => p.name === "green_time")?.isDefault).toBe(
      false,
    );
  });

  it("evaluates strategy compatibility detecting geometry and policy conflicts", () => {
    const doc = scenarioFromPreset("typical-urban");
    // Signal document evaluated against roundabout strategy
    const issues = evaluateStrategyCompatibility(
      "conventional_roundabout",
      doc,
    );
    expect(
      issues.some(
        (i) => i.code === "compat.roundabout_yield_requires_roundabout",
      ),
    ).toBe(true);

    // Roundabout document evaluated against adaptive signal
    doc.junction.type = "roundabout";
    const adaptiveIssues = evaluateStrategyCompatibility(
      "adaptive_signal",
      doc,
    );
    expect(
      adaptiveIssues.some(
        (i) => i.code === "compat.adaptive_unsupported_policy",
      ),
    ).toBe(true);
  });

  it("flags adaptive on a metered-entry roundabout, as the backend does", () => {
    const doc = scenarioFromPreset("typical-urban");
    doc.junction.type = "roundabout";
    setEntryControl(doc, "metered_entry");
    const issues = evaluateStrategyCompatibility("adaptive_signal", doc);
    expect(
      issues.some((i) => i.code === "compat.adaptive_unsupported_policy"),
    ).toBe(true);
  });

  it("places server diagnostics on the layer the code names, not by keyword", () => {
    const doc = scenarioFromPreset("typical-urban");
    const layerOf = (code: string) =>
      evaluateStrategyCompatibility("fixed_time_signal", doc, [
        `Server says no (${code})`,
      ]).find((i) => i.code === code)?.layerIndex;
    expect(layerOf("compat.priority_overlay_unsupported")).toBe(6);
    expect(layerOf("compat.phased_priority_unsupported")).toBe(3);
    expect(layerOf("compat.signal_requires_point_topology")).toBe(2);
    expect(layerOf("compat.unknown_strategy")).toBe(4);
    // A code this build does not know still shows, on the first layer.
    expect(layerOf("compat.future_rule")).toBe(1);
  });

  it("reports untouched roundabout parameters as defaults of the real controller", () => {
    const doc = scenarioFromPreset("typical-urban");
    doc.junction.type = "roundabout";
    doc.roundabout.circulatingLanes = undefined;
    const conventional = resolveParameterProvenance(
      "conventional_roundabout",
      doc,
    );
    expect(conventional.isAllDefault).toBe(true);
    setEntryControl(doc, "metered_entry");
    const metered = resolveParameterProvenance("metered_entry_roundabout", doc);
    expect(metered.isAllDefault).toBe(true);
  });

  it("reports untouched adaptive parameters as defaults of the real controller", () => {
    const doc = scenarioFromPreset("typical-urban");
    doc.signal.adaptive = { ...doc.signal.adaptive, ...ADAPTIVE_DEFAULTS };
    const provenance = resolveParameterProvenance("adaptive_signal", doc);
    expect(provenance.isAllDefault).toBe(true);
    doc.signal.adaptive.maxGreen = ADAPTIVE_DEFAULTS.maxGreen + 5;
    const edited = resolveParameterProvenance("adaptive_signal", doc);
    expect(
      edited.parameters.find((p) => p.name === "max_green")?.isDefault,
    ).toBe(false);
  });
});

describe("StrategySummaryCard rendering and live updates", () => {
  it("renders Strategy DNA card with 6 layers and fingerprint", () => {
    const doc = scenarioFromPreset("typical-urban");
    render(<StrategySummaryCard scenario={doc} />);

    expect(screen.getByText(/Strategy DNA & Contract/)).toBeInTheDocument();
    expect(screen.getByText("Fixed-Time Signal")).toBeInTheDocument();
    expect(screen.getByText("21b44f48677fff33")).toBeInTheDocument();
    expect(screen.getByText("Geometry Constraint")).toBeInTheDocument();
    expect(screen.getByText("Movement Topology")).toBeInTheDocument();
    expect(screen.getByText("Right-of-Way Rule")).toBeInTheDocument();
    expect(screen.getByText("Control Policy")).toBeInTheDocument();
    expect(screen.getByText("Adaptation Logic")).toBeInTheDocument();
    expect(screen.getByText("Priority Overlay")).toBeInTheDocument();
    expect(screen.getByText(/Configuration:/)).toBeInTheDocument();
  });

  it("updates live when junction type switches from signal to roundabout in ScenarioBuilder", () => {
    render(<BuilderHarness initial={scenarioFromPreset("typical-urban")} />);
    expect(screen.getByText("Fixed-Time Signal")).toBeInTheDocument();
    expect(screen.getByText("21b44f48677fff33")).toBeInTheDocument();

    // Click Roundabout in step 1
    const rbRadio = screen.getByLabelText(/Roundabout/);
    fireEvent.click(rbRadio);

    expect(screen.getByText("Conventional Roundabout")).toBeInTheDocument();
    expect(screen.getByText("b622164ad2527a01")).toBeInTheDocument();
    expect(
      screen.getAllByText(/Yield to ring \(offside priority\)/).length,
    ).toBeGreaterThanOrEqual(1);
  });

  it("updates live when roundabout entry control switches to metered entry", () => {
    const doc = scenarioFromPreset("typical-urban");
    doc.junction.type = "roundabout";
    render(<BuilderHarness initial={doc} />);

    expect(screen.getByText("Conventional Roundabout")).toBeInTheDocument();

    // Switch to metered entry
    const meteredRadio = screen.getByLabelText(/Metered entry \(signals\)/);
    fireEvent.click(meteredRadio);

    expect(
      screen.getByText("Metered-Entry Signalised Roundabout"),
    ).toBeInTheDocument();
    expect(screen.getByText("32511c2e97ffc1bb")).toBeInTheDocument();
    expect(
      screen.getAllByText(
        /Signal over yield \(metered entries yield to circulating flow\)/,
      ).length,
    ).toBeGreaterThanOrEqual(1);
  });

  it("switches tabs between candidate strategies in multi-strategy context", () => {
    const doc = scenarioFromPreset("typical-urban");
    render(
      <StrategySummaryCard
        scenario={doc}
        strategies={["fixed_time", "roundabout"]}
      />,
    );

    expect(screen.getByText("Fixed-Time Signal")).toBeInTheDocument();
    expect(screen.getByText(/Conventional Roundabout/)).toBeInTheDocument();

    // Click Conventional Roundabout tab
    const rbTab = screen.getByRole("button", {
      name: "Conventional Roundabout",
    });
    fireEvent.click(rbTab);

    // Active inspection card changes to Roundabout DNA
    expect(screen.getByText("b622164ad2527a01")).toBeInTheDocument();
    expect(screen.getByText("Comparison Alternative")).toBeInTheDocument();
  });

  it("surfaces server compatibility error diagnostics (compat.*) with layer conflict", () => {
    const doc = scenarioFromPreset("typical-urban");
    doc.junction.type = "roundabout";

    const serverErrors = [
      "controller.signalControl 'adaptive' requires a signalised junction (compat.adaptive_unsupported_policy)",
    ];

    render(
      <StrategySummaryCard
        scenario={doc}
        activeStrategy="adaptive_signal"
        serverErrors={serverErrors}
      />,
    );

    expect(screen.getByText(/Compatibility Warning/)).toBeInTheDocument();
    expect(
      screen.getAllByText(/compat\.adaptive_unsupported_policy/).length,
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("alert")).toHaveTextContent(
      /controller\.signalControl 'adaptive' requires a signalised junction/,
    );
  });

  it("passes axe-core accessibility checks with 0 violations", async () => {
    const doc = scenarioFromPreset("typical-urban");
    const { container } = render(
      <StrategySummaryCard
        scenario={doc}
        strategies={["fixed_time", "roundabout"]}
      />,
    );

    const violations = await axeViolations(container);
    expect(violations).toEqual([]);
  });

  it("passes axe-core accessibility checks in metered roundabout state", async () => {
    const doc = scenarioFromPreset("typical-urban");
    doc.junction.type = "roundabout";
    setEntryControl(doc, "metered_entry");

    const { container } = render(
      <StrategySummaryCard
        scenario={doc}
        strategies={["fixed_time", "roundabout"]}
      />,
    );

    const violations = await axeViolations(container);
    expect(violations).toEqual([]);
  });
});
