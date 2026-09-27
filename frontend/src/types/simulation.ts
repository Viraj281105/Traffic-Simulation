/**
 * TypeScript interfaces matching the backend snapshot contract.
 * Based on docs/architecture/05-snapshot-contract.md and backend/src/main.py
 */

// ── Layout toggle ──────────────────────────────────────────────────────────

/** Which intersection layout to render on the canvas. */
export type LayoutType = "signal" | "roundabout";

// ── Vehicle state ──────────────────────────────────────────────────────────

/**
 * Vehicle state enum matching backend VehicleStatus values.
 */
export type VehicleState =
  "approaching" | "waiting" | "crossing" | "in_roundabout" | "exited";

/**
 * A single vehicle in a live snapshot (multi-vehicle format).
 * Matches the `vehicles` array in the snapshot contract.
 */
export interface SnapshotVehicle {
  id: string;
  x: number;
  y: number;
  speed: number;
  acceleration: number;
  heading: number;
  length: number;
  width: number;
  state: VehicleState;
  laneId: string;
  direction: "north" | "south" | "east" | "west";
  turnIntent: "left" | "straight" | "right";
  waitTime: number;
  stopCount: number;
  spawnTime: number;
  exitTime: number | null;
  distanceTraveled: number;
}

// ── Signal / Controller state ──────────────────────────────────────────────

export type SignalColor = "red" | "yellow" | "green";
export type SignalDirection = "north" | "south" | "east" | "west";
/**
 * Approach group that a configured `controller.phaseSequence` entry activates:
 * a single approach, or an order-invariant pair sharing one green.
 */
export type SignalGroup = "n" | "s" | "e" | "w" | "ns" | "sn" | "ew" | "we";

/**
 * Name of the active signal phase, as reported in `controller.currentPhase`.
 *
 * The backend emits two vocabularies, and both must be represented here or the
 * type silently misdescribes real snapshots (it previously listed only the
 * paired-green names, so every snapshot from the default cycle was mistyped):
 *
 * - a configured `controller.phaseSequence` entry, e.g. `ns_green`, `w_yellow`,
 *   `all_red`;
 * - the default one-direction-at-a-time cycle used when `phaseSequence` is
 *   omitted, e.g. `north_straight_right`, `north_left`, `north_yellow`.
 *
 * Kept in sync with the `currentPhase` pattern in
 * `shared/schemas/snapshot.schema.json`.
 */
export type SignalPhase =
  | "all_red"
  | `${SignalGroup}_green`
  | `${SignalGroup}_yellow`
  | `${SignalDirection}_straight_right`
  | `${SignalDirection}_left`
  | `${SignalDirection}_yellow`;

export interface SignalHead {
  direction: SignalDirection;
  color: SignalColor;
}

export interface FixedTimeControllerState {
  type: "fixed_time_signal";
  timeInCurrentState: number;
  currentPhase: SignalPhase;
  phaseTimeRemaining: number;
  cycleNumber: number;
  signals: SignalHead[];
}

export interface RoundaboutControllerState {
  type: "roundabout";
  timeInCurrentState: number;
  innerRadius: number;
  outerRadius: number;
  circulatingCount: number;
  yieldingCount: number;
  gapAcceptance: number;
}

export type ControllerState =
  FixedTimeControllerState | RoundaboutControllerState;

// ── Intersection state ─────────────────────────────────────────────────────

export interface Approach {
  direction: SignalDirection;
  queueLength: number;
  laneCount: number;
}

export interface IntersectionState {
  type: "fixed_time_signal" | "roundabout";
  centerX: number;
  centerY: number;
  boundingRadius: number;
  approaches: Approach[];
}

// ── Running metrics ────────────────────────────────────────────────────────

export interface RunningMetrics {
  // Every field below is computed by the backend MetricCollector
  // (backend/src/metrics/collector.py). Unless noted, values cover
  // post-warmup activity only — see LiveSnapshot.warmupTime.

