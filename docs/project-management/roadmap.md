# Milestone Roadmap: Traffic Intersection Control Comparison Framework

This document outlines the complete milestone roadmap for the **Traffic Intersection Control Comparison Framework**. Each milestone represents a logical development phase containing specific targets, deliverables, exit criteria, and suggested issues to track in GitHub.

---

## Milestone 1: Phase 0 — Repository Setup & Docs
*   **Purpose**: Establish monorepo structure, review rules, static code analyzers, and centralize documentation.
*   **Description**: Prepares the project workspace with necessary boilerplate, sets up linting and formatting tooling (Ruff, ESLint, Prettier), and establishes the automated schema validation script to ensure contract stability from day one.
*   **Target Deliverables**:
    *   Root directories, `.gitignore`, and `.github/CODEOWNERS`.
    *   Validation script `scripts/validate-schemas.sh`.
    *   Linter configurations in `backend/pyproject.toml` and `frontend/eslint.config.js`.
    *   Synchronized Markdown specs for architecture, contracts, metrics, and APIs.
*   **Exit Criteria**:
    *   All baseline specifications are merged with mutual approvals from Developer A and B.
    *   Pre-commit configurations prevent committing unformatted or schema-failing JSON payloads.
*   **Dependencies**: None.
*   **Estimated Duration**: 3 days.
*   **Recommended Completion Order**: 
    1. Initialize repository structure and CODEOWNERS.
    2. Configure static analysis configs for backend and frontend.
    3. Implement validation scripts.
    4. Sync architecture specifications.
*   **Suggested GitHub Issues**: ISSUE-001, ISSUE-002, ISSUE-003, ISSUE-004, ISSUE-005, ISSUE-006, ISSUE-007, ISSUE-008.

---

## Milestone 2: Backend Core
*   **Purpose**: Establish core data models and helper structures for roads and vehicles.
*   **Description**: Creates the baseline classes to manage physical traffic elements. This includes defining Approach and Lane coordinates, building topology configurations for intersections, and setting up the Vehicle entity class to store positions, speed, and tracking counters.
*   **Target Deliverables**:
    *   `Lane` and `Approach` geometric entities (`backend/src/roads/`).
    *   `Vehicle` spatial entity models with state tracking enums (`backend/src/vehicles/`).
*   **Exit Criteria**:
    *   Unit tests verify correct coordinate math for approach lane lines and vehicle boundary boxes.
    *   Type safety validation passes under strict MyPy checks.
*   **Dependencies**: Milestone 1.
*   **Estimated Duration**: 4 days.
*   **Recommended Completion Order**:
    1. Define `Lane` and `Approach` structures.
    2. Develop `Vehicle` spatial entity model and speed update methods.
*   **Suggested GitHub Issues**: ISSUE-011, ISSUE-015.

---

## Milestone 3: Simulation Engine
*   **Purpose**: Build the discrete-time clock loop and vehicle spawning system.
*   **Description**: Develops the orchestration engine of the simulator. Implements the clock class for time conversion, the core `SimulationEngine` state loop, and the Poisson-process vehicle spawner that generates arrivals based on random seeds.
*   **Target Deliverables**:
    *   `Clock` time manager (`backend/src/core/clock.py`).
    *   `SimulationEngine` loop driver and status transitions (`backend/src/core/engine.py`).
    *   `VehicleSpawner` supporting Poisson and uniform arrival distributions (`backend/src/vehicles/spawner.py`).
    *   `VehiclePool` active collections manager (`backend/src/vehicles/pool.py`).
*   **Exit Criteria**:
    *   Simulation engine runs and ticks to completion, spawning and removing vehicles based on configurations.
    *   Spawning arrival intervals pass statistical validation checks (matching target Poisson parameters).
*   **Dependencies**: Milestone 2.
*   **Estimated Duration**: 5 days.
*   **Recommended Completion Order**:
    1. Implement `Clock` class.
    2. Build `SimulationEngine` skeleton.
    3. Develop `VehicleSpawner` and `VehiclePool` active tracker.
*   **Suggested GitHub Issues**: ISSUE-009, ISSUE-010, ISSUE-012, ISSUE-014, ISSUE-016, ISSUE-017.

---

