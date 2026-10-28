import { render, screen, waitFor } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

import scene from "../landing/data/scene.json";
import evidence from "../landing/data/evidence.json";
import {
  STRATEGY_IDS,
  formatClock,
  sampleRun,
  seriesAt,
  windowLength,
  type SceneData,
} from "../landing/scene/sceneData";
import { drawScene, type SceneTheme } from "../landing/scene/render";
import { Evidence } from "../landing/sections/Evidence";
import App from "../landing/App";

const data = scene as unknown as SceneData;

// jsdom has no IntersectionObserver; report every element as on screen so
// the scroll-triggered pieces render their final state.
beforeAll(() => {
  class InView {
    constructor(private readonly cb: IntersectionObserverCallback) {}
    observe(target: Element) {
      this.cb(
        [
          {
            isIntersecting: true,
            intersectionRatio: 1,
            target,
          } as IntersectionObserverEntry,
        ],
        this as unknown as IntersectionObserver,
      );
    }
    unobserve() {}
    disconnect() {}
    takeRecords() {
      return [];
    }
  }
  vi.stubGlobal("IntersectionObserver", InView);
});

describe("recorded landing scene", () => {
  it("holds one run per control strategy, recorded from one seed and one demand", () => {
    expect(Object.keys(data.runs).sort()).toEqual([...STRATEGY_IDS].sort());
    expect(data.provenance.gitCommit).toMatch(/^[0-9a-f]{40}$/);
    expect(data.provenance.seed).toBe(5);
    const lengths = new Set(
      STRATEGY_IDS.map((id) => data.runs[id].frames.length),
    );
    expect(lengths.size).toBe(1);
    for (const id of STRATEGY_IDS) {
      const run = data.runs[id];
      expect(run.series.length).toBeGreaterThan(100);
      expect(run.metrics.totalVehiclesSpawned).toBe(
        data.runs.fixed_time.metrics.totalVehiclesSpawned,
      );
    }
  });

  it("replays the same arrivals under every control", () => {
    // The seed fixes who arrives when, so vehicle ids present early in the
    // window overlap heavily between strategies.
    const first = (id: (typeof STRATEGY_IDS)[number]) =>
      new Set(data.runs[id].frames[0]?.v.map((v) => v[0]));
    const a = first("fixed_time");
    const b = first("roundabout");
    const shared = [...a].filter((v) => b.has(v)).length;
    expect(shared / Math.max(a.size, b.size)).toBeGreaterThan(0.5);
  });

  it("blends frames and loops without inventing vehicles", () => {
    const run = data.runs.fixed_time;
    const step = data.provenance.frameSeconds;
    const at = sampleRun(run, data, 10);
    const next = sampleRun(run, data, 10 + step / 2);
    const ids = new Set(run.frames.flatMap((f) => f.v.map((v) => v[0])));
    for (const v of next.vehicles) expect(ids.has(v.id)).toBe(true);
    const moved = next.vehicles.find((v) =>
      at.vehicles.some((w) => w.id === v.id),
    );
    expect(moved).toBeDefined();
    // Looping: one full window later is the same moment.
    const len = windowLength(data);
    expect(sampleRun(run, data, 10 + len).vehicles.length).toBe(
      at.vehicles.length,
    );
    // The seam fades the scene out.
    expect(sampleRun(run, data, 0).vehicles.every((v) => v.alpha < 0.05)).toBe(
      true,
    );
  });

  it("reads queue and departures from the per-second series, clamped to the run", () => {
    const run = data.runs.adaptive;
    expect(seriesAt(run, -5)).toEqual(seriesAt(run, 0));
    const end = seriesAt(run, 10_000);
    expect(end.departed).toBe(run.series[run.series.length - 1]?.[2]);
    expect(formatClock(75)).toBe("01:15");
  });
});

/** The fill colours a theme paints, in order, from a recording context. */
function fillsFor(theme: SceneTheme): string[] {
  const fills: string[] = [];
  const noop = () => undefined;
  const ctx = new Proxy(
    {},
    {
      get: (_t, prop) =>
        prop === "createRadialGradient" ? () => ({ addColorStop: noop }) : noop,
      set: (_t, prop, value) => {
        if (prop === "fillStyle" && typeof value === "string")
          fills.push(value);
        return true;
      },
    },
  ) as unknown as CanvasRenderingContext2D;
  const run = data.runs.fixed_time;
  const s = sampleRun(run, data, 20);
  drawScene(ctx, 800, 500, {
    strategy: "fixed_time",
    vehicles: s.vehicles,
    control: s.control,
    camera: { yaw: -30, elev: 40, zoom: 1, shiftX: 0, shiftY: 0 },
    innerRadius: 10,
    outerRadius: 20,
    clock: s.clock,
    theme,
  });
  return fills;
}

describe("scene themes", () => {
  it("paints a pale daylight ground in light mode and the night ground in dark mode", () => {
    expect(fillsFor("light")[0]).toBe("#edf1f7");
    expect(fillsFor("dark")[0]).toBe("#0a1626");
  });

  it("draws the two themes with different palettes and still draws vehicles", () => {
    const light = fillsFor("light");
    expect(light).not.toEqual(fillsFor("dark"));
    // Vehicle faces are the translucent rgba() fills.
    expect(light.some((f) => f.startsWith("rgba("))).toBe(true);
  });
});

describe("evidence section", () => {
  it("reports the study's own verdicts and counts", () => {
    render(<Evidence />);
    expect(
      screen.getByRole("heading", { name: /you do not know/i }),
    ).toBeInTheDocument();
    const inconclusive = evidence.deltas.filter(
      (d) => d.verdict === "inconclusive",
    ).length;
    expect(screen.getAllByText("inconclusive")).toHaveLength(inconclusive);
    expect(screen.getAllByText(/indicative only/i).length).toBeGreaterThan(0);
  });
});

describe("landing page", () => {
  it("opens with the application entry points and the story", async () => {
    render(<App />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      /Signal or/,
    );
    expect(screen.getByTestId("link-explore-simulation")).toHaveAttribute(
      "href",
      "/app/comparative",
    );
    expect(screen.getByTestId("link-run-another-scenario")).toHaveAttribute(
      "href",
      "/app/comparative",
    );
    expect(screen.getByTestId("link-plan-study")).toHaveAttribute(
      "href",
      "/app/planner",
    );
    // The chapter navigation is there for keyboard users of the pinned story.
    expect(
      screen.getByRole("navigation", { name: "Story chapters" }),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.getAllByRole("img", { name: /replayed|recorded/i }).length,
      ).toBeGreaterThan(0);
    });
  });
});
