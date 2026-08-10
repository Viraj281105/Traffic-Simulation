# Phase 5: Visualization & Dashboard Issues

## ISSUE-043: HTML5 Canvas Viewport and Scale Handler
- **Description**: Build the core `SimulationCanvas` React component in `frontend/src/simulation/SimulationCanvas.tsx` handling 2D viewports.
- **Objective**: Establish the 2D rendering area, translate coordinate systems (meters to pixels), and handle zoom/pan inputs.
- **Technical Background**: The simulation coordinates use meters. The canvas translates these coordinates to screen pixels using a scale factor (`pixelsPerMeter`, default 3.0). It updates dimensions on resize triggers.
- **Acceptance Criteria**:
  *   Create `SimulationCanvas` component using HTML5 2D context.
  *   Implement coordinate conversions: `metersToPixels(x, y)` and `pixelsToMeters(x, y)`.
  *   Support panning (dragging) and zooming (mouse wheel scaling).
  *   Ensure the canvas center matches the intersection's center coordinate.
- **Dependencies**: ISSUE-040
- **Estimated Effort**: M
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: frontend`, `phase: 5`
- **Suggested Assignee**: Frontend
- **Related Milestone**: `v0.3.0 — Frontend Core`
- **Definition of Done**: Canvas draws grid lines that scale and translate correctly during user pan and zoom interactions.

---

## ISSUE-044: Road Network Geometry and Lane Overlay Renderer
- **Description**: Add drawing handlers to render approaches, lanes, lane dividers, and exit boundaries on the canvas.
- **Objective**: Draw static road outlines and lane guides accurately from the config.
- **Technical Background**: Reads configuration dimensions (approachLength, laneWidth, lanesPerApproach) to construct parallel road corridors extending in all 4 directions.
- **Acceptance Criteria**:
  *   Render road outlines (pavements) in dark gray.
  *   Draw white dashed lines separating lanes in the same direction, and solid yellow lines separating opposing corridors.
  *   Draw yield/stop lines at approach mouths.
  *   Render the central intersection boundary box/circle.
- **Dependencies**: ISSUE-043
- **Estimated Effort**: M
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: frontend`, `phase: 5`
- **Suggested Assignee**: Frontend
- **Related Milestone**: `v0.3.0 — Frontend Core`
- **Definition of Done**: Canvas correctly renders intersection lanes, matching configured counts (e.g. 2-lane vs 4-lane layouts).

---

## ISSUE-045: Canvas Vehicle Renderer and Heading Rotation
- **Description**: Implement vehicle drawing functions in `frontend/src/simulation/vehicleRenderer.ts`.
- **Objective**: Render active vehicles as oriented rectangles colored by their physical states.
- **Technical Background**: Vehicles are drawn using their coordinates ($x, y$), width, and length. They must be rotated using 2D transformation matrices matching the heading angle (degrees clockwise from North).
- **Acceptance Criteria**:
  *   Draw vehicles as rectangles centered on their coordinates.
  *   Apply rotation: use `ctx.rotate(heading)` to align drawing angles.
  *   Color vehicles by state (approaching = blue, waiting = red, crossing = green, roundabout = orange).
  *   (Optional) Render ID tag overlay if `showVehicleIds` is enabled.
- **Dependencies**: ISSUE-043
- **Estimated Effort**: M
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: frontend`, `phase: 5`
- **Suggested Assignee**: Frontend
- **Related Milestone**: `v0.3.0 — Frontend Core`
- **Definition of Done**: Vehicles are drawn with correct heading alignments, matching their movement directions without offset glitches.

---

## ISSUE-046: Client-Side Frame Interpolation Engine
- **Description**: Build an interpolation utility in `frontend/src/simulation/interpolation.ts` to smooth vehicle animations.
- **Objective**: Fill in positions between 10 Hz snapshots to output a smooth 60 fps visual display.
- **Technical Background**: WebSockets transmit snapshots at 10 Hz. Displaying them directly causes jerky movements. The client maintains a buffer of two frames ($F_0$ and $F_1$) and computes intermediate positions:
  $$P(t) = P_0 + (P_1 - P_0) \times \alpha$$
  Where $\alpha$ is the elapsed fraction.
- **Acceptance Criteria**:
  *   Implement buffer holding the last two received snapshots.
  *   Calculate interpolation offsets based on local animation frame clocks.
  *   Render interpolated coordinates instead of raw snapshot coordinates.
  *   Gracefully fall back to snapping if network delays exceed timeout thresholds (e.g. 200ms).
- **Dependencies**: ISSUE-042, ISSUE-045
- **Estimated Effort**: L
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: frontend`, `phase: 5`
- **Suggested Assignee**: Frontend
- **Related Milestone**: `v0.3.0 — Frontend Core`
- **Definition of Done**: Visual animations display smooth, jitter-free movements, even when socket intervals contain minor delay variations.

---

## ISSUE-047: Playback Lifecycle Control Panel
- **Description**: Build the `PlaybackControls` React component in `frontend/src/components/PlaybackControls.tsx`.
- **Objective**: Render buttons to trigger simulation runs (Play, Pause, Step, Stop) and speed adjustment dropdowns.
- **Technical Background**: Control actions are sent to the REST API. Speed multipliers (0.5x, 1.0x, 2.0x, 5.0x) modify the backend's tick speed or the client's frame skip factors.
- **Acceptance Criteria**:
  *   Render control buttons: Play/Pause (toggle), Step Forward (1 frame), Stop/Reset.
  *   Map actions to backend HTTP endpoints.
  *   Add speed multiplier selector.
  *   Display current run progress (slider timeline) and elapsed seconds.
