# ADR-006: Scenario Configuration Format

## Status

Accepted

## Date

2026-07-23

## Context

To perform a fair comparison between the traffic control strategies, we must run them under identical scenario conditions (e.g., matching traffic arrival rates, lane counts, vehicle physical dimensions, speed limits, and simulation seeds). 

A simulation run is initialized using a configuration document. This configuration must specify parameters across multiple domains:
*   **Simulation Parameters**: Duration, timestep ($dt$), random seed, snapshot frequency.
*   **Traffic Demand**: Total vehicles to spawn, Poisson arrival rate, directional split, turn probabilities.
*   **Intersection Geometry**: Type (fixed-time signal vs. roundabout) and center coordinates.
*   **Road Geometry**: Approach arm length, lane width, lanes per approach, speed limits.
*   **Physics Constraints**: Intelligent Driver Model (IDM) parameters (max acceleration, comfort deceleration, desired time headway, etc.).
*   **Controller Parameters**: Controller-specific settings (e.g., green times for signals, critical gap for roundabouts).
*   **Metric / Visualization Preferences**: Sampling rate, canvas scale, color schemes.

We must select the data format and validation mechanism for this configuration.

## Problem Statement

What format and structure should be used for scenario configurations to ensure they:
1.  Are easy for humans to read and write (for manual scenario design)?
2.  Are easy for frontend forms to generate and backend servers to parse?
3.  Support strict validation of types, limits (e.g., positive speed limits, probabilities summing to 1.0), and structures before a simulation starts?
4.  Allow different properties based on the selected intersection type (discriminated union for controller parameters)?
5.  Guarantee simulation reproducibility?

## Decision

We will use **JSON** as the canonical format for all scenario configurations, validated using **JSON Schema (Draft 2020-12)**.

1.  **Schema Definition**: The contract is defined in `shared/schemas/config.schema.json`.
2.  **Schema Features**:
    *   *Sensible Defaults*: To make configuration creation simple, the schema defines default values for almost every field. A minimal JSON document containing only `{ "geometry": { "intersectionType": "roundabout" } }` is completely valid.
    *   *Discriminated Union*: The `controller` section of the config is dynamically validated based on the `geometry.intersectionType` value using JSON Schema's `oneOf` and `if/then` constructs. If the type is `fixed_time_signal`, green/yellow times are validated. If it is `roundabout`, inner/outer radii are validated.
    *   *Numeric Bounds*: Constraints (e.g., `minimum: 0`, `maximum: 1.0` for splits) are strictly enforced.
3.  **Reproducibility**: The configuration schema includes a mandatory/defaulted `randomSeed` integer. If the seed is provided, the backend's random number generator (for Poisson vehicle spawning and turning intents) is locked to that seed, guaranteeing that two separate runs with the same config will behave identically.

```
                      Scenario Configuration File (.json)
                                      │
                   Validated against config.schema.json
                                      ▼
                      ┌───────────────┴───────────────┐
                      ▼                               ▼
               Web API Request                  Local File Load
            (FastAPI / Pydantic)              (CLI / Batch Run)
```

## Alternatives Considered

### Alternative 1: YAML (YAML Ain't Markup Language)
YAML is often preferred for configuration files because it supports comments and has a cleaner syntax than JSON.
*   *Why it was rejected:* Browsers do not parse YAML natively. In a client-server architecture where the frontend constructs configurations in a web form, the configuration must be serialized to JSON anyway for transmission. Forcing the backend to accept YAML requires translating API payloads to YAML structures and adding YAML parsing dependencies to both React and Python. We chose JSON for its native compatibility with both ends. (Comments in configurations can be handled via separate metadata fields if necessary).

### Alternative 2: XML (Extensible Markup Language)
Use XML schemas (XSD) to define configuration parameters.
*   *Why it was rejected:* XML is excessively verbose, has poor readability for complex nested lists (like lane overrides), and requires heavy, non-native parsing libraries in JavaScript. JSON has emerged as the modern standard for configuration exchange in web architectures.

### Alternative 3: Flat Key-Value Formats (e.g., `.ini`, `.env` files)
Use a flat properties file format.
*   *Why it was rejected:* Flat structures do not support nested object trees. Defining per-lane geometries, multi-phase sequences, or turn probability splits in a flat file requires ugly string serialization hacks within keys (e.g., `roads.north.lane.1.speed_limit = 13.89`), which are difficult to validate and parse.

## Trade-offs

### Pros
*   **API Native:** The configuration can be pasted directly into a Swagger UI or sent via standard REST requests without conversion.
*   **Strict Verification:** The schema automatically catches user inputs that fall outside valid ranges (e.g., green light times of negative duration) before the backend attempts to compile road networks.
*   **Form Mapping:** In React, standard libraries can automatically generate interactive configuration forms directly from the `config.schema.json` file.

### Cons
*   **No Comments:** Standard JSON does not allow comments. To explain configuration parameters, developers must refer to `shared/config/README.md`.
*   **Verbose Syntax:** Writing nested JSON structures manually in a text editor requires matching brackets and commas, which is slightly more error-prone than YAML.

## Consequences

*   The backend config loader (`backend/src/config/loader.py`) must resolve default values and validate incoming configs against the schema.
*   If a configuration contains invalid data, the API will return a structured JSON response containing the exact path of the invalid field and the validation error message.
*   Example configurations (e.g., `examples/configs/high_traffic.json`) must be checked in the test suite to ensure they remain compatible with schema updates.

## Future Considerations

If human-authored YAML configurations are highly desired for command-line simulations, we can add a thin converter utility in `backend/src/config/loader.py` that reads a `.yaml` file, converts it to JSON, and validates it against the standard JSON schema. The core configuration contract, however, remains JSON.

## Related ADRs

*   [ADR-003: Shared Contract Layer](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-003-shared-contract-layer.md)
*   [ADR-005: Metric Contract Design](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-005-metric-contract-design.md)
*   [ADR-012: Future Controller Extensibility](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-012-future-controller-extensibility.md)
