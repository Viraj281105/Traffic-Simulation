# Phase 4: API & Frontend Foundation Issues

## ISSUE-035: FastAPI App Initialization and Global Error Middleware
- **Description**: Configure the main FastAPI application in `backend/src/main.py` and global exception middleware handlers in `backend/src/api/middleware/error_handler.py`.
- **Objective**: Establish the web server, configure CORS permissions, and build structured error response formats.
- **Technical Background**: The API handles CORS settings for React communication. The global exception middleware catches standard errors and maps them to JSON objects matching `errors.schema.json`.
- **Acceptance Criteria**:
  *   Initialize FastAPI app with versioning prefix `/api/v1`.
  *   Configure CORS middleware allowing localhost origins (React dev server).
  *   Implement custom exception handler for HTTP validation errors and internal server faults.
  *   Return error structures conforming to `errors.schema.json`.
- **Dependencies**: ISSUE-007
- **Estimated Effort**: S
- **Priority**: Critical
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 4`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.2.0 — Backend Core`
- **Definition of Done**: Accessing `/api/v1/health` returns healthy statuses, and invalid queries trigger structured validation errors.

---

## ISSUE-036: Configuration Validation and Creation REST Endpoints
- **Description**: Implement scenario configuration validation and simulation creation routes in `backend/src/api/routes/scenarios.py` and `simulation.py`.
- **Objective**: Provide REST endpoints to validate scenario files and register simulation instances.
- **Technical Background**: The validation endpoint checks payloads against `config.schema.json`. The creation endpoint instantiates the engine state and maps a unique `simulationId` using Pydantic models.
- **Acceptance Criteria**:
  *   Implement `POST /api/v1/configs/validate` endpoint returning validation statuses and schema errors.
  *   Implement `POST /api/v1/simulations` endpoint accepting scenario configs, initializing engines, and returning unique IDs.
  *   Apply configurations to simulation managers thread-safely.
- **Dependencies**: ISSUE-006, ISSUE-010, ISSUE-035
- **Estimated Effort**: M
- **Priority**: Critical
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 4`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.2.0 — Backend Core`
- **Definition of Done**: Postman/Swagger requests successfully validate configuration objects and register simulation IDs.

---

## ISSUE-037: Simulation Lifecycle Control and Final Metrics REST Endpoints
- **Description**: Build simulation playback control routes and summary metrics query routes.
- **Objective**: Expose controls for starting, pausing, resuming, and stopping active simulations, and retrieve final metrics reports.
- **Technical Background**: Exposes control signals matching actions (`start`, `pause`, `resume`, `stop`). The metrics route returns finalized comparison tables once execution terminates.
- **Acceptance Criteria**:
  *   Implement `POST /api/v1/simulations/{id}/control` supporting valid actions and executing state overrides on the engine.
  *   Implement `GET /api/v1/simulations/{id}` returning status percentages and ticks.
  *   Implement `GET /api/v1/simulations/{id}/metrics` returning final statistics.
- **Dependencies**: ISSUE-026, ISSUE-036
- **Estimated Effort**: M
- **Priority**: Critical
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 4`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.2.0 — Backend Core`
- **Definition of Done**: Control endpoints trigger appropriate lifecycle shifts, and metrics routes return aggregated objects.

---

## ISSUE-038: WebSocket Real-Time Snapshot Stream Route
- **Description**: Create the WebSocket route handler in `backend/src/api/routes/stream.py` to stream frames.
- **Objective**: Broadcast state snapshots to clients at the configured frequency.
- **Technical Background**: Connection upgrades are routed to `/ws/v1/stream?simulationId={id}`. The socket loop pushes snapshots while the simulation is running and handles disconnect flags cleanly.
- **Acceptance Criteria**:
  *   Implement WebSocket endpoint upgrades.
  *   Verify connection query contains active `simulationId`.
  *   Push serialized JSON snapshots using Uvicorn's event loop at target rates (e.g. 10 Hz).
  *   Gracefully close socket when simulation completes, aborts, or client disconnects.
- **Dependencies**: ISSUE-033, ISSUE-037
- **Estimated Effort**: M
- **Priority**: Critical
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 4`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.2.0 — Backend Core`
- **Definition of Done**: WebSocket streams state frames smoothly, terminating without server-side socket leakage.

---

