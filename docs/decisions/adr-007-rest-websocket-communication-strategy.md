# ADR-007: REST + WebSocket Communication Strategy

## Status

Accepted

## Date

2026-07-23

## Context

The separated architecture requires the backend to send simulation snapshots and metrics to the frontend, and the frontend to send configuration options and control instructions (such as start, pause, and stop commands) to the backend.

We need to choose the network protocols and endpoint architectures to support these operations.

## Problem Statement

What communication strategy should be implemented to:
1.  Support low-latency, high-frequency streaming of simulation snapshots (10 Hz or higher) to keep client visualization smooth?
2.  Provide reliable, standard request-response operations for configuration validation, simulation setup, and history queries?
3.  Minimize server resource consumption and socket overhead?
4.  Expose an API that is easy to document, test, and integrate?

## Decision

We will implement a **hybrid communication strategy** combining **REST APIs** for lifecycle management and **WebSockets** for real-time streaming:

1.  **REST APIs (HTTP/1.1 JSON)**: Used for stateless, transactional request-response actions.
    *   `GET /api/v1/health`: Server health check.
    *   `POST /api/v1/configs/validate`: Validates scenario configurations against schemas.
    *   `POST /api/v1/simulations`: Creates a new simulation run and allocates a unique ID.
    *   `GET /api/v1/simulations/{id}`: Queries current simulation state and progress percentage.
    *   `POST /api/v1/simulations/{id}/control`: Accepts commands (`start`, `pause`, `resume`, `stop`) to modify execution state.
    *   `GET /api/v1/simulations/{id}/metrics`: Retrieves final aggregated comparison metrics.
2.  **WebSockets (WS JSON)**: Used for persistent, low-overhead, bi-directional state streaming.
    *   `ws://localhost:8000/ws/v1/stream`: The frontend establishes a WebSocket connection containing the target `simulationId` in the query parameters.
    *   While the simulation status is `running`, the backend pushes JSON snapshots down this channel at the frequency specified in the simulation configuration (default 10 Hz).
    *   The connection remains open during pauses and terminates when the simulation finishes or is aborted.

```
                  ┌──────────────────────────────┐
                  │        React Frontend        │
                  └──────────┬──────────┬────────┘
                             │          │
        REST (HTTP JSON)     │          │  WebSockets (WS JSON)
        - Validate Config    │          │  - Real-Time Snapshot Stream
        - Create Sim         │          │  - 10 Hz Push Updates
        - Control playback   │          │
                             ▼          ▼
                  ┌──────────────────────────────┐
                  │        Python Backend        │
                  └──────────────────────────────┘
```

## Alternatives Considered

### Alternative 1: Pure REST with HTTP Polling
The frontend requests snapshots periodically by polling an HTTP endpoint (e.g., `GET /api/v1/simulations/{id}/snapshot` every 100ms).
*   *Why it was rejected:* HTTP polling incurs significant network overhead. Each request requires sending and validating HTTP headers, establishing/negotiating connections (if not using Keep-Alive effectively), and creating server log entries. If the server delays in processing, polling requests can queue up, leading to visual jumps and timeline sync errors. Polling at 10 Hz for hundreds of clients scales very poorly.

### Alternative 2: Server-Sent Events (SSE / EventSource)
SSE allows the backend to open an HTTP connection and stream text events to the frontend in a uni-directional fashion.
*   *Why it was rejected:* While SSE is a clean standard for uni-directional streaming, WebSockets are fully bi-directional. Using WebSockets allows us to extend the communication layer in the future to accept client-to-server commands (such as real-time user-driven traffic light overrides or manual vehicle steering inputs) directly within the high-frequency stream without triggering separate HTTP POST requests. WebSockets are also natively and robustly supported in Python/FastAPI and modern React.

### Alternative 3: Pure WebSocket API (All operations via WS)
Establish a WebSocket connection immediately at startup and perform all operations (including config validation and control commands) as WebSocket messages.
*   *Why it was rejected:* Standard CRUD actions are fundamentally request-response in nature. REST is standard, easily cacheable, maps perfectly to HTTP status codes (e.g., `201 Created` for simulation creation, `404 Not Found` for missing runs), and integrates out of the box with OpenAPI (Swagger) generation tools. A pure WebSocket API lacks these built-in architectural benefits, forcing developers to implement a custom request-response tracking wrapper (e.g., matching correlation IDs) inside WebSocket messages.

## Trade-offs

### Pros
*   **Optimal Protocol Fit:** REST handles structured configuration/setup cleanly, while WebSockets handle high-frequency data streaming with zero HTTP header overhead per frame.
*   **Standard Tooling:** Developers can test backend setups, configurations, and state transitions using standard HTTP utilities (`curl`, Postman, Swagger UI) without needing to configure WebSocket clients.
*   **Low Latency:** WebSockets utilize a single TCP connection, avoiding the overhead of connection handshakes for each snapshot frame.

### Cons
*   **Connection State Management:** The frontend must implement reconnection handlers, timeout checks, and connection lifecycle monitors for the WebSocket stream.
*   **Port Sharing Configuration:** Sharing the same port (e.g., `8000`) for both HTTP and WS in production requires setting up reverse proxies (like Nginx) or ASGI servers (like Uvicorn) to route protocol upgrades correctly.

## Consequences

*   The backend FastAPI app must support ASGI WebSocket routing.
*   The frontend client must handle WebSocket state changes (connecting, streaming, disconnected, error) gracefully in its React context, showing clean state indicators (e.g. green dot for connected, red dot for disconnected) to the user.
*   Security configurations (CORS and Allowed WebSocket Origins) must be synchronized between both layers.

## Future Considerations

If multiple users need to view the same running simulation simultaneously, the WebSocket layer on the backend can be connected to an in-memory pub-sub broker (like Redis). The simulation loop publishes snapshots to Redis, and the Uvicorn WebSocket handlers subscribe to Redis and broadcast to all connected clients, protecting the simulation thread from socket I/O blockages.

## Related ADRs

*   [ADR-002: Backend / Frontend Separation](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-002-backend-frontend-separation.md)
*   [ADR-004: Snapshot-Based Communication](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-004-snapshot-based-communication.md)
