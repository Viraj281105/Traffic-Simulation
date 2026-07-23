# ADR-005: Metric Contract Design

## Status

Accepted

## Date

2026-07-23

## Context

The primary goal of the **Traffic Intersection Control Comparison Framework** is to compare the efficiency and quality of traffic flow under two control strategies. This comparison is based on ten specific performance metrics:
1.  **Operational Efficiency**: Average Wait Time, Throughput, Throughput Rate, and Queue Length Statistics.
2.  **Traffic Flow Quality**: Stop Count, Speed Variance Index, and Travel Time Reliability.
3.  **System Capacity**: Idle Opportunity Loss and Critical Saturation Volume.
4.  **Equity**: Directional Fairness Index (Jain's Fairness Index across approaches).
5.  **Physical Constraints**: Space/Footprint consumed by the intersection geometry.

We must decide where these metrics are computed and how their mathematical formulas are defined to ensure consistency.

## Problem Statement

To ensure a scientifically valid comparison, how should we structure the metrics computation to:
1.  Guarantee that the metrics displayed on the frontend are 100% mathematically identical to the metrics analyzed in the backend reports?
2.  Minimize computational load on the frontend to protect rendering frame rates?
3.  Support running batch, headless simulations (e.g., parameter sweeps run from a command-line script) that produce metric reports without launching a browser interface?

## Decision

We will adopt a **Backend-Driven Metrics Computation** model supported by a shared mathematical specification:

1.  **Computation Ownership**: All metrics will be calculated entirely on the backend. The backend maintains a real-time `MetricCollector` and `MetricCalculator` within `backend/src/metrics/`.
2.  **Stateless Frontend Display**: The frontend receives pre-computed running metric values inside each snapshot payload and renders them in charts and summary cards. It does not perform any division, averaging, or statistical aggregation.
3.  **Shared Mathematical Definitions**: We will document the exact mathematical formulas, inputs, and edge cases in the shared contract directory under `shared/metrics/README.md`. This document serves as the absolute specification for Developer A's implementation.
4.  **Schema Enforcement**: The output structure of the metrics is defined in `shared/schemas/metrics.schema.json`. Both the running metrics in the WebSocket snapshot and the final summary metrics returned via the REST API conform to this schema.
5.  **Warmup Handling**: We will support a `warmupTime` configuration parameter. The backend metrics engine will track vehicle behaviors during this phase but exclude them from the final comparative metrics to avoid initial startup bias (when the intersection is artificially empty).

```
                      Backend (Python)
              ┌───────────────────────────────┐
              │  - Runs physics & simulation  │
              │  - Computes math & statistics │
              └──────────────┬────────────────┘
                             │  Running metrics (JSON)
                             ▼
                      Frontend (React)
              ┌───────────────────────────────┐
              │  - Renders UI cards & charts  │
              │  - Passive presentation       │
              └───────────────────────────────┘
```

## Alternatives Considered

### Alternative 1: Frontend-Driven Metrics Computation
The backend streams raw vehicle positions and speeds via WebSocket. The frontend monitors these positions, detects when vehicles stop, cross, or exit, and computes average wait times and throughput values.
*   *Why it was rejected:* This places a heavy mathematical load on the browser, which could cause rendering lag when simulating hundreds of vehicles. More importantly, it requires duplicating physical calculations (such as vehicle-lane association and conflict zone boundaries) on both the client and server. If the frontend JavaScript and backend Python implement these boundaries even slightly differently, the comparison will be invalid. Finally, running headless simulations to generate CSV reports would be impossible because the calculations would only exist in the browser.

### Alternative 2: Dual Computation (Calculated on both sides)
Both the backend and frontend implement the metric formulas independently. The frontend calculates them for the live display, and the backend calculates them for the final reports.
*   *Why it was rejected:* Double calculation introduces high code maintenance overhead and is a major source of bugs. Aligning floating-point mathematics, rounding rules, and edge-case handling across two different languages is notoriously difficult and prone to minor drifts that undermine the integrity of the comparison.

## Trade-offs

### Pros
*   **Scientific Rigor:** The exact same equations and code are used to generate live dashboard views, final REST summaries, and headless batch execution files.
*   **Performance:** React dashboard components remain lightweight, consuming CPU cycles only to render charts and numbers, not to perform high-frequency aggregations.
*   **Robustness:** Because the metrics are computed step-by-step on the backend, the system can handle vehicle transitions and events immediately as they happen in the physics loop.

### Cons
*   **Payload Size**: Streaming 15+ running metric values at 10 Hz inside the snapshot adds a small amount of extra data to the network packages.
*   **Less Interactive Customization**: Users cannot define custom metrics on the fly in the frontend UI without modifying the backend calculation engine.

## Consequences

*   A `warmupTime` parameter must be handled in the backend configuration loader.
*   The backend must expose a `/api/v1/simulations/{id}/metrics` endpoint to return the final, fully-aggregated metrics summary for report downloads.
*   If a new metric is introduced, the developer must first define its formula in `shared/metrics/README.md`, update the `metrics.schema.json`, and then implement the collector on the backend before the frontend can render it.

## Future Considerations

If we want to export the metrics to external tools (like Jupyter Notebooks, R, or Excel), the backend can easily export them directly to standard CSV or JSON files because the data structures are already finalized on the server side.

## Related ADRs

*   [ADR-002: Backend / Frontend Separation](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-002-backend-frontend-separation.md)
*   [ADR-003: Shared Contract Layer](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-003-shared-contract-layer.md)
*   [ADR-004: Snapshot-Based Communication](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-004-snapshot-based-communication.md)
*   [ADR-006: Scenario Configuration Format](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-006-scenario-configuration-format.md)