## ISSUE-039: Vite React TypeScript Project Initialization
- **Description**: Bootstrap the React application inside the `frontend/` folder.
- **Objective**: Setup Vite tools, verify compiler rules, and establish build scripts.
- **Technical Background**: Initializes dependencies (React, TS, Vite, CSS layers). Standardizes package outputs and verifies project compiles cleanly with strict flags.
- **Acceptance Criteria**:
  *   Run project bootstrap creating `package.json`, `tsconfig.json`, and `vite.config.ts`.
  *   Install React, TypeScript, and developer support configurations.
  *   Configure build scripts (`npm run build`, `npm run dev`, `npm run preview`).
- **Dependencies**: ISSUE-008
- **Estimated Effort**: S
- **Priority**: High
- **Suggested Labels**: `type: chore`, `scope: frontend`, `phase: 4`
- **Suggested Assignee**: Frontend
- **Related Milestone**: `v0.3.0 — Frontend Core`
- **Definition of Done**: Running `npm run build` compiles with zero errors, outputting assets into the dist folder.

---

## ISSUE-040: UI Design System Tokens and Layout Setup
- **Description**: Set up global styles, Tailwind CSS or CSS variables, and layout structures in the frontend.
- **Objective**: Define consistent theme variables (colors, spacing, fonts) and construct the primary dashboard shell.
- **Technical Background**: Implements a high-quality dashboard template. Configures CSS parameters (dark mode colors, grid parameters, typography specs) and designs the main header and content columns.
- **Acceptance Criteria**:
  *   Define styling tokens inside `frontend/src/styles/variables.css` (primary, secondary, status colors).
  *   Create page layout container `frontend/src/layouts/DashboardLayout.tsx` providing grid areas for Canvas, Metrics, and Controls.
  *   Ensure UI is responsive (adjusting scale on smaller displays).
- **Dependencies**: ISSUE-039
- **Estimated Effort**: S
- **Priority**: High
- **Suggested Labels**: `type: style`, `scope: frontend`, `phase: 4`
- **Suggested Assignee**: Frontend
- **Related Milestone**: `v0.3.0 — Frontend Core`
- **Definition of Done**: Dashboard layout loads with correct style formatting on local browser server.

---

## ISSUE-041: Frontend API Client Service
- **Description**: Implement HTTP REST service functions in `frontend/src/services/apiClient.ts` to query the backend.
- **Objective**: Create wrappers for config validation, simulation registration, lifecycle execution, and final report fetching.
- **Technical Background**: Utilizes Fetch or Axios to construct API calls. Includes parsing and mapping returned payloads into TypeScript interfaces.
- **Acceptance Criteria**:
  *   Create `apiClient` service configured with base URL `http://localhost:8000/api/v1`.
  *   Expose functions: `validateConfig()`, `createSimulation()`, `sendControlAction()`, `getFinalMetrics()`.
  *   Handle HTTP request failures, logging errors to user-facing notification hooks.
- **Dependencies**: ISSUE-036, ISSUE-037, ISSUE-040
- **Estimated Effort**: S
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: frontend`, `phase: 4`
- **Suggested Assignee**: Frontend
- **Related Milestone**: `v0.3.0 — Frontend Core`
- **Definition of Done**: API functions execute calls and resolve typescript-typed response payloads.

---

## ISSUE-042: Frontend WebSocket Connection Service and Reconnect Strategy
- **Description**: Implement the real-time WebSocket client in `frontend/src/services/websocketClient.ts` or custom hooks.
- **Objective**: Handle connection updates, snapshot parsing, and automatic reconnection limits.
- **Technical Background**: Maintains state hooks for socket connectivity. Implements exponential backoff reconnect logic if the socket drops unexpectedly.
- **Acceptance Criteria**:
  *   Implement connection handler accepting `simulationId`.
  *   Parse incoming payloads, validating compatibility using `schemaVersion`.
  *   Expose state hooks: `isConnected`, `latestSnapshot`, `connectionError`.
  *   Reconnection handler tries up to 5 times with growing delay steps.
- **Dependencies**: ISSUE-038, ISSUE-041
- **Estimated Effort**: M
- **Priority**: Critical
- **Suggested Labels**: `type: feature`, `scope: frontend`, `phase: 4`
- **Suggested Assignee**: Frontend
- **Related Milestone**: `v0.3.0 — Frontend Core`
- **Definition of Done**: Reconnection scripts attempt connection recovery, and version mismatches throw controlled alert cards.
