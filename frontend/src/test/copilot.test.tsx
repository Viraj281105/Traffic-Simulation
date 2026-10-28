import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ExperimentProposal } from "../services/v3/copilot";

const propose = vi.fn();
const applySuggestion = vi.fn();
const confirmProposal = vi.fn();

vi.mock("../services/v3/copilot", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../services/v3/copilot")>()),
  propose: (q: string, mode: string) => propose(q, mode) as Promise<unknown>,
  applySuggestion: (id: string, code: string) =>
    applySuggestion(id, code) as Promise<unknown>,
  confirmProposal: (p: unknown) => confirmProposal(p) as Promise<unknown>,
}));

import { CopilotPage } from "../components/copilot/CopilotPage";
import { axeViolations } from "./axe";

const base: ExperimentProposal = {
  id: "prop_1",
  question: "adaptive vs fixed",
  mode: "deterministic",
  aiUnavailableReason: "no AI provider is configured on this server",
  intent: {
    alternatives: ["adaptive", "fixed_time"],
    baseline: "fixed_time",
    aggression: "high",
    demand: "peak",
    unevenDemand: false,
    mix: "default",
    depth: "standard",
    replications: 2,
    primaryIndicator: "averageDelay",
  },
  experiment: {},
  fieldProvenance: { alternatives: "rule", aggression: "model" },
  assumptions: ["Baseline: Fixed-time signal."],
  warnings: [],
  suggestedChecks: ["Repeat with uneven directional demand."],
  clarification: null,
  estimatedRuns: 96,
  estimatedSimulatedSeconds: 23040,
  estimatedWallTime: "unverified",
  validated: true,
  issues: [],
  contentHash: "a".repeat(64),
  confirmed: false,
  experimentId: null,
};

describe("CopilotPage", () => {
  beforeEach(() => {
    propose.mockReset();
    applySuggestion.mockReset();
    confirmProposal.mockReset();
  });

  it("shows a validated proposal with its sources and confirms it", async () => {
    propose.mockResolvedValue(base);
    confirmProposal.mockResolvedValue({ id: "exp1" });
    const user = userEvent.setup();
    render(<CopilotPage />);
    await user.type(
      screen.getByLabelText("Research question"),
      "adaptive vs fixed",
    );
    await user.click(
      screen.getByRole("button", { name: /Propose an experiment/ }),
    );
    expect(await screen.findByText(/Rule-based proposal/)).toBeInTheDocument();
    expect(screen.getByText(/AI assistance unavailable/)).toBeInTheDocument();
    expect(screen.getByText("AI")).toBeInTheDocument(); // aggression came from the model
    expect(screen.getByText(/96 simulation runs/)).toBeInTheDocument();
    expect(screen.getByText(/Wall-clock time: unverified/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Confirm and run/ }));
    await waitFor(() => {
      expect(confirmProposal).toHaveBeenCalledWith(base);
    });
  });

  it("cannot confirm an invalid proposal and offers the corrected one", async () => {
    const invalid: ExperimentProposal = {
      ...base,
      validated: false,
      issues: [
        {
          code: "QUOTA_RUNS",
          message: "quota maxRunsPerExperiment: too many runs",
          suggestion: { "uncertainty.conditions": 8 },
        },
      ],
    };
    propose.mockResolvedValue(invalid);
    applySuggestion.mockResolvedValue({ ...base, id: "prop_2" });
    const user = userEvent.setup();
    render(<CopilotPage />);
    await user.type(screen.getByLabelText("Research question"), "too big");
    await user.click(
      screen.getByRole("button", { name: /Propose an experiment/ }),
    );
    const blocked = await screen.findByRole("button", {
      name: /Cannot run until the problems are fixed/,
    });
    expect(blocked).toBeDisabled();
    await user.click(
      screen.getByRole("button", { name: /Make a corrected proposal/ }),
    );
    expect(applySuggestion).toHaveBeenCalledWith("prop_1", "QUOTA_RUNS");
    expect(
      await screen.findByRole("button", { name: /Confirm and run/ }),
    ).toBeEnabled();
  });

  it("asks nothing of the server for an empty question and has no axe violations", async () => {
    const { container } = render(<CopilotPage />);
    expect(
      screen.getByRole("button", { name: /Propose an experiment/ }),
    ).toBeDisabled();
    expect(await axeViolations(container)).toEqual([]);
    expect(propose).not.toHaveBeenCalled();
  });
});
