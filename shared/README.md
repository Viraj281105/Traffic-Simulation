# Shared Contracts Layer

This directory contains the JSON Schema files shared by the backend and frontend. The backend loads `config.schema.json` to validate scenario configurations; the snapshot and vehicle schemas document payload shapes but are not applied to every WebSocket frame.

To ensure strict decoupling, it contains **zero executable code**. It defines structural formats in programming language-independent formats (JSON Schema), allowing both Python and TypeScript components to serialize, deserialize, and validate payloads reliably.

**Owners:** Joint ownership — modifications require mutual agreement between Backend and Frontend engineers.

---

## Folder Organization

```
shared/
├── schemas/
│   ├── config.schema.json        # Structural specification for Simulation Scenario Config
│   ├── snapshot.schema.json      # Structural specification for Real-time Simulation Engine Snapshot
│   ├── vehicle_state.json        # Structural specification for individual vehicle telemetry states
│   ├── v2/                       # V2.0 decision support, calibration, and network document schemas
│   │   ├── calibration-observations.schema.json
│   │   ├── calibration-options.schema.json
│   │   ├── network.schema.json
│   │   ├── planning-report.schema.json
│   │   └── planning-study.schema.json
│   └── v3/                       # V3.0 Robustness Lab experiment, uncertainty, and OpenAPI contracts
│       ├── experiment.schema.json
│       ├── openapi.v3.snapshot.json
│       └── uncertainty-spec.schema.json
└── README.md                     # This documentation file
```

---

## Schema Architecture & Data Contracts

| Schema | Describes | Enforced at runtime? |
| --- | --- | --- |
| `config.schema.json` | Scenario configuration: `simulation`, `traffic`, `geometry`, `roads`, `vehicleGeneration`, `controller`, `metrics`, `visualization` | **Yes** — `POST /api/v1/configs/validate`, `POST /api/v1/simulations`, and the compiled live-dashboard configuration (`backend/src/main.py`). The backend refuses to start if it is missing. |
| `snapshot.schema.json` | The streamed snapshot: `schemaVersion`, `simulationId`, `configId`, `timestamp`, `frameNumber`, `tick`, `wallClockTime`, `samplingFrequency`, `deltaTime`, `warmupTime`, `simulationStatus`, `vehicles`, `intersection`, `controller`, `metrics`, `vehicleCounts`, `units` | Documented contract; checked by backend contract tests (`tests/integration/test_snapshot_contract.py`), not on every frame |
| `vehicle_state.json` | The legacy single-vehicle demo payload (`vehicle_id`, `position`, `x`, `y`, `speed`, `acceleration`, `heading`, `state`, `lane_id`) served by `/api/simulation/single-vehicle` | Documented only |
| `v2/planning-study.schema.json` | V2.0 decision-support planning study input format (`/api/v2/planning`) | **Yes** — validated on study submission |
| `v2/planning-report.schema.json` | V2.0 decision-support study findings, indicators, and comparison report schema | Documented contract; verified by planning test suite |
| `v2/calibration-*.schema.json` | V1.8 calibration observed counts and comparison options (`/api/v2/calibration`) | **Yes** — validated on calibration submission |
| `v2/network.schema.json` | V1.9 multi-junction network document specification (`/api/v2/networks`) | **Yes** — validated and fingerprinted on compilation |
| `v3/experiment.schema.json` | V3.0 Robustness Lab experiment document specification (`/api/v3/experiments`) | **Yes** — validated by `tests/experiments/test_contract.py` and preparation layer |
| `v3/uncertainty-spec.schema.json` | V3.0 parameter uncertainty specification (factors, conditions, replications) | **Yes** — validated on experiment submission |
| `v3/openapi.v3.snapshot.json` | Frozen OpenAPI specification snapshot for `/api/v3` endpoints | Checked by contract tests; regenerated via `src.experiments.export_schemas` |

Key configuration fields (full reference: [docs/simulation/configuration.md](../docs/simulation/configuration.md), field-by-field: [docs/architecture/06-scenario-configuration-contract.md](../docs/architecture/06-scenario-configuration-contract.md)):

- `simulation.duration` (required), `timeStep`, `warmupTime`, `randomSeed`, `snapshotFrequency`
- `geometry.intersectionType` (required): `fixed_time_signal` or `roundabout`
- `roads.approachLength`, `laneWidth`, `lanesPerApproach` (one integer for all approaches), `speedLimit`
- `traffic.arrivalRate`, `arrivalDistribution`, `totalVehicles`, `directionalSplit`, `turnProbabilities`
- IDM parameters under `vehicleGeneration`: `maxAcceleration` (a), `comfortDeceleration` (b), `desiredTimeHeadway` (T), `minimumGap` (s₀), `idmDelta` (δ), plus `desiredSpeed` / `vehicleLength` / `vehicleWidth` ranges
- `controller`: signal timings (`straightRightDuration`, `nsGreenDuration`, `ewGreenDuration`, `yellowDuration`, `allRedDuration`, `phaseSequence`, `offset`) and roundabout parameters (`innerRadius`, `outerRadius`, `criticalGap`, `followUpTime`, `entrySpeed`, `circulatingSpeed`)

The snapshot's camelCase field names are what the backend actually emits; see the [API reference §8](../docs/api/README.md#8-websockets).

---

## Schema Validation Workflow

To check the schema files themselves, run the repository validator. It verifies that each top-level JSON file in `shared/schemas/` is well-formed JSON and has a `$schema` field; it does not validate arbitrary captured API messages or test against mock samples (payload validation is performed by the backend contract test suites).

- Execution Script: [`scripts/validate_schemas.py`](../scripts/validate_schemas.py)
- Command Line Run:
  ```bash
  python scripts/validate_schemas.py
  ```
- Shell Script Runner (automated via CI/CD):
  ```bash
  ./scripts/validate-schemas.sh
  ```
