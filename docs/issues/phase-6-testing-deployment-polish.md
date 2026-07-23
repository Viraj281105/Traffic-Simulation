# Phase 6: Testing, Deployment & Polish Issues

## ISSUE-053: IDM Physics Engine Pytest Suite
- **Description**: Create comprehensive unit tests for the Intelligent Driver Model (IDM) in `backend/tests/unit/test_idm.py`.
- **Objective**: Verify that physical acceleration, braking gaps, and headway computations match expected mathematical targets.
- **Technical Background**: Tests must evaluate edge conditions: vehicles at rest, tailgating, emergency decelerations, and negative gaps. It should run over a matrix of configurations.
- **Acceptance Criteria**:
  *   Create unit tests verifying `calculate_acceleration()`.
  *   Test free-flow scenarios (acceleration converges to desired speed).
  *   Test car-following scenarios (deceleration gap spacing).
  *   Test collision avoidance boundaries (no vehicle crashes under standard deceleration bounds).
- **Dependencies**: ISSUE-013
- **Estimated Effort**: M
- **Priority**: High
- **Suggested Labels**: `type: test`, `scope: backend`, `phase: 6`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v1.0.0 — Final Release`
- **Definition of Done**: Tests pass, verifying that IDM equations behave correctly across a parameter sweep.

---

## ISSUE-054: Backend End-to-End Simulation Run Pytest Suite
- **Description**: Implement integration tests in `backend/tests/integration/test_simulation_run.py` executing a full simulation run.
- **Objective**: Verify that the simulation initializes, ticks, compiles metrics, and outputs results without runtime faults.
- **Technical Background**: Loads configuration templates from the `examples/configs/` folder and ticks the engine to completion, checking that final outputs conform to schemas.
- **Acceptance Criteria**:
  *   Create integration tests loading configurations from JSON files.
  *   Execute a complete run (e.g. 100 ticks) and assert final status is `completed`.
  *   Verify that final metrics payload is not empty and validates against schemas.
  *   Ensure exceptions in update loops are logged and status switches to `error`.
- **Dependencies**: ISSUE-010, ISSUE-017, ISSUE-026
- **Estimated Effort**: M
- **Priority**: High
- **Suggested Labels**: `type: test`, `scope: backend`, `phase: 6`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v1.0.0 — Final Release`
- **Definition of Done**: Pytest runs complete simulation cycles, asserting correctness of state maps and metrics summaries.

---

## ISSUE-055: Vitest Frontend Component and Hook Tests
- **Description**: Configure and write frontend tests using Vitest and React Testing Library.
- **Objective**: Test UI rendering, API call hooks, and playback control state updates.
- **Technical Background**: Verifies that components react correctly to mock state changes. Tests the `useWebSocket` hook by mocking WebSocket servers.
- **Acceptance Criteria**:
  *   Configure Vitest environment inside `vite.config.ts`.
  *   Write unit tests for `MetricCard` rendering.
  *   Write tests for `PlaybackControls` asserting button click callbacks.
  *   Mock WebSocket clients to verify snapshot parsing and error bounds.
- **Dependencies**: ISSUE-039, ISSUE-047
- **Estimated Effort**: M
- **Priority**: Medium
- **Suggested Labels**: `type: test`, `scope: frontend`, `phase: 6`
- **Suggested Assignee**: Frontend
- **Related Milestone**: `v1.0.0 — Final Release`
- **Definition of Done**: Vitest checks verify component behaviors, and test scripts report zero errors.

---

## ISSUE-056: End-to-End API Integration Tests
- **Description**: Build end-to-end integration tests using FastAPI's TestClient inside `backend/tests/integration/test_api_endpoints.py`.
- **Objective**: Verify HTTP routing and WebSocket streaming communication channels.
- **Technical Background**: Simulates HTTP client requests, testing post validations, control requests, and websocket upgrading.
- **Acceptance Criteria**:
  *   Initialize FastAPI TestClient.
  *   Test scenario validation endpoint `/configs/validate` with valid/invalid JSON structures.
  *   Test simulation creation `/simulations` and lifecycle actions `/simulations/{id}/control`.
  *   Assert websocket streams upgrade requests and yield valid JSON snapshots.
- **Dependencies**: ISSUE-038, ISSUE-054
- **Estimated Effort**: M
- **Priority**: High
- **Suggested Labels**: `type: test`, `scope: backend`, `phase: 6`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v1.0.0 — Final Release`
- **Definition of Done**: Test client successfully logs in, ticks simulations via websocket mock listeners, and asserts REST structures.

---

## ISSUE-057: Pydantic Model Serialization Optimization
- **Description**: Benchmark and optimize backend snapshot serialization speeds.
- **Objective**: Ensure that the time required to build and serialize a snapshot remains well under the tick interval (e.g. < 5ms).
- **Technical Background**: High vehicle counts increase serialization overhead. Standard JSON serializers can be slow in Python. Profiling will determine if custom serialization mappings or alternative encoders (like `orjson`) are needed.
- **Acceptance Criteria**:
  *   Implement serialization speed profiling scripts in `scripts/benchmark-serialization.py`.
  *   Benchmark serialization for simulations containing 100, 200, and 500 vehicles.
  *   Optimize Pydantic model configurations (e.g., using `.model_dump()` or pre-rendered dict structures).
  *   Ensure serialization finishes in under 5ms for 200 vehicles.
- **Dependencies**: ISSUE-033, ISSUE-054
- **Estimated Effort**: S
- **Priority**: Medium
- **Suggested Labels**: `type: perf`, `scope: backend`, `phase: 6`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v1.0.0 — Final Release`
- **Definition of Done**: Benchmark scripts run successfully, asserting target serialization speeds are met.

