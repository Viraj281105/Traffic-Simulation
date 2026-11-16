import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ API_BASE_URL: "" }));
vi.mock("../auth/cognito", () => ({ getAuthToken: () => Promise.resolve("") }));

import { aimFixture } from "../aim/fixtures";
import { TABS } from "../coopage/tabs";
import { CooperationPage } from "../coopage/CooperationPage";
import { estimateFixture, runCostFixture } from "../costing/fixtures";
import {
  approvedFixture,
  auditFixture,
  listFixture,
  verifyOkFixture,
} from "../governance/fixtures";
import { platoonFixture } from "../platoon/fixtures";
import { resolveRoute } from "../routing";
import { failWith, stubNet } from "./netApi";

const PLATOON = "POST /api/v2/platoon/experiment";
const AIM = "POST /api/v2/aim/comparison";
const RECS = "/api/v2/governance/recommendations";
const AUDIT = "GET /api/v2/governance/audit";

function open(tab: string) {
  window.history.replaceState(null, "", `/app/cooperation?tab=${tab}`);
  render(<CooperationPage />);
}

beforeEach(() => {
  window.history.replaceState(null, "", "/app/cooperation");
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe("/app/cooperation", () => {
  it("is a routed view with four tabs, Platoons first", () => {
    expect(resolveRoute("/app/cooperation")).toEqual({
      kind: "view",
      view: "cooperation",
    });
    stubNet({});
    render(<CooperationPage />);
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
      "Platoons",
      "Signal-free",
      "Governance",
      "Cost",
    ]);
    expect(TABS).toHaveLength(4);
    expect(screen.getByRole("tab", { name: "Platoons" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("keeps the tab in the address", async () => {
    stubNet({ [`GET ${RECS}`]: { items: [] }, [AUDIT]: auditFixture });
    render(<CooperationPage />);
    await userEvent.click(screen.getByRole("tab", { name: "Governance" }));
    expect(window.location.search).toBe("?tab=governance");
    expect(
      await screen.findByRole("button", { name: "Create recommendation" }),
    ).toBeInTheDocument();
  });
});

describe("Platoons tab", () => {
  it("runs the experiment and shows the paired result, safety and caveat", async () => {
    const { calls } = stubNet({ [PLATOON]: platoonFixture });
    open("platoons");
    await userEvent.click(
      screen.getByRole("button", { name: "Run the platoon experiment" }),
    );
    expect(await screen.findByText("Safety: no collisions")).toBeVisible();
    expect(calls[0].body).toMatchObject({
      vehicles: 10,
      seeds: [1, 2, 3, 4, 5],
      channelSweep: { latenciesMs: [0, 200, 500] },
    });
    expect(
      screen.getByText(/in-model estimates, not measurements/),
    ).toBeVisible();
    expect(screen.getByText(/A beats B: 600/)).toBeVisible();
    expect(screen.getByText("Stable")).toBeVisible();
    const sweep = screen.getByRole("table", { name: /radio link/ });
    expect(within(sweep).getAllByRole("row")).toHaveLength(3);
    expect(screen.getAllByText("-9.5%").length).toBeGreaterThan(0);
  });

  it("shows the server's reason when the run is refused", async () => {
    stubNet({ [PLATOON]: failWith(422, "request too large") });
    open("platoons");
    await userEvent.click(
      screen.getByRole("button", { name: "Run the platoon experiment" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "request too large",
    );
  });
});

describe("Signal-free tab", () => {
  it("runs the comparison and shows the gate, warning and stress table", async () => {
    const { calls } = stubNet({ [AIM]: aimFixture });
    open("signal-free");
    await userEvent.click(
      screen.getByRole("button", { name: "Run the comparison" }),
    );
    expect(await screen.findByText("G-AIM safety: passed")).toBeVisible();
    expect(calls[0].body).toMatchObject({
      demandsVehPerHourPerApproach: [150, 300, 450, 600],
      messageLoss: { lossProbabilities: [0, 0.25, 0.5, 0.8, 0.95] },
    });
    expect(screen.getByText(/In-model best case/)).toBeVisible();
    expect(
      screen.getByRole("img", { name: /Mean delay against demand/ }),
    ).toBeInTheDocument();
    const stress = screen.getByRole("table", { name: /Message-loss stress/ });
    expect(within(stress).getAllByRole("row")).toHaveLength(3);
    expect(within(stress).getByText("95%")).toBeVisible();
  });

  it("shows a failed safety gate and request errors", async () => {
    const failed = {
      ...aimFixture,
      gateGAim: { ...aimFixture.gateGAim, passed: false },
    };
    stubNet({ [AIM]: failed });
    open("signal-free");
    await userEvent.click(
      screen.getByRole("button", { name: "Run the comparison" }),
    );
    expect(await screen.findByText("G-AIM safety: failed")).toBeVisible();
    vi.unstubAllGlobals();
    stubNet({ [AIM]: failWith(422, "seeds must be distinct") });
    await userEvent.click(
      screen.getByRole("button", { name: "Run the comparison" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "seeds must be distinct",
    );
  });
});

describe("Governance tab", () => {
  it("lists, transitions as an approver and verifies the audit log", async () => {
    const { calls } = stubNet({
      [`GET ${RECS}`]: listFixture,
      [AUDIT]: auditFixture,
      [`POST ${RECS}/rec-1/transition`]: approvedFixture,
      "GET /api/v2/governance/audit/verify": verifyOkFixture,
    });
    open("governance");
    expect(await screen.findByText("junction-a/peak")).toBeVisible();
    expect(screen.getByText(/never change a live system/)).toBeVisible();
    await userEvent.clear(screen.getByLabelText("Acting as"));
    await userEvent.type(screen.getByLabelText("Acting as"), "reviewer");
    await userEvent.click(screen.getByLabelText(/acting as an approver/));
    await userEvent.click(
      screen.getByRole("button", { name: "Approve rec-1" }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "rec-1 is now approved.",
    );
    const post = calls.find((c) => c.key.startsWith("POST"));
    expect(post?.body).toEqual({
      actor: "reviewer",
      roles: ["approver"],
      to: "approved",
      comment: null,
    });
    await userEvent.click(
      screen.getByRole("button", { name: "Verify the audit log" }),
    );
    expect(await screen.findByText("Chain intact")).toBeVisible();
  });

  it("creates a recommendation and reports a refusal", async () => {
    const { calls } = stubNet({
      [`GET ${RECS}`]: { items: [] },
      [AUDIT]: { total: 0, head: "0", entries: [] },
      [`POST ${RECS}`]: failWith(409, "recommendation already exists"),
    });
    open("governance");
    await screen.findByText("No recommendations yet.");
    await userEvent.type(screen.getByLabelText("Scenario reference"), "j/1");
    await userEvent.click(
      screen.getByRole("button", { name: "Create recommendation" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "recommendation already exists",
    );
    expect(calls.find((c) => c.key.startsWith("POST"))?.body).toMatchObject({
      actor: "analyst",
      scenarioRef: "j/1",
      proposedChange: { greenSeconds: 30 },
    });
  });

  it("shows a load error", async () => {
    stubNet({
      [`GET ${RECS}`]: failWith(500, "store down"),
      [AUDIT]: auditFixture,
    });
    open("governance");
    expect(await screen.findByText("store down")).toBeVisible();
  });
});

describe("Cost tab", () => {
  it("estimates a cost labelled as not a bill", async () => {
    const { calls } = stubNet({
      "POST /api/v2/costing/estimate": estimateFixture,
    });
    open("cost");
    expect(screen.getByText(/Estimate, not a bill/)).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: "Estimate the cost" }),
    );
    expect(await screen.findByText(/estimate, not a bill\)/)).toBeVisible();
    expect(calls[0].body).toMatchObject({ computeSeconds: 600, spot: false });
  });

  it("looks up a run and reports an unknown run", async () => {
    stubNet({ "GET /api/v2/costing/runs/run_1": runCostFixture });
    open("cost");
    await userEvent.type(screen.getByLabelText("Run id"), "run_1");
    await userEvent.click(
      screen.getByRole("button", { name: "Look up the run cost" }),
    );
    expect(await screen.findByText(/for acme on 2026-11-01/)).toBeVisible();
    await userEvent.clear(screen.getByLabelText("Run id"));
    await userEvent.type(screen.getByLabelText("Run id"), "nope");
    await userEvent.click(
      screen.getByRole("button", { name: "Look up the run cost" }),
    );
    expect(await screen.findByRole("alert")).toBeVisible();
  });
});
