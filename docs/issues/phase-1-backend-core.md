# Phase 1: Backend Core Issues

## ISSUE-009: Simulation Clock and Time Management Class
- **Description**: Implement a thread-safe simulation `Clock` class in `backend/src/core/clock.py` to manage elapsed time, ticks, and delta steps.
- **Objective**: Provide a consistent time-tracking source for the physics engine, metrics engine, and snapshot generator.
- **Technical Background**: The simulation advances in discrete steps (e.g., $dt = 0.1s$). The Clock tracks total elapsed simulation seconds, frame counts, and raw ticks, handling conversions between them.
- **Acceptance Criteria**:
  *   Implement `Clock` class with initialization options for `time_step` ($dt$).
  *   Provide methods: `tick() -> None` (advances clock), `reset() -> None`, `get_elapsed_time() -> float`, `get_tick_count() -> int`.
  *   Expose helper to convert seconds to ticks and vice-versa.
  *   Add unit tests verifying clock progression and resetting.
- **Dependencies**: ISSUE-007
- **Estimated Effort**: S
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 1`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.2.0 — Backend Core`
- **Definition of Done**: Pytest tests pass, code is fully typed with mypy passing, and Ruff lints successfully.

---

## ISSUE-010: Simulation Engine Lifecycle Controller and Tick Loop
- **Description**: Build the primary `SimulationEngine` class in `backend/src/core/engine.py` coordinating the loop execution and simulation status state machine.
- **Objective**: Manage the lifecycle transitions (`initializing` -> `running` -> `paused` -> `completed` / `error`) and drive the core tick loop.
- **Technical Background**: The engine drives all modules (roads, vehicles, intersection, metrics, snapshots) in order at each tick. The loop must support manual execution steps (single-tick advances) and run cycles (continuous execution).
- **Acceptance Criteria**:
  *   Implement `SimulationEngine` class managing a `SimulationStatus` enum.
  *   Implement `step() -> None` advancing the clock and ticking registered subsystems.
  *   Implement run/pause/resume/stop lifecycle functions thread-safely.
  *   Catch and handle run-time exceptions, transitioning status to `error`.
- **Dependencies**: ISSUE-009
- **Estimated Effort**: M
- **Priority**: Critical
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 1`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.2.0 — Backend Core`
- **Definition of Done**: Engine tests mock all sub-components, verify state machine transitions, and pass coverage guidelines.

---

## ISSUE-011: Approach and Lane Geometry Data Entities
- **Description**: Implement data models for `Approach` and `Lane` entities in `backend/src/roads/lane.py` and `approach.py` to represent road corridors.
- **Objective**: Store physical geometries (lengths, widths, start/end coordinates) and provide interfaces to track active vehicles in lanes.
- **Technical Background**: An approach arm (North, South, East, West) has a list of parallel lanes. Vehicles are associated with a single lane and follow its path geometry.
- **Acceptance Criteria**:
  *   Implement `Lane` entity storing coordinates (origin, destination), speed limit, and references to active vehicles.
  *   Implement `Approach` entity grouping multiple `Lane` instances by direction (enum).
  *   Provide helper functions to compute lane vectors, lane center lines, and vehicle spacing coordinates.
- **Dependencies**: ISSUE-007
- **Estimated Effort**: S
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 1`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.2.0 — Backend Core`
- **Definition of Done**: Unit tests verify lane coordinate geometry computations and active vehicle tracking structures.

---

## ISSUE-012: Road Network Graph Topology and Route Builder
- **Description**: Build the `RoadNetwork` class in `backend/src/roads/network.py` representing the complete intersection geometry and path topology.
- **Objective**: Interconnect lanes from approaches to conflict zones and exit directions, providing path lookup helpers for routing.
- **Technical Background**: The network acts as a directed graph where nodes are lanes and edges are lane connections. It builds connection paths (e.g. North approach Lane 1 turns left to East exit) based on geometry configurations.
- **Acceptance Criteria**:
  *   Implement `RoadNetwork` builder loading geometries from configurations.
  *   Compute lane routing paths for Left, Straight, and Right turns from all 4 approaches.
  *   Provide a function: `get_path(origin_direction, turn_intent) -> list[Lane]` returning the sequence of lanes to traverse.
- **Dependencies**: ISSUE-011
- **Estimated Effort**: M
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 1`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.2.0 — Backend Core`
- **Definition of Done**: Route builds return valid sequence of connected lanes for all directions and turn combinations.

---

## ISSUE-013: Intelligent Driver Model (IDM) Physics Engine
- **Description**: Implement the microscopic car-following logic using the Intelligent Driver Model (IDM) in `backend/src/vehicles/idm.py`.
- **Objective**: Calculate the instantaneous acceleration of a vehicle based on its current speed, the speed of the leading vehicle, and gap distance.
- **Technical Background**: IDM is a non-linear differential equation calculating acceleration as:
  $$a = a_0 \left[1 - \left(\frac{v}{v_0}\right)^\delta - \left(\frac{s^*(v, \Delta v)}{s}\right)^2\right]$$
  Where $s^*$ is the desired dynamic spacing. Hysteresis/limits must prevent division-by-zero or negative gaps.
