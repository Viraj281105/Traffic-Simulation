/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { IntegrityCheck } from "../components/IntegrityCheck";

vi.mock("../config", () => ({ API_BASE_URL: "http://localhost:8000" }));

const geometry = (valid: boolean, isDeterministic = true) => ({
  valid,
  isDeterministic,
  violations: valid ? [] : ["Tick 3: roundabout vehicle conservation violated"],
});

async function run(result: unknown) {
  vi.mocked(fetch).mockResolvedValueOnce(
    new Response(JSON.stringify(result), { status: 200 }),
  );
  render(<IntegrityCheck />);
  fireEvent.click(screen.getByRole("button", { name: /run integrity check/i }));
  await waitFor(() => {
    expect(screen.getByText(/Roundabout: /)).toBeInTheDocument();
  });
}

describe("IntegrityCheck", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("claims only what it checks: both geometries, and not real-world validity", () => {
    render(<IntegrityCheck />);
    const text = document.body.textContent;
    expect(text).toMatch(/both the signal and the roundabout/i);
    expect(text).toMatch(/conflicting greens/i);
    expect(text).toMatch(/not that its results match the real world/i);
  });

  it("reports each geometry separately", async () => {
    await run({
      valid: true,
      isDeterministic: true,
      ticksTested: 200,
      violations: [],
      signalGreenExclusivityValid: true,
      geometries: { signal: geometry(true), roundabout: geometry(true) },
    });
    expect(screen.getByText(/Signal: all invariants held/)).toBeInTheDocument();
    expect(
      screen.getByText(/Roundabout: all invariants held/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/no conflicting greens at the same time/i),
    ).toBeInTheDocument();
  });

  it("never lets a passing signal hide a failing roundabout", async () => {
    await run({
      valid: false,
      isDeterministic: true,
      ticksTested: 200,
      violations: ["Tick 3: roundabout vehicle conservation violated"],
      signalGreenExclusivityValid: true,
      geometries: { signal: geometry(true), roundabout: geometry(false) },
    });
    const signal = screen.getByText(/Signal: all invariants held/);
    const roundabout = screen.getByText(
      /Roundabout: an invariant was violated/,
    );
    expect(signal.className).toBe("ok");
    expect(roundabout.className).toBe("bad");
  });

  it("reports a geometry that fails to reproduce its own result", async () => {
    await run({
      valid: true,
      isDeterministic: false,
      ticksTested: 200,
      violations: [],
      geometries: { signal: geometry(true), roundabout: geometry(true, false) },
    });
    expect(
      screen.getByText(/Roundabout: .*did not reproduce delay and throughput/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Signal: .*same seed reproduced/),
    ).toBeInTheDocument();
  });
});
