import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ API_BASE_URL: "" }));
vi.mock("../auth/cognito", () => ({ getAuthToken: () => Promise.resolve("") }));

import { stubApi } from "../insights/testApi";
import { reportFixture } from "./fixtures";
import { ReportDocumentView, ReportView } from "./ReportView";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ReportDocumentView", () => {
  it("puts assumptions and limitations before any result", () => {
    render(<ReportDocumentView report={reportFixture} />);
    const headings = screen
      .getAllByRole("heading", { level: 2 })
      .map((h) => h.textContent);
    expect(headings[0]).toBe("Assumptions and limitations");
    expect(headings.indexOf("Summary")).toBeLessThan(
      headings.indexOf("Which option is better"),
    );
    expect(headings[headings.length - 1]).toBe("How to reproduce this");
  });

  it("includes the charts with intervals and the measures", () => {
    render(<ReportDocumentView report={reportFixture} />);
    expect(
      screen.getByRole("img", { name: /Gap in average delay/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /most influential first/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Model estimate, not a measurement"),
    ).toBeInTheDocument();
  });

  it("says whether the summary's numbers were checked", () => {
    const { rerender } = render(<ReportDocumentView report={reportFixture} />);
    expect(screen.getByText("Numbers checked")).toBeInTheDocument();
    rerender(
      <ReportDocumentView
        report={{
          ...reportFixture,
          summary: { ...reportFixture.summary, grounded: false },
        }}
      />,
    );
    expect(screen.getByText("Numbers not checked")).toBeInTheDocument();
  });

  it("leaves out sections the server did not compute and marks missing manifest entries", () => {
    render(
      <ReportDocumentView
        report={{
          ...reportFixture,
          comparison: null,
          sensitivity: null,
          metrics: null,
        }}
      />,
    );
    expect(
      screen.queryByText("Which option is better"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Not available")).toBeInTheDocument();
  });

  it("opens the print dialog from the button", async () => {
    const onPrint = vi.fn();
    render(<ReportDocumentView report={reportFixture} onPrint={onPrint} />);
    await userEvent.click(
      screen.getByRole("button", { name: /Print or save as PDF/ }),
    );
    expect(onPrint).toHaveBeenCalledTimes(1);
  });
});

describe("ReportView", () => {
  it("loads the report from the contract URL", async () => {
    const { calls } = stubApi({
      "GET /api/v3/experiments/exp1/report": reportFixture,
    });
    render(<ReportView experimentId="exp1" />);
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: reportFixture.title,
      }),
    ).toBeInTheDocument();
    expect(calls[0]?.key).toBe("GET /api/v3/experiments/exp1/report");
  });
});
