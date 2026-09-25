/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { VolumeAnalysisDashboard } from "../components/VolumeAnalysisDashboard";

// ── Mock config ────────────────────────────────────────────────────────────

vi.mock("../config", () => ({ API_BASE_URL: "http://localhost:8000" }));

// ── Helpers ────────────────────────────────────────────────────────────────

const makeSweepRun = (rate: number, sigDelay: number, rndDelay: number) => ({
  arrivalRate: rate,
  hourlyVolumeVehPerHour: Math.round(rate * 3600 * 4),
  winner: rndDelay < sigDelay ? "roundabout" : "signal",
  delayDeltaPercent: ((rndDelay - sigDelay) / Math.max(sigDelay, 0.01)) * 100,
  signal: { delay: sigDelay, throughput: 100, queue: 2 },
  roundabout: { delay: rndDelay, throughput: 95, queue: 1.5 },
});

const MOCK_SESSION = {
  sessionId: "abc123",
  name: "Test Sweep",
  duration: 30,
  randomSeed: 42,
  curves: {
    rates: [0.1, 0.3, 0.5],
    volumesVehPerHour: [360, 1080, 1800],
    signal: {
      delays: [5, 8, 14],
      throughputs: [100, 95, 80],
      queues: [1, 3, 7],
    },
    roundabout: {
      delays: [3, 9, 15],
      throughputs: [105, 90, 75],
      queues: [0.5, 2.5, 8],
    },
    crossoverArrivalRate: 0.3,
    crossoverHourlyVolume: 1080,
  },
  runs: [
    makeSweepRun(0.1, 5, 3),
    makeSweepRun(0.3, 8, 9),
    makeSweepRun(0.5, 14, 15),
  ],
};

const MOCK_SWEEPS_LIST = [
  { id: "abc123", name: "Test Sweep", created_at: "2026-09-01T12:00:00Z" },
];

// ── Tests ──────────────────────────────────────────────────────────────────