- **Acceptance Criteria**:
  *   Implement `calculate_acceleration(vehicle, leader, gap) -> float` matching the IDM formula.
  *   Support configurable physics parameters: max acceleration ($a_0$), comfort deceleration ($b$), desired time headway ($T$), desired speed ($v_0$), minimum spacing ($s_0$), and delta exponent.
  *   Enforce absolute minimum limits to prevent infinite deceleration.
- **Dependencies**: ISSUE-007
- **Estimated Effort**: M
- **Priority**: Critical
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 1`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.2.0 — Backend Core`
- **Definition of Done**: Math tests verify acceleration results for standard scenarios (free-flow, following, emergency braking) match analytic profiles.

---

## ISSUE-014: Lane Joining and Conflict Queue Traversal Logic
- **Description**: Create helper logic in `backend/src/vehicles/router.py` to manage vehicle lane-changing, joining queues, and leader identification.
- **Objective**: Identify the leading vehicle for any vehicle, whether it is in the same lane, entering a conflict zone, or waiting at a roundabout entry.
- **Technical Background**: IDM physics requires a defined "leader" to calculate deceleration gaps. If a lane is empty, the leader might be a virtual vehicle representing a stop line or roundabout boundary.
- **Acceptance Criteria**:
  *   Implement `find_leader(vehicle, network) -> tuple[Vehicle | None, float]` returning the leading vehicle (if any) and the actual gap distance.
  *   Support virtual leader creation representing active red lights (zero-speed leader at stop line).
  *   Support virtual leader creation representing roundabout entry yield lines.
- **Dependencies**: ISSUE-012, ISSUE-013
- **Estimated Effort**: M
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 1`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.2.0 — Backend Core`
- **Definition of Done**: Leader assignment accurately switches from real vehicle to stop-lines as signals change colors.

---

## ISSUE-015: Vehicle Entity Data Model
- **Description**: Implement the `Vehicle` entity class in `backend/src/vehicles/vehicle.py` representing a single simulated vehicle.
- **Objective**: Manage coordinates, speed, acceleration, dimension parameters, lane associations, routing states, and cumulative stats counters.
- **Technical Background**: Vehicles are ticked on every frame. They store coordinates ($x, y$), current speed ($v$), heading angle, and tracking states (e.g. cumulative wait time, stop counter) updated at each step.
- **Acceptance Criteria**:
  *   Define `Vehicle` class initialized with a unique ID, lane path, dimensions (length, width), and speed profiles.
  *   Implement `update_state(acceleration, dt) -> None` advancing speed and spatial coordinates along its lane sequence.
  *   Add properties to check vehicle boundaries (bounding box coordinates).
  *   Expose state-transition helpers: `transition_to(vehicle_state)`.
- **Dependencies**: ISSUE-009, ISSUE-011
- **Estimated Effort**: S
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 1`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.2.0 — Backend Core`
- **Definition of Done**: Entity states update correctly in time steps, and coordinate bounds math passes tests.

---

## ISSUE-016: Poisson Process Vehicle Spawner
- **Description**: Build the `VehicleSpawner` class in `backend/src/vehicles/spawner.py` handling vehicle generation on approach lanes.
- **Objective**: Generate new vehicles at approaches using a Poisson arrival process configured by splits and random seeds.
- **Technical Background**: Arrival rates are modeled as exponential distributions ($t_{next} = -\ln(u)/\lambda$). Spawning must respect minimum headway clearances to prevent overlaps at lane entrances.
- **Acceptance Criteria**:
  *   Implement `VehicleSpawner` with arrival distribution types (`poisson`, `uniform`).
  *   Use locked random number generators initialized with the config's `randomSeed`.
  *   Enforce safety distance checks: do not spawn a vehicle if the tail of the preceding vehicle is closer than `minimumGap + vehicleLength`.
- **Dependencies**: ISSUE-012, ISSUE-015
- **Estimated Effort**: M
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 1`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.2.0 — Backend Core`
- **Definition of Done**: Chi-square tests verify that vehicle spawning intervals follow Poisson profiles across runs.

---

## ISSUE-017: Active Vehicle Pool Manager
- **Description**: Implement the `VehiclePool` class in `backend/src/vehicles/pool.py` managing the active vehicle collection.
- **Objective**: Handle vehicle additions (spawns), updates, and removal (exits), exposing collections for metrics computations.
- **Technical Background**: Tracks vehicles currently on the road network. When a vehicle passes the end of its exit lane, it must be removed from the active loop and cataloged in the exited list.
- **Acceptance Criteria**:
  *   Implement `VehiclePool` managing collections of active and exited vehicles.
  *   Implement `update(dt, engine) -> None` driving vehicle updates, leader mappings, and removing vehicles that traverse past exit boundaries.
  *   Provide active count summaries categorized by direction and current vehicle state (enum).
- **Dependencies**: ISSUE-014, ISSUE-015, ISSUE-016
- **Estimated Effort**: M
- **Priority**: Critical
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 1`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.2.0 — Backend Core`
- **Definition of Done**: Simulation successfully tracks, moves, and cleanses 100+ vehicles over multiple ticks without leaks.
