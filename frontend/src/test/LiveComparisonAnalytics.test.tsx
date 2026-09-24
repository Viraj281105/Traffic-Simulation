import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { VehiclesFlowVisualizer } from "../components/analytics/VehiclesFlowVisualizer";
import { PerformanceCharts } from "../components/analytics/PerformanceCharts";
import { TrafficFlowVisualizer } from "../components/analytics/TrafficFlowVisualizer";
import { SafetyTimelineVisualizer } from "../components/analytics/SafetyTimelineVisualizer";
import { CapacityDemandVisualizer } from "../components/analytics/CapacityDemandVisualizer";
import { DistributionDiagnosticsVisualizer } from "../components/analytics/DistributionDiagnosticsVisualizer";
import type { LiveSnapshot } from "../types/simulation";
import type { MetricContext } from "../metrics/catalog";

const mockSignalSnapshot: LiveSnapshot = {
  schemaVersion: "1.0",
  simulationId: "sim_1",
  configId: "cfg_1",
  timestamp: 45.0,
  frameNumber: 450,
  tick: 450,
  wallClockTime: "2026-09-24T12:00:00Z",
  samplingFrequency: 10,
  deltaTime: 0.1,
  warmupTime: 30.0,
  vehicles: [],
  intersection: {
    type: "fixed_time_signal",
    centerX: 0,
    centerY: 0,
    boundingRadius: 30,
    approaches: [
      { direction: "north", queueLength: 3, laneCount: 1 },
      { direction: "south", queueLength: 2, laneCount: 1 },
      { direction: "east", queueLength: 1, laneCount: 1 },
      { direction: "west", queueLength: 0, laneCount: 1 },
    ],
  },
  controller: {
    type: "fixed_time_signal",
    timeInCurrentState: 15,
    currentPhase: "ns_green",
    phaseTimeRemaining: 15,
    cycleNumber: 2,
    signals: [],
  },
  vehicleCounts: {
    active: 14,
    approaching: 6,
    waiting: 5,
    crossing: 3,
    inRoundabout: 0,
    exited: 28,
  },
  metrics: {
    averageDelay: 8.5,
    medianDelay: 7.2,
    minDelay: 1.1,
    maxDelay: 22.4,
    p95Delay: 18.0,
    delayStdDev: 4.2,
    averageWaitTime: 5.1,
    throughput: 28,
    throughputRate: 18.6,
    currentQueueLengths: { north: 3, south: 2, east: 1, west: 0 },
    maxQueueLength: 6,
    averageQueueLength: 1.5,
    activeAverageQueueLength: 2.4,
    queueStdDev: 1.1,
    totalStops: 32,
    averageStopsPerVehicle: 1.14,
    speedVarianceIndex: 0.28,
    travelTimeReliability: 1.35,
    idleOpportunityLoss: 0.08,
    directionalFairnessIndex: 0.88,
    activeVehicleCount: 14,
    totalVehiclesSpawned: 45,
    averageTravelSpeed: 6.8,
    queueStabilityIndex: 0.73,
    congestionRecoveryTime: 4.2,
    spaceFootprintConsumed: 480,
    intersectionUtilization: 76.5,
    criticalSaturationVolume: 0.52,
    masterEfficiencyScore: 78.4,
    collisionCount: 1,
    minTTC: 2.1,
    ttcEventCount: 2,
    ttcSampleCount: 84,
    ttcThresholdSeconds: 1.5,
    minPET: 3.4,
    petEventCount: 1,
    petSampleCount: 18,
    petThresholdSeconds: 5.0,
    petApplicable: true,
  },
  simulationStatus: "running",
};

