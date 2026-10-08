# Field-data comparison (V1.8)

> Code: `backend/src/calibration/` · API: `/api/v2/calibration` · Tests: `backend/tests/calibration/`

V1.8 compares what UrbanFlow simulates with what someone **observed** at the junction. It supplies no observations of its own, never changes the engine, and never edits a scenario in place.

## What is compared

| Observed (input) | Simulated quantity (read from the unchanged engine) | Unit |
|---|---|---|
| `approachFlows` (veh/h, or a count + duration) | Vehicles that left the junction after warm-up, per origin approach ÷ measured seconds | veh/h |
| `turningMovements` (shares, or counts) | Movement share of that approach's exits, **over the movements supplied** | share |
| `vehicleMix` | Class share of all exited vehicles, for the classes supplied | share |
| `queues` (mean / max) | `approachBreakdown.averageQueueLength` / `maxQueueLength` (vehicles below the wait-speed threshold) | vehicles |
| `travelTimes` (per approach, optionally per movement) | Mean (exit − spawn) of exited vehicles; spawn is at the start of the approach | s |
| `signal.averageGreenSeconds` | `signalTiming.averageGreenDuration` (signal strategies only) | s |

Simulated values are the **mean over the repetitions** (`options.seeds`, default 3, max 10); `simulatedStd` and `seedsWithData` are reported per row. Anything with no simulated vehicles is listed as *not compared*, never filled in.

## Request

```jsonc
POST /api/v2/calibration/runs
{ "scenario": <urbanflow-scenario>,
  "observations": {
    "format": "urbanflow-observations", "version": 1, "name": "…",
    "period": {"label": "08:00-09:00", "durationSeconds": 3600, "source": "manual count"},
    "scenarioFingerprint": "optional — must equal the scenario's",
    "approachFlows": [{"approach": "north", "vehiclesPerHour": 320}],
    "turningMovements": [{"approach": "north", "movement": "left", "count": 20}],
    "vehicleMix": {"car": 0.8, "truck": 0.2},
    "queues": [{"approach": "north", "meanVehicles": 2, "maxVehicles": 6}],
    "travelTimes": [{"approach": "north", "meanSeconds": 30}],
    "signal": {"averageGreenSeconds": 30} },
  "options": {"strategy": null, "seeds": 3, "baseSeed": null, "fit": []} }
```

Strict validation: unknown fields rejected; exactly one unit per value; turning shares and the vehicle mix must sum to 1 ± 0.02 and are **never rescaled**; each approach/movement given once; at least one series.

`options.fit` (any of `demand`, `turning`, `mix`) writes those observed inputs into a **copy** of the scenario before running. Empty (default) simulates the scenario exactly as given, and mismatches between the scenario's inputs and the observations come back as warnings. Compared values that were fitted are marked `inputWasFitted: true` — reproducing an input is not evidence of calibration.

## Result (`urbanflow-calibration-result` v1)

`comparisons[]` rows: `metric`, `kind`, `location{approach, movement, vehicleClass}`, `observed`, `simulated`, `simulatedStd`, `seedsWithData`, `absoluteError` (simulated − observed), `percentError` (null when the observed value is below the minimum denominator), `geh` (flows only), `rating`, `inputWasFitted`, optional `note`.

Also: `fieldCalibration{status, classification, thresholds, coverage, engineCapacityCalibration}`, `appliedFit`, `warnings`, `caveats`, `scenario{name, strategy, fingerprint, fittedFingerprint}`, and `meta{seeds, baseSeed, repetitions, duration, warmupTime, measuredSeconds, timeStep, observationsFingerprint, gitCommit, pythonVersion, schemaVersion}`. The result is a pure function of the request and code version (no timestamps inside it); the stored envelope adds `id` and `createdAt`.

`engineCapacityCalibration` is the pre-existing `study.calibration.calibration_status` (UrbanFlow's own V1.0 capacity curve), embedded unchanged. It is a different thing from `fieldCalibration`.

## Rating thresholds (version 1)

error = simulated − observed. A comparison is **GOOD** if `|error| ≤ absGood` *or* `|error|/observed ≤ pctGood`; **MODERATE** if within `absModerate` or `pctModerate`; otherwise **POOR**. The percentage rule applies only when `|observed| ≥ minDenominator`.

| kind | unit | pctGood | pctModerate | absGood | absModerate | minDenominator |
|---|---|---|---|---|---|---|
| flow | veh/h | 10 % | 25 % | 20 | 50 | 20 |
| turning | share | 20 % | 40 % | 0.05 | 0.10 | 0.05 |
| mix | share | 20 % | 40 % | 0.03 | 0.06 | 0.05 |
| queue | vehicles | 25 % | 50 % | 1 | 2 | 1 |
| travelTime | s | 10 % | 25 % | 3 | 8 | 5 |
| signal | s | 10 % | 25 % | 2 | 5 | 5 |

**Overall** (`fieldCalibration.status`): `INSUFFICIENT_DATA` if nothing could be rated; `POOR` if more than 25 % of rated comparisons are POOR; `GOOD` if none are POOR and at least 80 % are GOOD; otherwise `MODERATE`. Served at `GET /api/v2/calibration/thresholds`.

## What this does and does not show

- The thresholds are transparent presentation choices, not a statistical test and not a published standard (GEH is shown because engineers expect it, but does not drive the rating).
- Agreement covers only the series that were observed. Flow-only agreement is stated as such in `caveats`.
- Fewer than 3 repetitions: the spread is flagged as unreliable. No confidence intervals are claimed.
- Observation methodology (detector vs manual count, queue definition, travel-time span) is the user's; differences from the simulator's definitions (above) are not corrected for.
- Nothing is tuned: V1.8 does not adjust driver-behaviour parameters to fit.
