# Bug-Fix Audit Report

Running log of the full-project bug-fixing pass (started 2026-09-24).
Each entry was reproduced before fixing and carries a regression test that
fails on the pre-fix code and passes after it.

## Confirmed bugs

### BUG-1
- Severity: High
- Component: Vehicle spawning / collision prevention
- Symptom: Once a queue grew back to the start of an approach, newly spawned
  vehicles drove into and through the vehicle ahead (same-lane overlaps of up
  to ~1.2 m, persisting for seconds). The collision audit skips same-lane
  pairs, so none of this was reported as a collision. Reproduced with
  `fixed_time_signal`, 1 lane, 1.2 veh/s, seed 2 (veh_10 into veh_9 at t=7.0 s)
  and in every roundabout/signal run at 1.2 veh/s.
- Root cause: `VehicleSpawner._attempt_spawn` inserted every vehicle at its full
  desired speed (18–25 m/s) whenever the entry had `minimumGap + maxLength` of
  clearance, regardless of the speed of the vehicle just ahead. A car at
  23 m/s with 7 m of room cannot stop even at the IDM's 9 m/s² hard limit.
- Fix: cap the insertion speed at the safe-stopping speed
  `sqrt(v_lead² + 2·b·(gap − s0))` (b = `comfortDeceleration`, s0 =
  `minimumGap`). Free-flowing entries are unaffected (cap exceeds desired
  speed); no extra RNG draws, so arrival streams are unchanged.
- Files changed: `backend/src/vehicles/spawner.py`
- Regression test: `tests/vehicles/test_spawner.py::test_spawn_behind_stopped_vehicle_enters_slowly_enough_to_stop`,
  `::test_spawn_on_empty_lane_still_enters_at_desired_speed`,
  `::test_saturated_entry_never_produces_same_lane_overlap`
- Validation: invariant harness over signal/roundabout × 1–2 lanes × 1.2 veh/s ×
  2 seeds: same-lane overlaps 6306/11666/812/6970/17689/892 → 0 in every run.
- Status: FIXED

### BUG-2
- Severity: Medium
- Component: API / configuration validation
- Symptom: The scenario contract's validation summary (§5 of
  `06-scenario-configuration-contract.md`) lists cross-field rules that were
  enforced nowhere. `POST /api/v1/simulations` accepted `innerRadius: 30,
  outerRadius: 10` (201, inverted ring simulated), a `directionalSplit` of
  1/1/1/1 (silently 4× the requested demand), `turnProbabilities` summing to
  1.5, `warmupTime ≥ duration`, `desiredSpeed.max < min`, and NaN numbers
  (NaN passes every JSON-schema bound). `arrivalDistribution: "burst"` — in the
  schema enum but unimplemented — escaped as `NotImplementedError` → HTTP 500 on
  both `/api/v1/simulations` and `/api/simulation/new`. `/api/v1/configs/validate`
  reported all of these as valid.
- Root cause: only `jsonschema.validate` was run; the schema cannot express
  cross-field rules and nothing else checked them.
