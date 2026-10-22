# ADR-016: Driver Aggression Profile

## Status

**Accepted** — Spike AG-1 sensitivity evaluation completed and evidence recorded (2026-10-22). Multipliers confirmed across IDM, MOBIL, and vehicle classes. Decision on roundabout safety margins recorded (preserved at 1.0 s without modification).

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
   * **`moderate`:** Time headway $T \times 0.85$; minimum gap $s_0 \times 0.875$; max acceleration $a \times 1.075$; desired speed $+0.025$ of class range (ceiling $1.075 \times \text{limit}$); lane-change politeness $\times 0.75$; lane-change threshold $\times 0.75$; **safe deceleration $b_{safe} = 4.0\text{ m/s}^2$ unchanged**.
   * **`high`:** Time headway $T \times 0.70$; minimum gap $s_0 \times 0.75$; max acceleration $a \times 1.15$; desired speed $+0.05$ of class range (ceiling $1.10 \times \text{limit}$); lane-change politeness $\times 0.50$; lane-change threshold $\times 0.50$; **safe deceleration $b_{safe} = 4.0\text{ m/s}^2$ unchanged**.
   * Comfort deceleration $b$ ($3.0\text{ m/s}^2$) and IDM exponent $\delta$ ($4.0$) are **strictly unchanged**.
3. **Roundabout Critical Gap & Safety Margins Decision:**
   * **Decision:** Roundabout internal convergence safety margins (`_EXIT_SAFETY_HEADWAY` and `_EXIT_COMMIT_MARGIN`) **must NOT be modified** and remain fixed at $1.0\text{ s}$. No physics-adjacent ADR is required.
   * **Justification:** Spike AG-1 proved that roundabout throughput sensitivity is dominated by approach IDM headway ($T$) and launch acceleration ($a$), yielding $+11\%$ to $+25\%$ entry flow without touching conflict zone buffers. Reducing `_EXIT_SAFETY_HEADWAY` below $1.0\text{ s}$ reduces physical clearance in circulating rings at $8\text{ m/s}$ to $< 5.6\text{ m}$, smaller than buses ($12\text{ m}$) or trucks ($10\text{ m}$), creating severe collision and deadlock hazards on curved paths and violating the project zero-collision invariant.
4. **Defaults.** Absent `driverAggression` ⇒ `standard` everywhere stored or frozen. New-scenario **authoring boundaries** (UI defaults and presets, builders, the Python client helper, `/api/v3` specifications, Copilot proposals, `.ufpkg` creation) **write `high` explicitly**. An explicit user choice is always preserved, including an explicit `standard`.
5. **Fingerprint and manifest.** `driverAggression` and the hash of the resolved parameter set are fingerprint components and appear in the manifest assumptions block; `.ufpkg` verify checks them.
6. **Separate from existing flags.** `unstructuredTraffic` (random noise) stays separate. **D-AG2:** `high` does **not** imply `aggressiveTwoWheelers` (approved).
7. **Wording.** Wherever shown: "driver aggression — a simulation assumption, not a measurement of real-world driver behaviour". V3.0 results under `high` are not comparable to V2.0 reports unless the profile is stated.
8. **Validity bounds.** Every profile stays inside the validated ranges of `config_validation`; $T > 0$ and $s_0 > 0$ stay positive; property tests assert no out-of-range parameters across all 5 vehicle classes.
9. **Release timing.** The default is merged only at the **end of W4**, so W1–W3 results are not redefined mid-sprint; their demos declare their profile explicitly.

## Spike AG-1 Evidence & Sensitivity Results

Empirical validation performed in `backend/tests/vehicles/test_aggression_spike.py`:

