import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ API_BASE_URL: "" }));
vi.mock("../auth/cognito", () => ({ getAuthToken: () => Promise.resolve("") }));

import { stubApi } from "../insights/testApi";
import { changeTone } from "./changeTone";
import { CompareRunsView } from "./CompareRunsView";
import { runDiffFixture } from "./fixtures";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("changeTone", () => {
  const [delay, served, co2] = runDiffFixture.metrics;
  it("reads direction against whether lower is better", () => {
    expect(changeTone(delay).word).toBe("Better");
    expect(changeTone(served).word).toBe("Better");
    expect(changeTone({ ...served, delta: -5 }).word).toBe("Worse");
    expect(changeTone({ ...delay, delta: 0 }).word).toBe("No change");
  });
  it("does not judge a metric missing on one side", () => {
    expect(changeTone(co2).word).toBe("Not comparable");
  });
});

describe("CompareRunsView", () => {
  it("asks for two valid ids before comparing", async () => {
    render(<CompareRunsView />);
    const button = screen.getByRole("button", { name: "Compare" });
    expect(button).toBeDisabled();
    await userEvent.type(screen.getByLabelText("First run ID"), "run-a");
    await userEvent.type(screen.getByLabelText("Second run ID"), "bad id!");
    expect(button).toBeDisabled();
  });

  it("shows the manifest and metric differences", async () => {
    const { calls } = stubApi({
      "GET /api/v3/runs/compare?a=run-a&b=run-b": runDiffFixture,
    });
    render(<CompareRunsView initialA="run-a" initialB="run-b" />);
    expect(
      await screen.findByText(/differ in their setup/),
    ).toBeInTheDocument();
    expect(calls[0]?.key).toBe("GET /api/v3/runs/compare?a=run-a&b=run-b");
    const manifest = screen.getAllByRole("table")[0];
    expect(within(manifest).getByText("Different")).toBeInTheDocument();
    const metrics = screen.getAllByRole("table")[1];
    const delayRow = within(metrics)
      .getByText(/Average delay/)
      .closest("tr");
    expect(delayRow).toHaveTextContent("-4.1 (-18.2%)");
    expect(delayRow).toHaveTextContent("Better");
    expect(within(metrics).getByText(/CO2/).closest("tr")).toHaveTextContent(
      "Not available",
    );
  });

  it("says when a run is not found", async () => {
    stubApi({});
    render(<CompareRunsView initialA="run-a" initialB="run-z" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("not found");
  });
});
