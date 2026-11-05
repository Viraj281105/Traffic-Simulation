import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ API_BASE_URL: "" }));
vi.mock("../auth/cognito", () => ({ getAuthToken: () => Promise.resolve("") }));

import { parseEvalDocument } from "../netrl/api";
import { evalFixture } from "../netrl/fixtures";
import { NetworkRlComparison } from "../netrl/NetworkRlComparison";
import { NetworkRlTab } from "../netrl/NetworkRlTab";
import { outcome, statsLine } from "../netrl/rlText";
import { rlFixture } from "../rlcompare/fixtures";
import { axeViolations } from "./axe";
import { stubNet } from "./netApi";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("NetworkRlComparison", () => {
  it("shows the server's verdict with interval and p-value for each baseline", () => {
    render(<NetworkRlComparison doc={evalFixture} />);
    expect(screen.getByText(/^rl_ppo beats fixed_time/)).toBeInTheDocument();
    expect(
      screen.getByText(
        /No reliable difference between rl_ppo and max_pressure/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /95% interval -12.90 to -7.42 s; p < 0.001; paired_t, 5 paired seeds/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/only 5 paired seeds: the interval is wide/),
    ).toBeInTheDocument();
  });

  it("carries the caveat that mean wait is stopped vehicle-seconds per entered vehicle", () => {
    render(<NetworkRlComparison doc={evalFixture} />);
    expect(
      screen.getByText(/stopped vehicle-seconds per entered vehicle/),
    ).toBeInTheDocument();
  });

  it("lists each held-out seed with every policy's value, and switches measure", async () => {
    render(<NetworkRlComparison doc={evalFixture} />);
    const table = screen.getByRole("table", { name: /for each held-out seed/ });
    const row = within(table)
      .getByRole("rowheader", { name: "10002" })
      .closest("tr");
    expect(row).toHaveTextContent("43.5");
    expect(row).toHaveTextContent("29.8");
    await userEvent.selectOptions(
      screen.getByLabelText("Measure"),
      "mean_queue",
    );
    expect(
      screen.getByRole("table", { name: /Mean queue/ }),
    ).toBeInTheDocument();
  });

  it("reads direction from the server and never recomputes it", () => {
    const [a, b] = evalFixture.paired_comparisons;
    expect(outcome(a)).toBe("better");
    expect(outcome(b)).toBe("none");
    expect(outcome({ ...a, lower_is_better: false })).toBe("worse");
    expect(statsLine(b)).toContain("p = 0.098");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<NetworkRlComparison doc={evalFixture} />);
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("parseEvalDocument", () => {
  it("accepts the evaluation document and refuses anything else", () => {
    expect(parseEvalDocument(JSON.stringify(evalFixture)).seeds).toHaveLength(
      5,
    );
    expect(() => parseEvalDocument("{")).toThrow("not valid JSON");
    expect(() => parseEvalDocument('{"format":"other"}')).toThrow(
      "urbanflow-rl-eval",
    );
  });
});

describe("NetworkRlTab", () => {
  it("shows pasted evaluation JSON", async () => {
    render(<NetworkRlTab />);
    await userEvent.click(
      screen.getByLabelText(/paste the urbanflow-rl-eval/i),
    );
    await userEvent.paste(JSON.stringify(evalFixture));
    await userEvent.click(
      screen.getByRole("button", { name: "Show comparison" }),
    );
    expect(
      await screen.findByText(/^rl_ppo beats fixed_time/),
    ).toBeInTheDocument();
  });

  it("explains a document it cannot use", async () => {
    render(<NetworkRlTab />);
    await userEvent.click(
      screen.getByLabelText(/paste the urbanflow-rl-eval/i),
    );
    await userEvent.paste("{}");
    await userEvent.click(
      screen.getByRole("button", { name: "Show comparison" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "not a network RL evaluation",
    );
  });

  it("loads a junction comparison by id from /api/v3/rl/comparisons", async () => {
    const { calls } = stubNet({ "GET /api/v3/rl/comparisons/rl1": rlFixture });
    render(<NetworkRlTab />);
    await userEvent.type(screen.getByLabelText("RL comparison ID"), "rl1");
    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(
      await screen.findByText("RL policy beats Fixed-time signal"),
    ).toBeInTheDocument();
    expect(calls[0]?.key).toBe("GET /api/v3/rl/comparisons/rl1");
  });
});