const mockRoundaboutSnapshot: LiveSnapshot = {
  ...mockSignalSnapshot,
  intersection: {
    ...mockSignalSnapshot.intersection,
    type: "roundabout",
  },
  controller: {
    type: "roundabout",
    timeInCurrentState: 45,
    innerRadius: 10,
    outerRadius: 16,
    circulatingCount: 2,
    yieldingCount: 1,
    gapAcceptance: 3.5,
  },
  vehicleCounts: {
    active: 11,
    approaching: 5,
    waiting: 3,
    crossing: 1,
    inRoundabout: 2,
    exited: 33,
  },
  metrics: {
    ...mockSignalSnapshot.metrics,
    averageDelay: 5.2,
    medianDelay: 4.8,
    minDelay: 0.8,
    maxDelay: 15.6,
    p95Delay: 11.2,
    delayStdDev: 3.1,
    averageWaitTime: 3.2,
    throughput: 33,
    throughputRate: 22.0,
    currentQueueLengths: { north: 1, south: 1, east: 1, west: 0 },
    maxQueueLength: 4,
    averageQueueLength: 0.75,
    activeAverageQueueLength: 1.8,
    queueStdDev: 0.8,
    totalStops: 24,
    averageStopsPerVehicle: 0.72,
    speedVarianceIndex: 0.19,
    travelTimeReliability: 1.18,
    idleOpportunityLoss: 0.0,
    directionalFairnessIndex: 0.94,
    activeVehicleCount: 11,
    totalVehiclesSpawned: 45,
    averageTravelSpeed: 8.2,
    queueStabilityIndex: 0.52,
    congestionRecoveryTime: 1.8,
    spaceFootprintConsumed: 804,
    intersectionUtilization: 88.2,
    criticalSaturationVolume: 0.65,
    masterEfficiencyScore: 86.2,
    collisionCount: 0,
    minTTC: 2.8,
    ttcEventCount: 0,
    ttcSampleCount: 92,
    minPET: null,
    petEventCount: 0,
    petSampleCount: 0,
    petApplicable: false,
  },
};

const signalCtx: MetricContext = {
  metrics: mockSignalSnapshot.metrics,
  geometry: "fixed_time_signal",
  inWarmup: false,
};

const roundaboutCtx: MetricContext = {
  metrics: mockRoundaboutSnapshot.metrics,
  geometry: "roundabout",
  inWarmup: false,
};

