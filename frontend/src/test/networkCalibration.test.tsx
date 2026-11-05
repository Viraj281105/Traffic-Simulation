import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ API_BASE_URL: "" }));
vi.mock("../auth/cognito", () => ({ getAuthToken: () => Promise.resolve("") }));

import { CalibrationReportView } from "../calibration/CalibrationReportView";
import { CalibrationTab } from "../calibration/CalibrationTab";
import {
  countsInvalidFixture,
  countsValidFixture,
  failingReportFixture,
  recalibratedFixture,
  reportFixture,
} from "../calibration/fixtures";
import { readInputs } from "../calibration/inputs";
import { gridFixture } from "../mapview/fixtures";
import { axeViolations } from "./axe";
import { stubNet } from "./netApi";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CalibrationReportView", () => {
  it("shows a G-CAL PASS badge with before and after error", () => {
    render(<CalibrationReportView report={reportFixture} />);
    expect(
      screen.getByRole("status", { name: "Gate G-CAL: PASS" }),
    ).toBeInTheDocument();
    const table = screen.getByRole("table", {
      name: /before and after calibration/,
    });
    const rmse = within(table)
      .getByText("Root mean square error")
      .closest("tr");
    expect(rmse).toHaveTextContent("142.3 veh/h");
    expect(rmse).toHaveTextContent("31.4 veh/h");
    expect(
      within(table).getByText("Links with GEH below 5").closest("tr"),
    ).toHaveTextContent("100% (4 of 4)");
  });

  it("shows FAIL with the reasons when the gate is not met", () => {
    render(<CalibrationReportView report={failingReportFixture} />);
    expect(
      screen.getByRole("status", { name: "Gate G-CAL: FAIL" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("list", { name: "Why the gate failed" }),
    ).toHaveTextContent("85% required");
  });

  it("lists every link's residual before and after", () => {
    render(<CalibrationReportView report={reportFixture} />);
    const row = screen.getByRole("rowheader", { name: "W>J1" }).closest("tr");
    expect(row).toHaveTextContent("720");
    expect(row).toHaveTextContent("-180");
    expect(row).toHaveTextContent("7.2 (miss)");
    expect(row).toHaveTextContent("-2.5%");
  });

  it("flags drifted parameters as a cue to recalibrate", () => {
    render(<CalibrationReportView report={recalibratedFixture} />);
    expect(
      screen.getByText(/Recalibrate: 1 parameter moved by more than 15%/),
    ).toBeInTheDocument();
    const row = screen
      .getAllByRole("rowheader", { name: "demand:N1->S2" })[1]
      .closest("tr");
    expect(row).toHaveTextContent("+22%");
    expect(row).toHaveTextContent("Drifted");
  });

  it("states provenance: counts source, fingerprints and network", () => {
    render(<CalibrationReportView report={reportFixture} />);
    const prov = screen.getByRole("list", { name: "Provenance" });
    expect(prov).toHaveTextContent("Counts: upload, 24 rows on 4 links");
    expect(prov).toHaveTextContent(reportFixture.manifest.hash);
    expect(prov).toHaveTextContent("Two-junction corridor");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <CalibrationReportView report={recalibratedFixture} />,
    );
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("readInputs", () => {
  it("explains what is wrong with each box", () => {
    expect(() => readInputs("nope", "[]", "x")).toThrow(
      "network is not valid JSON",
    );
    expect(() => readInputs("{}", "[]", "x")).toThrow("at least one flow");
    expect(() => readInputs("{}", '[{"origin":"a"}]', " ")).toThrow(
      "counts file",
    );
    expect(readInputs("{}", '[{"origin":"a"}]', "c").countsCsv).toBe("c");
  });
});

describe("CalibrationTab", () => {
  const fill = async () => {
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", { name: "Load example network" }),
    );
    await screen.findByText(/Example network loaded/);
    await user.click(screen.getByLabelText(/^Counts \(CSV/));
    await user.paste("link_id,interval_start,count\nJ1>J2,0,10");
    return user;
  };

  it("loads the example network, then calibrates with the contract body", async () => {
    const { calls } = stubNet({
      "GET /api/v2/network-metrics/grid?vehiclesPerHour=300&preset=3x3":
        gridFixture,
      "POST /api/v2/calibration/network-fit": reportFixture,
    });
    render(<CalibrationTab />);
    const user = await fill();
    await user.click(screen.getByRole("button", { name: "Calibrate" }));
    expect(
      await screen.findByRole("status", { name: "Gate G-CAL: PASS" }),
    ).toBeInTheDocument();
    const post = calls.find(
      (c) => c.key === "POST /api/v2/calibration/network-fit",
    );
    expect(post?.body).toMatchObject({
      countsCsv: "link_id,interval_start,count\nJ1>J2,0,10",
      flows: gridFixture.flows,
      options: { budget: 150 },
      sim: { duration: 600 },
    });
  });

  it("recalibrates warm-started from the shown report's fitted parameters", async () => {
    const { calls } = stubNet({
      "GET /api/v2/network-metrics/grid?vehiclesPerHour=300&preset=3x3":
        gridFixture,
      "POST /api/v2/calibration/network-fit": reportFixture,
      "POST /api/v2/calibration/network-fit/recalibrate": recalibratedFixture,
    });
    render(<CalibrationTab />);
    const user = await fill();
    await user.click(screen.getByRole("button", { name: "Calibrate" }));
    await screen.findByRole("status", { name: "Gate G-CAL: PASS" });
    await user.click(
      screen.getByRole("button", { name: "Recalibrate from this report" }),
    );
    expect(
      await screen.findByText(/Recalibration and drift/),
    ).toBeInTheDocument();
    const post = calls.find((c) => c.key.endsWith("/recalibrate"));
    expect(post?.body).toMatchObject({
      previous: reportFixture.parameters.fitted,
    });
  });

  it("checks the counts file and reports problems", async () => {
    stubNet({
      "GET /api/v2/network-metrics/grid?vehiclesPerHour=300&preset=3x3":
        gridFixture,
      "POST /api/v2/calibration/network-fit/validate-counts":
        countsInvalidFixture,
    });
    render(<CalibrationTab />);
    const user = await fill();
    await user.click(screen.getByRole("button", { name: "Check counts" }));
    expect(
      await screen.findByText("The counts file cannot be used yet."),
    ).toBeInTheDocument();
    expect(screen.getByText(/not in the network/)).toBeInTheDocument();
  });

  it("accepts a valid counts check", async () => {
    stubNet({
      "GET /api/v2/network-metrics/grid?vehiclesPerHour=300&preset=3x3":
        gridFixture,
      "POST /api/v2/calibration/network-fit/validate-counts":
        countsValidFixture,
    });
    render(<CalibrationTab />);
    const user = await fill();
    await user.click(screen.getByRole("button", { name: "Check counts" }));
    expect(
      await screen.findByText(/counts file is usable: 24 rows on 4 links/),
    ).toBeInTheDocument();
  });

  it("asks for inputs instead of calling the server when they are missing", async () => {
    const { calls } = stubNet({});
    render(<CalibrationTab />);
    await userEvent.click(screen.getByRole("button", { name: "Calibrate" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "network is not valid JSON",
    );
    expect(calls).toHaveLength(0);
  });
});
