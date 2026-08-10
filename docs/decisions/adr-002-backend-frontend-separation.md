# ADR-002: Backend / Frontend Separation

## Status

Accepted

## Date

2026-07-23

## Context

The framework is designed to compare two distinct traffic control strategies (Fixed-Time Signal vs. Modern Roundabout) under identical traffic conditions. Doing this requires:
1. Running mathematically precise, discrete-time simulations (microscopic vehicle behavior via the Intelligent Driver Model).
2. Collecting and aggregating a wide variety of performance metrics.
3. Displaying an interactive, real-time visual playback of vehicle movements, alongside charts and controls.

In many historical traffic simulation tools, the simulation engine and the visual user interface are tightly coupled within a single process (e.g., a desktop GUI application using Pygame or Qt). We need to determine the optimal relationship between our simulation logic and user interface layers.

## Problem Statement

How should we structure the boundary between the simulation execution and the user interface to:
1. Maximize simulation performance and execution accuracy?
2. Maintain clean architectural boundaries, preventing user interface code from interfering with physics and metric calculations?
3. Enable independent deployment, testing, and technology choices for the engine and the UI?

## Decision

We will implement a strict **logical and physical separation** between the backend and frontend systems, operating on a headless client-server model:

1.  **Headless Python Backend (`backend/`)**: 
    *   Acts as the simulation engine. It runs the main simulation loop, updates vehicle physics (IDM), makes traffic control decisions, and computes performance metrics.
    *   Exposes no user interface and imports no rendering libraries.
    *   Outputs structured JSON data representing the state of the simulation at each tick.
2.  **Interactive React/TS Frontend (`frontend/`)**:
    *   Acts as a passive visualizer. It receives state snapshots, draws vehicles and roads onto an HTML5 Canvas, and renders dashboards and charts using React components.
    *   Maintains no simulation physics, vehicle velocities, or intersection state logic. It relies entirely on the backend as the source of truth.
    *   Sends user commands (e.g., start, pause, stop, or configure) back to the backend via an API.

```
┌───────────────────────────────────────┐            ┌───────────────────────────────────────┐
│           Python Backend              │            │           React Frontend              │
│  - Run simulation loop (10Hz)         │            │  - Draw vehicles on HTML5 Canvas      │
│  - Compute IDM physics & routing      │   JSON     │  - Render metrics & charts            │
│  - Make control decisions (Signal/RA) ├───────────►│  - Capture user controls (Play/Pause) │
│  - Aggregate performance metrics      │            │  - Passive state rendering            │
└───────────────────────────────────────┘            └───────────────────────────────────────┘
```

## Alternatives Considered

### Alternative 1: Unified Desktop Application (e.g., Python + Pygame/PyQt)
The entire application runs as a single local process. The simulation logic directly calls rendering functions (e.g., Pygame drawing routines) on each iteration of the loop.
*   *Why it was rejected:* Desktop GUIs are difficult to share and deploy across different operating systems. It makes running automated, headless test suites in CI/CD pipelines more complex (requiring virtual framebuffers like Xvfb). Furthermore, it tightly couples simulation execution to rendering frame rates, which can introduce variance in physics timing.

### Alternative 2: Server-Side Rendering (SSR) / Thin Client (e.g., HTML template updates)
The server renders the visual states (e.g., generating SVG paths or images) and sends them to a thin client browser.
*   *Why it was rejected:* Traffic simulations require high-frequency updates (at least 10 Hz) for smooth vehicle animation. Sending fully rendered visual elements or updating the DOM at this frequency consumes excessive server CPU and network bandwidth, resulting in stuttering playback and poor user experience.

### Alternative 3: Client-Side Simulation (React / JavaScript only)
Port the simulation physics and logic to JavaScript and run the entire framework directly in the browser.
*   *Why it was rejected:* Python is the industry standard for scientific computing, traffic modeling, and mathematical analysis. It offers a robust ecosystem (e.g., NumPy) and makes it easier to write and debug mathematical equations. Keeping the engine in Python also makes it easier to integrate future machine learning models (e.g., reinforcement learning agents for adaptive control) which are almost universally built in Python.

## Trade-offs

### Pros
*   **Separation of Concerns:** The simulation engine can be developed and unit-tested without mock UIs. Similarly, UI layouts, styling, and charts can be tested using mock JSON snapshots.
*   **Performance Isolation:** UI rendering lags in the browser cannot block or distort the physics calculations occurring on the backend.
*   **Flexibility:** The backend can run on a remote server or cloud instance while the frontend runs in the user's browser, enabling remote monitoring of runs.

### Cons
*   **Serialization Overhead:** Converting the high-frequency state of hundreds of vehicles to JSON, transmitting it over a network socket, and parsing it on the client consumes CPU cycles and network bandwidth.
*   **Redundant State Definition:** Some geometric concepts (e.g., the road layout coordinates) must be understood by the backend (for car routing) and the frontend (for canvas drawing), requiring synchronization.

## Consequences

*   The backend and frontend must communicate exclusively through serializable JSON payloads sent over REST (HTTP) and WebSockets.
*   The frontend must implement smooth interpolation between snapshots to ensure fluid animations on the canvas, even if network packets arrive with minor jitter.
*   Changes to the road layouts or physics configurations must be coordinated through the shared contract schemas.

## Future Considerations

If simulation scale demands it, the backend can be migrated to a high-performance language (like Rust or C++) without changing a single line of React code in the frontend, provided the JSON schemas and WebSocket API contracts remain unchanged.

## Related ADRs

*   [ADR-001: Repository Structure](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-001-repository-structure.md)
*   [ADR-004: Snapshot-Based Communication](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-004-snapshot-based-communication.md)
*   [ADR-007: REST + WebSocket Communication Strategy](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-007-rest-websocket-communication-strategy.md)
