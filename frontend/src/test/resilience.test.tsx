import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ API_BASE_URL: "" }));
vi.mock("../auth/cognito", () => ({ getAuthToken: () => Promise.resolve("") }));

import {
  incidentCatalogueFixture,
  resilienceFixture,
  simulateFixture,
} from "../incidents/fixtures";
import { dryRunFixture, queueStatsFixture } from "../jobs/fixtures";
import {
  emergencyFixture,
  priorityCatalogueFixture,
  transitFixture,
} from "../priority/fixtures";
import { TABS } from "../respage/tabs";
import { ResiliencePage } from "../respage/ResiliencePage";
import { resolveRoute } from "../routing";
import { meFixture, usageFixture } from "../tenancy/fixtures";
import { v2xFixture } from "../v2x/fixtures";
import { axeViolations } from "./axe";
import { failWith, stubNet } from "./netApi";

const CAT = "GET /api/v2/incidents/catalogue";

beforeEach(() => {
  window.history.replaceState(null, "", "/app/resilience");
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe("/app/resilience", () => {
  it("is a routed view with five tabs, Incidents first", () => {
    expect(resolveRoute("/app/resilience")).toEqual({
      kind: "view",
      view: "resilience",
    });
    stubNet({ [CAT]: incidentCatalogueFixture });
    render(<ResiliencePage />);
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
      "Incidents",
      "Resilience",
      "Priority",
      "Cooperation",
      "Account",
    ]);
    expect(TABS).toHaveLength(5);
    expect(screen.getByRole("tab", { name: "Incidents" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("keeps the tab in the address", async () => {
    stubNet({
      [CAT]: incidentCatalogueFixture,
    });
    render(<ResiliencePage />);
    await userEvent.click(screen.getByRole("tab", { name: "Resilience" }));
    expect(window.location.search).toBe("?tab=resilience");
    expect(
      await screen.findByRole("button", { name: "Compare strategies" }),
    ).toBeInTheDocument();
  });

  it("has no accessibility violations on the incidents tab", async () => {
    stubNet({ [CAT]: incidentCatalogueFixture });
    const { container } = render(<ResiliencePage />);
    await screen.findByRole("button", { name: "Simulate the disruption" });
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("Incidents tab", () => {
  it("fills the form from a preset and posts the scenario", async () => {
    const { calls } = stubNet({
      [CAT]: incidentCatalogueFixture,
      "POST /api/v2/incidents/simulate": simulateFixture,
    });
    render(<ResiliencePage />);
    const picker = await screen.findByLabelText("Scenario preset");
    expect(
      within(picker)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual([
      "Crash on the corridor arterial",
      "Heavy rain on a 3x3 grid",
      "Event-day surge towards the east gate",
    ]);
    expect(screen.getByLabelText("Incident 1 links")).toHaveValue("J1>J2");
    await userEvent.selectOptions(picker, "grid-heavy-rain");
    expect(screen.getByLabelText("Weather 1 kind")).toHaveValue("rain");
    await userEvent.selectOptions(picker, "corridor-crash");
    await userEvent.click(
      screen.getByRole("button", { name: "Simulate the disruption" }),
    );
    expect(
      await screen.findByRole("img", {
        name: /Mean accrued delay of the vehicles in the network over time/,
      }),
    ).toBeInTheDocument();
    const body = calls.find((c) => c.key.includes("/simulate"))?.body as {
      preset: string;
      compareBaseline: boolean;
      scenario: { incidents: { links: string[]; type: string }[] };
    };
    expect(body.preset).toBe("corridor-crash");
    expect(body.compareBaseline).toBe(true);
    expect(body.scenario.incidents[0]).toMatchObject({
      type: "crash",
      links: ["J1>J2"],
    });
    expect(screen.getByText(/Recovery time: 1 min 0 s/)).toBeInTheDocument();
    expect(
      screen.getByText(/Resilience score: 0.7 out of 1/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Without it \(baseline\)/)).toBeInTheDocument();
  });

  it("says so when recovery could not be measured", async () => {
    stubNet({
      [CAT]: incidentCatalogueFixture,
      "POST /api/v2/incidents/simulate": { ...simulateFixture, metrics: null },
    });
    render(<ResiliencePage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Simulate the disruption" }),
    );
    expect(
      await screen.findByText(/Recovery could not be measured/),
    ).toBeInTheDocument();
  });

  it("shows the server's reason when a request is refused", async () => {
    stubNet({
      [CAT]: incidentCatalogueFixture,
      "POST /api/v2/incidents/simulate": failWith(422, "unknown preset"),
    });
    render(<ResiliencePage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Simulate the disruption" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "unknown preset",
    );
  });

  it("edits and removes incidents", async () => {
    stubNet({ [CAT]: incidentCatalogueFixture });
    render(<ResiliencePage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Remove incident 1" }),
    );
    expect(screen.getByRole("status")).toHaveTextContent("no disruption yet");
    await userEvent.click(screen.getByRole("button", { name: "Add weather" }));
    expect(screen.getByLabelText("Weather 1 kind")).toBeInTheDocument();
  });
});

describe("Resilience tab", () => {
  it("compares strategies with intervals, the formula and the in-model statement", async () => {
    window.history.replaceState(null, "", "/app/resilience?tab=resilience");
    const { calls } = stubNet({
      [CAT]: incidentCatalogueFixture,
      "POST /api/v2/incidents/resilience": resilienceFixture,
    });
    render(<ResiliencePage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Compare strategies" }),
    );
    expect(
      await screen.findByText(/Best under this scenario: Max-pressure signals/),
    ).toBeInTheDocument();
    const body = calls.find((c) => c.key.includes("/resilience"))?.body as {
      strategies: string[];
      seeds: number[];
    };
    expect(body.strategies).toEqual(["fixed_time", "max_pressure"]);
    expect(body.seeds).toEqual([1, 2, 3]);
    const table = screen.getByRole("table");
    expect(within(table).getByText("0.55 to 0.69")).toBeInTheDocument();
    expect(within(table).getByText("2 of 3")).toBeInTheDocument();
    expect(
      screen.getByText(/Score = 0.35 x recovery \+ 0.25 x throughput/),
    ).toBeInTheDocument();
    expect(screen.getByText(/In-model only\./)).toBeInTheDocument();
    expect(
      screen.getByRole("img", {
        name: /Resilience score of each signal strategy/,
      }),
    ).toBeInTheDocument();
  });
});

describe("Priority tab", () => {
  it("shows the emergency comparison, collateral delay and safety badges", async () => {
    window.history.replaceState(null, "", "/app/resilience?tab=priority");
    const { calls } = stubNet({
      "GET /api/v2/priority/catalogue": priorityCatalogueFixture,
      "POST /api/v2/priority/emergency-comparison": emergencyFixture,
      "POST /api/v2/priority/transit-comparison": transitFixture,
    });
    render(<ResiliencePage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Compare emergency response" }),
    );
    expect(
      await screen.findByRole("img", {
        name: /Emergency vehicle travel time for each seed/,
      }),
    ).toBeInTheDocument();
    const body = calls.find((c) => c.key.includes("emergency"))?.body as {
      emergencyVehicles: { kind: string }[];
      numSeeds: number;
    };
    expect(body.emergencyVehicles[0].kind).toBe("ambulance");
    expect(body.numSeeds).toBe(4);
    expect(screen.getAllByText(/A beats B/).length).toBeGreaterThan(0);
    expect(
      screen.getByText(/No reliable difference between A and B/),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Signal audit passed")).toHaveLength(2);
    expect(screen.getAllByText("No collisions")).toHaveLength(2);
    expect(
      screen.getAllByText(/In-model only: results describe/).length,
    ).toBeGreaterThan(0);
  });

  it("shows the transit comparison with a failed audit and a dropped seed", async () => {
    window.history.replaceState(null, "", "/app/resilience?tab=priority");
    stubNet({
      "GET /api/v2/priority/catalogue": priorityCatalogueFixture,
      "POST /api/v2/priority/transit-comparison": transitFixture,
    });
    render(<ResiliencePage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Compare transit priority" }),
    );
    expect(
      await screen.findByRole("img", { name: /Person delay for each seed/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /Bus lateness for each seed/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("Signal audit failed")).toBeInTheDocument();
    expect(screen.getByText(/seed 5 \(no bus reached/)).toBeInTheDocument();
  });
});

describe("Cooperation tab", () => {
  it("shows the sweep, delivery, heatmap and assumptions", async () => {
    window.history.replaceState(null, "", "/app/resilience?tab=cooperation");
    const { calls } = stubNet({
      "POST /api/v2/v2x/experiment": v2xFixture,
    });
    const { container } = render(<ResiliencePage />);
    await userEvent.click(
      screen.getByRole("button", { name: "Run the experiment" }),
    );
    expect(
      await screen.findByRole("img", {
        name: /Change in delay, stops, fuel and CO2/,
      }),
    ).toBeInTheDocument();
    const body = calls[0].body as {
      seeds: number[];
      sensitivity: { latenciesMs: number[] };
    };
    expect(body.seeds).toEqual([1, 2, 3, 4, 5]);
    expect(body.sensitivity.latenciesMs).toHaveLength(5);
    expect(screen.getByText("-4 s (-4.5 to -3.5)")).toBeInTheDocument();
    expect(screen.getByText("No messages")).toBeInTheDocument();
    expect(container.querySelectorAll("[data-cell]")).toHaveLength(9);
    expect(
      screen.getByText(/Fuel and CO2 are relative proxies/),
    ).toBeInTheDocument();
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("Account tab", () => {
  const PATHS = {
    me: "GET /api/v2/tenancy/me",
    usage: "GET /api/v2/tenancy/usage",
    stats: "GET /api/v2/jobs/queue-stats",
    dry: "POST /api/v2/jobs/enqueue-dry-run",
  };

  beforeEach(() => {
    window.history.replaceState(null, "", "/app/resilience?tab=account");
  });

  it("shows identity, permissions, quota bars, usage, queue and a dry run", async () => {
    const { calls } = stubNet({
      [PATHS.me]: meFixture,
      [PATHS.usage]: usageFixture,
      [PATHS.stats]: queueStatsFixture,
      [PATHS.dry]: dryRunFixture,
    });
    const { container } = render(<ResiliencePage />);
    expect(await screen.findByText("Tenant: acme")).toBeInTheDocument();
    expect(screen.getByText("Role: analyst")).toBeInTheDocument();
    expect(screen.getByText("usage:read")).toBeInTheDocument();
    const bar = screen.getByRole("progressbar", { name: "Runs today" });
    expect(bar).toHaveAttribute("aria-valuenow", "24");
    expect(await screen.findByText("Whole tenant")).toBeInTheDocument();
    expect(await screen.findByText("Waiting")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Tenant"), "acme");
    await userEvent.type(screen.getByLabelText("Cost tag: env"), "staging");
    await userEvent.type(screen.getByLabelText("Cost tag: owner"), "team");
    await userEvent.click(
      screen.getByRole("button", { name: "Check the job" }),
    );
    expect(await screen.findByText(/Nothing was enqueued/)).toBeInTheDocument();
    const body = calls.find((c) => c.key.includes("dry-run"))?.body as {
      tenant: string;
      costTags: Record<string, string>;
      run: { numSeeds: number };
    };
    expect(body.tenant).toBe("acme");
    expect(body.costTags).toEqual({
      project: "urbanflow",
      env: "staging",
      owner: "team",
    });
    expect(body.run.numSeeds).toBe(5);
    expect(await axeViolations(container)).toEqual([]);
  });

  it("explains the OIDC requirement on 403 and 503", async () => {
    stubNet({
      [PATHS.me]: failWith(403, "No valid tenant on this token"),
      [PATHS.stats]: failWith(503, "queue unavailable: down"),
    });
    render(<ResiliencePage />);
    const alerts = await screen.findAllByRole("alert");
    expect(alerts[0]).toHaveTextContent(/OIDC identity provider/);
    expect(alerts[0]).toHaveTextContent(/tenant claim/);
    expect(
      await screen.findByText("The queue is unavailable right now."),
    ).toBeInTheDocument();
  });

  it("says when the role lacks usage permission", async () => {
    stubNet({
      [PATHS.me]: meFixture,
      [PATHS.usage]: failWith(403, "Permission denied"),
      [PATHS.stats]: queueStatsFixture,
    });
    render(<ResiliencePage />);
    expect(
      await screen.findByText(/does not include the usage:read permission/),
    ).toBeInTheDocument();
  });

  it("shows a dry-run validation failure", async () => {
    stubNet({
      [PATHS.me]: meFixture,
      [PATHS.usage]: usageFixture,
      [PATHS.stats]: queueStatsFixture,
      [PATHS.dry]: failWith(422, "missing mandatory tag(s): env, owner"),
    });
    render(<ResiliencePage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Check the job" }),
    );
    expect(
      await screen.findByText(/missing mandatory tag/),
    ).toBeInTheDocument();
  });
});