---

## ISSUE-058: HTML5 Canvas Rendering Optimization
- **Description**: Profile and optimize the frontend canvas rendering pipeline.
- **Objective**: Prevent rendering lag when drawing high vehicle counts, maintaining a stable 60 fps display rate.
- **Technical Background**: Canvas operations (like rotate, translate, and font rendering) can be slow. Offscreen canvas caching, bounding box clipping, and coordinate rounding will optimize rendering speeds.
- **Acceptance Criteria**:
  *   Profile render loop frame rates for simulations containing 200+ vehicles.
  *   Optimize path drawings: compile static road networks to an offscreen canvas and draw it as a single background image.
  *   Optimize vehicle renders: round rendering coordinates to avoid sub-pixel anti-aliasing calculations.
  *   Ensure rendering cycles take less than 10ms.
- **Dependencies**: ISSUE-045, ISSUE-046
- **Estimated Effort**: S
- **Priority**: Medium
- **Suggested Labels**: `type: perf`, `scope: frontend`, `phase: 6`
- **Suggested Assignee**: Frontend
- **Related Milestone**: `v1.0.0 — Final Release`
- **Definition of Done**: Profiling data shows average frame render durations remain under 10ms for 200 vehicles.

---

## ISSUE-059: Multi-Stage Dockerfile Configurations
- **Description**: Configure multi-stage Docker deployment setups for the backend and frontend.
- **Objective**: Create lightweight, reproducible container images to simplify deployment.
- **Technical Background**: The backend container installs Python packages and exposes FastAPI using Uvicorn. The frontend container uses Node to compile assets, serving static HTML/JS outputs via an Nginx web server.
- **Acceptance Criteria**:
  *   Create `backend/Dockerfile` using a lightweight Python image.
  *   Create `frontend/Dockerfile` using multi-stage builds (compiling React with Node, then deploying static assets to Nginx).
  *   Create `docker-compose.yml` orchestrating both containers on a shared network interface.
- **Dependencies**: ISSUE-035, ISSUE-039
- **Estimated Effort**: S
- **Priority**: Medium
- **Suggested Labels**: `type: chore`, `scope: ci-cd`, `phase: 6`
- **Suggested Assignee**: Both
- **Related Milestone**: `v1.0.0 — Final Release`
- **Definition of Done**: Running `docker-compose up` builds both images and starts the application stack successfully.

---

## ISSUE-060: Dashboard Reconnection Indicators and UI Polish
- **Description**: Polish the user interface, adding network indicators, dark mode layouts, and error toasts.
- **Objective**: Enhance the visual design and UX of the comparison dashboard.
- **Technical Background**: Uses CSS animations and toast notification modules. Displays prominent indicators for WebSocket status and shows clear overlay alerts when connections drop.
- **Acceptance Criteria**:
  *   Render WebSocket connectivity badges (Connected = green, Disconnected = red, Reconnecting = yellow).
  *   Implement error toast notifications for API failures (like invalid configurations).
  *   Apply consistent typography, subtle borders, and smooth hover animations.
- **Dependencies**: ISSUE-040, ISSUE-042
- **Estimated Effort**: S
- **Priority**: Medium
- **Suggested Labels**: `type: style`, `scope: frontend`, `phase: 6`
- **Suggested Assignee**: Frontend
- **Related Milestone**: `v1.0.0 — Final Release`
- **Definition of Done**: UI elements adapt correctly to connection states, and styling fits the dark/light design token system.

---

## ISSUE-061: Comparison Reports and Project Documentation
- **Description**: Complete comparison report templates and write final user guides in `docs/README.md`.
- **Objective**: Provide comprehensive guides for running simulations, analyzing metrics, and generating reports.
- **Technical Background**: Synthesizes engineering output, documenting simulation runs, parameters, and comparison metrics.
- **Acceptance Criteria**:
  *   Create user guide detailing how to build configurations, run UIs, and execute batch CLI commands.
  *   Provide a Markdown template for comparing fixed-time signals and roundabouts.
  *   Check in reference scripts in `scripts/` to generate comparison charts.
- **Dependencies**: ISSUE-004, ISSUE-060
- **Estimated Effort**: S
- **Priority**: Critical
- **Suggested Labels**: `type: documentation`, `scope: docs`, `phase: 6`
- **Suggested Assignee**: Both
- **Related Milestone**: `v1.0.0 — Final Release`
- **Definition of Done**: Documentation files are committed, and instructions are verified to be complete.
