/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { WeightedScoringPanel } from "../components/WeightedScoringPanel";
import { DEFAULT_WEIGHTS, computeWeightedScore } from "../types/scoring";
import type { RunningMetrics } from "../types/simulation";

function metrics(overrides: Partial<RunningMetrics>): RunningMetrics {
  return {
    averageDelay: 0,
    medianDelay: 0,
    minDelay: 0,
    maxDelay: 0,
    p95Delay: 0,
    delayStdDev: 0,
    averageWaitTime: 0,
    throughput: 0,
    throughputRate: 0,
    currentQueueLengths: { north: 0, south: 0, east: 0, west: 0 },
    maxQueueLength: 0,
    averageQueueLength: 0,
    activeAverageQueueLength: 0,
    queueStdDev: 0,
    totalStops: 0,
    averageStopsPerVehicle: 0,
    speedVarianceIndex: 0,
    travelTimeReliability: 1,
    idleOpportunityLoss: 0,
    directionalFairnessIndex: 1,
    activeVehicleCount: 0,
    totalVehiclesSpawned: 0,
    averageTravelSpeed: 0,
    queueStabilityIndex: 0,
    congestionRecoveryTime: 0,
    spaceFootprintConsumed: 0,
    intersectionUtilization: 0,
    criticalSaturationVolume: 0,
    collisionCount: 0,
    ...overrides,
  };
}

describe("WeightedScoringPanel", () => {
  const signal = metrics({
    throughput: 30,
    averageWaitTime: 24.5,
    throughputRate: 20,
    averageQueueLength: 3.2,
    averageStopsPerVehicle: 1.8,
    directionalFairnessIndex: 0.72,
  });
  const roundabout = metrics({
    throughput: 30,
    averageWaitTime: 12.3,
    throughputRate: 24,
    averageQueueLength: 1.1,
    averageStopsPerVehicle: 0.4,
    directionalFairnessIndex: 0.91,
  });

  it("shows both scores and a neutral summary, never a 'winner'", () => {
    render(
      <WeightedScoringPanel
        metricsSignal={signal}
        metricsRoundabout={roundabout}
        weights={DEFAULT_WEIGHTS}
        onWeightsChange={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("heading", {
        name: /Weighted score \(your priorities\)/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Under these weights the roundabout scores/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/winner/i)).toBeNull();
    expect(screen.queryByText(/lead/i)).toBeNull();
    // Sliders are reachable by their labels.
    expect(screen.getByLabelText(/Average queued time/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Directional fairness/i)).toBeInTheDocument();
  });

  it("says the score reflects the chosen weights, not a finding", () => {
    render(
      <WeightedScoringPanel
        metricsSignal={signal}
        metricsRoundabout={roundabout}
        weights={DEFAULT_WEIGHTS}
        onWeightsChange={vi.fn()}
      />,
    );
    expect(
      screen.getByText(/reflects the weights you chose, not a finding/i),
    ).toBeInTheDocument();
  });

  it("shows no score before a vehicle has exited on both sides", () => {
    render(
      <WeightedScoringPanel
        metricsSignal={{ ...signal, throughput: 0 }}
        metricsRoundabout={roundabout}
        weights={DEFAULT_WEIGHTS}
        onWeightsChange={vi.fn()}
      />,
    );
    expect(screen.getByText(/No score yet/i)).toBeInTheDocument();
    expect(screen.queryByText(/\/ 100/)).toBeNull();
    expect(screen.queryByText(/points higher/i)).toBeNull();
  });

  it("shows no score during warm-up even when metrics hold placeholders", () => {
    const placeholder = metrics({
      throughput: 12,
      directionalFairnessIndex: 1,
    });
    render(
      <WeightedScoringPanel
        metricsSignal={placeholder}
        metricsRoundabout={placeholder}
        signalCtx={{
          metrics: placeholder,
          geometry: "fixed_time_signal",
          inWarmup: true,
        }}
        roundaboutCtx={{
          metrics: placeholder,
          geometry: "roundabout",
          inWarmup: true,
        }}
        weights={DEFAULT_WEIGHTS}
        onWeightsChange={vi.fn()}
      />,
    );
    expect(screen.getByText(/No score yet/i)).toBeInTheDocument();
  });

  it("applies presets", () => {
    const onWeightsChange = vi.fn();
    render(
      <WeightedScoringPanel
        metricsSignal={signal}
        metricsRoundabout={roundabout}
        weights={DEFAULT_WEIGHTS}
        onWeightsChange={onWeightsChange}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Throughput first/i }));

    expect(onWeightsChange).toHaveBeenCalledWith(
      expect.objectContaining({ weightThroughput: 50 }),
    );
  });

  it("reports individual slider changes", () => {
    const onWeightsChange = vi.fn();
    render(
      <WeightedScoringPanel
        metricsSignal={signal}
        metricsRoundabout={roundabout}
        weights={DEFAULT_WEIGHTS}
        onWeightsChange={onWeightsChange}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Average queued time/i), {
      target: { value: "45" },
    });
    expect(onWeightsChange).toHaveBeenCalledWith(
      expect.objectContaining({ weightWaitTime: 45 }),
    );
  });
});

describe("computeWeightedScore", () => {
  it("always reads throughputRate as vehicles per minute", () => {
    const onlyThroughput = {
      weightWaitTime: 0,
      weightThroughput: 100,
      weightQueue: 0,
      weightFairness: 0,
      weightStops: 0,
    };
    // 1.2 veh/min is 0.02 veh/s -> 1% of the 2 veh/s cap. It used to be
    // read as 1.2 veh/s (60% of the cap) because it was <= 2.
    expect(
      computeWeightedScore(metrics({ throughputRate: 1.2 }), onlyThroughput),
    ).toBe(1);
    expect(
      computeWeightedScore(metrics({ throughputRate: 60 }), onlyThroughput),
    ).toBe(50);
  });
});
