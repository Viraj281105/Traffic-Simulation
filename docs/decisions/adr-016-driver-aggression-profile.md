# ADR-016: Driver Aggression Profile

## Status

**Accepted (implementation); not closed for gate G-AG.** AG-1 evidence was recorded on 2026-10-22 and corrected by the W4 integration audit the same day (see *Audit corrections*). The single-lane signal gridlock the audit found is fixed by [ADR-019](adr-019-stop-line-position-under-driver-aggression.md), which is still **Proposed**. G-AG also needs ADR-019 accepted and the matrix reviewed. The `high` authoring default is not merged until then.

## Date

2026-10-14 (draft) · 2026-10-22 (accepted, AG-1 spike evidence)

## Context

There is **no driver-aggression setting** today. Related mechanisms exist but are different things: `traffic.aggressiveTwoWheelers` (lane-change gaps only, and only with `unstructuredTraffic`), `traffic.unstructuredTraffic` (random per-tick noise in `StochasticIDM`), per-class IDM parameters, global IDM overrides, and hard-coded roundabout safety constants. The project wants high aggression as the default for **new** scenarios. Stored scenarios, `/api/v1`, `/api/v2` and V2.0 reports must not change meaning. Source: strategy §14.

## Problem Statement

How do we introduce a systematic, named aggression assumption as the default for new scenarios without changing any existing result or duplicating the two existing flags?

## Decision

1. **A profile, not a flag flip.** New field `traffic.driverAggression ∈ {standard, moderate, high}`. `standard` is today's behaviour **bit for bit**. A profile is a set of multipliers or offsets applied on top of each vehicle class's base values.
2. **Definitive Multipliers (validated by Spike AG-1):**
   * **`standard`:** All multipliers $1.0$, offsets $0.0$ (bit-for-bit identical to baseline engine).
   * **`moderate`:** Time headway $T \times 0.85$; minimum gap $s_0 \times 0.875$; max acceleration $a \times 1.075$; desired-speed factor $+0.025$ (ceiling $1.10 \times \text{limit}$, the same for every profile); lane-change politeness $\times 0.75$; lane-change threshold $\times 0.75$; **safe deceleration $b_{safe} = 4.0\text{ m/s}^2$ unchanged**.
   * **`high`:** Time headway $T \times 0.70$; minimum gap $s_0 \times 0.75$; max acceleration $a \times 1.15$; desired-speed factor $+0.05$ (ceiling $1.10 \times \text{limit}$); lane-change politeness $\times 0.50$; lane-change threshold $\times 0.50$; **safe deceleration $b_{safe} = 4.0\text{ m/s}^2$ unchanged**.
   * Comfort deceleration $b$ ($3.0\text{ m/s}^2$) and IDM exponent $\delta$ ($4.0$) are **strictly unchanged**.
3. **Roundabout Critical Gap & Safety Margins Decision:**
   * **Decision:** The profile does **not** parametrise roundabout gap acceptance or the internal margins (`_EXIT_SAFETY_HEADWAY`, `_EXIT_COMMIT_MARGIN`, both $1.0\text{ s}$). Since no physics-adjacent change is made, no separate physics ADR is needed.
   * **Justification (measured):** Strategy §14.2 allows parametrising the exit headway only if AG-1 shows it is the dominant lever. On a saturated single-lane roundabout (1,000 veh/h per arm, 300 s, 6 seeds), `_EXIT_SAFETY_HEADWAY` at $0.7\text{ s}$ gave results identical to $1.0\text{ s}$, run for run, under both `standard` and `high`, so it is not binding there. The profile's approach levers alone raised discharge from 96.5 to 106.2 vehicles (+10 %), with 0 collisions. The earlier argument, that 0.7 s is a collision hazard because $8\text{ m/s} \times 0.7\text{ s}$ is shorter than a bus, was arithmetic rather than a measurement, and is withdrawn.
