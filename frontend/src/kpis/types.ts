/** Contract: GET /api/v3/runs/{runId}/metrics. See src/CONTRACTS.md.
 *  Any value the run could not produce is null, never 0. */

export interface MetricValue {
  value: number | null;
  unit: string;
  /** Interval, when the run is one of several replications. */
  ci?: [number, number] | null;
}

export interface RunMetrics {
  runId: string;
  vehiclesCompleted: number | null;
  delay: {
    mean: MetricValue;
    p95: MetricValue;
    /** Delay is time beyond free-flow travel time. */
    definition: string;
  };
  travelTime: {
    mean: MetricValue;
    p95: MetricValue;
    definition: string;
  };
  safety: {
    /** Smallest time-to-collision seen. */
    minTtc: MetricValue;
    /** Number of encounters with time-to-collision below the threshold. */
    conflicts: MetricValue;
    thresholdSeconds: number;
    definition: string;
  };
  emissions: {
    fuel: MetricValue;
    co2: MetricValue;
    co2PerVehicle: MetricValue;
    model: { name: string; version?: string | null };
    definition: string;
  };
  /** Extra assumptions the server wants shown with the numbers. */
  notes?: string[];
}
