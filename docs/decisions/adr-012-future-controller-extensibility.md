# ADR-012: Future Controller Extensibility

## Status

Accepted

## Date

2026-07-23

## Context

The framework currently compares two traffic control strategies: a **Fixed-Time Traffic Signal** and a **Modern Roundabout**. These represent two very different methods of managing conflict zones: signal-based time-sharing (where approaches are stopped in phases) vs. priority-based space-sharing (where approaching vehicles yield to circulating vehicles).

In the future, researchers or developers may want to compare other strategies, such as:
*   Actuated / Adaptive Traffic Signals (using virtual loop detectors to adjust green times based on demand).
*   Reinforcement Learning (RL) agents (using neural networks to optimize signal timing dynamically).
*   All-way Stop Control (stop signs) or Yield Control.

To make the codebase long-lived, we must ensure these future controllers can be integrated without rewriting the simulation engine or breaking the frontend visualization.

## Problem Statement

How should we design the backend architecture, frontend visualizer, and shared contracts to:
1.  Allow new intersection control strategies to be integrated with minimal modifications to the core simulation loop?
2.  Adhere to the Open-Closed Principle (code should be open for extension, but closed for modification)?
3.  Prevent adding new controller-specific properties from breaking existing snapshot and configuration schema validation?
4.  Ensure the frontend visualizer can render new controller types gracefully, falling back to a safe default if specific rendering code is missing?

## Decision

We will implement a modular, pluggable controller architecture based on **Polymorphic Interfaces**, the **Registry Pattern**, and **Schema Discriminated Unions**:

### 1. Backend Polymorphic Interface (`BaseController`)
We define an abstract base class `BaseController` in `backend/src/controllers/base.py` that outlines a strict contract for all controllers:
```python
class BaseController(ABC):
    @abstractmethod
    def update(self, delta_time: float, active_vehicles: list[Vehicle]) -> None:
        """Called on every simulation tick to advance the controller state."""
        pass

    @abstractmethod
    def get_state(self) -> dict[str, Any]:
        """Returns the serializable state of the controller matching the schema."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Resets the controller to its initial state."""
        pass
```
Specific controllers (e.g., `FixedTimeSignalController`, `RoundaboutController`) inherit from `BaseController` and implement these methods.

### 2. Backend Registry Pattern
We maintain a centralized registry in `backend/src/controllers/registry.py`. 
*   Controllers register themselves using a decorator (e.g., `@register_controller("adaptive_signal")`).
*   The main simulation loop does not reference specific controller classes. Instead, it reads the `intersectionType` string from the configuration and requests the corresponding class from the registry:
    ```python
    controller_cls = controller_registry.get(config.geometry.intersection_type)
    self.controller = controller_cls(config.controller)
    ```

### 3. Shared Contract Discriminated Unions
Both `config.schema.json` and `snapshot.schema.json` use a discriminated union pattern. The `intersectionType` or `controller.type` field serves as the discriminator. Adding a new controller involves adding a new branch under `oneOf` in the schema definition, preserving the validation of all other base properties.

### 4. Frontend Fallback Rendering
In the frontend, the visualization dashboard uses a registry of overlay renderers. When rendering the intersection:
*   The frontend checks if it has a custom renderer for the active `controller.type` (e.g., drawing colored signal heads for `fixed_time_signal`).
*   If a renderer is found, it is executed.
*   If no custom renderer is found (e.g., a new `rl_signal` controller is running), the frontend **falls back to a default visualizer**. This default visualizer still draws the base roads and animated vehicles accurately from the snapshot, preventing browser crashes and ensuring basic visibility.

```
                    ┌──────────────────────────────┐
                    │      Simulation Engine       │
                    └──────────────┬───────────────┘
                                   │ Updates
                                   ▼
                       ┌───────────────────────┐
                       │  BaseController (ABC) │
                       └───────────┬───────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
     ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
     │ FixedTimeSignal │  │    Roundabout   │  │   [FUTURE] RL   │
     │   Controller    │  │   Controller    │  │   Controller    │
     └─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Alternatives Considered

### Alternative 1: Hardcoded Conditional Logic (Switch Cases)
Insert conditional code blocks directly inside the main simulation loop (e.g., `if type == "signal": update_signals() elif type == "roundabout": update_roundabout()`).
*   *Why it was rejected:* This violates the Open-Closed Principle. Every time a developer adds a controller, they must edit the core `SimulationEngine` file. This increases the risk of introducing bugs into the core simulation loop, makes the code harder to read, and blocks the packaging of the engine as a clean, reusable library.

### Alternative 2: Separate Simulation Engines per Control Strategy
Create two separate repositories or distinct simulation files (e.g., `roundabout_simulator.py` and `signal_simulator.py`).
*   *Why it was rejected:* This leads to massive code duplication. The vehicle physics (IDM), lane structures, vehicle spawn logic, and metric calculations are identical across both strategies. Separating the engines would double maintenance work and guarantee that the physics implementations would drift, making it impossible to perform a mathematically "fair" comparison.

## Trade-offs

### Pros
*   **Decoupled Architecture:** The simulation engine remains clean and focused solely on ticking the clock and moving vehicles. Control policies are completely isolated in separate module files.
*   **Low Integration Friction:** A new developer can implement a new control strategy by writing a single Python file containing a `BaseController` subclass and registering it, without touching the rest of the codebase.
*   **Robust UI:** The frontend remains resilient. Even if the backend team develops a complex new AI controller, the frontend dashboard will still render the vehicles and lanes without requiring an immediate frontend update.

### Cons
*   **Upfront Abstraction Complexity:** Designing abstract interfaces requires careful planning. If the base interface is too restrictive, it might be difficult to feed necessary data (like virtual camera inputs) to future AI controllers.

## Consequences

Adding a new controller (e.g., `adaptive_signal`) is reduced to a standard 4-step checklist:
1.  **Contract Update**: Add the new key to the `ControllerType` enum and update the configurations/snapshots schemas in `shared/schemas/` to define the new parameters.
2.  **Backend Implementation**: Subclass `BaseController` in `backend/src/controllers/`, implementing its physics-interaction and state serialization rules. Register it in `registry.py`.
3.  **Frontend Update**: (Optional) Write a React overlay component in the frontend to draw specific features (like queue detectors). If omitted, fallback rendering applies.
4.  **Configuration**: Create a sample scenario configuration file inside `examples/configs/` using the new type and parameters to demonstrate its usage.

## Future Considerations

This extensibility model makes it easy to integrate research-grade simulators or machine learning environments (like Gymnasium/OpenAI Gym) in the future. The RL environment can simply wrap the simulation engine and implement the `BaseController` interface to control signals via a neural network.

## Related ADRs

*   [ADR-002: Backend / Frontend Separation](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-002-backend-frontend-separation.md)
*   [ADR-003: Shared Contract Layer](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-003-shared-contract-layer.md)
*   [ADR-006: Scenario Configuration Format](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-006-scenario-configuration-format.md)