describe("VolumeAnalysisDashboard", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("renders the trigger panel with Run Sweep button", async () => {
    // Return empty sweep list
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify([]), { status: 200 }),
    );

    render(<VolumeAnalysisDashboard />);
    await waitFor(() =>
      expect(
        screen.getByText(/Traffic Volume & Capacity Analysis/i),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: /Run Sweep/i }),
    ).toBeInTheDocument();
  });

  it("shows saved sweeps after loading", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_SWEEPS_LIST), { status: 200 }),
    );

    render(<VolumeAnalysisDashboard />);

    await waitFor(() =>
      expect(screen.getByText(/Saved Sweeps/i)).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: /Saved Sweeps/i }));
    expect(screen.getByText("Test Sweep")).toBeInTheDocument();
  });

  it("displays crossover badge when a sweep session is active", async () => {
    // First fetch: sweep list; second fetch (loadSweep): session data
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify(MOCK_SWEEPS_LIST), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(MOCK_SESSION), { status: 200 }),
      );

    render(<VolumeAnalysisDashboard />);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /Saved Sweeps/i }),
      ).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: /Saved Sweeps/i }));
    fireEvent.click(screen.getByText("Test Sweep"));

    await waitFor(() =>
      expect(
        screen.getByText(/Where the lower-delay control changes/i),
      ).toBeInTheDocument(),
    );
    expect(screen.getAllByText(/1,080/).length).toBeGreaterThanOrEqual(1);
  });

  it("shows error message on failed sweep run", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response("error", {
          status: 500,
          statusText: "Internal Server Error",
        }),
      );

    render(<VolumeAnalysisDashboard />);

    fireEvent.click(screen.getByRole("button", { name: /Run Sweep/i }));

    await waitFor(() =>
      expect(screen.getByText(/HTTP 500/i)).toBeInTheDocument(),
    );
  });

  it("disables Run Sweep button while running", async () => {
    // List loads fine, sweep call hangs
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockImplementationOnce(() => new Promise(() => undefined)); // never resolves

    render(<VolumeAnalysisDashboard />);

    const btn = screen.getByRole("button", { name: /Run Sweep/i });
    fireEvent.click(btn);

    await waitFor(() => expect(btn).toBeDisabled());
  });

  it("renders summary table rows for each run", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify(MOCK_SWEEPS_LIST), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(MOCK_SESSION), { status: 200 }),
      );

    render(<VolumeAnalysisDashboard />);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /Saved Sweeps/i }),
      ).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: /Saved Sweeps/i }));
    fireEvent.click(screen.getByText("Test Sweep"));

    await waitFor(() => {
      expect(
        screen.getByText(/Head-to-Head Volume Matrix/i),
      ).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/Head-to-Head Volume Matrix/i));

    // The 3 run rows (one per arrival rate)
    await waitFor(() => {
      const rows = screen.getAllByText(/Roundabout|Signal|Tie/);
      expect(rows.length).toBeGreaterThanOrEqual(3);
    });
  });

  it("loads a saved sweep with nested results format without crashing", async () => {
    const nestedPayload = {
      id: "nested-1",
      name: "Nested Results Sweep",
      config: {},
      created_at: "2026-09-01T12:00:00Z",
      results: {
        sessionId: "nested-1",
        name: "Nested Results Sweep",
        curves: MOCK_SESSION.curves,
        runs: [
          ...MOCK_SESSION.runs,
          {
            arrivalRate: 0.2,
            hourlyVolumeVehPerHour: 720,
            winner: "tie" as const,
            delayDeltaPercent: 0.0,
            signal: {
              delay: 6.0,
              delayStdDev: 0.5,
              delayMin: 5.2,
              delayMax: 6.8,
              throughput: 50,
              queue: 1,
              queueMax: 2,
            },
            roundabout: {
              delay: 6.1,
              delayStdDev: 0.4,
              delayMin: 5.5,
              delayMax: 6.9,
              throughput: 50,
              queue: 1,
              queueMax: 2,
            },
          },
        ],
      },
    };

    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "nested-1",
              name: "Nested Results Sweep",
              created_at: "2026-09-01T12:00:00Z",
            },
          ]),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(nestedPayload), { status: 200 }),
      );

    render(<VolumeAnalysisDashboard />);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /Saved Sweeps/i }),
      ).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: /Saved Sweeps/i }));
    fireEvent.click(screen.getByText("Nested Results Sweep"));

    await waitFor(() =>
      expect(screen.getByText(/Capacity Studio/i)).toBeInTheDocument(),
    );

    // Toggle uncertainty envelopes and delta trend
    const envelopeBtn = screen.getByRole("button", {
      name: /± Driver spread/i,
    });
    expect(envelopeBtn).toBeInTheDocument();
    fireEvent.click(envelopeBtn);

    const deltaTrendBtn = screen.getByRole("button", {
      name: /% Delta Trend/i,
    });
    expect(deltaTrendBtn).toBeInTheDocument();
    fireEvent.click(deltaTrendBtn);

    // Switch to Matrix tab and check Parity filter
    fireEvent.click(screen.getByText(/Head-to-Head Volume Matrix/i));
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /⚖️ About the same/i }),
      ).toBeInTheDocument();
    });
  });

  async function openSession(session: unknown) {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify(MOCK_SWEEPS_LIST), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(session), { status: 200 }),
      );
    render(<VolumeAnalysisDashboard />);
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /Saved Sweeps/i }),
      ).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: /Saved Sweeps/i }));
    fireEvent.click(screen.getByText("Test Sweep"));
    await waitFor(() =>
      expect(screen.getByText(/Capacity Studio/i)).toBeInTheDocument(),
    );
  }

  it("never presents unmeasured claims in the reading guide", async () => {
    await openSession(MOCK_SESSION);
    fireEvent.click(screen.getByText(/How to read this sweep/i));

    const text = document.body.textContent;
    // Claims the tool does not calculate must not appear.
    expect(text).not.toMatch(/up to 50%/i);
    expect(text).not.toMatch(/mathematically required/i);
    expect(text).not.toMatch(/emission reductions|fuel consumption/i);
    expect(text).not.toMatch(/higher safety margins/i);
    expect(text).not.toMatch(/must be deployed|planning design threshold/i);
    // What it does say is limited to what was run and what it cannot show.
    expect(text).toMatch(/one random traffic pattern/i);
    expect(text).toMatch(/does not calculate emissions, fuel use, cost or/i);
    expect(text).toMatch(/not the same as time queued/i);
  });

  it("uses the shared level-of-service bands for both controls", async () => {
    await openSession(MOCK_SESSION);
    fireEvent.click(screen.getByText(/How to read this sweep/i));
    // Roundabout bands (10/15/25/35/50) are listed alongside the signal's.
    expect(screen.getAllByText(/Roundabout: ≤ 10 s/).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/Traffic signal: ≤ 10 s/).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText(/Roundabout: 15 – 25 s/).length).toBeGreaterThan(
      0,
    );
    expect(
      screen.getAllByText(/Traffic signal: 20 – 35 s/).length,
    ).toBeGreaterThan(0);
  });

  it("labels an inconclusive tier as inconclusive, not as a win", async () => {
    const session = {
      ...MOCK_SESSION,
      tieTolerance: { absSeconds: 1, relative: 0.05 },
      calibration: { calibrated: true, note: "Calibrated comparison." },
      runs: [
        {
          ...makeSweepRun(0.1, 5, 3),
          winner: "inconclusive",
          inconclusiveReason: "low_sample",
        },
        { ...makeSweepRun(0.3, 8, 9), winner: "tie" },
        {
          ...makeSweepRun(0.5, 14, 15),
          winner: "inconclusive",
          vehicleLimitReached: true,
          inconclusiveReason: "vehicle_limit_reached",
        },
      ],
      curves: {
        ...MOCK_SESSION.curves,
        crossoverArrivalRate: null,
        crossoverHourlyVolume: null,
      },
    };
    await openSession(session);
    expect(screen.getByText(/2 inconclusive/i)).toBeInTheDocument();
    expect(screen.getByText(/No tier could be decided/i)).toBeInTheDocument();
    expect(screen.getByText(/Demand was cut off/i)).toBeInTheDocument();
    expect(screen.getByText(/≤1 s or ≤5%/)).toBeInTheDocument();
  });

  it("reports the direction found in the data, not an assumed one", async () => {
    // Signal lower first, roundabout lower later: the opposite of the
    // direction the old text assumed.
    const session = {
      ...MOCK_SESSION,
      calibration: { calibrated: true, note: "Calibrated comparison." },
      runs: [
        { ...makeSweepRun(0.1, 3, 9), winner: "signal" },
        { ...makeSweepRun(0.3, 30, 9), winner: "roundabout" },
      ],
      curves: {
        ...MOCK_SESSION.curves,
        crossoverArrivalRate: 0.3,
        crossoverHourlyVolume: 1080,
        crossoverBracketArrivalRates: [0.1, 0.3],
      },
    };
    await openSession(session);
    expect(
      screen.getByText(/Lower mean delay: signal before, roundabout after/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/roundabout before, signal after/i)).toBeNull();
  });

  it("flags an exploratory (multi-lane) sweep", async () => {
    await openSession({
      ...MOCK_SESSION,
      calibration: {
        calibrated: false,
        note: "Exploratory, not calibrated: more than one lane.",
      },
    });
    expect(
      screen.getByText(/Exploratory, not calibrated\./),
    ).toBeInTheDocument();
  });

  it("defaults the sweep to the calibrated one-lane comparison", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify([]), { status: 200 }),
    );
    render(<VolumeAnalysisDashboard />);
    fireEvent.click(
      (await screen.findAllByRole("button", { name: /Advanced Config/i }))[0],
    );
    const calibrated = await screen.findByRole("button", {
      name: /1 Lane \(calibrated comparison\)/i,
    });
    expect(calibrated.className).toMatch(/active/);
    const exploratory = screen.getByRole("button", {
      name: /2 Lanes \(exploratory/i,
    });
    expect(exploratory.className).not.toMatch(/active/);
  });

  it("sends the road speed limit, not a hard-coded desired speed", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockImplementationOnce(() => new Promise(() => undefined));
    render(<VolumeAnalysisDashboard />);
    await waitFor(() => {
      expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1);
    });
    fireEvent.click(screen.getByRole("button", { name: /Run Sweep/i }));
    const body = JSON.parse(
      vi.mocked(fetch).mock.calls[1][1]?.body as string,
    ) as {
      duration: number;
      arrivalRates: number[];
      customConfig: {
        simulation: { warmupTime: number };
        roads: { speedLimit: number };
        vehicleGeneration?: unknown;
      };
    };
    expect(body.customConfig.roads.speedLimit).toBeCloseTo(13.89);
    expect(body.customConfig.vehicleGeneration).toBeUndefined();
    // Long enough to measure after the 30 s warm-up every study uses.
    expect(body.duration).toBe(240);
    expect(body.customConfig.simulation.warmupTime).toBe(30);
    // 20%-160% of the measured 1-lane capacity (1,250 veh/h).
    expect(body.arrivalRates[0]).toBeCloseTo(0.069, 3);
    expect(body.arrivalRates[body.arrivalRates.length - 1]).toBeCloseTo(
      0.556,
      3,
    );
  });
});
