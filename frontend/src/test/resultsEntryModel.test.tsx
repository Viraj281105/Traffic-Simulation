/**
 * @vitest-environment jsdom
 *
 * The results page names the entry model that ran (checkpoint 12, found in
 * the browser: it listed traffic, lanes, mix and length but not the model).
 * The chip follows what the engines report, and flags a run that differs
 * from the request or strategies that disagree.
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { entryModelChip } from "../metrics/entryModel";
import { StrategyResults } from "../components/guided/StrategyResults";
import { DEFAULT_CONFIG_VALUES } from "../types/config";

vi.mock("../config", () => ({ API_BASE_URL: "http://localhost:8000" }));

const QUEUE = { enabled: true, capacity: 25 };

describe("entry model chip", () => {
  it("names the queue the engines ran, with its limit", () => {
    expect(entryModelChip(QUEUE, ["queue", "queue"])).toEqual({
      text: "Arrivals queue outside the map (at most 25 per road)",
      caution: false,
    });
  });

  it("adds nothing for the default model", () => {
    expect(entryModelChip(null, ["suspend", "suspend"])).toBeNull();
    expect(entryModelChip({ enabled: false }, [])).toBeNull();
  });

  it("uses the request until the first metrics arrive", () => {
    expect(entryModelChip(QUEUE, [undefined, undefined])?.text).toMatch(
      /queue outside the map/,
    );
  });

  it("flags a run that did not use the requested model", () => {
    const chip = entryModelChip(QUEUE, ["suspend", "suspend"]);
    expect(chip?.caution).toBe(true);
    expect(chip?.text).toMatch(/requested, but arrivals were held back/);
    expect(entryModelChip(null, ["queue", "queue"])?.caution).toBe(true);
  });

  it("flags strategies that ran different models as not comparable", () => {
    const chip = entryModelChip(QUEUE, ["queue", "suspend"]);
    expect(chip).toEqual({
      text: "Strategies ran different entry models: not comparable",
      caution: true,
    });
  });
});

describe("results page", () => {
  it("lists the entry model among the scenario chips", () => {
    render(
      <StrategyResults
        snapshot={null}
        config={{ ...DEFAULT_CONFIG_VALUES, entryQueue: QUEUE }}
        replayName={null}
        complete={false}
        running
        warmupSeconds={30}
        elapsedSeconds={10}
        canSave={false}
        onSave={() => {}}
        onWatch={() => {}}
        onChangeScenario={() => {}}
        onTryScenario={() => {}}
        onOpenAnalytics={null}
        sessionRuns={[]}
        currentRunId={null}
      />,
    );
    const chips = screen.getByRole("list", { name: "Scenario" });
    expect(
      within(chips).getByText(
        "Arrivals queue outside the map (at most 25 per road)",
      ),
    ).toBeInTheDocument();
  });
});

describe("entry model sentence", () => {
  const used = { model: "queue" as const, capacity: null };

  it("states how each page treats the wait outside", async () => {
    const { entryModelSentence } = await import("../metrics/entryModel");
    expect(entryModelSentence(used)).toMatch(
      /shown separately as "wait to enter"/,
    );
    expect(entryModelSentence(used, "objective")).toMatch(
      /objective here includes that wait/,
    );
    expect(entryModelSentence(used, "not-shown")).toMatch(
      /do not include that wait/,
    );
    expect(entryModelSentence({ model: "suspend", capacity: null })).toBeNull();
  });
});