| Lever / Measurement | Standard | Moderate | High | Sensitivity Effect / Justification |
| :--- | :---: | :---: | :---: | :--- |
| **Desired Time Headway $T$ (Car)** | $1.50\text{ s}$ | $1.275\text{ s}$ | $1.05\text{ s}$ | $-30\%$ in High: tighter following at cruising speeds |
| **Minimum Standstill Gap $s_0$ (Car)** | $2.00\text{ m}$ | $1.75\text{ m}$ | $1.50\text{ m}$ | $-25\%$ in High: $-7.7\%$ physical queue footprint |
| **Max Launch Acceleration $a$ (Car)** | $2.00\text{ m/s}^2$ | $2.15\text{ m/s}^2$ | $2.30\text{ m/s}^2$ | $+15\%$ in High: reduced startup lost time |
| **Desired Speed Factor (Car)** | $[0.90, 1.05]$ | $[0.925, 1.075]$ | $[0.95, 1.10]$ | Safe upper bound at $1.10\times$ speed limit |
| **Equilibrium Spacing at $50\text{ km/h}$** | $22.84\text{ m}$ | $19.46\text{ m}$ | $16.08\text{ m}$ | Monotonic reduction ($-14.8\%$ Mod, $-29.6\%$ High) |
| **Stopline Saturation Capacity** | $1,974\text{ veh/h}$ | $2,251\text{ veh/h}$ | $2,620\text{ veh/h}$ | $+14.0\%$ Mod, $+32.7\%$ High theoretical capacity |
| **5-Vehicle Queue Clearance** | $12.20\text{ s}$ | $11.10\text{ s}$ | $9.90\text{ s}$ | High clears stopline $2.30\text{ s}$ faster than Standard |
| **Emergency Shockwave Braking** | $0$ collisions | $0$ collisions | $0$ collisions | $4\text{ m/s}^2$ lead braking: follower stops safely at $s_0$ |
| **MOBIL Politeness $p$** | $0.30$ | $0.225$ | $0.15$ | Lower altruism allows ego-advantageous changes |
| **MOBIL Threshold $\Delta a_{th}$** | $0.20\text{ m/s}^2$ | $0.15\text{ m/s}^2$ | $0.10\text{ m/s}^2$ | Marginal gain ($+0.70\text{ m/s}^2$ ego, $-2.41$ follower): Std rejects, Mod/High accept |
| **Safe Deceleration $b_{safe}$** | $4.0\text{ m/s}^2$ | $4.0\text{ m/s}^2$ | $4.0\text{ m/s}^2$ | **Strict invariant**: unsafe lane cuts ($>4\text{ m/s}^2$ braking) rejected $100\%$ |
| **Roundabout 120s Simulation** | $18$ exited | $20$ exited | $20$ exited | $+11\%$ throughput gain with $0$ collisions without altering exit safety margins |

## Alternatives Considered

- **Reuse `unstructuredTraffic`:** random noise is not a systematic assumption and cannot be fingerprinted as one.
- **Single boolean `aggressive`:** hides which parameters change and cannot be tested lever by lever.
- **Change global defaults:** would silently redefine every stored scenario and break fingerprints.
- **Tune b and δ as well:** conflates aggression with vehicle dynamics.
- **Relax roundabout exit safety headway:** rejected by AG-1 spike due to severe collision risk on multi-lane ring convergence zones.

## Trade-offs

- **Pros:** reproducibility preserved; behaviour declared and testable; the matrix shows what aggression does to each strategy; zero-collision invariant maintained.
- **Cons:** about 3.0 ED of work including a 108-cell matrix; `high` results are not comparable to earlier reports.

## Consequences

- Required tests: defaults at every authoring boundary, overrides preserved, absent ⇒ `standard` with unchanged fixture fingerprints, schema/TypeScript/package round trip, determinism per profile, and the profile × mix × strategy × density matrix (collisions = 0 and no deadlock asserted; spillback and throughput reported).
- Gate G-AG (Wed 25 Nov 17:00): if it fails, the default is not merged and W4 is not shown at the interim presentation.

## Future Considerations

Per-class or per-approach profiles; calibration against observed headways if real data ever exists (not claimable in V3.0).

## Related ADRs

[ADR-006](adr-006-scenario-configuration-format.md) · [ADR-013](adr-013-v3-integration-contract-and-versioning.md) · [ADR-014](adr-014-strategy-registry-and-entry-gate-seam.md) · [ADR-015](adr-015-robustness-lab-uncertainty-design.md)