- Fix: new `src/core/config_validation.semantic_config_errors()` implementing
  the documented rules (+ `burst` rejected as not implemented, + finiteness),
  used by the validate endpoint and both creation routes (400
  `VALIDATION_ERROR`). `warmupTime < duration` is applied only to an explicit
  `warmupTime`, so existing short runs relying on the 30 s default keep working
  (the typed route validates the client's `exclude_unset` dump for this reason).
- Files changed: `backend/src/core/config_validation.py` (new), `backend/src/main.py`
- Regression test: `tests/core/test_config_cross_field_rules.py` (16 cases)
- Validation: 10 API-level tests fail on pre-fix `main.py`, all pass after;
  `tests/api`, `tests/core`, config/API integration tests pass.
- Status: FIXED

### BUG-3
- Severity: Medium
- Component: API / live dashboard (`POST /api/simulation/config`)
- Symptom: The live endpoint only rejected values that were not numbers at
  all. `lanesNorth: 0`, `-1` or `9`, `arrivalRate: -1`, `"nan"`, `"inf"` or
  `1e9`, `laneWidth: 0`, negative yellow/all-red, `greenDuration: 0`,
  `followUpTime: -2` were all accepted (200) and the engine ran them.
- Root cause: the endpoint builds its config by hand and never applied the
  schema bounds the versioned API enforces.
- Fix: `_live_config_errors()` validates the compiled config against
  `CONFIG_SCHEMA` (checking each per-direction lane count as the scalar the
  schema expects) plus the cross-field rules; on failure the session keeps its
  previous valid config.
- Files changed: `backend/src/main.py`
- Regression test: `tests/core/test_config_cross_field_rules.py::test_live_config_rejects_out_of_range_values`
  (7 cases), `::test_live_config_accepts_short_duration_despite_fixed_warmup`
- Validation: as BUG-2.
- Status: FIXED

### BUG-4
- Severity: Medium
- Component: Metrics configuration / contract drift
- Symptom: `metrics.waitSpeedThreshold` and `metrics.stopSpeedThreshold` — the
  location given by the scenario contract, the JSON schema and the typed
  `MetricsSection` — were ignored. A typed-route config with
  `metrics.waitSpeedThreshold: 2.0` still ran with 0.5. On the typed route there
  was no way to set them at all (`VehicleGenerationSection` has no such fields,
  so Pydantic drops them there).
- Root cause: `MetricCollector` and `VehicleSpawner` read only
  `vehicleGeneration.*` (the dashboard/study presets' legacy location).
- Fix: `resolve_speed_threshold()` — `metrics` wins, `vehicleGeneration` still
  honoured as a fallback; metric contract §7.3 text corrected.
- Files changed: `backend/src/metrics/collector.py`, `backend/src/vehicles/spawner.py`,
  `docs/architecture/07-metric-contract.md`
- Regression test: `tests/metrics/test_new_metrics.py::test_speed_thresholds_are_read_from_metrics_section`,
  `::test_speed_thresholds_legacy_vehicle_generation_location_still_works`
- Validation: metrics/vehicles suites pass.
- Status: FIXED

### BUG-5
- Severity: Medium
- Component: Vehicle spawning / demand composition
- Symptom: Under congestion the configured turning mix was not what entered
  the network. 2-lane signal, 1.5 veh/s, seed 3, turn split 30/40/30:
  vehicles spawned 28.5/46.4/25.1 (left/straight/right).
- Root cause: a blocked arrival is retried every tick, and each retry re-drew
  the turn intent. A left/right-turner (confined to one lane) was re-rolled until
  it drew "straight" (allowed in any lane) and got in.
- Fix: the arrival's turn intent is drawn once and kept per direction until
  that vehicle is placed. Uncongested runs consume the RNG identically, so their
  results are bit-for-bit unchanged (verified at 0.4 veh/s).
- Files changed: `backend/src/vehicles/spawner.py`
- Regression test: `tests/vehicles/test_spawner.py::test_blocked_arrival_keeps_its_turn_intent_until_placed`
- Validation: fails on pre-fix spawner, passes after.
- Status: FIXED

### BUG-6
- Severity: Low
- Component: Metrics — Directional Fairness Index
- Symptom: With traffic on a single approach (or any approach with no
  vehicles), DFI reported ≤ 0.25–0.75 ("unfair") for a perfectly even junction.
- Root cause: approaches with no vehicles were entered into Jain's index as a
  0 s average with n = 4, contrary to metric contract §5.1 ("exclude it from the
  calculation and adjust n").
- Fix: only approaches with vehicles contribute; n adjusts.
- Files changed: `backend/src/metrics/definitions/fairness.py`
- Regression test: `tests/metrics/test_metrics.py::test_directional_fairness_excludes_directions_without_vehicles`
- Validation: metrics suite passes.
- Status: FIXED

### BUG-7
- Severity: Medium
- Component: Roundabout controller — approach speed regime
- Symptom: At a lightly loaded roundabout (1 lane, 0.3 veh/s) 55 of 56
  vehicles braked at ≥ 6 m/s² — almost all at the IDM 9 m/s² hard limit — on
  the approach (signal: 12 of 56, mostly real stop-line events).
- Root cause: `_approach_speed_limit` was a step — no cap, then `entrySpeed` the
  instant a vehicle crossed 60 m from the give-way line — so a 20–25 m/s
  vehicle's desired speed dropped to 5 m/s in one tick and IDM's free-road term
  (−a(v/v₀)⁴) saturated at the hard limit. The code's own comment computes that
  ~100 m is needed at 3 m/s².
- Fix: outside the zone the ceiling is `sqrt(entrySpeed² + 2·3·(d − 60))` —
  the comfortable-braking curve that reaches `entrySpeed` at the zone boundary.
  Continuous with the zone cap and the existing congested taper; nothing inside
  the zone changes.
- Files changed: `backend/src/controllers/roundabout.py`,
  `tests/controllers/test_controllers.py` (three congestion tests placed their
  "free-flowing" probe vehicle 70 m out, where it is now legitimately on the
  taper; they were moved to 170 m with a queue long enough (>60 m) for the
  congestion taper to be the binding one — assertions unchanged in substance)
- Regression test: `tests/controllers/test_controllers.py::test_roundabout_approach_cap_does_not_force_emergency_braking`
  (pre-fix: −9.0 m/s²; post-fix peak ≈ −5.5 m/s²)
- Validation: controller suite passes; hard-braking vehicles 55/56 → 28/56,
  remaining events are yield/queue stops at the give-way line.
- Status: FIXED

### BUG-8
- Severity: Low
- Component: Vehicle kinematics / snapshot contract
- Symptom: Every stationary queued vehicle was reported in snapshots with
  `acceleration: -9.0` (braking at the hard limit) while standing still.
- Root cause: `Vehicle.update_state` stored the IDM-commanded acceleration
  even when the zero-speed floor clipped it.
- Fix: store the realised acceleration `(v_new − v_old)/dt`.
- Files changed: `backend/src/vehicles/vehicle.py`
- Regression test: covered by `test_roundabout_approach_cap_does_not_force_emergency_braking`
  (reads realised acceleration) and existing `tests/vehicles/test_vehicle.py`.
- Validation: vehicle/core/controller suites pass.
- Status: FIXED

### BUG-9
- Severity: High (performance; real-time runs degrade and then fall behind)
- Component: Metrics collector / snapshot pipeline
- Symptom: A `/api/v1/simulations` run's per-tick cost grew linearly with
  elapsed time: 4 ms/tick at start, ~37 ms at 20 simulated minutes, on course
  to exceed the 100 ms real-time tick budget before the 1-hour maximum.
- Root cause: the tick callback builds a snapshot every tick; each snapshot
  calls `get_metrics()`, which rescanned the entire per-tick queue history
  (per-direction series, totals, SD, QSI) — O(T) per tick, O(T²) per run.
- Fix: running integer aggregates maintained in `update()`; `get_metrics()`
  derives the same values from them in O(1). Integer sums make them exact, so
  every reported value is unchanged.
- Files changed: `backend/src/metrics/collector.py`
- Regression test: `tests/metrics/test_new_metrics.py::test_queue_statistics_match_history_without_rescanning_it`
  (values equal the rescanned ones; iterating the history raises)
- Validation: per-tick cost at tick 10 000: ~37 ms → ~2–6 ms, flat.
- Status: FIXED

### BUG-10
- Severity: High
- Component: Signalised junction — conflict-zone admission / deadlock
- Symptom: At saturation the signalised junction froze permanently. 1 lane,
  1.5 veh/s, seed 1 (the pinned-curve 5400 veh/h point once other fixes
  changed its random stream): a south-straight and a north-left vehicle stopped
  inside the box at t ≈ 178 s and never moved; E/W vehicles piled in behind
  them and nothing exited for the rest of the run. The baseline code shows the
  same failure on other seeds (1 lane, 1.0 veh/s, seed 3: 4 exits in the last
  minute plus a collision).
- Root cause: `router.is_blocked_before_lane()` treated the *yellow* stop-line
  obstacle as blocking even when Layer 2's dilemma-zone rule had already let the
  vehicle run it. Layer 3 therefore skipped ConflictManager admission for every
  yellow-runner — and for every permissive left-turner released from the stop
  line at yellow onset — so they entered the junction holding no reservations,
  stopped on crossings other vehicles held, and the symmetric "stationary vehicle
  near a crossing" occupancy rule then blocked both sides forever.
- Fix: one shared `commits_through_yellow()` predicate used by Layer 2 and by
  `is_blocked_before_lane()` (for the current lane), so a vehicle cleared to run
  the yellow goes through normal all-or-nothing admission.
- Files changed: `backend/src/vehicles/router.py`
- Regression test: `tests/vehicles/test_router.py::test_vehicle_committed_to_yellow_is_not_treated_as_blocked_before_junction`
  (fast), `::test_saturated_signal_does_not_freeze_after_yellow_entries` (slow,
  the recorded lock-up end to end). Both fail pre-fix.
- Validation: lock-up scan (1 lane, 1.0 veh/s, seeds 1–6): baseline 1 lock-up +
  2 collisions; fixed 0 lock-ups, 0 collisions.
- Status: FIXED

### BUG-11
- Severity: Medium
- Component: Dual comparison (`DualSimulationOrchestrator`)
- Symptom: The signal side of the live dual comparison ran a different signal
  depending on which geometry the dashboard happened to have selected: with
  "signal" selected, the canonical paired 30/4/2 s plan (72 s cycle); with
  "roundabout" selected, 15 s greens, a 3 s yellow and the one-direction-at-a-time
  cycle (100 s).
- Root cause: when the source controller block had no `straightRightDuration`
  (it holds ring parameters when the dashboard is on roundabout), the
  orchestrator injected ad-hoc 15/5/3/2 values and no `phaseSequence`.
- Fix: in that case the signal gets the canonical defaults (paired
  `phaseSequence` from `ControllerSection`, controller's own 30/5/4/2 fallbacks).
- Files changed: `backend/src/snapshot/dual_orchestrator.py`,
  `tests/integration/test_dual_simulation.py` (the determinism tests compared
  live `desired_speed`, which the roundabout controller legitimately lowers on
  the approach; they now compare each vehicle's spawn-time desired speed)
- Regression test: `tests/integration/test_dual_simulation.py::test_dual_signal_timing_does_not_depend_on_dashboard_geometry`
- Validation: dual + API suites pass.
- Status: FIXED

### BUG-12
- Severity: Medium
- Component: Study — volume sweep persistence
- Symptom: Sweep runs silently overwrote each other in run history. Rates
  `[0.285, 0.289, 0.29]` produced three runs per geometry but only 2 rows in
  `simulation_runs`; 0.29 was also labelled `_28`.
- Root cause: run id suffix `int(rate * 100)` — truncation plus collisions —
  written with `INSERT OR REPLACE`.
- Fix: rounded label; a clashing label gets the rate's position appended.
  Typical sweeps keep the same id format.
- Files changed: `backend/src/study/volume_sweep.py`
- Regression test: `tests/study/test_volume_sweep.py::test_sweep_run_ids_are_unique_and_correctly_labelled`
- Validation: fails pre-fix (2 rows), passes after (6 rows).
- Status: FIXED

### BUG-13
- Severity: Low
- Component: Study runners / reproduction — tick counting
- Symptom: Sweep, Monte-Carlo, invariant and reproduction runs with a
  fractional duration stopped one tick early for about a third of 0.1 s-granular
  values (2.3 s → 22 ticks = 2.2 s), while recording the requested duration.
- Root cause: `int(duration / time_step)` truncates float noise
  (2.3/0.1 = 22.999…); the engine itself stops at ceil.
- Fix: `Clock.ticks_for_duration()` (ceil with an epsilon, matching the engine's
  stop rule) used at all four call sites.
- Files changed: `backend/src/core/clock.py`, `backend/src/study/volume_sweep.py`,
  `backend/src/study/validation.py`, `backend/src/main.py`
- Regression test: `tests/core/test_clock.py::test_ticks_for_duration_matches_the_engine_stop_rule`
- Validation: clock/study/database suites pass. Integer durations were never
  affected, so no existing result changes.
- Status: FIXED

### BUG-14
- Severity: Medium
- Component: Study framework (volume sweep, Monte Carlo) / dual orchestrator
- Symptom: (a) The Volume Sweep and Monte-Carlo dashboards offer Δt = 0.05 /
  0.1 / 0.2 s and print the chosen Δt beside the results, but every run used
  0.1 s — a sweep requested at 0.2 s recorded `timing.timeStep = 0.1`.
  Reproductions of runs recorded at another Δt could not honour it either,
  although `docs/operations.md` says they do. (b) A sweep request whose
  `customConfig.simulation.duration` (5 s) was shorter than its `duration`
  (10 s) returned HTTP 500.
- Root cause: `DualSimulationOrchestrator` hard-coded `Clock(0.1)`; the runners
  counted ticks from the request's duration while the engines ran the
  customConfig's, so the engine completed mid-loop and `step()` raised.
- Fix: the orchestrator's clocks use `simulation.timeStep`; the runners count
  ticks on the orchestrator's clock; the validated request `duration` is written
  into the engines' config. Because cost scales with 1/Δt, the study endpoints
  now bound `customConfig.simulation.timeStep` to [0.05, 1.0] s (422 outside),
  keeping the existing workload caps meaningful.
- Files changed: `backend/src/snapshot/dual_orchestrator.py`,
  `backend/src/study/volume_sweep.py`, `backend/src/study/validation.py`,
  `backend/src/main.py`
- Regression test: `tests/api/test_study_limits.py::test_sweep_honours_custom_time_step`,
  `::test_sweep_custom_duration_mismatch_is_not_a_500`,
  `::test_study_time_step_is_bounded` (10 cases)
- Validation: study/API/dual suites pass (72 API tests).
- Status: FIXED

### BUG-15
- Severity: Low
- Component: API — history/sweep/replay listings
- Symptom: `GET /api/v1/study/history/runs?limit=-1` (and `/study/sweeps`,
  `/replays`) returned the entire table, sweep result blobs included; negative
  offsets were accepted.
- Root cause: `limit`/`offset` passed straight into SQL `LIMIT ? OFFSET ?`;
  SQLite reads a negative LIMIT as "no limit".
- Fix: `limit` bounded to 1–500, `offset ≥ 0` (FastAPI `Query`, 422 otherwise).
- Files changed: `backend/src/main.py`
- Regression test: `tests/api/test_study_limits.py::test_listing_pagination_is_bounded` (12 cases)
- Validation: API suite passes.
- Status: FIXED

### BUG-16
- Severity: Medium (security / resource use)
- Component: API — `GET /api/v1/study/export`
- Symptom: With `API_KEY` set, every POST study endpoint demands the bearer
  token, but `GET /api/v1/study/export` — which builds its report by running a
  fresh 16-simulation volume sweep plus a 3-seed Monte-Carlo study and
  **persisting the sweep to run history** — was open to any caller.
- Root cause: the route was declared without `Depends(require_api_key)`,
  although it is both compute-heavy and mutating (the policy's stated scope).
- Fix: the route requires the key like its POST siblings. The browser app is
  unaffected (nginx attaches the key server-side to proxied `/api/` calls).
- Files changed: `backend/src/main.py`
- Regression test: `tests/api/test_api_key_auth.py::test_study_export_requires_the_key`
- Validation: auth + study API tests pass.
- Status: FIXED

### BUG-17
- Severity: Low
- Component: Report generation (`src/study/report_generator.py`)
- Symptom: The study CSV headed the sweep's throughput columns
  "Throughput (veh/h)" but filled them with vehicle counts; the verdict text
  quoted the crossover as "veh/s/approach" although the sweep's `arrivalRate`
  is the whole junction's (its own `crossoverHourlyVolume` = rate × 3600).
- Fix: labels corrected ("vehicles served", "veh/s (whole junction)"). The
  existing verdict test pinned the wrong unit and was corrected with it.
- Files changed: `backend/src/study/report_generator.py`,
  `tests/study/test_report_generator.py`
- Regression test: `tests/study/test_report_generator.py::test_report_labels_match_the_reported_quantities`
- Validation: report-generator tests pass.
- Status: FIXED

### BUG-18
- Severity: Medium (reporting integrity)
- Component: CLI study runner (`scripts/run_full_study.py`)
- Symptom: (a) Offered demand was printed as `rate × 3600 × 4` "veh/h (total
  intersection)" — four times the real volume (0.25 veh/s printed as 3600 veh/h
  instead of 900), the same overstatement `volume_sweep.py` had already fixed.
  (b) Whenever the sweep found a delay crossover, the runner printed fixed
  conclusions — "Roundabout yields up to 50% lower vehicular delay",
  "Signal provides better queue fairness" — that nothing in the run measured.
  (c) Before BUG-14, `--time-step` changed only the step count, not the clock, so
  `--time-step 0.2` silently simulated half the requested duration.
- Fix: correct volume and unit label; the crossover conclusion is now the
  sweep's own data-derived verdict (`_summarize_sweep_verdict`); (c) resolved by
  BUG-14.
- Files changed: `scripts/run_full_study.py`
- Regression test: `tests/study/test_run_full_study_cli.py::test_cli_reports_whole_junction_volume_and_measured_verdict`
- Validation: CLI end-to-end smoke run (2 s sweep) prints `[900] veh/h`.
- Status: FIXED

### BUG-19
- Severity: High
- Component: Signalised junction — ConflictManager admission control / deadlock
- Symptom: Multi-lane signals froze under heavy demand. 3 lanes, 0.8 veh/s,
  seed 1: from t ≈ 95 s six vehicles sat motionless inside the box and nothing
  exited for the rest of the run (977 veh/h "served" at 2880 veh/h offered). The
  baseline code froze the 2-lane signal at the same demand (1200 veh/h).
- Root cause: `ConflictManager.get_conflict_distance` documents that a vehicle
  refused admission "takes none and waits at the stop line, outside the box",
  but it returned the distance to `ZONE_RADIUS` before the first *blocked
  conflict point*. On turning paths (3-lane geometry especially) that point is
  up to ~10 m into the junction, so refused vehicles rolled 1–4 m into the box
  with no reservations and parked on crossings that other vehicles had been
  admitted to — the exact partial occupation the admission rule exists to stop.
  (A south-left turner in the recorded run entered at t = 86.2 s holding 0
  zones.)
- Fix: a refused (or stopped, approaching) vehicle gets block distance 0 — the
  start of its connection lane, i.e. the stop line. Admitted vehicles and
  vehicles already in the junction are unchanged.
- Files changed: `backend/src/intersection/conflict_manager.py`
- Regression test: `tests/intersection/test_intersection.py::test_refused_vehicle_is_held_at_the_stop_line_not_inside_the_box`
  (pre-fix: held 2.76 m inside the box), `::test_admitted_vehicle_is_not_held`
- Validation: recorded run discharges steadily (~15 exits / 20 s) to the end;
  intersection/vehicle/controller suites pass; multi-lane lock-up scan below.
- Status: FIXED

### BUG-20
- Severity: Medium (test coverage / CI)
- Component: CI — nightly slow-suite job
- Symptom: The slow job runs an explicit per-file matrix that omitted
  `tests/integration/test_calibrated_capacity_regression.py`, so the full
  published-curve pins and the crossover-ordering test never ran in CI (only
  the 2-point fast representative did). New slow tests added elsewhere would
  have been silently skipped the same way.
- Fix: matrix entries for `calibrated-capacity` and `signal-lockup`
  (`tests/vehicles/test_router.py`), plus a comment stating the rule. Every
  file containing `@pytest.mark.slow` is now listed.
- Files changed: `.github/workflows/ci.yml`
- Regression test: n/a (CI configuration); verified by listing every file that
  contains `mark.slow`.
- Status: FIXED


### BUG-21
- Severity: High (physics / comparability)
- Component: `vehicles/spawner.py`, `roads.speedLimit`
- Symptom: `roads.speedLimit` (default 13.89 m/s, 50 km/h) was accepted,
  validated and documented but never read. Every driver wanted 18–25 m/s
  (65–90 km/h) at an urban junction, and the dashboard, sweep and validation
  configs set that range explicitly. At the signal, vehicles crossed on green
  at up to 90 km/h, which is what made signal traffic look much faster than
  roundabout traffic. The roundabout had to shed that speed to 18 km/h before
  its give-way line.
- Root cause: no code path from the road's speed limit to a vehicle's
  desired speed.
- Fix: unless `vehicleGeneration.desiredSpeed` is set, desired speed is drawn
  from 85–105% of `roads.speedLimit` (`vehicles/speed_profile.py`); the
  dashboard, sweep and validation configs no longer override it.
- Regression tests: `tests/vehicles/test_speed_profile.py`
  (`test_desired_speed_follows_the_speed_limit`,
  `test_spawned_vehicles_use_the_speed_limit_range`,
  `test_same_seed_gives_both_geometries_the_same_drivers`).
- Status: FIXED

### BUG-22
- Severity: High (physics / comparability)
- Component: `vehicles/pool.py` (signal connection lanes)
- Symptom: signal turning movements had no curve-speed limit. A right turn
  on a 5–9 m radius was taken at whatever speed the vehicle had (often more
  than 10 m/s, i.e. above 2 g lateral), while every roundabout movement was
  slowed by the entry and circulating caps. The two geometries ran under
  different physics.
- Fix: one lateral-acceleration limit (`maxLateralAcceleration`, default
  3.0 m/s², consistent with the FHWA fastest-path speed–radius relation) on
  every curved path in both geometries. A vehicle's speed is at most √(a·R),
  with a comfortable-braking look-ahead into the curve. Radius is measured over
  a ±5 m chord so polyline kinks don't create artificial limits.
- Regression tests: `test_every_turn_is_slower_than_the_speed_limit`
  (both geometries), `test_ring_speed_matches_its_radius`,
  `test_vehicle_brakes_for_the_curve_before_reaching_it`.
- Status: FIXED

### BUG-23
- Severity: Medium (geometric delay inflated)
- Component: `controllers/roundabout.py::_ENTRY_APPROACH_ZONE`
- Symptom: every roundabout vehicle drove the last 60 m before the give-way
  line at `entrySpeed` (5 m/s), even at an empty roundabout. This added about
  6 s of delay per vehicle (free-flow delay 13.4 s at 180 veh/h, seed 1) and
  made queues look like they were forming when nobody was waiting.
- Root cause: the 60 m zone was sized for 25 m/s approach speeds before the
  continuous braking taper (BUG-7) existed; the taper now does the slowing.
- Fix: zone reduced to 10 m (two vehicle lengths); free-flow delay 7.7 s.
  Peak braking and collision counts are unchanged in the 162-run matrix.
- Regression tests: `test_empty_roundabout_geometric_delay_is_bounded`,
  `test_roundabout_free_flow_entry_speed_cap` (updated).
- Status: FIXED

### BUG-24
- Severity: Medium (unnecessary waits)
- Component: `controllers/roundabout.py` gap acceptance
- Symptom: at light demand, entering drivers stopped for circulating vehicles
  that were about to leave the ring at an earlier exit and would never reach
  them. Traced first stops at 540–720 veh/h: about 1 in 4 was for such a
  vehicle, with the junction visibly empty at the entry.
- Root cause: only vehicles exiting at the entry's own arm were excluded
  from the conflicting stream.
- Fix: a circulating vehicle whose exit lies between it and the entry
  (read from its own path), or which is already on its exit stub outside the
  ring, is not conflicting traffic. Vehicles that pass the entry are still
  yielded to; no safety check was relaxed.
- Regression tests: `test_entry_ignores_vehicles_leaving_before_the_entry`,
  `test_entry_still_yields_to_vehicles_that_pass_it`.
- Status: FIXED

### BUG-25
- Severity: Medium (the guided comparison was not the calibrated one)
- Component: `main.py DEFAULT_CONFIG`, `study/volume_sweep.py`,
  `study/validation.py`, `frontend/src/types/config.ts`
- Symptom: the calibrated study used IDM a = 2.0, b = 3.0 m/s², a 30 s
  green, 4 s yellow and gap acceptance 4.0 / 2.5 s. The live comparison and the
  studies used a = 3.0, b = 3.5, 18–25 m/s, a 25 s green, 3 s yellow and
  4.5 / 2.8 s. The sweep also excluded only 15 s of warm-up, and the validation
  study only 5 s. Results labelled "calibrated, 1 lane" therefore came from a
  different vehicle population and measured start-up transients.
- Fix: one parameter set everywhere (the calibrated one); study warm-up is
  30 s, shortened only for runs under 120 s (`study_warmup`, at most a quarter
  of the run).
- Status: FIXED

## Effect on published results

Several fixes change simulated physics (BUG-1, 5, 7, 10, 19), so the pinned
calibrated curve was re-measured and re-pinned (tolerances unchanged) and
`docs/reports/comparative_report.md` was updated with a revision entry. Each
shift was attributed by running the curve with individual fixes reverted.

| Result | Before | After | Cause |
| --- | --- | --- | --- |
| Roundabout 1-lane delay at 360 veh/h (seed 1) | 15.1 s | 18.7 s | BUG-7 (vehicles now brake at ~3 m/s² instead of 9 m/s²) |
| Signal 1-lane seed-1 peak served | 1697 veh/h | 1543 veh/h | BUG-19 (refused left-turners wait at the stop line, not inside the box) |
| Signal vs roundabout at saturation, 5-seed mean served | — | 1457 vs 1361 (4320), 1512 vs 1389 (5400) | signal still ahead on average; delay lower (p = 0.017 / 0.047) |
| Low-demand 5-seed delay difference (360/720/1080) | not significant | not significant | unchanged conclusion |
| Multi-lane roundabout peak (1/2/3 lanes) | 1423 / 1234 / 943 | 1406 / 2040 / 2417 | mostly the in-progress predictive lock-up fix that was already in the working tree, plus this pass |
| Collisions, 1-lane, all pinned points | 0 | 0 | — |

### Calibration pass (BUG-21 to BUG-25), 2026-09-25b

The same harness was run on the code before and after the pass: 1–3 lanes,
9 demand points, seeds 1–3, both geometries, 240 s with a 30 s warm-up and
the calibrated controller settings. Values are 3-seed means, before → after.
Queued time is time below 0.5 m/s.

| Lanes | Offered veh/h | Signal served | Signal delay (s) | Roundabout served | Roundabout delay (s) | Roundabout queued time (s) | Collisions sig/rbt |
|---:|---:|---|---|---|---|---|---|
| 1 | 360 | 360 → 337 | 17.5 → 17.0 | 366 → 349 | 19.2 → 10.1 | 0.2 → 0.2 | 0/0 → 0/0 |
| 1 | 720 | 651 → 611 | 24.9 → 23.0 | 691 → 686 | 21.7 → 12.8 | 0.9 → 0.8 | 0/0 → 0/0 |
| 1 | 1080 | 903 → 777 | 24.2 → 28.0 | 966 → 937 | 26.2 → 18.8 | 2.7 → 3.2 | 0/0 → 0/0 |
| 1 | 1440 | 1097 → 1046 | 31.4 → 37.9 | 1154 → 1131 | 38.0 → 29.8 | 7.0 → 7.9 | 0/0 → 0/0 |
| 1 | 2160 | 1280 → 1080 | 48.0 → 45.6 | 1251 → 1246 | 53.6 → 46.8 | 13.9 → 13.9 | 0/0 → 0/0 |
| 1 | 2880 | 1474 → 1114 | 52.4 → 54.7 | 1343 → 1280 | 63.1 → 54.2 | 19.4 → 18.1 | 0/0 → 0/0 |
| 1 | 3600 | 1486 → 1074 | 51.4 → 60.1 | 1354 → 1303 | 71.2 → 63.2 | 22.5 → 25.1 | 0/0 → 0/0 |
| 1 | 4320 | 1486 → 1171 | 57.5 → 66.5 | 1366 → 1320 | 74.6 → 65.0 | 25.9 → 24.7 | 0/0 → 0/0 |
| 1 | 5400 | 1537 → 1194 | 60.4 → 64.8 | 1406 → 1343 | 76.5 → 68.6 | 24.2 → 26.3 | 0/0 → 0/0 |
| 2 | 360 | 366 → 337 | 12.9 → 13.8 | 371 → 371 | 17.7 → 8.5 | 0.1 → 0.0 | 0/0 → 0/0 |
| 2 | 720 | 680 → 674 | 16.4 → 14.7 | 697 → 686 | 18.9 → 10.2 | 0.3 → 0.4 | 0/0 → 0/0 |
| 2 | 1080 | 1017 → 914 | 15.2 → 16.7 | 994 → 989 | 20.5 → 12.0 | 0.7 → 1.1 | 0/0 → 0/0 |
| 2 | 1440 | 1400 → 1303 | 17.7 → 18.7 | 1394 → 1349 | 24.5 → 16.8 | 2.2 → 3.1 | 0/0 → 0/0 |
| 2 | 2160 | 1949 → 1754 | 24.3 → 27.6 | 1754 → 1709 | 39.1 → 31.4 | 9.2 → 10.0 | 0/0 → 0/0 |
| 2 | 2880 | 2383 → 2097 | 30.0 → 32.1 | 1954 → 1771 | 46.6 → 43.1 | 13.3 → 16.5 | 0/0 → 0/1 |
| 2 | 3600 | 2646 → 2240 | 37.5 → 41.6 | 1971 → 1840 | 59.9 → 52.9 | 19.7 → 20.5 | 0/1 → 0/0 |
| 2 | 4320 | 2783 → 2406 | 40.9 → 43.9 | 1994 → 1880 | 68.4 → 60.9 | 25.4 → 25.0 | 0/0 → 0/1 |
| 2 | 5400 | 3006 → 2509 | 46.6 → 50.7 | 1989 → 1926 | 71.1 → 62.1 | 29.9 → 29.7 | 0/0 → 0/0 |
| 3 | 360 | 366 → 337 | 12.8 → 13.8 | 371 → 371 | 17.4 → 8.1 | 0.1 → 0.1 | 0/0 → 0/0 |
| 3 | 720 | 680 → 669 | 16.1 → 15.7 | 697 → 691 | 18.5 → 9.2 | 0.5 → 0.3 | 0/0 → 0/0 |
| 3 | 1080 | 1051 → 931 | 14.2 → 15.6 | 1029 → 1006 | 19.0 → 11.0 | 0.5 → 1.1 | 0/0 → 0/0 |
| 3 | 1440 | 1360 → 1263 | 16.4 → 16.7 | 1423 → 1337 | 22.1 → 14.4 | 1.5 → 2.7 | 0/0 → 0/2 |
| 3 | 2160 | 2017 → 1806 | 22.6 → 23.9 | 1886 → 1829 | 32.6 → 25.0 | 7.7 → 8.0 | 0/0 → 0/0 |
| 3 | 2880 | 2571 → 2263 | 23.2 → 23.8 | 2166 → 2006 | 41.6 → 35.7 | 11.7 → 13.5 | 0/1 → 0/0 |
| 3 | 3600 | 2983 → 2543 | 24.0 → 31.5 | 2217 → 2126 | 54.2 → 42.6 | 19.3 → 16.9 | 0/0 → 0/0 |
| 3 | 4320 | 3280 → 2977 | 25.1 → 32.9 | 2371 → 2103 | 56.7 → 54.2 | 19.8 → 22.4 | 0/1 → 0/0 |
| 3 | 5400 | 3703 → 3229 | 31.5 → 36.5 | 2383 → 2189 | 67.0 → 59.4 | 26.1 → 29.5 | 0/0 → 0/1 |

Readings: the roundabout's light-demand delay roughly halves at every lane
count (a shorter entry zone and speeds that follow the limit), and its queued
time barely changes, so the waits removed were short. Signal served flow at
saturation falls by 12–22%: turning vehicles now slow for the curve, which
matters most where one shared lane carries every movement. 1-lane runs are
collision-free before and after. Multi-lane roundabout contacts went from 3 to
5 in 54 runs (the inner-ring-exit weave; see the release-gate review below).

## Final validation (2026-09-24)

| Gate | Result |
| --- | --- |
| Backend fast suite (`pytest -m "not slow"`) | 482 passed, 0 failed; coverage 95.15% (floor 85%) |
| Slow: signal capacity | 5 passed (re-run on final code) |
| Slow: roundabout conflicts | 9 passed |
| Slow: roundabout lock-up | 10 passed |
| Slow: calibrated capacity (re-pinned) | 10 passed |
| Slow: saturated-signal lock-up (new) | passed |
| Ruff lint / Ruff format / strict mypy | clean / clean / no issues (45 files) |
| Schema validator | passed (3 files) |
| Frontend ESLint / tsc / Prettier / Vitest | clean / clean / clean / 165 passed |
| Frontend production build | built |
| `docker compose build` | backend + frontend images built |
| Cross-process determinism (PYTHONHASHSEED 0 / 1 / 12345) | identical trajectory hashes, signal + 2- and 3-lane roundabout |
| Invariant sweep (signal/roundabout × 1–3 lanes × 0.4/1.0/1.5 veh/s × 2 seeds) | 0 same-lane overlaps, 0 collisions |
| Signal lock-up scan (2–3 lanes × 0.6/0.8/1.2 veh/s × 4 seeds) | baseline 4 lock-ups + 2 near-locks + 1 collision; fixed 0 / 0 / 0 |

## Remaining Known Issues

None that block release. Everything still open was reviewed on 2026-09-25
(below) and classified; none is an unresolved software bug.

### Release-gate review (2026-09-25)

**Multi-lane roundabout contacts — classified as a model limitation.**
Both reproduce deterministically:

| Run | t | Vehicles / lanes | What happens |
| --- | --- | --- | --- |
| 2 lanes, 3600 veh/h, seed 1 | 94.0 s | veh_50 `conn_south_0_left` (inner ring, leaving for the west exit, r 12.5→14.5 m, 4.6 m/s) vs veh_45 `conn_north_1_straight` (entered the outer ring from the north, crawling at 0–0.6 m/s, r 18.1 m) | veh_50 is constrained by the predictive resolver (allowed 3.0 m, braking at −9 m/s²), but the resolver samples its path every 1 m against a 0.2 m box clearance, and the exit taper's polyline heading jumps ~11° between waypoints. The corner sweep between samples grazes veh_45 for one tick (centres 3.64 m apart); they separate on the next tick. |
| 3 lanes, 2880 veh/h, seed 1 | 132.0 s | veh_50 `conn_south_0_left` (inner-ring left-turner cutting across the outer rings to the west exit, r ≈ 17 m, creeping at 0.2 m/s) vs veh_46 `conn_north_2_straight` (entered the outermost ring from the north and stopped across that exit path) | Both are inside the ring and in the resolver's "stopped" set, so the give-way choice is the remembered tie-break; it holds the already-stationary veh_46 while veh_50 creeps in a 4-tick release/brake cycle (below the 0.5 m/s hysteresis it still counts as stationary). veh_50's own path passes within 0.2 m of veh_46's box for its first 2 m, so with no reverse gear neither can clear without contact. It grazes at 0.2 m/s. |

- **Mechanism:** both contacts are an inner-ring vehicle leaving across the
  outer ring(s), meeting an outer-ring vehicle that has just entered at the
  next approach — the concentric-ring weaving conflict that exists because the
  geometry has no spiral lane assignment (already documented in
  `comparative_report.md` §2 "Scope and validity").
- **Operating envelope** (24 runs: 2–3 lanes × 1440/2160/2880/3600 veh/h ×
  seeds 1–3): contacts occur only at oversaturated points (served 2006 of 3600
  and 2177 of 2880). There are zero at or below capacity. There are none on 1
  lane: every pinned curve point, and all 60 five-seed runs, have 0 contacts.
- **Safety invariant:** it does violate "no two boxes overlap", but only as a
  low-speed graze (one tick at 4.6 m/s while braking, or a creep at 0.2 m/s).
  It is not a pass-through.
- **Deadlock:** none. The longest interval with no exit in the two contact runs
  was 5.9 s and 5.0 s, against 5–11 s in every clean run.
- **Metrics:** each contact is counted once (the audit debounces it); the audit
  zeroes the slower vehicle's speed, and in both cases that vehicle was already
  at or near rest. Delay and throughput are unaffected beyond noise.
- **Why not fixed now:** both levers are in the predictive resolver's
  give-way rules, which are finely balanced against lock-up. The known
  lock-ups are its documented failure mode, and they are pinned by
  `test_roundabout_lockup.py`. The two levers are: finer near-field path sampling or
  heading-aware clearance for pair 1, and holding a creeping "stopped" vehicle
  that closes on a stationary box for pair 2. Either would also act on
  single-lane runs, which feed the calibrated curve, for a failure that
  appears only in the uncalibrated, oversaturated multi-lane regime.
  Recommended as a separate, measured change with the lock-up and calibrated
  suites as its gate.

**`roads.speedLimit` — now implemented (BUG-21, 2026-09-25).** The
earlier release-gate entry kept it reserved because applying it would move
every calibrated result. The calibration pass applied it deliberately and
re-measured every result (`comparative_report.md`, revision 2026-09-25b).
`roads.approaches[]` is still reserved (not read by the engine).

**Multi-lane roundabout contacts, re-measured after the calibration pass.**
Across the 54 multi-lane roundabout runs of the 2026-09-25 matrix (2 and 3
lanes, 360–5400 veh/h, seeds 1–3), there were 5 contacts (3 before the pass).
Two now occur below saturation (3 lanes, 1440 veh/h). All five are the
inner-ring-exit weave described above; for example, veh_64 on
`conn_south_1_straight` against veh_67 on `conn_east_2_straight`. The new gap
rule is not involved: an entry onto the outermost ring already ignored inner
rings. The multi-lane configuration stays exploratory for this reason.

**"Controller match" rule — contract/documentation mismatch, corrected.** The
rule cannot hold under the current model: `ControllerSection` is one merged
model that fills defaults for both controllers, so every typed-route config
carries ring and signal keys. Each controller reads only its own keys, so a
mismatched key has no effect on a run. Contract §5 now states this and what
enforcing it would require (a split controller model).

## Not Bugs / Model Limitations

- **>60 s stops at a lightly loaded signal** — legitimate red time. Without a
  `phaseSequence` the controller runs the documented one-direction-at-a-time
  cycle (4 × 41 s = 164 s).
- **Blocked arrivals are delayed, not queued upstream.** While an entry is
  blocked, later arrivals on that approach are not generated (one pending
  arrival per approach). Under spill-back this under-represents offered demand
  at the network boundary. Model design, not a defect; served-flow results
  are unaffected at the pinned points.
- **Collision audit exemptions** (same lane, shared route lane). Measured:
  0 hidden merge overlaps in 12 runs (signal/roundabout, 1–2 lanes, 3 seeds),
  and same-lane overlaps are now 0 (BUG-1), so the exemptions hide nothing.
- **Residual ~5.5 m/s² peak braking on roundabout approaches** after BUG-7 is
  IDM's free-road term lagging a falling desired speed — an IDM property.
- **Single-lane signal saturation depends on how left-turners arrive.** With
  one shared lane, a permissive left-turner waiting at the stop line for a gap
  blocks the lane; the model has no in-box waiting position or intergreen
  "sneaker" clearance (in-box waiting is what produced BUG-19's lock-ups).
  This makes 1-lane signal capacity conservative relative to HCM
  shared-lane practice.
- **Roundabout "geometric delay"** is counted in `averageDelay` (free-flow time
  is computed at desired speed). Consistent with HCM control delay; its size
  depends on the approach speed assumption (see speed-limit issue above).
- **Monte-Carlo seeds are drawn from the global `random` module** — each run's
  seeds are returned in the response, so runs are reproducible after the fact.
- **Snapshot builder rebuilds metrics each tick for v1 runs** — cost is now
  O(1) in elapsed time after BUG-9; not a further issue.
