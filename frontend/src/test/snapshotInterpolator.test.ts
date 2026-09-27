import { describe, expect, it } from "vitest";
import { SnapshotInterpolator } from "../components/snapshotInterpolator";
import type { LiveSnapshot, SimulationStatus } from "../types/simulation";

/** A snapshot with one vehicle travelling +x at 10 m/s. */
function snap(
  tick: number,
  status: SimulationStatus = "running",
  simulationId = "sim",
): LiveSnapshot {
  const timestamp = Math.round(tick) / 10;
  return {
    simulationId,
    configId: "cfg",
    tick,
    timestamp,
    deltaTime: 0.1,
    simulationStatus: status,
    vehicles: [
      {
        id: "v1",
        x: timestamp * 10,
        y: 0,
        heading: 90,
        state: "approaching",
      },
    ],
  } as unknown as LiveSnapshot;
}

function xAt(interp: SnapshotInterpolator, now: number): number {
  const frame = interp.sample(now);
  if (!frame) throw new Error("no frame");
  return frame.vehicles[0].x;
}

describe("SnapshotInterpolator", () => {
  it("returns nothing before any snapshot", () => {
    expect(new SnapshotInterpolator().sample(0)).toBeNull();
  });

  it("shows a paused snapshot exactly and reports no change once drawn", () => {
    const interp = new SnapshotInterpolator();
    interp.push(snap(5, "paused"), 0);
    const first = interp.sample(0);
    expect(first?.vehicles[0].x).toBe(5);
    expect(first?.changed).toBe(true);
    expect(interp.sample(16)?.changed).toBe(false);
  });

  // The backend steps the simulation and sends snapshots on two independent
  // loops, each ~100 ms plus its own work, so their rates drift apart.
  it.each([
    // Measured while running: a message every ~110 ms against a tick every
    // ~100 ms, so about one message in eleven advances two ticks.
    ["the stream is slower than the simulation", 110, 100],
    // The reverse (a busier simulation step): some messages repeat a tick.
    ["the simulation is slower than the stream", 100, 111],
  ])("moves smoothly when %s", (_, messageMs, tickMs) => {
    const interp = new SnapshotInterpolator();
    const xs: number[] = [];
    let sent = 0;
    const end = 40 * messageMs;
    for (let now = 0; now <= end; now += 16) {
      while (sent * messageMs <= now) {
        const at = sent * messageMs;
        interp.push(snap(Math.floor(at / tickMs)), at);
        sent += 1;
      }
      xs.push(xAt(interp, now));
    }
    const steps = xs.slice(1).map((x, i) => x - xs[i]);
    // Once warmed up, the vehicle never stalls or jumps backwards…
    const settled = steps.slice(Math.floor(steps.length / 3));
    for (const step of settled) expect(step).toBeGreaterThan(0);
    // …and never lurches: per-frame motion stays near the true ~0.15 m.
    for (const step of settled) expect(step).toBeLessThan(0.3);
  });

  it("never renders beyond the newest snapshot", () => {
    const interp = new SnapshotInterpolator();
    interp.push(snap(0), 0);
    interp.push(snap(1), 100);
    // Long gap with no data: playback holds at the newest pose.
    expect(xAt(interp, 5000)).toBeLessThanOrEqual(1);
  });

  it("passes exactly through snapshot positions", () => {
    const interp = new SnapshotInterpolator();
    interp.push(snap(0), 0);
    interp.push(snap(1), 100);
    interp.push(snap(2), 200);
    interp.push(snap(3), 300);
    const x = xAt(interp, 300);
    // Playback trails by 1.5 ticks; wherever it is, it lies on the path.
    expect(x).toBeGreaterThanOrEqual(0);
    expect(x).toBeLessThanOrEqual(3);
  });

  it("drops the previous run on a reset instead of interpolating across it", () => {
    const interp = new SnapshotInterpolator();
    interp.push(snap(50), 0);
    interp.push(snap(51), 100);
    interp.push(snap(0, "initialized"), 200);
    expect(xAt(interp, 200)).toBe(0);
  });

  it("clears when the snapshot goes away", () => {
    const interp = new SnapshotInterpolator();
    interp.push(snap(1, "paused"), 0);
    interp.push(null, 10);
    expect(interp.sample(20)).toBeNull();
  });
});
