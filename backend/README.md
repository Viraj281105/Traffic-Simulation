# Simulation Backend & Engine

The simulation backend is a high-performance Python 3.11+ application. It features a physics-based simulation engine utilizing the **Intelligent Driver Model (IDM)**, custom traffic intersection controllers, live metrics collection, persistent SQLite storage, and a FastAPI wrapper providing REST controls and WebSocket streams.

**Owner:** Viraj Jadhao (Simulation/Data)
**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Pydantic, SQLite, Pytest

---

## Directory Organization & Module Architecture

```
backend/
├── src/
│   ├── core/                     # Core orchestrator and simulation engine
│   │   ├── clock.py              # Discrete time stepper (dt steps)
│   │   ├── config_models.py      # Scenario validation models (Pydantic schemas)
│   │   ├── engine.py             # Main execution loop, spawning, and updates
│   │   └── enums.py              # Status enums (Running, Paused, etc.)
│   ├── controllers/              # Intersection flow controllers
│   │   ├── base.py               # Abstract base class for controllers
│   │   ├── fixed_time_signal.py  # Standard cyclic traffic signal phase generator
│   │   ├── roundabout.py         # Yield-at-entry circular controller
│   │   └── registry.py           # Controller instantiation mapper
│   ├── database/                 # SQLite storage layer
│   │   ├── db.py                 # SQLite engine & session generators
│   │   ├── dao.py                # Database Access Object for runs & configs
│   │   └── sweep_runner.py       # Parameter sweep scripting across volumes
│   ├── intersection/             # Spatial intersection geometries
│   │   ├── conflict_zones.py     # Yielding points and overlaps prevention
│   │   └── geometry.py           # Coordinate converters and intersections
│   ├── roads/                    # Topological road definitions
│   │   ├── approach.py           # N/S/E/W entry/exit roads
│   │   ├── lane.py               # Spatially oriented driving lanes
│   │   └── network.py            # Complete graph representing the junction
│   ├── snapshot/                 # Simulation state serialization
│   │   ├── buffer.py             # Windowed cache storing historical snapshots
│   │   ├── builder.py            # Assembles snapshot models from live components
│   │   ├── serializer.py         # Encodes snapshots to JSON compatible schemas
│   │   └── dual_orchestrator.py  # Lockstep runner for side-by-side comparisons
│   ├── vehicles/                 # Vehicle modeling & routing
│   │   ├── idm.py                # Intelligent Driver Model math equations
│   │   ├── pool.py               # Active vehicles manager (spawns & exits)
│   │   ├── router.py             # Maps vehicles to valid origin-destination paths
│   │   ├── spawner.py            # Poisson/Uniform vehicle generation queues
│   │   └── vehicle.py            # Instantiated vehicle parameters and telemetry
│   ├── metrics/                  # Statistical collection and winners evaluation
│   │   ├── definitions/          # Standardized metric formulas
│   │   │   ├── fairness.py       # Directional Fairness Index (DFI)
│   │   │   ├── idle_loss.py      # Idle Opportunity Loss calculation
│   │   │   ├── new_metrics.py    # Extended statistics (utilization, saturation)
│   │   │   ├── queue_length.py   # Mean & Max Queue Sizes
│   │   │   ├── speed_variance.py # Velocity variability checks
│   │   │   ├── stop_count.py     # Hysteresis-based vehicle stops count
│   │   │   ├── throughput.py     # Total vehicles cleared per time window
│   │   │   ├── travel_time.py    # Mean travel time & travel reliability index
│   │   │   └── wait_time.py      # Delay time spent below 1.0 m/s threshold
│   │   ├── collector.py          # Central aggregator computing periodic metrics
│   │   └── efficiency.py         # Normalized Master Efficiency Score calculator
│   └── main.py                   # FastAPI routing, app bootsrapper, & socket server
├── tests/                        # Comprehensive unit & system test packages
├── requirements.txt              # Production pip dependencies
├── pyproject.toml                # Project configurations and black/ruff configurations
└── Dockerfile                    # Containerization instructions
```

---

## Core Simulation Submodules

### 1. Physics Modeling (IDM)

The longitudinal vehicle kinematics are governed by the **Intelligent Driver Model (IDM)**, which updates vehicle speed $v$ and position $x$ dynamically at each step:
$$\frac{dv}{dt} = a \left[ 1 - \left(\frac{v}{v_0}\right)^\delta - \left(\frac{s^*(v, \Delta v)}{s}\right)^2 \right]$$
Where:

- $v_0$ is the desired speed.
- $s$ is the actual distance to the leading vehicle.
- $s^*(v, \Delta v) = s_0 + v T + \frac{v \Delta v}{2\sqrt{a b}}$ is the dynamic desired spacing.
- $a$ is maximum acceleration, and $b$ is comfortable deceleration.

### 2. Intersection Controllers

- **Fixed-Time Signal Control (`fixed_time_signal.py`)**: Rotates through standard phases (`NS_Green` -> `NS_Yellow` -> `AllRed` -> `EW_Green` -> `EW_Yellow` -> `AllRed`) utilizing predefined time offsets.
- **Roundabout Control (`roundabout.py`)**: Models yield-at-entry circular gap acceptance. Vehicles check circulating traffic spacing and speed before committing to cross the entry line.

### 3. Snapshot Builder & Dual Orchestrator

- **State Snapshots**: Periodically captures the physical coordinates, velocities, and light statuses at 10Hz and validates the output against `shared/schemas/snapshot.schema.json`.
- **Lockstep Dual Simulation**: Runs the Fixed-Time and Roundabout simulation engines concurrently. Both engines consume identical seed streams ensuring the exact same vehicle generation intervals for mathematical parity.

---

## Database Schema & Volume Sweep Runs

The database is built on SQLite (`simulation.db`) using raw SQL scripts managed by `DAO`:

- **`configurations` Table**: Stores validated configuration JSON models.
- **`simulation_runs` Table**: Records metadata (seed, controller type, status, simulation time, duration).
- **`run_metrics` Table**: Keeps historical logs of the 10 performance metrics.

### Automated Sweeper Script

To perform a sensitivity analysis across arrival rates ($0.1, 0.3, 0.5, 0.7$ vehicles/sec):

```bash
python -m src.database.sweep_runner
```

This stores all resulting metrics back to SQLite for comparisons.

---

## Setup & Execution Guide

### Local Installation

1. Navigate to the backend folder:
   ```bash
   cd backend
   ```
2. Initialize virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # Windows
   # source .venv/bin/activate     # macOS/Linux
   ```
3. Install project dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Execution

Run the FastAPI Web API:

```bash
python -m src.main
```

The API becomes available at `http://localhost:8000`. Interactive API Docs are served at `http://localhost:8000/docs`.

### Testing

Execute unit tests:

```bash
python -m pytest
```

---

## API Documentation

### REST Control Endpoints

- `POST /api/simulation/new`: Starts a new single-vehicle tracking simulation run using the input configuration.
- `POST /api/simulation/start`: Activates the polling engine clock.
- `POST /api/simulation/stop`: Pauses the running simulation engine.
- `POST /api/simulation/reset`: Reinitializes the simulation state.
- `POST /api/simulation/dual/play`: Boots lockstep dual simulations.
- `POST /api/simulation/dual/pause`: Pauses lockstep dual simulations.
- `POST /api/simulation/dual/reset`: Recreates both roundabout and signal configurations.

### WebSockets Stream Endpoints

- `WS /ws/simulation/live`: Standard single-vehicle snapshot stream.
- `WS /ws/simulation/dual`: Side-by-side comparative snapshots stream broadcasted at 10Hz.