## Milestone 4: Traffic Controllers (Intersection Logic & Physics)
*   **Purpose**: Implement IDM physics, path conflict zone checking, and abstract controller interfaces.
*   **Description**: Integrates the vehicle car-following physics (Intelligent Driver Model) and implements the base class for intersection controllers. Solves path collision checking by injecting virtual obstacles at conflict zones.
*   **Target Deliverables**:
    *   `IDMModel` physics formulas (`backend/src/vehicles/idm.py`).
    *   `BaseController` abstract interface (`backend/src/controllers/base.py`).
    *   `ConflictZoneDetector` safety boundaries checker (`backend/src/intersection/conflict_zones.py`).
*   **Exit Criteria**:
    *   Vehicles accelerate and decelerate safely following IDM formulas without crashes.
    *   Mock controllers successfully intercept vehicles at simulated conflict zones.
*   **Dependencies**: Milestone 3.
*   **Estimated Duration**: 5 days.
*   **Recommended Completion Order**:
    1. Implement IDM physics formulas.
    2. Define `BaseController` abstract interface.
    3. Build conflict zone overlap detection algorithms.
*   **Suggested GitHub Issues**: ISSUE-013, ISSUE-018, ISSUE-019, ISSUE-020.

---

## Milestone 5: Traffic Controllers (Control Strategies)
*   **Purpose**: Implement Fixed-Time Signal and Roundabout control strategies.
*   **Description**: Build the two target comparison controllers. The fixed-time signal cycles phases (Green, Yellow, Red) and injects stop obstacles. The roundabout controller manages entrance yield checks using critical time-gaps.
*   **Target Deliverables**:
    *   `FixedTimeSignalController` state transitions (`backend/src/controllers/fixed_time_signal.py`).
    *   `RoundaboutController` entries yielding checker (`backend/src/controllers/roundabout.py`).
    *   Centralized `ControllerRegistry` class decorator mapper (`backend/src/controllers/registry.py`).
*   **Exit Criteria**:
    *   Signal timings transition exactly according to configurations, stopping vehicles on Red/Yellow.
    *   Roundabout vehicles yield correctly at yield lines to circulating cars and enter circle paths dynamically.
*   **Dependencies**: Milestone 4.
*   **Estimated Duration**: 6 days.
*   **Recommended Completion Order**:
    1. Implement Fixed-Time Signal timing transition loop.
    2. Build signal stop-line obstacle injection.
    3. Implement Roundabout yielding checking.
    4. Write roundabout circular trajectory overrides.
    5. Register all classes in the centralized registry.
*   **Suggested GitHub Issues**: ISSUE-021, ISSUE-022, ISSUE-023, ISSUE-024, ISSUE-025.

---

## Milestone 6: Metric Engine
*   **Purpose**: Build metric calculators for operational efficiency and traffic flow quality.
*   **Description**: Implements the metrics collection framework. Calculates average wait time, throughput, rolling rates, queue length statistics, stop counters (with hysteresis), speed variance, travel reliability, directional fairness, and capacity wastage.
*   **Target Deliverables**:
    *   `MetricCollector` aggregator with warmup duration filters (`backend/src/metrics/collector.py`).
    *   Metric calculators for wait times, queue lists, stops, reliability indexes, and Jain's fairness index.
*   **Exit Criteria**:
    *   Metric calculations return validated numbers matching analytical test fixtures.
    *   Warmup time filter discards metrics logged during startup cycles.
*   **Dependencies**: Milestone 5.
*   **Estimated Duration**: 6 days.
*   **Recommended Completion Order**:
    1. Build `MetricCollector` base database and warmup filters.
    2. Implement wait time and throughput math.
    3. Develop queue statistics and stop count hysteresis trackers.
    4. Implement speed variance, PTI, fairness index, and idle loss calculations.
*   **Suggested GitHub Issues**: ISSUE-026, ISSUE-027, ISSUE-028, ISSUE-029, ISSUE-030, ISSUE-031, ISSUE-032.

---

## Milestone 7: API Layer
*   **Purpose**: Develop REST endpoints and WebSocket stream routes in FastAPI.
*   **Description**: Exposes the backend engine to network clients. Creates REST routes for validating scenarios, registering simulation instances, managing playback state, and querying final reports. Implements a WebSocket channel to stream live snapshots.
*   **Target Deliverables**:
    *   FastAPI application setup with CORS middleware configurations (`backend/src/main.py`).
    *   REST routes for validation, creation, playback control, and reports.
    *   WebSocket upgrade handler streaming real-time JSON frames (`backend/src/api/websocket/stream.py`).
*   **Exit Criteria**:
    *   STAT REST API handles inputs, rejecting invalid configurations with schema validation codes.
    *   WebSocket streams serialized snapshot JSONs at target frequencies (e.g. 10 Hz) and exits cleanly.
