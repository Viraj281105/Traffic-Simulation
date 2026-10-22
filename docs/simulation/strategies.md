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
| `compat.unknown_strategy` | Explicit strategy must be registered | `strategy` names neither a canonical ID nor a legacy alias | Choose a registered strategy from the list in the message. |
| `compat.strategy_config_mismatch` | Explicit strategy must agree with the physical layout | e.g. `conventional_roundabout` on signal geometry, or `metered_entry_roundabout` without `entryControl: "metered_entry"` | Set the geometry / entry control to match, or change the strategy. |

`COMPATIBILITY_CODE_LAYERS` (`strategies/validator.py`) maps every code to the layers it can implicate; it is the contract the Strategy DNA card uses to place a diagnostic on a layer (`COMPAT_CODE_LAYER_INDEX` in `strategySummaryModel.ts`). Tests sweep the validator's input space to prove emitted issues stay within their declared layers and that the frontend table covers exactly the backend codes.

An explicit `strategy: adaptive` (or `adaptive_signal`) together with an explicit `controller.signalControl: "fixed_time"` is reported as `compat.strategy_config_mismatch`; the strategy would otherwise silently win. An absent `signalControl` is not a contradiction. Strategy inference and this validator read the junction through one helper (`extract_geometry_type`: `geometry.intersectionType`, then document-style `junction.type`).

The adaptive rule is applied to scenario configurations as well as descriptors: `signalControl: "adaptive"` on **any** roundabout, metered or not, reports `compat.adaptive_unsupported_policy`, because no adaptive signalised roundabout exists until the gated W3-T6 (the descriptor rule alone would accept `gap_out_extension` on a `metering` policy).

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

---

## 8. Strategy Robustness, Security Invariants & Limitations (ADR-014, W3-T5)

The composable strategy architecture enforces strict boundary conditions, security invariants, and failure-containment guarantees across both backend and frontend environments:

### Robustness & Security Invariants

1. **Strict Descriptor Schema & Boundary Validation:**
   - All descriptors and layer models enforce Pydantic strictness (`extra="forbid"`), preventing prototype poisoning or unauthorized payload properties.
   - Identifier patterns are strictly constrained (`^[a-z0-9_]+$`).
   - Parameter bounds enforce invariant ordering (`min_value <= max_value`) and default containment (`min_value <= default_value <= max_value`).
   - Geometry bounds enforce 3–4 approaches (`min_arms <= max_arms`); `circulating_lanes` entries must be unique integers in 1..2 (the engine's `MAX_CIRCULATING_LANES`; the config schema allows 3, but scenario validation rejects it as unsupported). An empty list is left to `compat.roundabout_requires_circulating_lanes`.

2. **Registry Isolation & Safe Custom Compositions (ADR-014 §3):**
   - Registration strictly requires concrete `StrategyDescriptor` instances. Unvalidated client dicts, JSON strings, or arbitrary objects are rejected with `TypeError`.
   - Re-registration of existing identifiers is strictly forbidden (`ValueError`).
   - Cyclic alias definitions (e.g. $A \to B \to A$) are detected and blocked at registration time and guarded during resolution.
   - An alias can never reuse a registered strategy ID (aliases are consulted first, so it would silently redirect that strategy), an existing alias cannot be re-targeted, and a strategy ID cannot reuse an existing alias.
   - The registry keeps private copies: descriptors returned by `get()` / `list_all()` and the instance a caller registered are detached from registry state, so mutating them cannot alter later resolutions or fingerprints.
   - Custom descriptors registered in isolated `StrategyRegistry` instances never leak into the global singleton registry (`get_strategy_registry()`).

3. **Pre-Simulation Initialization Guards & Database Isolation:**
   - Pre-simulation guards (`check_scenario_strategy_compatibility` and `resolve_strategy_parameters`) run before any simulation engine, road network, or controller is instantiated.
   - Parameter values outside descriptor bounds (e.g. green duration $< 5\,\text{s}$ or $> 120\,\text{s}$) and non-numeric values trigger `InvalidSimulationConfigError` immediately.
   - Roundabout descriptors list only tunables backed by a bounded config key: `critical_gap` (`controller.criticalGap`), `inner_radius` (`controller.innerRadius`), `metering_yellow` / `metering_all_red` (`controller.entryMetering.yellow` / `.allRed`). Values the engine derives (metering cycle, red) or fixes (entry setback) are not parameters, and unbounded keys (`followUpTime`, `entrySpeed`) are omitted so the guard can never reject a schema-valid value. `cycle_time` (fixed-time) and `passage_gap` (adaptive) remain as derived/informational descriptor knobs with no config key; a test pins that list.
   - Descriptor bounds for parameters that map onto a config key (`controller.yellowTime`, `controller.allRedTime`, `controller.adaptive.*`) must cover the config schema's range, and adaptive defaults must equal the controller defaults; `test_strategy_integration_hardening.py` enforces this so the guard can never reject a schema-valid configuration.
   - Failed initializations produce zero state changes in `simulations_db`: no leaked simulation IDs, no orphan worker threads, and no partial database records.

4. **Backward-Compatible Error Diagnostics:**
   - All 16 diagnostic codes (`compat.*`) provide stable, machine-readable keys, clear human-readable messages, and actionable remediation suggestions.
   - Legacy configuration validation (`semantic_config_errors`) and scenario document validation (`validate_scenario`) seamlessly support both canonical strategy identifiers and legacy aliases.

### Documented Scope Boundaries & Remaining Limitations

* **Phased Priority Roundabouts:** Suspending circulating priority (`phased_priority` mode) remains strictly **deferred/stretch** under ADR-014 D-SR1, as it requires a separate movement-conflict contract and circulating queue ring-clearance proof.
* **Priority Overlay (Layer 6):** Emergency preemption and transit priority are architectural placeholders reserved for Future Scope **FS-1**. All current descriptors enforce `overlay: "none"`.
* **Visual Drag-and-Drop Composer:** Strategy configuration is authored through high-level scenario parameters; direct canvas drag-and-drop layer assembly remains explicitly **deferred**.
* **Adaptive Signalised Roundabout (W3-T6):** Green extension on metered roundabout entries remains **conditional on PO signoff of Gate G-SR**.