- **Dependencies**: ISSUE-041, ISSUE-046
- **Estimated Effort**: S
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: frontend`, `phase: 5`
- **Suggested Assignee**: Frontend
- **Related Milestone**: `v0.3.0 — Frontend Core`
- **Definition of Done**: Control panels correctly toggle simulation states, and UI states (disabled/active buttons) reflect engine conditions.

---

## ISSUE-048: Playback Scrubbing and Timeline Slider
- **Description**: Add timeline scrubbing features to the playback control panel.
- **Objective**: Enable the user to scrub backward and forward through the simulation run.
- **Technical Background**: When a simulation is paused, the client can scrub by sending specific frame queries to the backend's snapshot history buffer, or by rendering cached snapshots stored in local arrays.
- **Acceptance Criteria**:
  *   Implement slider mapped to current tick / total ticks.
  *   Scrubbing updates the canvas visualization to show historical vehicle coordinates.
  *   Disable real-time socket listeners while scrubbing history.
  *   Resume simulation from the selected tick on play.
- **Dependencies**: ISSUE-034, ISSUE-047
- **Estimated Effort**: M
- **Priority**: Medium
- **Suggested Labels**: `type: feature`, `scope: frontend`, `phase: 5`
- **Suggested Assignee**: Frontend
- **Related Milestone**: `v0.6.0 — Integration`
- **Definition of Done**: Users can scrub the slider to review past simulation states, and canvas drawings update instantly.

---

## ISSUE-049: Scenario Configuration Form Builder
- **Description**: Create the configuration designer component in `frontend/src/pages/ScenarioConfigPage.tsx`.
- **Objective**: Expose input forms mapping scenario options (traffic flows, geometry parameters, physics) to construct configurations.
- **Technical Background**: Configurations are built by binding HTML forms to JSON keys matching `config.schema.json`. Sensible defaults are loaded by query wrappers.
- **Acceptance Criteria**:
  *   Create inputs for arrivalRate, duration, lanes, speed limits.
  *   Expose conditional parameters: render green time fields only if `fixed_time_signal` is selected, and roundabout radii only if `roundabout` is selected.
  *   Add "Submit to Run" button converting form states to JSON configurations.
- **Dependencies**: ISSUE-041
- **Estimated Effort**: L
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: frontend`, `phase: 5`
- **Suggested Assignee**: Frontend
- **Related Milestone**: `v0.6.0 — Integration`
- **Definition of Done**: Forms correctly assemble config JSON payloads, reflecting correct parameters for both control systems.

---

## ISSUE-050: Schema Validation Error Visualizer
- **Description**: Implement a validation error visualizer component within the scenario config page.
- **Objective**: Display schema errors returned by the API validation endpoint, highlighting offending fields.
- **Technical Background**: When config validation fails, the backend returns JSON path errors. The client must highlight the target form inputs and display descriptive warnings.
- **Acceptance Criteria**:
  *   Catch validation error codes from API.
  *   Map error paths (e.g. `simulation.duration`) to specific form fields.
  *   Render red validation messages near invalid inputs.
  *   Block submission if validation errors are unresolved.
- **Dependencies**: ISSUE-049
- **Estimated Effort**: S
- **Priority**: Medium
- **Suggested Labels**: `type: feature`, `scope: frontend`, `phase: 5`
- **Suggested Assignee**: Frontend
- **Related Milestone**: `v0.6.0 — Integration`
- **Definition of Done**: Submitting out-of-bounds parameters (like negative green times) flags fields red, showing details of the validation error.

---

## ISSUE-051: Real-Time Charts Component Integration
- **Description**: Implement line and bar chart components in `frontend/src/charts/LiveCharts.tsx`.
- **Objective**: Plot running metrics (such as wait times, queue lengths, and throughput rates) dynamically during simulation runs.
- **Technical Background**: Integrates a charting library (like Chart.js or Recharts). Feeds metrics arrays from snapshot stream history into chart datasets, updating data plots at regular intervals (e.g. 1 Hz).
- **Acceptance Criteria**:
  *   Set up Chart.js (or Recharts) canvases.
  *   Render Live Queue Length line chart (queues over time per approach).
  *   Render Live Wait Time bar chart comparing approach averages.
  *   Optimally throttle chart updates (e.g. once per second) to preserve browser performance.
- **Dependencies**: ISSUE-040, ISSUE-042
- **Estimated Effort**: M
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: frontend`, `phase: 5`
- **Suggested Assignee**: Frontend
- **Related Milestone**: `v0.5.0 — Metrics`
- **Definition of Done**: Live charts plot rolling metric values, updating dynamically without browser memory leaks.

---

## ISSUE-052: Metrics Dashboard Cards and Side-by-Side Comparison Layout
- **Description**: Build the dashboard metrics viewport in `frontend/src/pages/DashboardPage.tsx`.
- **Objective**: Display metrics summary cards and configure comparison views comparing signal and roundabout runs side-by-side.
- **Technical Background**: Creates layout containers holding metric cards (average wait time, stops, throughput) alongside comparison grids.
- **Acceptance Criteria**:
  *   Render 6 primary metric cards with status icons (e.g. average wait time, total stops).
  *   Create a dual layout allowing users to compare snapshots of a signal run alongside a roundabout run.
  *   Display delta percentages (e.g. "Roundabout average wait time was 12% lower").
- **Dependencies**: ISSUE-040, ISSUE-051
- **Estimated Effort**: L
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: frontend`, `phase: 5`
- **Suggested Assignee**: Frontend
- **Related Milestone**: `v0.6.0 — Integration`
- **Definition of Done**: Dashboard layout fits the canvas, live cards, and charts in a structured screen view, with comparison summaries compiling delta percentages correctly.