*   **Dependencies**: Milestone 6.
*   **Estimated Duration**: 5 days.
*   **Recommended Completion Order**:
    1. Set up FastAPI boot configurations and error middleware.
    2. Implement scenario validation and simulation creation REST routes.
    3. Develop lifecycle control endpoints.
    4. Build WebSocket streaming loops.
*   **Suggested GitHub Issues**: ISSUE-035, ISSUE-036, ISSUE-037, ISSUE-038.

---

## Milestone 8: Frontend Foundation
*   **Purpose**: Initialize the Vite React TS dashboard project and client connection utilities.
*   **Description**: Sets up the React client framework. Defines visual CSS tokens (dark mode styles, status colors), implements the HTTP API client wrapper, and builds a robust WebSocket service managing reconnect backoffs.
*   **Target Deliverables**:
    *   Vite React TypeScript setup with strict compiler configs (`frontend/`).
    *   Global design system styling tokens and page grids.
    *   HTTP REST client services (`frontend/src/services/apiClient.ts`).
    *   WebSocket connection manager with connection state callbacks.
*   **Exit Criteria**:
    *   Frontend compiles with zero warnings, showing the blank dashboard shell.
    *   WebSocket service connects to backend stream, validating schema major compatibility.
*   **Dependencies**: Milestone 7.
*   **Estimated Duration**: 4 days.
*   **Recommended Completion Order**:
    1. Run Vite React TS bootstrap.
    2. Set up layout templates and CSS tokens.
    3. Implement REST API Client.
    4. Implement WebSocket client with reconnect backoffs.
*   **Suggested GitHub Issues**: ISSUE-039, ISSUE-040, ISSUE-041, ISSUE-042.

---

## Milestone 9: Visualization
*   **Purpose**: Build HTML5 Canvas rendering engine and vehicle animations.
*   **Description**: Implements the live simulation visualizer. Set up coordinate converters (meters to pixels), pan/zoom controls, static road layout overlays, vehicle boxes, and signal indicators.
*   **Target Deliverables**:
    *   `SimulationCanvas` HTML5 viewport manager (`frontend/src/simulation/SimulationCanvas.tsx`).
    *   Road network graphics overlays drawing lane dividers and yield indicators.
    *   Vehicle draw utilities with rotations matching heading vectors.
*   **Exit Criteria**:
    *   Road assets render cleanly matching configured lane dimensions.
    *   Active vehicles animate smoothly on the viewport matching coordinate updates.
*   **Dependencies**: Milestone 8.
*   **Estimated Duration**: 5 days.
*   **Recommended Completion Order**:
    1. Create HTML5 Canvas component and viewport transformers.
    2. Develop static road overlay draw functions.
    3. Implement vehicle rectangles and heading rotations.
*   **Suggested GitHub Issues**: ISSUE-043, ISSUE-044, ISSUE-045.

---

## Milestone 10: Analytics Dashboard (Live Views & Charts)
*   **Purpose**: Develop live chart components and layout cards.
*   **Description**: Integrates reporting components into the dashboard. Displays metrics summary cards (throughput, wait time averages) and plots running queues or wait distributions using visual line and bar charts.
*   **Target Deliverables**:
    *   Dashboard layouts grouping Canvas, Charts, and Metrics.
    *   Summary metric cards displaying real-time aggregated parameters.
    *   Live charts (using Chart.js or Recharts) plotting rolling metrics.
*   **Exit Criteria**:
    *   Metrics dashboard matches layout tokens, rendering active cards clearly.
    *   Line and bar charts update data sets on metrics ticks without leaking memory.
*   **Dependencies**: Milestone 9.
*   **Estimated Duration**: 5 days.
*   **Recommended Completion Order**:
    1. Build Metric summary layout cards.
    2. Integrate Chart.js component containers.
    3. Connect snapshot metric arrays to chart data plots.
*   **Suggested GitHub Issues**: ISSUE-051, ISSUE-052.

---

## Milestone 11: Integration (Configuration & Playback UI)
- **Purpose**: Wire configuration validation forms, client-side interpolation, and timeline scrubbers.
- **Description**: Connects all individual modules end-to-end. Creates input forms for custom scenarios, maps validation error overlays, adds client-side frame interpolation for smooth 60fps rendering, and builds playback controls with back-scrubbing history timeline sliders.
- **Target Deliverables**:
  *   Scenario configuration editor forms with validation warnings panels.
  *   Client-side interpolation updates (`frontend/src/simulation/interpolation.ts`).
  *   Playback control panel (play, pause, step, speed toggles) with timeline scrubber sliders.
