# Simulation Backend & Engine

This folder contains the core simulation engine, traffic physics modeling (IDM), intersection controllers, metrics collection systems, SQLite storage, and the FastAPI REST/WebSocket API wrapper.

**Owner:** Viraj Jadhao (Simulation/Data)
**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Pydantic, SQLite, Pytest

---

## Features

### 1. Physics & Model (IDM)
*   **Intelligent Driver Model (IDM)**: Realistic longitudinal vehicle kinematics, handling safe-spacing, deceleration bounds, and acceleration tapers.
*   **Conflict Zones & Spawners**: Dynamic vehicle spawner with Poisson/Uniform rates and route selection. Yielding logic prevents collisions under conflicting paths.

### 2. Intersection Controllers
*   **Fixed-Time Signal Control**: Cycles through phases (`NS_Green` -> `NS_Yellow` -> `AllRed` -> `EW_Green` -> `EW_Yellow` -> `AllRed`) according to predefined time intervals.
*   **Roundabout Control**: Gap acceptance controller utilizing critical gaps, follow-up times, entry speeds, and circulating radius tangent vectors for layout coordination.

### 3. Dual-Simulation Orchestrator
*   Supports launching parallel Fixed-Time and Roundabout simulations side-by-side using the exact same random seed for identical traffic streams.
*   WS stream broadcasts dual snapshots at **10Hz** for comparative visual playback.

### 4. Metrics Collector
*   **Operational Efficiency**: Average Wait Time (crawler limit < 1.0 m/s), Throughput, Queue Length Stats.
*   **Traffic Flow Quality**: Hysteresis-based Stop Counts, Speed Variance Index, Travel Time Reliability.
*   **System Performance**: Idle Opportunity Loss, Critical Saturation Volume, Intersection Utilization %.
*   **Fairness & Stability**: Directional Fairness Index (DFI), Queue Stability Index (QSI).
*   **Space / Footprint Consumed**: Roundabout circle area ($\pi r^2$) vs. Signal conflict box area.
*   **Master Efficiency Score**: Normalizes and weights all key metrics into a single unified performance score (0.0 to 100.0) for winner evaluation.

### 5. Persistent SQLite Layer
*   Database tables for `configurations`, `simulation_runs`, and `run_metrics` with full transactional integrity and rollback handling.
*   **Volume Sweep Runner**: Automation to execute runs across a gradient of arrival rates (`0.1`, `0.3`, `0.5`, `0.7`) and store the resulting data in `simulation.db` for post-run analysis.

---

## Setup & Running

Ensure you have Python 3.11+ installed.

1.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the API Server locally**:
    ```bash
    python -m src.main
    ```
    The server will start at `http://localhost:8000`. Interactive Swagger docs are available at `http://localhost:8000/docs`.

3.  **Run the Volume Sweep script**:
    ```bash
    python -m src.database.sweep_runner
    ```

4.  **Run test suites**:
    ```bash
    python -m pytest
    ```

---

## API Endpoints

### REST API
*   `POST /api/simulation/new` (or `POST /api/v1/simulations`): Validates incoming JSON configs using Pydantic validation and initializes a new simulation run. Returns `simulationId` and `configId`.
*   `POST /api/v1/simulations/{id}/control`: Play (`start`), pause (`pause`), or stop (`stop`) simulation cycles.
*   `GET /api/v1/simulations/{id}/report`: Exports run summary report in CSV or JSON formats.
*   `POST /api/simulation/dual/play`: Starts parallel dual runs.
*   `POST /api/simulation/dual/pause`: Pauses parallel dual runs.
*   `POST /api/simulation/dual/reset`: Recreates and resets dual parallel engines under matching seeds.
*   `GET /api/simulation/dual/status`: Returns current progress, tick, and status of the dual orchestrator.

### WebSockets
*   `WS /ws/v1/stream?simulationId={id}`: Streams real-time snapshots of the specified run.
*   `WS /ws/simulation/live`: Streams live snapshots of the active demo simulation.
*   `WS /ws/simulation/dual`: Streams parallel lockstep snapshots of the dual comparative run.
