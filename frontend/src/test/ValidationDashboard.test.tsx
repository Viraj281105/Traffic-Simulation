/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ValidationDashboard } from "../components/ValidationDashboard";

// ── Mock config ────────────────────────────────────────────────────────────

vi.mock("../config", () => ({ API_BASE_URL: "http://localhost:8000" }));

// ── Helpers ────────────────────────────────────────────────────────────────

const makeStat = (mean: number) => ({
  mean,
  std: 1.2,
  min: mean - 2,
  max: mean + 2,
  ci95: 0.8,
});

const MOCK_VALIDATION = {
  numSeeds: 5,
  seeds: [1001, 1002, 1003, 1004, 1005],
  duration: 30,
  signal: {
    delay: makeStat(12),
    throughput: makeStat(80),
    queue: makeStat(4),
  },
  roundabout: {
    delay: makeStat(8),
    throughput: makeStat(90),
    queue: makeStat(2),
  },
  comparison: {
    delay: { pValue: 0.012, cohensD: 1.4, significant: true },
    throughput: { pValue: 0.045, cohensD: 0.9, significant: true },
    queue: { pValue: 0.08, cohensD: 0.6, significant: false },
  },
  seedRuns: [
    {
      seed: 1001,
      signal: { delay: 11, throughput: 79, queue: 3.8 },
      roundabout: { delay: 7, throughput: 91, queue: 1.9 },
    },
    {
      seed: 1002,
      signal: { delay: 13, throughput: 81, queue: 4.2 },
      roundabout: { delay: 9, throughput: 89, queue: 2.1 },
    },
  ],
  individualRuns: [],
};

// ── Tests ──────────────────────────────────────────────────────────────────

