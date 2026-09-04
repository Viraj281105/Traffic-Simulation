/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  WeightedScoringPanel,
  DEFAULT_WEIGHTS,
} from "../components/WeightedScoringPanel";
import { RunningMetrics } from "../types/simulation";

describe("WeightedScoringPanel", () => {
  const mockSignalMetrics: RunningMetrics = {
    averageWaitTime: 24.5,
    throughput: 120,
    queueLength: 6.2,
    maxWaitTime: 45.0,
    totalVehicles: 150,
    stoppedVehicles: 40,
    fairnessIndex: 0.72,
  };

  const mockRoundaboutMetrics: RunningMetrics = {
    averageWaitTime: 12.3,
    throughput: 145,
    queueLength: 2.1,
    maxWaitTime: 22.0,
    totalVehicles: 155,
    stoppedVehicles: 10,
    fairnessIndex: 0.91,
  };

  it("renders scoring panel with winner banner and default weights", () => {
    render(
      <WeightedScoringPanel
        metricsSignal={mockSignalMetrics}
        metricsRoundabout={mockRoundaboutMetrics}
        weights={DEFAULT_WEIGHTS}
        onWeightsChange={vi.fn()}
      />,
    );

    expect(screen.getByText(/Custom Weighted Scoring Model/i)).toBeInTheDocument();
    expect(screen.getByText("Overall Scoring Winner")).toBeInTheDocument();
    expect(screen.getByText("Modern Roundabout")).toBeInTheDocument();
    expect(screen.getByText("Average Wait Time")).toBeInTheDocument();
    expect(screen.getByText("Throughput Volume")).toBeInTheDocument();
    expect(screen.getByText("Queue Clearance")).toBeInTheDocument();
    expect(screen.getByText("Directional Fairness")).toBeInTheDocument();
  });

  it("changes weight presets when preset buttons are clicked", () => {
    const onWeightsChange = vi.fn();
    render(
      <WeightedScoringPanel
        metricsSignal={mockSignalMetrics}
        metricsRoundabout={mockRoundaboutMetrics}
        weights={DEFAULT_WEIGHTS}
        onWeightsChange={onWeightsChange}
      />,
    );

    const highThroughputBtn = screen.getByRole("button", { name: /High Throughput/i });
    fireEvent.click(highThroughputBtn);

    expect(onWeightsChange).toHaveBeenCalledWith(
      expect.objectContaining({
        weightThroughput: 50,
      }),
    );
  });

  it("allows individual slider adjustments and invokes onWeightsChange", () => {
    const onWeightsChange = vi.fn();
    render(
      <WeightedScoringPanel
        metricsSignal={mockSignalMetrics}
        metricsRoundabout={mockRoundaboutMetrics}
        weights={DEFAULT_WEIGHTS}
        onWeightsChange={onWeightsChange}
      />,
    );

    const sliders = screen.getAllByRole("slider");
    expect(sliders.length).toBeGreaterThanOrEqual(4);
    
    // Change first slider (Wait Time)
    fireEvent.change(sliders[0], { target: { value: "45" } });
    expect(onWeightsChange).toHaveBeenCalledWith(
      expect.objectContaining({
        weightWaitTime: 45,
      }),
    );
  });
});