4. **Defaults.** Absent `driverAggression` ⇒ `standard` everywhere stored or frozen. New-scenario **authoring boundaries** (UI defaults and presets, builders, the Python client helper, `/api/v3` specifications, Copilot proposals, `.ufpkg` creation) **write `high` explicitly**. An explicit user choice is always preserved, including an explicit `standard`.
5. **Fingerprint and manifest.** `driverAggression` and the hash of the resolved parameter set are fingerprint components and appear in the manifest assumptions block; `.ufpkg` verify checks them.
6. **Separate from existing flags.** `unstructuredTraffic` (random noise) stays separate. **D-AG2:** `high` does **not** imply `aggressiveTwoWheelers` (approved).
7. **Wording.** Wherever shown: "driver aggression — a simulation assumption, not a measurement of real-world driver behaviour". V3.0 results under `high` are not comparable to V2.0 reports unless the profile is stated.
8. **Validity bounds.** Every profile stays inside the validated ranges of `config_validation`; $T > 0$ and $s_0 > 0$ stay positive; property tests assert no out-of-range parameters across all 5 vehicle classes.
9. **Release timing.** The default is merged only at the **end of W4**, so W1–W3 results are not redefined mid-sprint; their demos declare their profile explicitly.

## Spike AG-1 Evidence & Sensitivity Results

Rows marked *analytic* or with no marking come from `backend/tests/vehicles/test_aggression_spike.py`, which uses IDM formulas and isolated IDM/MOBIL micro-tests. Rows marked *measured* are full-engine runs from the W4 integration audit.

| Lever / Measurement | Standard | Moderate | High | Sensitivity Effect / Justification |
| :--- | :---: | :---: | :---: | :--- |
| **Desired Time Headway $T$ (Car)** | $1.50\text{ s}$ | $1.275\text{ s}$ | $1.05\text{ s}$ | $-30\%$ in High: tighter following at cruising speeds |
| **Minimum Standstill Gap $s_0$ (Car)** | $2.00\text{ m}$ | $1.75\text{ m}$ | $1.50\text{ m}$ | $-25\%$ in High: $-7.7\%$ physical queue footprint |
| **Max Launch Acceleration $a$ (Car)** | $2.00\text{ m/s}^2$ | $2.15\text{ m/s}^2$ | $2.30\text{ m/s}^2$ | $+15\%$ in High: reduced startup lost time |
| **Desired Speed Factor (Car)** | $[0.85, 1.05]$ | $[0.875, 1.075]$ | $[0.90, 1.10]$ | Upper bound $1.10\times$ speed limit |
| **Equilibrium Spacing at $50\text{ km/h}$** | $22.84\text{ m}$ | $19.46\text{ m}$ | $16.08\text{ m}$ | Monotonic reduction ($-14.8\%$ Mod, $-29.6\%$ High) |
| **Stopline Saturation Capacity (analytic, 4.5 m car)** | $1,829\text{ veh/h}$ | $2,087\text{ veh/h}$ | $2,430\text{ veh/h}$ | $+14\%$ Mod, $+33\%$ High: what the parameters imply, **not** a simulation result |
| **5-Vehicle Queue Clearance** | $12.20\text{ s}$ | $11.10\text{ s}$ | $9.90\text{ s}$ | High clears stopline $2.30\text{ s}$ faster than Standard |
| **Emergency Shockwave Braking** | $0$ collisions | $0$ collisions | $0$ collisions | $4\text{ m/s}^2$ lead braking: follower stops safely at $s_0$ |
| **MOBIL Politeness $p$** | $0.30$ | $0.225$ | $0.15$ | Lower altruism allows ego-advantageous changes |
| **MOBIL Threshold $\Delta a_{th}$** | $0.20\text{ m/s}^2$ | $0.15\text{ m/s}^2$ | $0.10\text{ m/s}^2$ | Marginal gain ($+0.70\text{ m/s}^2$ ego, $-2.41$ follower): Std rejects, Mod/High accept |
| **Safe Deceleration $b_{safe}$** | $4.0\text{ m/s}^2$ | $4.0\text{ m/s}^2$ | $4.0\text{ m/s}^2$ | **Strict invariant**: unsafe lane cuts ($>4\text{ m/s}^2$ braking) rejected $100\%$ |
| **Saturated 1-lane roundabout, 300 s, 6 seeds (measured)** | $96.5$ exited | $101.2$ exited | $105.0$ exited | $+9\%$, 0 collisions; `_EXIT_SAFETY_HEADWAY` 0.7 s gives identical results to 1.0 s |
| **Saturated 1-lane fixed-time signal, 300 s, 6 seeds (measured, after ADR-019)** | $93.8$ / $88.3$ exited | $90.8$ / $100.5$ | $96.0$ / $105.8$ | no mix / `{car: 1.0}`; 0 collisions; longest stall ≤ 42 s (before ADR-019: 4 of 24 runs gridlocked) |
| **108-cell matrix, 2-lane, 240 s (measured, after ADR-019)** | headway $3.07\text{ s}$, queued gap $2.60\text{ m}$ | $2.84\text{ s}$, $2.33\text{ m}$ | $2.59\text{ s}$, $2.15\text{ m}$ | 0 collisions, no stall > 40.8 s; see `docs/simulation/driver-aggression.md` §6 |