  // Delay (seconds) of post-warmup exited vehicles: actual minus free-flow
  // travel time.
  averageDelay: number;
  medianDelay: number;
  minDelay: number;
  maxDelay: number;
  p95Delay: number;
  delayStdDev: number;
  averageWaitTime: number;
  /** Vehicles exited after warmup (a count). */
  throughput: number;
  /** Exits per minute over the most recent 60 s (a rate). */
  throughputRate: number;
  /** Vehicles queued right now, per approach (instantaneous). */
  currentQueueLengths: Record<SignalDirection, number>;
  maxQueueLength: number;
  averageQueueLength: number;
  /** Mean total queue over ticks where any queue existed. */
  activeAverageQueueLength: number;
  queueStdDev: number;
  totalStops: number;
  averageStopsPerVehicle: number;
  speedVarianceIndex: number;
  // Planning Time Index (95th percentile / median travel time). null for a
  // genuine zero-median-travel-time case — see
  // calculate_travel_time_reliability() in the backend, which returns None
  // (not a fabricated 1.0) when real travel-time data exists but the
  // computed median is exactly 0.
  travelTimeReliability: number | null;
  /** True when fewer than 20 exited vehicles back the reliability value. */
  travelTimeReliabilityLowSampleSize?: boolean;
  /** Fraction (0-1) of post-warmup ticks where a red approach had a queue
   *  while every green approach was empty. Signal-only by construction. */
  idleOpportunityLoss: number;
  /** Jain's index (0.25-1) across the four approaches' mean waits. */
  directionalFairnessIndex: number;
  /** Vehicles in the network right now (instantaneous). */
  activeVehicleCount: number;
  /** All vehicles spawned since the run began (not warmup-limited). This is
   *  the offered demand only while `vehicleLimitReached` is false. */
  totalVehiclesSpawned: number;
  /** Per-run cap on vehicles generated (traffic.totalVehicles). */
  vehicleLimit?: number;
  /** True once generation hit the cap: later demand was not offered. */
  vehicleLimitReached?: boolean;
  /** Mean instantaneous speed (m/s) of vehicles in the network right now. */
  averageTravelSpeed: number;
  queueStabilityIndex: number;
  /** Post-warmup time (s) with more than 5 vehicles queued in total. */
  congestionRecoveryTime: number;
  /** Intersection footprint area (m²) from the configured geometry. */
  spaceFootprintConsumed: number;
  /** Percent (0-100) of post-warmup ticks with demand in which vehicles
   *  were moving on average. */
  intersectionUtilization: number;
  /** Estimated saturation volume in vehicles per second. */
  criticalSaturationVolume: number;
  /** Fixed-weight composite (0-100). Valid only for comparing runs of the
   *  same geometry and scenario, never a signal against a roundabout. null
   *  until a vehicle has exited after warm-up. */
  masterEfficiencyScore?: number | null;
  // Running total of debounced collision events (VehiclePool.collision_count
  // — one event per overlapping vehicle pair, counted once when the overlap
  // begins, not once per tick it persists). 0 when no collision has
  // occurred, including the zero-vehicle case. Not warmup-limited.
  collisionCount: number;
  // Surrogate safety measures (measurement-only; thresholds are literature
  // defaults, not validated for this model). min* is null when nothing was
  // observed — never a synonym for "no risk".
  minTTC?: number | null;
  ttcEventCount?: number;
  ttcSampleCount?: number;
  ttcThresholdSeconds?: number;
  minPET?: number | null;
  petEventCount?: number;
  petSampleCount?: number;
  petThresholdSeconds?: number;
  /** False where PET is not measured at all (roundabout geometry). */
  petApplicable?: boolean;
}

// ── Vehicle counts ─────────────────────────────────────────────────────────

export interface VehicleCounts {
  active: number;
  approaching: number;
  waiting: number;
  crossing: number;
  inRoundabout: number;
  exited: number;
}

// ── Live snapshot (WebSocket message payload) ──────────────────────────────

export type SimulationStatus =
  | "initialized"
  | "initializing"
  | "running"
  | "paused"
  | "completed"
  | "error"
  | "stopped";

export interface LiveSnapshot {
  schemaVersion: string;
  simulationId: string;
  configId: string;
  timestamp: number;
  frameNumber: number;
  tick: number;
  wallClockTime: string;
  samplingFrequency: number;
  deltaTime: number;
  /** Simulated seconds before most metrics start accumulating. Optional
   *  because snapshots from older backends omit it. */
  warmupTime?: number;
  vehicles: SnapshotVehicle[];
  intersection: IntersectionState;
  controller: ControllerState;
  metrics: RunningMetrics;
  vehicleCounts: VehicleCounts;
  simulationStatus: SimulationStatus;
}

export interface DualSnapshot {
  tick: number;
  elapsed: number;
  signal: LiveSnapshot;
  roundabout: LiveSnapshot;
}

// ── Legacy single-vehicle types (Sprint 1 compatibility) ──────────────────

/**
 * Response from GET /api/simulation/single-vehicle.
 * Kept for backward compatibility with IntersectionCanvas.
 */
export interface SingleVehicleResponse {
  vehicle_id: string;
  position: number;
  speed: number;
  acceleration: number;
  x: number;
  y: number;
  heading: number;
  state: VehicleState;
  lane_id: string;
  wait_time: number;
  stop_count: number;
  sim_time: number;
  tick: number;
  simulation_status: SimulationLifecycle;
}

export type SimulationLifecycle = "stopped" | "running" | "completed";

export interface SimulationStatusResponse {
  status: SimulationLifecycle;
  sim_time: number;
  tick: number;
  vehicle_state: VehicleState;
  message: string;
}

export interface ControlResponse {
  status: SimulationLifecycle;
  message: string;
}

export interface PollingState {
  vehicle: SingleVehicleResponse | null;
  status: SimulationLifecycle;
  isLoading: boolean;
  error: string | null;
}

// ── Canvas viewport ────────────────────────────────────────────────────────

export interface Viewport {
  canvasW: number;
  canvasH: number;
  ppm: number;
  centerWorldX: number;
  centerWorldY: number;
}
