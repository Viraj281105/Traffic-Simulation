/**
 * TypeScript interfaces matching the backend single-vehicle API schema.
 * Based on tests/api/test_main.py and docs/architecture/05-snapshot-contract.md
 */

// ── Layout toggle ──────────────────────────────────────────────────────────

/** Which intersection layout to render on the canvas. */
export type LayoutType = 'signal' | 'roundabout';

// ── Vehicle state ──────────────────────────────────────────────────────────

/**
 * Vehicle state enum matching backend VehicleStatus values.
 * Mirrors the `state` field from GET /api/simulation/single-vehicle.
 */
export type VehicleState = 'approaching' | 'waiting' | 'crossing' | 'exited';

/**
 * Response from GET /api/simulation/single-vehicle.
 * Every field comes directly from the backend — nothing is fabricated.
 */
export interface SingleVehicleResponse {
  /** Unique vehicle identifier, e.g. "vehicle_1" */
  vehicle_id: string;
  /** Linear distance traveled along the route (meters) */
  position: number;
  /** Current speed (m/s) */
  speed: number;
  /** Current acceleration (m/s², negative = decelerating) */
  acceleration: number;
  /** World X-coordinate — East positive, meters */
  x: number;
  /** World Y-coordinate — North positive, meters */
  y: number;
  /** Heading angle in degrees, 0 = North, clockwise */
  heading: number;
  /** Current vehicle state */
  state: VehicleState;
  /** Current lane identifier */
  lane_id: string;
  /** Cumulative time spent waiting (speed < 0.3 m/s), seconds */
  wait_time: number;
  /** Number of times vehicle came to a complete stop */
  stop_count: number;
  /** Elapsed simulation time in seconds */
  sim_time: number;
  /** Simulation tick counter */
  tick: number;
  /** Overall simulation lifecycle status */
  simulation_status: SimulationLifecycle;
}

// ── Simulation lifecycle ───────────────────────────────────────────────────

/**
 * Lifecycle status of the simulation engine.
 * Matches backend SimStatus literal type.
 */
export type SimulationLifecycle = 'stopped' | 'running' | 'completed';

/** Response from GET /api/simulation/status */
export interface SimulationStatusResponse {
  status: SimulationLifecycle;
  sim_time: number;
  tick: number;
  vehicle_state: VehicleState;
  message: string;
}

/** Response from POST /api/simulation/start | stop | reset */
export interface ControlResponse {
  status: SimulationLifecycle;
  message: string;
}

// ── Polling hook state ─────────────────────────────────────────────────────

/** All state returned by useSimulationPolling. */
export interface PollingState {
  /** Latest vehicle snapshot from the backend, or null if none yet */
  vehicle: SingleVehicleResponse | null;
  /** Current lifecycle status */
  status: SimulationLifecycle;
  /** True while waiting for first response or during start/stop operations */
  isLoading: boolean;
  /** Human-readable error string, or null if no error */
  error: string | null;
}

// ── Canvas viewport ────────────────────────────────────────────────────────

/**
 * Viewport parameters for coordinate mapping.
 * World space: X = East (meters), Y = North (meters).
 * Canvas space: X = right (pixels), Y = down (pixels).
 */
export interface Viewport {
  /** Canvas width in CSS pixels */
  canvasW: number;
  /** Canvas height in CSS pixels */
  canvasH: number;
  /** Pixels per meter (zoom factor) */
  ppm: number;
  /** World X coordinate shown at canvas center */
  centerWorldX: number;
  /** World Y coordinate shown at canvas center */
  centerWorldY: number;
}
