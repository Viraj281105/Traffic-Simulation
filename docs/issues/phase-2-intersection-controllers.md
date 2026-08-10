# Phase 2: Intersection & Controllers Issues

## ISSUE-018: Intersection Geometry and Approach Connector Mappings
- **Description**: Implement the `IntersectionGeometry` class in `backend/src/intersection/geometry.py` defining spatial bounds and entry/exit coordinates.
- **Objective**: Manage the physical layout of the intersection center point, approach arm connections, and lanes alignment.
- **Technical Background**: Serves as the central coordinate system. Maps 2D geometries (bounding circle radius, centers) and links approaching lanes to their corresponding exit lanes across the conflict center.
- **Acceptance Criteria**:
  *   Implement `IntersectionGeometry` initialized with center ($x, y$) and bounding radius.
  *   Define landing connection nodes: map approach lanes to crossing start points, and crossing end points to exit lanes.
  *   Provide a function: `is_within_intersection(x, y) -> bool` using circle geometry.
- **Dependencies**: ISSUE-011
- **Estimated Effort**: S
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 2`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.4.0 — Controllers`
- **Definition of Done**: Coordinate geometry checks pass unit testing, verifying boundary entry/exit detections.

---

## ISSUE-019: Conflict Zones and Collision Prevention Logic
- **Description**: Build the collision safety controller in `backend/src/intersection/conflict_zones.py` to identify intersecting vehicle paths.
- **Objective**: Detect overlap points between lane configurations (conflict zones) and insert deceleration constraints to prevent collisions.
- **Technical Background**: In a roundabout or signal-controlled intersection, paths cross. Vehicles must check if their intended path intersects with another vehicle's bounding box and decelerate if safety margins are violated.
- **Acceptance Criteria**:
  *   Implement `ConflictZoneDetector` mapping all physical conflict points (intersection paths).
  *   Provide a function: `check_conflicts(vehicle, active_vehicles) -> float` returning the safety gap to the nearest path competitor.
  *   Integrate safety margins: decelerate vehicle using IDM if another vehicle holds priority inside the path intersection box.
- **Dependencies**: ISSUE-012, ISSUE-013, ISSUE-018
- **Estimated Effort**: L
- **Priority**: Critical
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 2`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.4.0 — Controllers`
- **Definition of Done**: Multi-vehicle overlap simulations execute without collisions, asserting that priorities are respected at conflict zones.

---

## ISSUE-020: Abstract BaseController Interface
- **Description**: Define the `BaseController` abstract base class in `backend/src/controllers/base.py`.
- **Objective**: Establish the common interface for all intersection control strategies, enforcing uniform structures for updates and state outputs.
- **Technical Background**: Adheres to the Open-Closed Principle. The main engine references this class, permitting dynamic strategy injection (signals vs roundabouts) without loop modifications.
- **Acceptance Criteria**:
  *   Create `BaseController` using Python's `abc` module.
  *   Require methods: `update(delta_time, active_vehicles)`, `get_state() -> dict`, `reset()`.
  *   Add typing annotations matching the shared schemas.
- **Dependencies**: ISSUE-010, ISSUE-017
- **Estimated Effort**: S
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 2`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.4.0 — Controllers`
- **Definition of Done**: Code passes strict MyPy checks, and mock subclasses instantiate without errors.

---

## ISSUE-021: Fixed-Time Traffic Signal State Machine
- **Description**: Implement the `FixedTimeSignalController` state transitions in `backend/src/controllers/fixed_time_signal.py`.
- **Objective**: Handle timing sequences across signal phases (Green, Yellow, All-Red) for North-South and East-West approaches.
- **Technical Background**: The controller tracks phase progress. Transition sequences are loaded from config (e.g., greenTime, yellowTime, allRedTime) and ticked using the simulation clock.
- **Acceptance Criteria**:
  *   Implement `FixedTimeSignalController` subclassing `BaseController`.
  *   Manage phase cycle transitions: `ns_green` -> `ns_yellow` -> `all_red` -> `ew_green` -> `ew_yellow` -> `all_red`.
  *   Tick timings using `update(dt, vehicles)` and decrement phase timers.
- **Dependencies**: ISSUE-009, ISSUE-020
- **Estimated Effort**: M
- **Priority**: Critical
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 2`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.4.0 — Controllers`
- **Definition of Done**: State timings transition exactly to the decimal second when ticked through simulated runs.

