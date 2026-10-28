# ADR-019: Stop-Line Position Under Driver Aggression

## Status

**Proposed**: implemented and tested on 2026-10-22 in the W4 integration audit. This is a physics-adjacent change (sprint plan §1.4), so it needs Product Owner acceptance before gate G-AG can pass.

## Date

2026-10-22

## Context

ADR-016 shortens the IDM standstill gap *s₀* under `moderate` (×0.875) and `high` (×0.75). The engine used *s₀* for every stationary obstacle, including signal stop lines, roundabout yield lines and the conflict layer's "refused admission, wait at the line" hold. A head vehicle under `high` therefore stopped 1.5 m short of its stop line instead of 2.0 m.

The junction was laid out for 2.0 m. `SIGNAL_STOP_LINE_SETBACK` and the conflict clearances assume a vehicle waiting at its own red stays out of the paths crossing in front of it. With the extra 0.5 m, a head vehicle's body entered the swept corridor of a right turn (lateral offset 2.22 m against a 2.34 m corridor), and a four-vehicle circular wait formed:

1. A right-turner inside the box stopped for the cross-street head vehicle (the emergency proximity layer).
2. A follower entered behind the right-turner.
3. The opposing right-turner stopped for that follower.
4. The head vehicle waited on the conflict zone the first turner was stalled in.

From then on nothing exited. On saturated single-lane fixed-time signals (1,000 veh/h per arm, 300 s), this happened in 4 of 24 `moderate`/`high` runs, with stalls of 115–169 s and throughput collapsing to 21–41 vehicles. `standard` never stalled beyond 37 s. The 108-cell matrix uses two-lane approaches and never produced this geometry.

## Decision

A stop line is a road marking, not a vehicle. A driver-aggression profile changes the standstill gap to the **vehicle ahead**, not **where a driver stops at a line**.

* `VirtualObstacle` gains `stop_line: bool` (default `False`). It is set by the fixed-time and adaptive signal stop lines, by the roundabout and metered-entry yield lines, and by the conflict layer's refusal held at the start of a connection lane.
* Against a stop-line obstacle only, `VehiclePool` reduces the IDM gap by `stop_line_margin(s₀, profile)` = *s₀ / gap_mult − s₀*. That is the vehicle's own unscaled gap minus its scaled one, so every class stops where it would under `standard`.
* For `standard` (`gap_mult = 1`) the branch is never taken, so pre-W4 behaviour is bit for bit unchanged.
* Gaps to real vehicles, the emergency-proximity stand-ins and the predictive-conflict constraint keep the profile's *s₀*. Queues still compact under `high`.

## Evidence

| Saturated 1-lane fixed-time signal, 300 s, 6 seeds | Before | After |
| :--- | :---: | :---: |
| `standard`, no mix: mean discharged / longest stall | 93.8 / 33 s | 93.8 / 33 s (identical) |
| `high`, no mix | 77.2 / 115 s | 96.0 / 35 s |
| `high`, `{car: 1.0}` | 81.7 / 169 s | 105.8 / 42 s |
| `moderate`, `{car: 1.0}` | 77.2 / 156 s | 100.5 / 36 s |

All runs had 0 collisions. On the roundabout, `high` discharges 105.0 vehicles against 96.5 for `standard`. A head vehicle stopped at a red signal measures 2.0 m from the line under both `standard` and `high` (`test_stopped_head_vehicle_position_is_profile_independent`). The seeds that locked up are pinned as slow regressions in `backend/tests/vehicles/test_aggression_integration_regressions.py`.

## Alternatives Considered

* **Move the stop line back under aggression.** That changes geometry and the snapshot/visual stop line, and treats every class the same even though their *s₀* differ.
* **Exempt queued vehicles from the emergency-proximity check.** That weakens a collision guard to fix a placement problem.
* **Do not scale *s₀* at all.** That drops a lever ADR-016 approved and the matrix shows working (−10.6 % measured queued gap).

## Consequences

* `moderate`/`high` results change at every junction type wherever a vehicle waits at a line. The 108-cell matrix was re-run after this change (`docs/simulation/driver-aggression.md` §6).
* Any future obstacle that represents a marking must set `stop_line=True`. One that represents a vehicle must not.

## Related ADRs

[ADR-016](adr-016-driver-aggression-profile.md) · [ADR-014](adr-014-strategy-registry-and-entry-gate-seam.md)
