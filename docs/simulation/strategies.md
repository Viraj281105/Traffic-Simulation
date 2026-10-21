# Composable Traffic-Control Strategies & Compatibility Validation

> **Status:** Implemented in V3.0 W3 ([ADR-014](../decisions/adr-014-strategy-registry-and-entry-gate-seam.md), [Weekly Sprint Plan §3.4](../roadmap/V3_WEEKLY_SPRINT_PLAN.md#34-w3--fri-13--thu-19-nov-composable-control-strategies), [Execution Plan](../planning/w2-closure-audit-and-w3-execution-plan.md)).  
> **Normative Sources:** [ADR-014](../decisions/adr-014-strategy-registry-and-entry-gate-seam.md) · [V3 Product Strategy §13.6](../roadmap/V3_PRODUCT_STRATEGY.md#136-registry-compatibility-validation-fingerprints-committed-w3) · [Sprint Plan §3.4](../roadmap/V3_WEEKLY_SPRINT_PLAN.md#34-w3--fri-13--thu-19-nov-composable-control-strategies).

---

## 1. Architectural Overview

UrbanFlow models junction control through declarative, layered strategy descriptors (`urbanflow-strategy` v1). Rather than treating junction types as monolithic silos or relying on dynamic external code execution, a traffic-control strategy is a structured composition of six orthogonal architectural layers.

### The 6 Strategy Layers

| Layer | Component | Allowed Values / Roles | Description |
| :--- | :--- | :--- | :--- |
| **1** | **Geometry Constraint** | `fixed_time_signal`, `roundabout`; arms (3–4); circulating lanes | Physical roadway layout and lane constraints |
| **2** | **Movement Topology** | `point_based_conflicts`, `zone_based_conflicts`; U-turns | Conflict model governing vehicle interactions |
| **3** | **Right-of-Way Rule** | `signal`, `yield_to_ring`, `signal_over_yield` | Authoritative rule governing vehicle entry into the conflict area |
| **4** | **Control Policy** | `fixed_time_phase_plan`, `metering`, `uncontrolled`; cycle awareness | Operational policy driving entry signals or yields |
| **5** | **Adaptation Logic** | `none`, `gap_out_extension`; determinism flag | Actuation / dynamic green extension logic |
| **6** | **Priority Overlay** | `none` (V3.0); `emergency_preemption` (Reserved FS-1) | Priority vehicle preemptions (bus / emergency) |

---

## 2. Strategy Compatibility Validation Engine (ADR-014 §2, W3-T2)

Before any simulation object (`SimulationEngine`, `RoadNetwork`, or `BaseController`) is constructed, candidate strategy descriptors and scenario configurations pass through a **pure, deterministic compatibility validator** (`src/strategies/validator.py`).

Contradictory or physically impossible layer combinations are rejected with stable, machine-readable diagnostic codes (`compat.*`), human-readable messages, and actionable repair suggestions.

### Rule & Diagnostic Code Specification Table

| Diagnostic Code | Rule Description | Rejected Condition | Suggestion |
| :--- | :--- | :--- | :--- |
| `compat.signal_requires_signal_geometry` | Signal right-of-way requires signal geometry | `right_of_way.rule == "signal"` on `geometry.intersection_type == "roundabout"` | Use `fixed_time_signal` geometry, or change right-of-way to `yield_to_ring` or `signal_over_yield`. |
| `compat.roundabout_yield_requires_roundabout` | Roundabout yield rules require roundabout geometry | `right_of_way.rule ∈ {"yield_to_ring", "signal_over_yield"}` on `fixed_time_signal` | Use `roundabout` geometry, or change right-of-way to `signal`. |
| `compat.phased_priority_unsupported` | Full circulating priority preemption is unsupported | `right_of_way.rule == "phased_priority"` (ADR-014 §6, D-SR1) | Use `signal_over_yield` (`metered_entry`) mode with entry metering instead. |
| `compat.signal_requires_point_topology` | Signal geometry requires point conflicts | `fixed_time_signal` with `zone_based_conflicts` | Set `movement_topology.topology_type` to `point_based_conflicts`. |
| `compat.roundabout_requires_zone_topology` | Roundabout geometry requires zone conflicts | `roundabout` with `point_based_conflicts` | Set `movement_topology.topology_type` to `zone_based_conflicts`. |
| `compat.roundabout_requires_circulating_lanes` | Roundabout geometry requires circulating lanes | `roundabout` with `circulating_lanes` missing or empty | Specify `circulating_lanes` (e.g. `[1]` or `[1, 2]`). |
| `compat.signal_forbids_circulating_lanes` | Signal geometry forbids circulating lanes | `fixed_time_signal` with `circulating_lanes` specified | Set `geometry.circulating_lanes` to `None`. |
| `compat.arms_range_invalid` | Arm range bounds sanity | `min_arms > max_arms` | Ensure `min_arms <= max_arms`. |
| `compat.signal_row_requires_phase_plan` | Signal right-of-way requires phase plan | `right_of_way.rule == "signal"` with `uncontrolled` or `metering` | Set `control_policy.policy` to `fixed_time_phase_plan`. |
| `compat.yield_to_ring_requires_uncontrolled` | Conventional roundabout yield requires uncontrolled policy | `right_of_way.rule == "yield_to_ring"` with `fixed_time_phase_plan` or `metering` | Set `control_policy.policy` to `uncontrolled`, or use `signal_over_yield` for metered roundabouts. |
| `compat.signal_over_yield_requires_metering` | Signal-over-yield right-of-way requires metering policy | `right_of_way.rule == "signal_over_yield"` with non-metering policy | Set `control_policy.policy` to `metering`. |
| `compat.adaptive_unsupported_policy` | Adaptive gap-out actuation requires phase plan or metering | `adaptation_logic.logic == "gap_out_extension"` with `uncontrolled` policy | Set `control_policy.policy` to `fixed_time_phase_plan` or `metering`, or set `adaptation_logic.logic` to `none`. |
| `compat.uncontrolled_cannot_be_cycle_aware` | Uncontrolled policy cannot be cycle-aware | `control_policy.policy == "uncontrolled"` and `cycle_aware == True` | Set `control_policy.cycle_aware` to `False`. |
| `compat.priority_overlay_unsupported` | Priority overlay reserved for future scope | `priority_overlay.overlay != "none"` | Set `priority_overlay.overlay` to `none`. |

---

## 3. Formal Replacement of Legacy Adaptive Error

Historically, UrbanFlow emitted the un-coded string:
`"controller.signalControl 'adaptive' applies to a signalised junction, not a roundabout"`

Under ADR-014 §2 and W3-T2, this check is unified with the strategy compatibility validation engine:
- In scenario configuration validation (`src/scenario/config_validation.py`), evaluating `intersectionType: "roundabout"` with `signalControl: "adaptive"` now maps directly to the architectural layers (`roundabout` + `uncontrolled` + `gap_out_extension`) and emits the machine-readable diagnostic code:
  `controller.signalControl 'adaptive' requires a signalised junction; incompatible with unmetered roundabout control policy 'uncontrolled' (compat.adaptive_unsupported_policy)`
- In simulation registration (`src/simulations/registry.py`), `check_scenario_strategy_compatibility(config)` executes prior to engine allocation and raises `StrategyCompatibilityError` (which cleanly surfaces as HTTP 400 `InvalidSimulationConfigError`).

---

## 4. Built-in Strategy Descriptors

The registry loads four standard, frozen built-ins on initialization:

1. **`fixed_time_signal`**: Classic cyclic fixed-duration signalized intersection.
2. **`adaptive_signal`**: Demand-actuated gap-out signalized intersection.
3. **`conventional_roundabout`**: Offside-priority yield-at-entry circular intersection.
4. **`metered_entry_roundabout`**: Hybrid roundabout with metered entry signals.

Every built-in passes internal self-check and layer compatibility validation on import.

---

## 5. Security & Extension Model (ADR-014 §3)

* **No uploaded code:** The simulation engine accepts zero client-supplied executable strategies, scripts, or arbitrary dict registrations.
* **Pull-request entry only:** New strategies enter the codebase solely through reviewed pull requests defining a valid `StrategyDescriptor` and passing `validate_strategy_compatibility`.

---

## 6. Strategy Resolution, Parity & Contracts (ADR-014 §4, W3-T3)

### Strategy Resolution Contract

The strategy resolution engine (`src/strategies/resolution.py`) provides an explicit, deterministic contract for mapping input representations to canonical `StrategyDescriptor` instances:

1. **Resolution API (`resolve_strategy`)**:
   - Canonical strategy ID (e.g. `"fixed_time_signal"`, `"metered_entry_roundabout"`).
   - Legacy alias (e.g. `"fixed_time"`, `"roundabout"`, `"signalised_roundabout"`).
   - Explicit `StrategyDescriptor` instance.
   - Scenario document or engine configuration dict:
     - Extracts explicit strategy from root (`strategy`), controller (`controller.strategy`), or scenario block (`scenario.strategy`).
     - If explicit strategy is absent, infers canonical strategy from structural configuration (`geometry.intersectionType`, `controller.signalControl`, `controller.entryControl`).
     - Validates that explicit strategy declarations match the physical layout (preventing contradictions like `strategy: "conventional_roundabout"` with signal geometry).

2. **Validation & Pre-Simulation Guard**:
   - `validate_scenario_strategy_compatibility` checks explicit strategies and structural layers, producing `compat.unknown_strategy` and `compat.strategy_config_mismatch` if invalid.
   - `register_simulation` executes this validation before constructing any `SimulationEngine` or controller, guaranteeing that invalid configurations fail fast with machine-readable diagnostics.
   - Active registry entries stamp `strategy_id` onto each simulation record.

3. **Controller Factory Contract**:
   - `create_controller(config, network)` resolves the configuration to its canonical `StrategyDescriptor` and instantiates the authoritative controller (`FixedTimeSignalController`, `AdaptiveSignalController`, `RoundaboutController`, or `SignalisedRoundaboutController`).

### Configuration Equivalence & Fingerprint Parity

* **Equivalent Configurations:** Configurations specifying a control mode via canonical strategy ID, legacy alias, or implicit geometry/controller settings resolve to identical controllers and execute with 100% bit-identical simulation results (metrics, vehicle states, and snapshot sequences).
* **Fingerprint Invariant:** All pre-existing scenario fixture presets (`frontend/src/scenario/presets.json`) maintain 100% bit-identical scenario and result fingerprints.
* **Golden Parity:** Pre-seam conventional roundabout golden fingerprints (`roundabout_golden_fingerprints.json`) are preserved 100% bit-identical.
* **Strategy Instance Fingerprinting (ADR-014 §4):**
  - `compute_strategy_instance_fingerprint(descriptor, resolved_parameters)` computes a 16-hex deterministic SHA-256 digest over the descriptor ID, version, descriptor fingerprint, and canonical resolved parameter bounds.

---

## 7. Strategy Summary UI & Strategy DNA Card (ADR-014, W3-T4)

The frontend Scenario Builder, Planner, and Research Lab present the resolved strategy through the **Strategy DNA Card** (`StrategySummaryCard.tsx`):

### 6-Layer DNA Representation

1. **Geometry Constraint (Layer 1):** Validates and summarizes intersection type (`fixed_time_signal` vs `roundabout`), approach arm count (3–4), and circulating ring lanes (1–2).
2. **Movement Topology (Layer 2):** Highlights conflict management topology (`point_based_conflicts` at orthogonal signals vs `zone_based_conflicts` across circular circulating segments) and U-turn support.
3. **Right-of-Way Rule (Layer 3):** Details active priority mechanisms (`signal`, `yield_to_ring`, or `signal_over_yield` hybrid metering).
4. **Control Policy (Layer 4):** Summarizes operational policy (`fixed_time_phase_plan`, `metering`, or `uncontrolled`) with cycle awareness and active phase counts.
5. **Adaptation Logic (Layer 5):** Exposes detection logic (`none` vs actuated `gap_out_extension` with green bounds).
6. **Priority Overlay (Layer 6):** Displays priority treatment (`none` standard FIFO; reserved for future emergency preemption).

### Selection Status & Parameter Provenance

* **Selected vs. Resolved Default:** Clearly distinguishes configurations explicitly chosen by the user (`User Selected` / `Preset Selected`) from candidate alternatives evaluated in comparative studies (`Comparison Alternative`).
* **Parameter Provenance:** Tracks whether parameters match descriptor defaults or have been customized by the user, providing a transparent breakdown of values (e.g. green times, yellow/red clearances, critical headways, detector setbacks).
* **Compatibility Surfacing:** Conflicting layers are visually highlighted with amber caution borders and alert badges when invalid combinations (e.g. `compat.adaptive_unsupported_policy`, `compat.signal_requires_signal_geometry`) occur, displaying machine-readable codes alongside actionable suggestions.

