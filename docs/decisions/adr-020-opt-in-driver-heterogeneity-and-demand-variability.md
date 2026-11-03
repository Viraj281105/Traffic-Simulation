# ADR-020: Opt-In Driver Heterogeneity and Demand Variability

## Status

**Accepted** on 2026-11-03 (V3.1 W31, decision D1 "opt-in heterogeneity" taken by the project owner). Both models are **off by default**; with them off, every existing result is bit-identical.

## Date

2026-11-03

## Context

The V3.1 roadmap row for W31 asks for "random driver and demand models". Today:

* Every vehicle of a class drives with the same IDM parameters. Only length, width and desired speed are drawn per vehicle, and `unstructuredTraffic` (F-38) adds per-*step* noise to acceleration, not a persistent trait of a driver.
* Arrivals are Poisson at a fixed `traffic.arrivalRate` for the whole run. The one run-level randomness (directional split and turn probabilities when not configured) is drawn from the engine's own stream.

With both fixed, repeating a scenario over many seeds varies arrival times and vehicle sizes but not how drivers behave or how busy the hour is, so the spread across seeds understates real variability. W32 will attach confidence intervals to that spread; this week makes the spread worth measuring.

Changing either by default would move every golden fingerprint (roundabout corpus, W31 signal corpus) and every published capacity pin.

## Decision

Two independent, opt-in blocks under `traffic`. Absent, `enabled: false`, or all spreads 0 means the model is off.

### `traffic.driverHeterogeneity`

| Field | Meaning | Bounds |
| :--- | :--- | :--- |
| `enabled` | turn the model on | boolean, default false |
| `headwaySpread` | half-width of the multiplier on desired time headway *T* | 0 – 0.5 |
| `accelerationSpread` | same, on maximum acceleration *a* | 0 – 0.5 |
| `decelerationSpread` | same, on comfortable deceleration *b* | 0 – 0.5 |

At spawn each vehicle draws three multipliers, each uniform on `[1 − spread, 1 + spread]`, and keeps them for its whole trip (a persistent trait, not noise). They scale the vehicle's **own class baseline** (or the engine-wide IDM for a vehicle without a class), including any driver-aggression setting. Desired speed already varies per vehicle and is not touched. Lane-change gap checks keep using the class baseline.

### `traffic.demandVariability`

| Field | Meaning | Bounds |
| :--- | :--- | :--- |
| `enabled` | turn the model on | boolean, default false |
| `spread` | half-width of the multiplier on `arrivalRate` | 0 – 0.8 |
| `intervalSeconds` | block length; omitted: one multiplier for the whole run | 30 – 3600 |

Each block draws one multiplier uniform on `[1 − spread, 1 + spread]`. Arrivals stay Poisson (or uniform) within a block at the scaled rate. The rate used for an arrival is the one in force when that arrival is scheduled, which is the standard approximation for slowly varying rates.

### Isolation of the draws

Each model has its **own** random stream, `random.Random` seeded from SHA-256 of `"urbanflow-<model>-v1:<simulation seed>"`. Neither touches the engine's main stream (`spawner.rng`), so:

* turning a model on cannot shift any draw the engine already makes (arrival times, turns, classes, sizes);
* the two models cannot shift each other;
* a seed reproduces the run exactly, and a model that is off draws nothing.

### Claims register

The spreads are **assumed**, not calibrated (same honesty as ADR-015's parameter bounds). The result may be described as "driver and demand variability under assumed ranges", never as measured driver behaviour. Calibration against observed headways and counts is out of scope for W31.

### Relation to existing flags

* `unstructuredTraffic` (per-step noise) and `driverAggression` (class-wide offsets) are unchanged and compose with these blocks: aggression sets the baseline, heterogeneity spreads individual drivers around it.
* Scenario documents do not expose the blocks in W31; they are reachable through the engine configuration (`customConfig` of the study routes). Adding them to the scenario document must follow the optional-field pattern so `scenario_fingerprint` is unchanged when absent.

## Consequences

* New optional config blocks, validated strictly (finite numbers, ordered bounds, caps above); invalid input is rejected with a field-named error.
* One extra attribute on `Vehicle`, set only when the model is on.
* The golden corpora enforce "off ⇒ unchanged"; new tests enforce determinism, stream isolation and distribution bounds with the models on.
* The multi-seed runner (W31 T2) shows non-zero spread of delay across seeds with the models on.

## Alternatives considered

* **On by default.** Rejected: moves every pinned result and every published curve.
* **Draw from the main stream.** Rejected: enabling a model would shift all later draws, making "on vs off" comparisons at one seed compare different arrival sequences.
* **Per-step noise only.** Already present (`unstructuredTraffic`); it does not create driver-to-driver differences.