describe("ValidationDashboard", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("renders trigger panel with heading and button", () => {
    render(<ValidationDashboard />);
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /Statistical validation/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByTitle("Run the study with the current settings"),
    ).toBeInTheDocument();
  });

  it("shows loading state after clicking Run Validation", async () => {
    vi.mocked(fetch).mockImplementationOnce(() => new Promise(() => undefined));

    render(<ValidationDashboard />);
    fireEvent.click(
      screen.getByTitle("Run the study with the current settings"),
    );

    await waitFor(() =>
      expect(
        screen.getByText(/Running 5 traffic patterns on both controls/i),
      ).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: /Running/i })).toBeDisabled();
  });

  it("renders verdict and metric stats after successful validation", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_VALIDATION), { status: 200 }),
    );

    const { container } = render(<ValidationDashboard />);
    fireEvent.click(
      screen.getByTitle("Run the study with the current settings"),
    );

    // Wait for verdict card to appear
    await waitFor(
      () => {
        const verdictCard = container.querySelector(".verdict-card");
        expect(verdictCard).not.toBeNull();
      },
      { timeout: 5000 },
    );

    // Metric labels should appear in stat card headings (multiple matches OK)
    await waitFor(() => {
      const h4s = container.querySelectorAll(".stat-card h4");
      expect(h4s.length).toBeGreaterThanOrEqual(3);
    });
  });

  it("renders per-seed raw results table", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_VALIDATION), { status: 200 }),
    );

    render(<ValidationDashboard />);
    fireEvent.click(
      screen.getByTitle("Run the study with the current settings"),
    );

    // Switch to table tab
    await waitFor(() =>
      expect(screen.getByText(/Per-pattern table/i)).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByText(/Per-pattern table/i));

    await waitFor(() =>
      expect(screen.getByText(/Per-pattern results/i)).toBeInTheDocument(),
    );
    // Seed values in the table
    expect(screen.getByText(/1001/)).toBeInTheDocument();
    expect(screen.getByText(/1002/)).toBeInTheDocument();
  });

  it("displays an error message on failed API call", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response("fail", { status: 503, statusText: "Service Unavailable" }),
    );

    render(<ValidationDashboard />);
    fireEvent.click(
      screen.getByTitle("Run the study with the current settings"),
    );

    await waitFor(() =>
      expect(screen.getByText(/HTTP 503/i)).toBeInTheDocument(),
    );
  });

  it("shows significance tags per metric", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_VALIDATION), { status: 200 }),
    );

    render(<ValidationDashboard />);
    fireEvent.click(
      screen.getByTitle("Run the study with the current settings"),
    );

    await waitFor(() => {
      // Two 'Significant' tags for delay+throughput, one 'Not Significant' for queue
      const sigTags = screen.getAllByText(/Significant|Sig/i);
      expect(sigTags.length).toBeGreaterThanOrEqual(3);
    });
  });

  it("shows Cohen's d values in metric cards", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_VALIDATION), { status: 200 }),
    );

    render(<ValidationDashboard />);
    fireEvent.click(
      screen.getByTitle("Run the study with the current settings"),
    );

    await waitFor(() => {
      expect(screen.getByText("1.400")).toBeInTheDocument();
    });
  });

  const runOnce = async (payload: unknown) => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(payload), { status: 200 }),
    );
    render(<ValidationDashboard />);
    fireEvent.click(
      screen.getByTitle("Run the study with the current settings"),
    );
    await screen.findByText(/Result for each traffic pattern/i);
  };

  it("sends the chosen confidence level and shows the level the backend used", async () => {
    await runOnce({
      ...MOCK_VALIDATION,
      confidenceLevel: 0.99,
      alpha: 0.01,
      comparison: {
        delay: { pValue: 0.008, cohensD: 1.4, significant: true },
        throughput: { pValue: 0.2, cohensD: 0.9, significant: false },
        queue: { pValue: 0.3, cohensD: 0.6, significant: false },
      },
    });
    const body = JSON.parse(
      vi.mocked(fetch).mock.calls[0][1]?.body as string,
    ) as { confidenceLevel: number };
    expect(body.confidenceLevel).toBe(0.95);
    // The header reads the backend's alpha, not a hard-coded 0.05 / 95 %.
    expect(
      screen.getByText(/statistically supported on some metrics at α = 0\.01/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/99% Student-t/i)).toBeInTheDocument();
    expect(screen.queryByText(/supported .* at α = 0\.05/i)).toBeNull();
  });

  it("draws the interval the backend computed (Student-t), not a local z multiple", async () => {
    await runOnce({
      ...MOCK_VALIDATION,
      confidenceLevel: 0.95,
      alpha: 0.05,
      signal: {
        ...MOCK_VALIDATION.signal,
        delay: { ...makeStat(12), std: 1.2, ci: 2.71, ci95: 2.71 },
      },
    });
    // 2.71 comes from the backend; a local 1.96 * 1.2 / sqrt(5) would be 1.05.
    expect(screen.getAllByText(/±2\.71/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/±1\.05/)).toBeNull();
  });

  it("does not say that non-significance means the controls are equal", async () => {
    await runOnce({
      ...MOCK_VALIDATION,
      alpha: 0.05,
      comparison: {
        delay: { pValue: 0.4, cohensD: 0.3, significant: false },
        throughput: { pValue: 0.5, cohensD: 0.2, significant: false },
        queue: { pValue: 0.6, cohensD: 0.1, significant: false },
      },
    });
    expect(
      screen.getByText(/No statistically supported difference/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /cannot distinguish the controls, not that they are equal/i,
      ),
    ).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/Confirmed|Proofs|parity/i);
  });

  it("labels a multi-lane run exploratory and reports demand cut-off", async () => {
    await runOnce({
      ...MOCK_VALIDATION,
      calibration: {
        calibrated: false,
        note: "Exploratory, not calibrated: more than one lane.",
      },
      vehicleLimitReachedSeeds: [1001, 1002],
    });
    expect(
      screen.getByText(/Exploratory, not calibrated\./),
    ).toBeInTheDocument();
    expect(screen.getByText(/Demand was cut off\./)).toBeInTheDocument();
  });

  it("describes the method as Student-t, not 1.96", async () => {
    await runOnce(MOCK_VALIDATION);
    fireEvent.click(screen.getByText(/How it was tested/i));
    expect(screen.getByText(/t\(N−1\)/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/1\.96 ×/);
  });
});
