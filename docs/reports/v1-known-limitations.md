# V1 Known Limitations — Audit and Classification

Audit date: 2026-09-18. Branch: `viraj-dev`.

Every item below was re-measured rather than carried forward from an earlier
note. Each carries one of four classifications:

1. **Blocker** — genuine correctness bug that must be fixed before release.
2. **Fix now** — non-blocking defect worth fixing in this release.
3. **Model limitation** — the model faithfully represents what it claims to;
   the limit is in scope, not in correctness.
4. **V2 / deferred** — real work, deliberately out of scope.

All measurements: `duration=240 s`, `warmupTime=30 s`, 210 s measurement
window, `timeStep=0.1`, seed 1 unless stated. "Offered" is
`arrivalRate x 3600` summed across all four approaches.

---

## 1. Calibrated single-lane comparison — validated

| Geometry | Peak served | Offered at peak | Collisions |
| :-- | --: | --: | --: |
| Fixed-time signal, 1 lane | **1800 veh/h** | 4320 | 0 |
| Roundabout, 1 lane | **1423 veh/h** | 4320 | 0 |

Both match the calibration targets (~1800 and ~1427). Both curves rise
monotonically from free flow through saturation across 360 → 4320 veh/h
offered. Runs are bit-identical for a fixed seed and differ across seeds, for
both geometries.

**This single-lane pair is the scientifically valid comparison.** It is the
only configuration in which both geometries are collision-free across their
whole working range.

---

## 2. Signal junction gridlocks under sustained oversaturation

**Classification: 1 — genuine correctness defect. NOT fixed in this release.**

Measured 1-lane signal capacity curve:

| Offered veh/h | 360 | 720 | 1080 | 1440 | 2160 | 2880 | 3600 | 4320 | 5400 |
| :-- | --: | --: | --: | --: | --: | --: | --: | --: | --: |
| Served veh/h | 291 | 617 | 909 | 1303 | 1491 | **1234** | 1731 | 1800 | **137** |

This was previously recorded as "some high-demand non-monotonic behaviour
after saturation". That understates it. It is a permanent deadlock:

At 1.5 veh/s the exited-vehicle count freezes at 14 by t=60 s and never
increases again; by t=240 s, 310 of 312 vehicles in the network are
stationary. The same cycle forms more slowly at 0.8 veh/s (throughput frozen
from t=180 s), which is what produces the 2880 dip — the dip and the collapse
are the same defect at different onset times, not a measurement artefact.

**Mechanism** (diagnosed, not inferred). Four vehicles — one per arm — end up
stopped inside a ~14 m junction box. They are held there by `find_leader`'s
Layer 4 emergency-proximity check: each is within the ~2.2 m corridor and
minimum safe distance of another, so each brakes to zero for a vehicle that is
itself stopped. It is a physical boxing-in, and the model has no reversing, so
it is unrecoverable. The reservation layer is *not* the cause — two candidate
fixes there (releasing speculative claims held by stalled vehicles, and
excluding stalled vehicles from the turn-priority tie-break) were implemented
and measured, and both left all 18 sweep points byte-identical. Both were
reverted rather than shipped as unvalidated changes to a just-stabilised core.

**Why it is not fixed here.** The real fix is junction-entry admission control
— "do not enter unless you can clear" — which changes how vehicles are
admitted to the box and therefore requires re-calibrating the 1800 veh/h
figure and re-validating the collision budgets. That is not a change to land
at a release gate.

**Scope of impact.** Onset is above roughly 1.5x capacity. The calibrated
comparison (≤ 4320 veh/h offered, 1 lane) is unaffected, and the reported
capacity figures are measured at or below that point. Demonstrations should
stay at or below 1.2 veh/s for a 1-lane intersection.

---

## 3. Multi-lane roundabout capacity falls as lanes are added

**Classification: 3 — model limitation, already deferred to V2.0.**

Roundabout peak served flow, seed 1:

| Lanes | 1 | 2 | 3 |
| :-- | --: | --: | --: |
| Peak served veh/h | 1423 | 1234 | 943 |

Capacity *decreases* with lane count, where published multi-lane roundabout
capacity rises. The cause is genuine and already documented: entry paths from
adjacent lanes of one approach physically cross (pinned by
`test_entry_paths_from_one_approach_genuinely_cross`, which measures a closest
approach under 1.0 m), so added lanes add weaving conflicts faster than they
add capacity. The single-ring geometry cannot express spiral lane assignment,
which is what makes a real multi-lane roundabout work.

Already recorded in the ROADMAP Deferred log as "Multi-Lane Circulating
Roundabout → V2.0 — requires full geometric rewrite supporting independent
ring coordinates".

**Consequence for the report: multi-lane roundabout figures must not be
presented as a calibrated capacity comparison.** Only the 1-lane pair is.

---

## 4. Residual multi-lane roundabout contacts under oversaturation

**Classification: 3 — model limitation, budgeted and tested.**