---

## ISSUE-022: Fixed-Time Signal Head Control and Stop-Line Constraints
- **Description**: Integrate signal head indicators with approach lane stop-lines inside `FixedTimeSignalController`.
- **Objective**: Map active phases to lane indicators (Green, Yellow, Red) and update virtual leader obstacles to stop vehicles on Red/Yellow.
- **Technical Background**: Vehicles approaching a Red/Yellow signal must detect a virtual obstacle at the stop line, forcing IDM deceleration. Green signals remove this obstacle, permitting flow.
- **Acceptance Criteria**:
  *   Map signal phases to individual approach direction colors (`green`, `yellow`, `red`).
  *   Implement stop-line leader injection: when signal is Red/Yellow, place a virtual stationary leader ($v=0$) at the approach stop coordinate.
  *   When signal is Green, clear the stop obstacle.
- **Dependencies**: ISSUE-014, ISSUE-021
- **Estimated Effort**: M
- **Priority**: Critical
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 2`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.4.0 — Controllers`
- **Definition of Done**: Vehicles decelerate smoothly to a complete standstill behind red lights and accelerate when signals transition to green.

---

## ISSUE-023: Modern Roundabout Yield Line and Entering Logic
- **Description**: Implement roundabout entry control logic in `backend/src/controllers/roundabout.py`.
- **Objective**: Direct vehicle entries into the circular roadway, forcing approaching vehicles to yield to circulating vehicles.
- **Technical Background**: Roundabouts prioritize vehicles already circulating. Entering vehicles must check oncoming gaps in circulating lanes. If the gap is less than the `criticalGap` threshold, entry is blocked.
- **Acceptance Criteria**:
  *   Implement `RoundaboutController` subclassing `BaseController`.
  *   Define yielding areas at the entrance of each approach arm.
  *   Calculate time-gap clearances to approaching circulating vehicles.
  *   Inject virtual yield-line stop obstacles ($v=0$) when incoming gap is unsafe.
- **Dependencies**: ISSUE-014, ISSUE-019, ISSUE-020
- **Estimated Effort**: L
- **Priority**: Critical
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 2`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.4.0 — Controllers`
- **Definition of Done**: Vehicles yield at entry lines when circulating vehicles are within conflict bounds, entering only when safety gaps are met.

---

## ISSUE-024: Roundabout Circulating Speed and Lane Splines
- **Description**: Add circulating path equations and velocity overrides for vehicles within the roundabout circle.
- **Objective**: Guide vehicles along circular splines and restrict target speeds to the roundabout's design limit.
- **Technical Background**: Circulating vehicles travel along a circular path (inner/outer radius boundaries). Their physics model must transition from straight approach paths to circular coordinates, utilizing adjusted target speeds.
- **Acceptance Criteria**:
  *   Create path generator for the circulating circle lane.
  *   Override vehicle heading to match circular tangents based on polar coordinates.
  *   Enforce roundabout speed limit overrides (`circulatingSpeed`) on active vehicles within the circle.
- **Dependencies**: ISSUE-015, ISSUE-023
- **Estimated Effort**: M
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 2`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.4.0 — Controllers`
- **Definition of Done**: Vehicles transition smoothly from linear approaches to circular routes, maintaining configured roundabout target speeds.

---

## ISSUE-025: Centralized Controller Registry
- **Description**: Build the registry mapper class in `backend/src/controllers/registry.py`.
- **Objective**: Support dynamic instantiation of controllers based on configuration identifiers.
- **Technical Background**: Maps string keys (e.g. `"roundabout"`, `"fixed_time_signal"`) to class implementations using decorators, eliminating hardcoded imports inside the core engine.
- **Acceptance Criteria**:
  *   Create `ControllerRegistry` class and register decorator `@register_controller(type_name)`.
  *   Provide getter method `get_controller_class(type_name) -> Type[BaseController]`.
  *   Raise descriptive `ValueError` if a non-existent controller type is requested.
- **Dependencies**: ISSUE-021, ISSUE-023
- **Estimated Effort**: S
- **Priority**: Medium
- **Suggested Labels**: `type: refactor`, `scope: backend`, `phase: 2`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.4.0 — Controllers`
- **Definition of Done**: The simulation engine successfully instantiates signal and roundabout controllers dynamically via registry mappings.
