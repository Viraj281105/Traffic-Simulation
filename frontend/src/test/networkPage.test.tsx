import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ API_BASE_URL: "" }));
vi.mock("../auth/cognito", () => ({ getAuthToken: () => Promise.resolve("") }));

import { NetworkPage } from "../netpage/NetworkPage";
import { TABS } from "../netpage/tabs";
import { resolveRoute } from "../routing";
import { axeViolations } from "./axe";

beforeEach(() => {
  window.history.replaceState(null, "", "/app/network");
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe("/app/network", () => {
  it("is a routed view", () => {
    expect(resolveRoute("/app/network")).toEqual({
      kind: "view",
      view: "network",
    });
  });

  it("offers the seven tabs, Map first", () => {
    render(<NetworkPage />);
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(
      TABS.map((t) => t.label),
    );
    expect(TABS.map((t) => t.label)).toEqual([
      "Map",
      "Congestion",
      "Metrics",
      "Calibration",
      "RL",
      "Twin",
      "Load tests",
    ]);
    expect(screen.getByRole("tab", { name: "Map" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("keeps the tab in the address and shows its screen", async () => {
    render(<NetworkPage />);
    await userEvent.click(screen.getByRole("tab", { name: "Congestion" }));
    expect(window.location.search).toBe("?tab=congestion");
    expect(
      await screen.findByRole("button", { name: "Analyse congestion" }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Twin" }));
    expect(
      await screen.findByText("Prediction against observation"),
    ).toBeInTheDocument();
  });

  it("opens the tab named in the address, and Map for an unknown one", () => {
    window.history.replaceState(null, "", "/app/network?tab=rl");
    const first = render(<NetworkPage />);
    expect(screen.getByRole("tab", { name: "RL" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    first.unmount();
    window.history.replaceState(null, "", "/app/network?tab=zzz");
    render(<NetworkPage />);
    expect(screen.getByRole("tab", { name: "Map" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<NetworkPage />);
    expect(await axeViolations(container)).toEqual([]);
  });
});