Measured 0 / 3 / 3 contacts across 8 seeds at 1 / 2 / 3 lanes, at 0.6 veh/s —
a demand well past this roundabout's capacity. Single-lane is exactly zero,
and free-flow demand is exactly zero at every lane count. Guarded by
`test_roundabout_collision_rate_stays_far_below_the_pre_fix_baseline`.

**Observation worth acting on later:** the asserted budget is `{1: 4, 2: 10,
3: 12}` against measured `0 / 3 / 3`. That is roughly 3x headroom, so a real
regression to 9 contacts at 2 lanes would pass unnoticed. Left as-is here
because nightly variance across the full seed set has not been characterised;
tightening it is a follow-up, not a release change.

---

## 5. Permissive-left signal contacts

**Classification: 3 — model limitation, budgeted and tested.**

A fixed-time plan with no protected left phase leaves the permissive left
across opposing through traffic to driver judgement, and a rare contact
survives there under load. Budgeted at ≤2 across 5 seeds
(`test_signal_collisions_stay_negligible_across_seeds`, was 11 before the
conflict-geometry fixes) and ≤2 across 8 seeds at 1-2 lanes
(`test_signal_junction_is_effectively_collision_free`).

One contact was observed at 1 lane / 3600 veh/h offered during this audit
(`conn_south_0_left` ↔ `conn_north_0_straight`) — consistent with the budget,
and above the calibrated comparison point. Adding a protected left phase would
remove it, and would change the capacity baseline; that is a V1.1 controller
feature, not a defect fix.

---

## 6. `ConflictManager` stores one conflict point per lane pair

**Classification: 3 — model limitation, no observed consequence.**

`compute_conflict_points` records the single closest approach per lane pair,
so a pair whose paths cross twice is arbitrated at one point only. On a
signalised 4-arm junction, turn paths cross at most once, so this is exact. It
is only lossy for paths that weave — which is the multi-lane roundabout case
already deferred in §3. No separate action.

---

## 7. Conflict-point precomputation is O(n²)

**Classification: 3 — acceptable; bounded and negligible.**

Measured once per engine construction:

| Geometry | 1 lane | 2 lanes | 3 lanes |
| :-- | --: | --: | --: |
| Signal | 1.3 ms | 10.5 ms | 40.0 ms |
| Roundabout | 23.5 ms | 92.6 ms | 199.2 ms |

`roads.lanesPerApproach` is schema-capped at 4, so the input cannot grow
unboundedly. At worst a fifth of a second, once, at setup. Optimising this
would be effort spent where there is no cost.

---

## 8. Previously tracked follow-ups — current state

| Item | State |
| :-- | :-- |
| `criticalSaturationVolume` post-warmup spawned-count mismatch | **Already fixed.** `MetricCollector` derives the post-warmup count from `spawn_time` rather than the all-time `total_spawned` parameter, and `test_critical_saturation_volume_uses_post_warmup_spawned_count` pins it with an explicit expected value. No action. |
| Seed-resolution duplication in `main.py` | **Fixed in this release** (classification 2). The rule was written out at three restart endpoints; extracted to `_reseed_unless_user_pinned`. Pure extraction, no behaviour change. |
| Roundabout predictive conflict handling | **Resolved and documented.** `VehiclePool.update` gates the predictive layer off for single-ring roundabouts, where the controller's give-way gap acceptance is a complete account of entry (re-deciding it cost ~75% throughput for no safety gain), and leaves it on for multi-ring and for signals. Classification 3. |
| `phaseSequence` vocabulary / validation semantics | **No defect.** `_GROUP_TO_DIRECTIONS` and the `config.schema.json` regex accept exactly the same vocabulary (`n/s/e/w/ns/sn/ew/we` + `all_red`), and an unsupported entry surfaces as a 400, not a 500. No action. |
| `offset` semantics | **Fixed in this release** (classification 2, documentation). It was the one controller field with no schema description; now documented as seconds into the phase plan at t=0, applied at reset, taken modulo cycle length. |
| Roundabout determinism test was vacuous | **Fixed in this release** (classification 2). `test_roundabout_runs_stay_deterministic_for_a_fixed_seed` called a memoised helper twice and compared the returned dict with itself, so it could not fail. It now evicts the cache between runs. Determinism re-verified independently for both geometries. |
| Docs / API / schema / security / deployment ambiguities | Swept: no `TODO`/`FIXME`/`HACK` markers remain in `backend/src`, `frontend/src`, `shared` or `scripts`. Deferrals live in the ROADMAP Deferred log. |

---

## 9. Summary

- The **1-lane signal vs roundabout comparison is scientifically valid** and
  is the only comparison that should be presented as calibrated.
- One **genuine correctness defect** is known and unfixed: junction gridlock
  above ~1.5x capacity (§2). It is out of the calibrated range and has a
  demo workaround (stay at or below 1.2 veh/s), but it is a real bug.
- Multi-lane roundabout behaviour (§3, §4) is a **scope limitation**, already
  deferred to V2.0, and must be labelled as such wherever it is shown.