describe("Live Comparison Analytics Visualizers", () => {
  it("renders VehiclesFlowVisualizer with 4 stages and paired values", () => {
    render(
      <VehiclesFlowVisualizer
        signal={mockSignalSnapshot}
        roundabout={mockRoundaboutSnapshot}
        compact={false}
      />,
    );

    expect(screen.getByText("In Network")).toBeInTheDocument();
    expect(screen.getAllByText("Waiting").length).toBeGreaterThan(0);
    expect(screen.getAllByText("In Junction").length).toBeGreaterThan(0);
    expect(screen.getByText("Exited (Served)")).toBeInTheDocument();

    // Verify signal active count (14) and roundabout active count (11)
    expect(screen.getByText("14")).toBeInTheDocument();
    expect(screen.getByText("11")).toBeInTheDocument();
  });

  it("renders PerformanceCharts with key KPI cards and switches tabs", async () => {
    const user = userEvent.setup();
    const history = [
      {
        time: 40,
        timeFormatted: "0:40",
        inWarmup: false,
        signalAvgDelay: 8.0,
        roundaboutAvgDelay: 5.0,
        signalMedianDelay: 7.0,
        roundaboutMedianDelay: 4.5,
        signalP95Delay: 17.5,
        roundaboutP95Delay: 11.0,
        signalAvgWait: 5.0,
        roundaboutAvgWait: 3.0,
        signalThroughput: 25,
        roundaboutThroughput: 30,
        signalThroughputRate: 18.0,
        roundaboutThroughputRate: 21.0,
        signalSpeed: 6.5,
        roundaboutSpeed: 8.0,
        signalPti: 1.35,
        roundaboutPti: 1.18,
        signalAvgQueue: 1.5,
        roundaboutAvgQueue: 0.8,
        signalActiveAvgQueue: 2.4,
        roundaboutActiveAvgQueue: 1.8,
        signalStopsPerVeh: 1.14,
        roundaboutStopsPerVeh: 0.72,
        signalTotalStops: 32,
        roundaboutTotalStops: 24,
        signalFairness: 0.88,
        roundaboutFairness: 0.94,
        signalMinTtc: 2.1,
        roundaboutMinTtc: 2.8,
        signalTtcEvents: 2,
        roundaboutTtcEvents: 0,
        signalCollisions: 1,
        roundaboutCollisions: 0,
        signalMinPet: 3.4,
        signalPetEvents: 1,
        signalUtilization: 76.5,
        roundaboutUtilization: 88.2,
        signalIdleLoss: 8.0,
        signalActiveVehicles: 14,
        roundaboutActiveVehicles: 11,
        signalSpawned: 45,
        roundaboutSpawned: 45,
      },
    ];

    render(
      <PerformanceCharts
        history={history}
        signalCtx={signalCtx}
        roundaboutCtx={roundaboutCtx}
        compact={false}
      />,
    );

    expect(screen.getByText("Average Delay")).toBeInTheDocument();
    expect(screen.getByText("Queued Time")).toBeInTheDocument();
    expect(screen.getByText("Vehicles Served")).toBeInTheDocument();
    expect(screen.getByText("Throughput Rate")).toBeInTheDocument();
    expect(screen.getByText("Mean Speed")).toBeInTheDocument();
    expect(screen.getByText("Planning Time Index")).toBeInTheDocument();

    const speedTabBtn = screen.getByRole("button", { name: /mean travel speed/i });
    await user.click(speedTabBtn);
    expect(speedTabBtn).toHaveClass("active");
  });

  it("renders TrafficFlowVisualizer with 4-way approach queues and directional fairness", () => {
    render(
      <TrafficFlowVisualizer
        signalCtx={signalCtx}
        roundaboutCtx={roundaboutCtx}
        compact={false}
      />,
    );

    expect(screen.getByText(/approach queue distribution/i)).toBeInTheDocument();
    expect(screen.getByText("NORTH")).toBeInTheDocument();
    expect(screen.getByText("SOUTH")).toBeInTheDocument();
    expect(screen.getByText("EAST")).toBeInTheDocument();
    expect(screen.getByText("WEST")).toBeInTheDocument();
    expect(screen.getByText("Directional Fairness")).toBeInTheDocument();
  });

  it("renders SafetyTimelineVisualizer with collision cards and disclaimer", () => {
    render(
      <SafetyTimelineVisualizer
        history={[]}
        collisionEvents={[
          {
            id: "sig-1",
            time: 25.0,
            timeFormatted: "0:25",
            control: "signal",
            newCount: 1,
          },
        ]}
        signalCtx={signalCtx}
        roundaboutCtx={roundaboutCtx}
        compact={false}
      />,
    );

    expect(screen.getAllByText(/distinct overlaps/i).length).toBe(2);
    expect(screen.getByText(/zero collisions recorded/i)).toBeInTheDocument();
    expect(screen.getByText(/surrogate safety measures notice/i)).toBeInTheDocument();
    expect(screen.getByText(/event timeline/i)).toBeInTheDocument();
  });

  it("renders CapacityDemandVisualizer with demand balance and utilization", () => {
    render(
      <CapacityDemandVisualizer
        signalCtx={signalCtx}
        roundaboutCtx={roundaboutCtx}
        compact={false}
      />,
    );

    expect(screen.getByText("Demand vs. Served Balance")).toBeInTheDocument();
    expect(screen.getByText("Service Utilization")).toBeInTheDocument();
    expect(screen.getByText("Critical Saturation Volume")).toBeInTheDocument();
    expect(screen.getByText("Idle Green Loss")).toBeInTheDocument();
    expect(screen.getByText("Junction Footprint")).toBeInTheDocument();
  });

  it("renders DistributionDiagnosticsVisualizer with delay spread and composite scores", () => {
    render(
      <DistributionDiagnosticsVisualizer
        signalCtx={signalCtx}
        roundaboutCtx={roundaboutCtx}
        compact={false}
      />,
    );

    expect(screen.getByText(/delay distribution spread/i)).toBeInTheDocument();
    expect(screen.getByText("Composite Score (Fixed Weights)")).toBeInTheDocument();
    expect(screen.getByText("78.4")).toBeInTheDocument();
    expect(screen.getByText("86.2")).toBeInTheDocument();
  });
});