## Audit corrections (2026-10-22)

* `moderate`'s speed-factor ceiling was recorded as $1.075\times$, but the implementation caps every profile at $1.10\times$ (only the motorcycle reaches it). The car's base factor is $[0.85, 1.05]$, not $[0.90, 1.05]$.
* The theoretical capacities could not be reproduced from the spike test and have been recomputed. The "Roundabout 120 s" row had no backing test and is replaced by measured runs.
* The legacy cars-only population (no vehicle mix) did not receive the speed offset or the politeness multiplier. This is now fixed, so no mix and `{car: 1.0}` behave identically under every profile.

## Alternatives Considered

- **Reuse `unstructuredTraffic`:** random noise is not a systematic assumption and cannot be fingerprinted as one.
- **Single boolean `aggressive`:** hides which parameters change and cannot be tested lever by lever.
- **Change global defaults:** would silently redefine every stored scenario and break fingerprints.
- **Tune b and δ as well:** conflates aggression with vehicle dynamics.
- **Relax roundabout exit safety headway:** not adopted, because AG-1 measured no effect from it in the tested cells (it is not the dominant lever).

## Trade-offs

- **Pros:** reproducibility preserved; behaviour declared and testable; the matrix shows what aggression does to each strategy; zero-collision invariant maintained.
- **Cons:** about 3.0 ED of work including a 108-cell matrix; `high` results are not comparable to earlier reports.

## Consequences

- Required tests: defaults at every authoring boundary, overrides preserved, absent ⇒ `standard` with unchanged fixture fingerprints, schema/TypeScript/package round trip, determinism per profile, and the profile × mix × strategy × density matrix (collisions = 0 and no deadlock asserted; spillback and throughput reported).
- Gate G-AG (Wed 25 Nov 17:00): if it fails, the default is not merged and W4 is not shown at the interim presentation.
- **Resolved blocker (pending acceptance):** saturated single-lane fixed-time signals gridlocked under `moderate`/`high` because the shorter standstill gap moved head vehicles into a turning corridor. [ADR-019](adr-019-stop-line-position-under-driver-aggression.md) keeps the stop position at a line profile-independent, and the seeds that locked up are slow regressions in `backend/tests/vehicles/test_aggression_integration_regressions.py`.

## Future Considerations

Per-class or per-approach profiles; calibration against observed headways if real data ever exists (not claimable in V3.0).

## Related ADRs

[ADR-006](adr-006-scenario-configuration-format.md) · [ADR-013](adr-013-v3-integration-contract-and-versioning.md) · [ADR-014](adr-014-strategy-registry-and-entry-gate-seam.md) · [ADR-015](adr-015-robustness-lab-uncertainty-design.md)

