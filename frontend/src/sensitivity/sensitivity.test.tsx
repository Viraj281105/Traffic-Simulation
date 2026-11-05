import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ API_BASE_URL: "" }));
vi.mock("../auth/cognito", () => ({ getAuthToken: () => Promise.resolve("") }));

import { stubApi } from "../insights/testApi";
import { SensitivityChart } from "./SensitivityChart";
import { sensitivityFixture } from "./fixtures";
import { rankInputs } from "./rank";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("rankInputs", () => {
  it("puts the most influential input first without changing the input", () => {
    const original = [...sensitivityFixture.inputs];
    const ranked = rankInputs(sensitivityFixture.inputs);
    expect(ranked.map((i) => i.id)).toEqual([
      "demand_scale",
      "arrival_rate",
      "heavy_share",
    ]);
    expect(sensitivityFixture.inputs).toEqual(original);
  });
});

describe("SensitivityChart", () => {
  it("shows the ranking, the headline input and the method with its seed", async () => {
    stubApi({
      "GET /api/v3/experiments/exp1/sensitivity": sensitivityFixture,
    });
    render(<SensitivityChart experimentId="exp1" />);
    expect(await screen.findByText(/changes average delay/)).toHaveTextContent(
      "Demand scale changes average delay the most",
    );
    const rows = within(screen.getByRole("table")).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("Demand scale");
    expect(rows[1]).toHaveTextContent("61%");
    expect(rows[1]).toHaveTextContent("68%");
    expect(
      screen.getByText(/Sobol indices, 2,048 samples, seed 42/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /most influential first/ }),
    ).toBeInTheDocument();
  });

  it("shows an empty state when there is no analysis", async () => {
    stubApi({});
    render(<SensitivityChart experimentId="none" />);
    expect(await screen.findByText("No sensitivity yet")).toBeInTheDocument();
  });
});
