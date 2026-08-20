# Shared Contracts Layer

This directory serves as the **single source of truth** for all data contracts, schemas, and API communication payloads between the Backend (Simulation Engine) and the Frontend (Visualization Dashboard).

To ensure strict decoupling, it contains **zero executable code**. It defines structural formats in programming language-independent formats (JSON Schema), allowing both Python and TypeScript components to serialize, deserialize, and validate payloads reliably.

**Owners:** Joint ownership — modifications require mutual agreement between Backend and Frontend engineers.

---

## Folder Organization

```
shared/
├── schemas/
│   ├── config.schema.json        # Structural specification for Simulation Scenario Config
│   ├── snapshot.schema.json      # Structural specification for Real-time Simulation Engine Snapshot
│   └── vehicle_state.json        # Structural specification for individual vehicle telemetry states
└── README.md                     # This documentation file
```

---

## Schema Architecture & Data Contracts

### 1. Scenario Configuration Schema (`config.schema.json`)

Defines the parameters needed to initialize, customize, and save a simulation run.

- **Intersection Layout Settings**:
  - `lanes_north`, `lanes_south`, `lanes_east`, `lanes_west` (integer): The number of incoming lanes for each approach.
  - `lane_width` (number): Lane width in meters (default is 3.5m).
  - `intersection_size` (number): Size of the central conflict zone box.
- **Simulation Controls**:
  - `seed` (integer): Random number generator seed for deterministic and reproducible runs.
  - `time_step` (number): Update delta time ($\Delta t$) per simulation tick (typically 0.1s for 10Hz updates).
  - `max_duration` (number): Maximum running time in simulation seconds.
- **Physics and Car-Following Parameters (Intelligent Driver Model)**:
  - `desired_speed` ($v_0$): Ideal target speed on clear lanes.
  - `safe_time_gap` ($T$): Preferred time headway behind leading cars.
  - `max_acceleration` ($a$): Maximum vehicle acceleration power.
  - `comfortable_deceleration` ($b$): Preferred braking rate.
  - `min_gap` ($s_0$): Minimum static safety margin spacing.

### 2. Real-Time Snapshot Schema (`snapshot.schema.json`)

Defines the state payload broadcasted by the backend at 10Hz over WebSockets to feed the visualization engine:

- **Global Context**:
  - `simulation_id` (string): UUID of the active run.
  - `tick` (integer): Monotonically increasing tick counter.
  - `sim_time` (number): Cumulative simulation elapsed time in seconds.
  - `status` (string): State of the simulation runtime lifecycle (e.g., `running`, `paused`, `completed`, `error`).
- **Vehicle Telemetry Collection**:
  - Contains an array of active vehicle states conforming to the vehicle state sub-schema.
- **Infrastructure Phase States**:
  - Traffic light active indexes, time remaining on the active phase, and signal statuses for signalized intersections.

### 3. Vehicle State Schema (`vehicle_state.json`)

Defines properties tracked for each active vehicle:

- `vehicle_id` (string): Unique identifier.
- `position_x`, `position_y` (numbers): Coordinates in meters relative to the intersection center $(0,0)$.
- `speed` (number): Instantaneous velocity in m/s.
- `acceleration` (number): Instantaneous acceleration in $m/s^2$.
- `lane_id` (string): Identifier of the lane currently occupied.
- `heading` (number): Orientation angle in radians (0 to $2\pi$).

---

## Schema Validation Workflow

To prevent integration failures, all configuration files, REST requests, and WebSocket messages must be validated against these JSON Schemas.

A Python-based validation utility is available to test schemas against mock samples:

- Execution Script: [`scripts/validate_schemas.py`](../scripts/validate_schemas.py)
- Command Line Run:
  ```bash
  python scripts/validate_schemas.py
  ```
- Shell Script Runner (automated via CI/CD):
  ```bash
  ./scripts/validate-schemas.sh
  ```