- **Exit Criteria**:
  *   Frontend configuration forms validate and initialize runs on the backend.
  *   Visual animations display 60fps smoothing using frame interpolation.
  *   Timeline sliders allow backward and forward scrubbing through simulation runs.
- **Dependencies**: Milestone 10.
- **Estimated Effort / Duration**: 6 days.
- **Recommended Completion Order**:
  1. Build scenario configuration forms and error banners.
  2. Implement client-side frame interpolation buffers.
  3. Integrate playback control triggers.
  4. Write timeline slider history scrubbers.
- **Suggested GitHub Issues**: ISSUE-034, ISSUE-046, ISSUE-047, ISSUE-048, ISSUE-049, ISSUE-050.

---

## Milestone 12: Testing (Pytest, Vitest, E2E)
- **Purpose**: Enforce system testing constraints on physics, REST/WS routes, and React components.
- **Description**: Implements validation test sweeps. Writes unit and integration tests for IDM vehicle physics, full simulation executions, FastAPI route clients, and Vitest visual component actions.
- **Target Deliverables**:
  *   Pytest unit suites for physics model validations (`backend/tests/unit/test_idm.py`).
  *   Backend integration tests checking complete simulation runs.
  *   FastAPI TestClient suites verifying REST/WS endpoints.
  *   Vitest UI component tests verifying client click controls.
- **Exit Criteria**:
  *   All backend unit and integration tests pass with coverage exceeding 80% on core loops.
  *   API clients handle validations and WebSocket upgrades without errors in automated tests.
  *   Vitest checks pass with zero warnings.
- **Dependencies**: Milestone 11.
- **Estimated Effort / Duration**: 5 days.
- **Recommended Completion Order**:
  1. Develop unit tests for IDM physics formulas.
  2. Write backend integration run check scripts.
  3. Write TestClient tests for FastAPI routers.
  4. Develop Vitest component mock tests.
- **Suggested GitHub Issues**: ISSUE-053, ISSUE-054, ISSUE-055, ISSUE-056.

---

## Milestone 13: Performance Optimization & Deployment
- **Purpose**: Benchmark serialization, optimize canvas rendering, and configure Docker containers.
- **Description**: Profiles bottlenecks in high-load scenarios. Optimizes Pydantic serializer loops to run in under 5ms, optimizes canvas drawings via offscreen overlays, and prepares multi-stage Dockerfiles with Nginx static proxies.
- **Target Deliverables**:
  *   Serialization profiling scripts and optimized Pydantic dict dumps.
  *   Offscreen canvas background caching templates.
  *   Multi-stage `Dockerfile` structures for Python and React deployments.
  *   `docker-compose.yml` orchestrating the runtime stack.
- **Exit Criteria**:
  *   Backend serialization takes less than 5ms for 200 active vehicles.
  *   Frontend canvas renders frames in under 10ms.
  *   `docker-compose up` builds and deploys the entire application stack.
- **Dependencies**: Milestone 12.
- **Estimated Effort / Duration**: 4 days.
- **Recommended Completion Order**:
  1. Benchmark and optimize Python JSON serialization.
  2. Implement offscreen canvas path caching.
  3. Author backend and frontend Dockerfiles.
  4. Create orchestration docker-compose files.
- **Suggested GitHub Issues**: ISSUE-057, ISSUE-058, ISSUE-059.

---

## Milestone 14: Documentation & Final Demonstration
- **Purpose**: Write user manuals, comparative metrics reports, and polish visual status indicators.
- **Description**: Finalizes the project lifecycle. Adds network indicators (WebSocket status logs), designs comparative report templates comparing signals against roundabouts, and documents setup and running instructions in user guides.
- **Target Deliverables**:
  *   Connectivity indicators and error toast notifications.
  *   Complete user guide and CLI run manuals.
  *   Comparative metrics Markdown reports comparing intersection efficiency.
- **Exit Criteria**:
  *   UI displays real-time connection badges and shows clear alerts on disconnect.
  *   Documentation files are complete and check in successfully.
- **Dependencies**: Milestone 13.
- **Estimated Effort / Duration**: 3 days.
- **Recommended Completion Order**:
  1. Polish connection UI indicators and error toast notifications.
  2. Author final user manual.
  3. Draft comparison report templates.
- **Suggested GitHub Issues**: ISSUE-060, ISSUE-061.
