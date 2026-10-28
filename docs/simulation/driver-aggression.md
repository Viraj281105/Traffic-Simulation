# Driver Aggression Profiles

> **driver aggression — a simulation assumption, not a measurement of real-world driver behaviour**
>
> V3.0 results under `moderate` or `high` are not comparable to V2.0 reports unless the profile is stated.

**Status:** implemented in V3.0 W4 ([ADR-016](../decisions/adr-016-driver-aggression-profile.md), [Product Strategy §14](../roadmap/V3_PRODUCT_STRATEGY.md#14-high-driver-aggression-as-the-default-for-new-scenarios), issue [#165](https://github.com/Viraj281105/Traffic-Simulation/issues/165)). The `high` **default at authoring boundaries is not merged**: it waits for gate G-AG (§4, §7).

---

## 1. What a profile is

`traffic.driverAggression ∈ {standard, moderate, high}` is a named, deterministic set of multipliers and offsets applied on top of each vehicle class's base parameters. `standard` is the pre-W4 behaviour bit for bit.

It is separate from the two older flags:

* `traffic.unstructuredTraffic` — random per-tick noise (`StochasticIDM`). Aggression is systematic; both can be on.
* `traffic.aggressiveTwoWheelers` — two-wheeler lane-change gaps, only with `unstructuredTraffic`. **`high` does not turn it on** (decision D-AG2). An aggressive two-wheeler keeps its own lane-change rules (politeness 0, threshold 0.05); the profile's lane-change levers do not apply to it.

Resolution has one owner, [`backend/src/vehicles/driver_aggression.py`](../../backend/src/vehicles/driver_aggression.py): every engine component (shared IDM, spawner, class population, lane changing) reads the profile through `aggression_multipliers_for(config)`. Absent or `null` is `standard`; any other value that is not a profile name raises `ValueError` — the API layers reject it earlier with a 400 (`semantic_config_errors`, the JSON Schema enum, the scenario document's `Literal`).

## 2. The levers

| Lever | `standard` | `moderate` | `high` | Applied where |
| :--- | :---: | :---: | :---: | :--- |
| IDM desired time headway *T* | ×1.00 | ×0.85 | ×0.70 | every class; the legacy cars-only shared IDM |
| IDM standstill gap *s₀* | ×1.00 | ×0.875 | ×0.75 | to the vehicle ahead only, for every class, the shared IDM and the spawner insertion gap. **Not** at a stop or yield line, where every profile stops where `standard` does ([ADR-019](../decisions/adr-019-stop-line-position-under-driver-aggression.md)) |
| IDM max acceleration *a* | ×1.00 | ×1.075 | ×1.15 | every class; shared IDM |
| Desired-speed factor | +0.000 | +0.025 | +0.050 | every class, capped at **1.10 × the limit for every profile**; the legacy cars-only speed range is scaled exactly like the car class |
| MOBIL politeness *p* | ×1.00 | ×0.75 | ×0.50 | every class; legacy cars (0.3) |
| MOBIL acceleration threshold | ×1.00 | ×0.75 | ×0.50 | the scenario default (0.2 m/s²) |

An explicit `roads.laneChange.accelerationThreshold` or `politeness` in a config is a user setting and wins over the profile.

**Not changed by any profile:** MOBIL safe deceleration *b_safe* = 4.0 m/s², IDM comfort deceleration *b* = 3.0 m/s², IDM δ = 4, roundabout gap acceptance (critical gap, follow-up time) and the roundabout's internal margins `_EXIT_SAFETY_HEADWAY` / `_EXIT_COMMIT_MARGIN` = 1.0 s. §6 records why the last two stay fixed.

## 3. Resolved values by class

Generated from `DEFAULT_PROFILES` through `apply_aggression_to_profile` (2026-10-22). The car's IDM values come from `vehicleGeneration` (defaults shown); explicit `vehicleTypes` overrides are applied first and the profile scales them.

| Class | Parameter | `standard` | `moderate` | `high` |
| :--- | :--- | :---: | :---: | :---: |
| **Car** | *T* (s) | 1.5 | 1.275 | 1.05 |
| | *s₀* (m) | 2 | 1.75 | 1.5 |
| | *a* (m/s²) | 2 | 2.15 | 2.3 |
| | Desired-speed factor | [0.85, 1.05] | [0.875, 1.075] | [0.9, 1.1] |
| | Politeness | 0.3 | 0.225 | 0.15 |
| **SUV** | *T* (s) | 1.6 | 1.36 | 1.12 |
| | *s₀* (m) | 2 | 1.75 | 1.5 |
| | *a* (m/s²) | 1.8 | 1.935 | 2.07 |
| | Desired-speed factor | [0.85, 1.05] | [0.875, 1.075] | [0.9, 1.1] |
| | Politeness | 0.3 | 0.225 | 0.15 |
| **Bus** | *T* (s) | 1.8 | 1.53 | 1.26 |
| | *s₀* (m) | 2.5 | 2.188 | 1.875 |
| | *a* (m/s²) | 1 | 1.075 | 1.15 |
| | Desired-speed factor | [0.75, 0.9] | [0.775, 0.925] | [0.8, 0.95] |
| | Politeness | 0.5 | 0.375 | 0.25 |
| **Truck** | *T* (s) | 2 | 1.7 | 1.4 |
| | *s₀* (m) | 3 | 2.625 | 2.25 |
| | *a* (m/s²) | 0.8 | 0.86 | 0.92 |
| | Desired-speed factor | [0.7, 0.9] | [0.725, 0.925] | [0.75, 0.95] |
| | Politeness | 0.5 | 0.375 | 0.25 |
| **Motorcycle / bike** | *T* (s) | 1.1 | 0.935 | 0.77 |
| | *s₀* (m) | 1.5 | 1.312 | 1.125 |
| | *a* (m/s²) | 3 | 3.225 | 3.45 |
| | Desired-speed factor | [0.9, 1.1] | [0.925, 1.1] | [0.95, 1.1] |
| | Politeness | 0.1 | 0.075 | 0.05 |

The motorcycle is already at the 1.10 ceiling, so only its lower bound moves.

## 4. Defaults and boundaries

| Boundary | Behaviour today |
| :--- | :--- |
| Stored configs, `/api/v1`, `/api/v2`, fixtures, presets | Absent ⇒ `standard`; fingerprints unchanged (§5) |
| Scenario document (`traffic.driverAggression`), engine config (`traffic.driverAggression`), dashboard flat payload (`driverAggression`) | Any of the three profiles accepted and run; anything else rejected with a 400 |
| UI: quick setup (`ScenarioSetup`) and scenario builder (`AdvancedSettings`) | Selector shown with the disclaimer; **defaults to `standard`** |
| New-scenario helpers `create_scenario()` (backend) and `newScenarioDocument()` (frontend) | Write `high` explicitly, but **nothing calls them yet** |
| Presets, Python client helper, `/api/v3` specifications, Copilot, `.ufpkg` | **No `high` default yet** |
| Explicit user choice | Always preserved, including an explicit `standard` |

Strategy §14.3 makes `high` the written default at every new-scenario authoring boundary. Sprint plan §3.5 merges that default **only after gate G-AG passes**; until then the boundaries above stay at `standard`. Wiring the default is a separate change once the gate passes.

## 5. Reproducibility

* **Fingerprint.** A document with no profile or with `standard` has the pre-W4 fingerprint (verified against commit `4b2d4e1` for every preset, with and without an explicit `standard`). `moderate` and `high` add `{driverAggression, driverAggressionHash}` to the fingerprinted body, so re-tuning a profile's multipliers changes the identity of every document that uses it.
* **Parameter hash.** `compute_aggression_parameter_hash` covers the profile name, its multipliers, *b_safe* and the speed-factor ceiling.
* **Manifest.** `/api/v3` experiment results carry `manifest.assumptions.{driverAggression, driverAggressionHash, disclaimer}`, resolved from the compiled config — so an `advanced.traffic.driverAggression` override is what is recorded, because it is what runs.
* **Replay.** Same document, seed and profile ⇒ identical metrics (`test_aggression_deterministic_replay.py`, matrix determinism test).

## 6. Evidence

### Lever sensitivity (AG-1, measured 2026-10-22, after ADR-019)

Saturated single-lane junction, 1,000 veh/h per arm, 300 s (60 s warm-up), 6 seeds, cars only. Each cell gives the mean number of vehicles discharged, with the longest stall in brackets:

| Junction | `standard` | `moderate` | `high` |
| :--- | :---: | :---: | :---: |
| Roundabout | 96.5 (47 s) | 101.2 (46 s) | 105.0 (45 s), +9 % |
| Fixed-time signal, no mix | 93.8 (33 s) | 90.8 (42 s) | 96.0 (35 s), +2 % |
| Fixed-time signal, `{car: 1.0}` | 88.3 (37 s) | 100.5 (36 s) | 105.8 (42 s), +20 % |

All runs had 0 collisions. Before ADR-019, the same signal cells gridlocked in 4 of 24 `moderate`/`high` runs (§7).

`_EXIT_SAFETY_HEADWAY` at 0.7 s instead of 1.0 s gave **identical** results, run for run, under both `standard` and `high` on the roundabout. In these cells it is not binding, so it is not the dominant lever. The strategy's condition for parametrising it (§14.2) is not met, and it stays fixed. This is the measured reason. The earlier argument that 0.7 s "creates collision hazards" was never tested and is withdrawn.

The analytic steady-state values in `test_aggression_spike.py` (equilibrium spacing at 50 km/h, theoretical stop-line capacity) describe what the IDM parameters imply. They are not simulation measurements.

### 108-cell matrix (W4-T5, 2026-10-22, after ADR-019)

The matrix crosses profile (3), vehicle mix (car-only with no mix, mixed, heavy 70 % bus/truck), strategy (fixed-time, adaptive, roundabout, metered-entry roundabout) and density (200 / 500 / 1,000 veh/h per arm). It uses two-lane approaches, 240 s per cell with a 30 s warm-up, and seed 1. Harness: `backend/tests/vehicles/test_aggression_matrix.py`; the full-strength run is under `-m slow`, in CI's nightly slow job. On 4 workers it took 14.5 min wall time (56 CPU-minutes; the slowest cell took 132 s).

* **Safety and liveness:** 108/108 cells ran to completion with 0 collisions and no deadlock-detector trip. The longest stall was 40.8 s (bound 70 s). Every cell ran its strategy's controller and its mix's vehicle classes. The `standard` cells are identical to the run before ADR-019.
* **Measured levers:** the mean following time headway was 3.07 / 2.84 / 2.59 s (`high` −15.7 %). The mean gap between queued vehicles was 2.60 / 2.33 / 2.15 m (`high` −17.5 %).
* **Outcomes**, given as mean throughput / mean delay (s) / unserved-demand share:

| | `standard` | `moderate` | `high` |
| :--- | :---: | :---: | :---: |
| Fixed-time signal | 68.9 / 43.9 / 0.138 | 71.1 / 43.7 / 0.122 | 78.3 / 40.7 / 0.119 |
| Adaptive signal | 71.1 / 39.8 / 0.134 | 75.9 / 35.4 / 0.113 | 79.9 / 38.6 / 0.091 |
| Roundabout | 69.0 / 39.9 / 0.133 | 71.7 / 39.6 / 0.110 | 74.7 / 38.3 / 0.098 |
| Metered-entry roundabout | 58.4 / 52.1 / 0.143 | 60.3 / 51.6 / 0.133 | 62.6 / 50.5 / 0.131 |
| Saturated cells | 83.8 / 65.8 / 0.303 | 88.2 / 64.2 / 0.270 | 95.1 / 64.3 / 0.253 |

* **Adverse results (12 of 72 comparisons, all under `moderate`):** throughput was 1–5 vehicles lower, or unserved demand up to 1.5 points higher, than `standard`. These cells are spread across all four strategies and are mostly roundabout cells. `high` had none. With one seed per cell these differences are within run-to-run noise, so they are reported, not interpreted. `moderate` is not a guaranteed improvement on `standard`.

## 7. Limitations and open findings

* **Fixed: saturated single-lane signals gridlocked under aggression.** The shorter standstill gap made a head vehicle wait 0.5 m nearer the junction box, inside the corridor of a right turn crossing in front of it, and a four-vehicle circular wait followed. 4 of 24 `moderate`/`high` runs stalled 115–169 s. [ADR-019](../decisions/adr-019-stop-line-position-under-driver-aggression.md) keeps the stop position at a line profile-independent. The runs that locked up are slow regressions in `test_aggression_integration_regressions.py`. ADR-019 is **Proposed**: it is a physics-adjacent change awaiting Product Owner acceptance.
* The matrix still uses two-lane approaches only. The single-lane case is covered by the regression tests above, not by the matrix.
* Profiles are assumptions: they are not fitted to naturalistic driving data, and every vehicle of a class gets the same multiplier.
* The matrix uses one seed per cell. Its throughput and delay differences are descriptive, not statistical.
* Real-world validity: **None — assumptions only.**
