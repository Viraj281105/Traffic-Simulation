# V3.0 W1 — How each uncertainty factor is applied to a scenario

> **Status:** WP0 spike result for the Robustness Lab ([#151](https://github.com/Viraj281105/Traffic-Simulation/issues/151)), 2026-10-15. Normative source: [strategy §5.1](../roadmap/V3_PRODUCT_STRATEGY.md) and [ADR-015](../decisions/adr-015-robustness-lab-uncertainty-design.md). This note fixes the **meaning** of the six factor kinds so the runner (WP3) and the tests (WP2) are written against one definition. Items marked **Decision** were chosen by the engineer as the simplest defensible option and are open to the product owner.

## Principle

A factor value never edits engine or physics code. It produces a **new `ScenarioDocument`** from the base one, which is then validated and compiled exactly like any scenario (`compile_scenario`). A perturbed document that fails validation is **rejected and counted**, never repaired. The perturbation is applied to every alternative's resolved document in the same way, so alternatives differ only by their own patch and control (common random numbers, strategy §5.3).

Every factor is **global** in v1: it acts on all arms and all vehicle classes identically. Per-approach factors are outside the v1 specification.

## The six factors

| Kind | Value *s* | Applied through | Effect |
| --- | --- | --- | --- |
| `demand_scale` | multiplier, > 0 | `approaches.<arm>.vehiclesPerHour` on every present arm | `vph × s`. A result above the 7200 vph arm limit fails document validation → rejected and counted |
| `turning_shift` | −1 … +1 | `approaches.<arm>.turning` on every present arm | **Decision:** moves share between *straight* and *turning* (left + right), conserving the total. *s* > 0 moves the fraction *s* of the straight share to left/right in their existing proportion (evenly if both are 0); *s* < 0 moves the fraction \|*s*\| of left + right into straight. The U-turn share is untouched |
| `mix_shift` | −1 … +1 | `vehicles.mix` and every `approaches.<arm>.vehicleMix` that is declared | **Decision:** moves share between *light* (car, suv, motorcycle) and *heavy* (bus, truck), conserving the total. *s* > 0 moves the fraction *s* of the light share into the heavy classes in proportion to their existing shares (equally between bus and truck when both are 0); *s* < 0 does the reverse. **A base scenario with no declared mix is rejected** for this factor: adding a mix would switch the engine from its legacy single-car population to the mixed one (a different random stream), which is more than the factor claims |
| `headway_scale` | multiplier, > 0 | `advanced.vehicleGeneration.desiredTimeHeadway` and `advanced.vehicleGeneration.vehicleTypes.<class>.desiredTimeHeadway` | Multiplies the IDM desired time headway of every class. Labelled a **proxy** for driver behaviour: the engine has no reaction delay. Minimum gap is unchanged |
| `desired_speed_scale` | multiplier, > 0 | `advanced.vehicleGeneration.desiredSpeed` (`min`, `max`) | Scales the car's desired-speed range; every other class derives its range from the car's by a fixed ratio, so all classes scale together |
| `max_acceleration_scale` | multiplier, > 0 | `advanced.vehicleGeneration.maxAcceleration` and `…vehicleTypes.<class>.maxAcceleration` | Multiplies the IDM maximum acceleration of every class |

### Reading the effective base value

The three IDM-style factors write **absolute** values, computed from the base scenario's *effective* parameters, not from hard-coded defaults. The effective values are read from the engine's own resolution (`compile_scenario` → `resolve_vehicle_population`, `resolve_desired_speed_range`), so a base scenario that already overrides a class parameter is scaled from that override. Classes written are the union of the global mix and every arm mix; the scalar `vehicleGeneration` values cover the legacy single-car population and the reference car.

### Rejections the runner must count

* The perturbed document fails `parse_scenario` / `validate_scenario` (e.g. demand above the arm limit, desired speed outside what the config contract allows).
* `mix_shift` requested but the base scenario declares no mix.
* The base scenario's `advanced` already sets the same `vehicleGeneration` key the factor writes (the factor would be silently overridden by the deep merge). Reported by name; the experiment is refused at submission, not per condition.

## Spike evidence (2026-10-15)

Prototype run on the development machine (Python 3.14.7), base scenario: four single-lane arms, 450 veh/h each, fixed-time signal, 240 s with 30 s warm-up, mean of seeds 11–13. `valid` = `validate_scenario` passed for `fixed_time`, `adaptive` and `roundabout`.

| Factor (values *s*) | Legacy population: mean delay (s) | Mixed population: mean delay (s) | Valid for all three strategies |
| --- | --- | --- | :-: |
| baseline | 49.6 | 50.2 | — |
| `demand_scale` 0.7 / 1.3 | 28.2 / 42.5 | 45.8 / 58.6 | yes |
| `turning_shift` −0.5 / +0.5 | 30.5 / 51.3 | 48.1 / 50.3 | yes |
| `mix_shift` −1 / +1 | rejected (no declared mix), as designed | 30.2 / 66.9 | yes |
| `headway_scale` 0.8 / 1.5 | 43.9 / 46.5 | 50.2 / 59.9 | yes |
| `desired_speed_scale` 0.8 / 1.2 | 47.7 / 38.6 | 59.1 / 53.9 | yes |
| `max_acceleration_scale` 0.6 / 1.5 | 43.0 / 41.2 | 54.5 / 45.6 | yes |

**What this establishes**

* All six factors can be applied through existing scenario inputs (document fields and the `advanced` merge) with **no engine or physics change**, in both the legacy single-car population and the mixed population. Every perturbed document validated.
* The compiled engine config carries the intended values (checked for headway in a mixed population: every class's `desiredTimeHeadway` is scaled, the car's from the scalar `vehicleGeneration` value).
* Directions agree with traffic intuition except where noise dominates (below).

**What it does not establish**

* Effect sizes. Each run exits only about 55 vehicles inside 240 s, so a 3-seed mean is noisy: legacy delay at demand ×1.3 (42.5) is *lower* than at ×1.0 (49.6), and mixed headway ×0.8 equals the baseline to two decimals by coincidence of the mean (single seed 11 gives 46.2 vs 48.8). Nothing here is a finding about the junction.
* Consequence for the runner (WP3): the experiment presets need a longer duration or more replications than this spike used, and the exclusion rule must not hide a short horizon. The duration will be chosen from a measured stability check, not assumed.

**Measured cost (unverified outside this machine):** about 12–17 s per 240 s run on one process (the spike ran 70 runs in about 20 minutes). A 24-condition × 3-alternative × 2-replication study is 144 runs, roughly 30–40 min on one process; the worker pool will divide that, but the figure stays *unverified* until measured with the pool.

**Implementation notes for WP3**

* Round every applied value to 6 decimals (the spike produced `1.4400000000000002`), so fingerprints do not depend on float formatting.
* `run_scenario_comparison` already runs every strategy on the same seed and supports `num_seeds=1, base_seed=<derived>`, but it runs one call per condition. For parallelism the runner should instead build `SimTask`s for all (condition, alternative, replication) and call `run_simulation_tasks` once.
