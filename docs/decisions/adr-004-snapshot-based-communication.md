# ADR-004: Snapshot-Based Communication

## Status

Accepted

## Date

2026-07-23

## Context

The simulation generates high-frequency state updates (10 Hz by default). The frontend must display this simulation visually as an animation where vehicles move smoothly along roads, stop at intersections, yield in roundabouts, and update their speeds. Additionally, the dashboard must display live metrics matching the vehicle movements.

To achieve this, the simulation state must be serialized on the backend and transmitted to the frontend.

## Problem Statement

How should we structure and transmit the simulation state so that:
1. The frontend can render the simulation accurately and in real time without accumulating lag.
2. The rendering is robust against minor network jitter or packet drops.
3. The frontend rendering engine remains simple and stateless, avoiding the need to duplicate complex simulation state-tracking logic.
4. Developers can easily record, save, and play back simulation runs.

## Decision

We will use a **Snapshot-Based Communication** model. 

1.  **Self-Contained State**: At each simulation tick, the backend generates a single, immutable, and self-contained **Snapshot** payload. This payload contains the absolute state of *every* vehicle, the intersection signals, the active controller state, and current aggregated metrics at that exact millisecond.
2.  **Stateless Frontend Rendering**: The frontend operates as a stateless renderer. When a snapshot is received, the frontend:
    *   Clears the HTML5 Canvas.
    *   Iterates through the list of vehicles in the snapshot and draws each at its absolute `x` and `y` coordinates.
    *   Updates the signal head colors based on the `controller` section of the snapshot.
    *   Refreshes the dashboard metrics.
    *   Does not maintain a local "world history" or attempt to calculate physics.
3.  **Snapshot Composition**: The snapshot includes:
    *   `schemaVersion`, `simulationId`, `timestamp`, `frameNumber`, `tick`.
    *   `vehicles`: Array of active vehicles, each containing its ID, coordinates (`x`, `y`), speed, heading, state (e.g., `waiting`, `crossing`), lane, cumulative wait time, and stop count.
    *   `intersection`: Geometries of approaches and instantaneous queue lengths.
    *   `controller`: Extensible state of the active traffic controller (e.g., green times remaining, roundabout yield counts).
    *   `metrics`: Cumulative performance metrics.

```
                  Snapshot (Tick N) ──► Renders Frame N
                  Snapshot (Tick N+1) ──► Renders Frame N+1
                  (Each snapshot contains 100% of state)
```

## Alternatives Considered

### Alternative 1: Delta-Based / Event-Driven State (Incremental updates)
Instead of sending the full state, the backend emits events only when something changes (e.g., `vehicle_spawned`, `vehicle_moved`, `signal_changed`).
*   *Why it was rejected:* While delta updates significantly reduce payload sizes, they require the frontend to maintain a complex state machine matching the backend. If a single WebSocket packet is dropped, reordered, or delayed, the client's state diverges from the server's. This leads to visual bugs such as "ghost" vehicles that never exit the screen, or vehicles floating off roads. Recovering from desynchronization requires requesting a full sync, complicating client logic.

### Alternative 2: Client-Side Trajectory Extrapolation (Dead Reckoning)
The backend sends coarse updates (e.g., once per second) containing vehicle positions and velocity vectors. The frontend calculates vehicle positions locally between updates by assuming constant speed.
*   *Why it was rejected:* Traffic flow is highly non-linear, especially in conflict zones like roundabouts or stop lines. Vehicles decelerate rapidly and turn frequently. Simple linear extrapolation causes vehicles to visually "teleport" or overshoot stop lines when a new correction packet arrives. Replicating the Intelligent Driver Model (IDM) equations on the frontend to improve extrapolation would violate our separation of concerns and risk mathematical divergence between JS and Python floats.

## Trade-offs

### Pros
*   **High Reliability:** If a snapshot packet is lost, the frontend simply skips it. The next snapshot contains the complete system state, auto-correcting any visual anomalies immediately.
*   **Simple Client Architecture:** The frontend canvas component has zero business or physics logic. It is a pure, easily testable presentation layer.
*   **Simple Playback & Debugging:** Because a simulation run is just a list of sequential snapshots, we can implement playback scrubbing (rewind, fast-forward) by simply storing the snapshots in an array and feeding them to the renderer.

### Cons
*   **Network Bandwidth:** A snapshot for 100 vehicles is approximately 15 KB. At 10 Hz, this requires ~150 KB/s of bandwidth. While negligible for localhost, this could impact network performance if the backend is deployed on a remote server with constrained bandwidth.
*   **Serialization Load:** Serializing hundreds of vehicle objects to JSON at 10 Hz incurs a small CPU overhead on the backend.

## Consequences

*   The backend must optimize snapshot serialization (e.g., using Pydantic's fast serialization or pre-built dictionaries).
*   To prevent visual stuttering, the frontend will implement a simple interpolation buffer (holding 1-2 frames) to smooth out vehicle movements between 10 Hz snapshots, rendering them at a fluid 60 frames per second.
*   All simulation metrics are bundled inside the snapshot, ensuring they are perfectly synchronized in time with the visual representation.

## Future Considerations

If network bandwidth becomes an issue, we can apply gzip compression to the WebSocket connection (typically reducing JSON sizes by 70-80%) or switch to a binary format like MessagePack without changing the logical snapshot contract.

## Related ADRs

*   [ADR-002: Backend / Frontend Separation](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-002-backend-frontend-separation.md)
*   [ADR-003: Shared Contract Layer](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-003-shared-contract-layer.md)
*   [ADR-007: REST + WebSocket Communication Strategy](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-007-rest-websocket-communication-strategy.md)
