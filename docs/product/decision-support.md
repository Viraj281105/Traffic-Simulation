# V2.0 Decision support (planning studies)

A planning study answers one question: **given this junction and these traffic
conditions, what does the evidence show for each alternative?** It never names
a universally better geometry or control, and no field in the result ranks or
scores alternatives.

```
scenario → alternatives → seeds × demand scales → run_scenario_comparison (per alternative)
        → indicators → paired comparison vs baseline → findings → report → export
```

Code: `backend/src/planning/` (orchestration only; the engine, metrics and
comparison are the V1.5 ones). Tests: `backend/tests/planning/`.

## API (`/api/v2/planning`)

| Route | Purpose |
|---|---|
| `POST /validate` | Parse the study, patch and validate every alternative; no simulation. Returns `{valid, errors, warnings, simulations, scenarioFingerprint, alternatives[]}`. |
| `POST /run` | Synchronous run (small studies); returns the stored record. |
| `POST /jobs` | 202 + `{id, status}`. Max 2 concurrent planning jobs (429 beyond that). |
| `GET /{id}` | `{id, name, status: queued\|running\|completed\|failed, error, result}`. Another user's id is a 404. |
| `GET /{id}/report?format=json\|md\|csv` | Download (attachment). Unsupported format → 422. |
| `POST /{id}/reproduce` | Re-executes the stored request; `{reproduced, originalResultFingerprint, rerunResultFingerprint}`. |

Mounted from `main.py` with `create_router(user_dependency=get_current_user_id, dependencies=[Depends(require_api_key)])`.

## Request: `urbanflow-planning-study` v1

`subject.scenario` (a `urbanflow-scenario`), `alternatives[]` (first is the
baseline; omitted = fixed-time, adaptive, roundabout), `demand.scales`
(default `[1.0]`, 0.1–3.0), `repetitions{seeds (1–30, default 5), baseSeed,
confidenceLevel}`, `indicators[]`. An alternative is
`{id, label, strategy, patch}`; `patch` is a JSON merge-patch over a copy of
the scenario, re-validated by `ScenarioDocument` (unknown fields rejected) and
`validate_scenario`. `simulation.*` cannot be patched (seeds, duration and
warm-up are shared so seeds pair). Patches that change demand are allowed but
warned. Limits: ≤6 alternatives, ≤5 scales, ≤240 simulations. Give exactly one
subject: `subject.scenario`, or `subject.network` (a V1.9 `urbanflow-network`
with exactly one junction carrying an inline scenario; its route-implied volume
and turning become the scenario that runs; more than one junction is refused),
or omit both and set `calibration.useFittedScenario`. Optional
`calibration: {runId, useFittedScenario}` attaches a stored V1.8 run
(`POST /api/v2/calibration/runs`); it only applies to the scenario that run
simulated (original or fitted), anything else is a validation error.

## Result: `urbanflow-planning-result` v1

* `scenario` — `id` (`scn_<fingerprint>`), `fingerprint`, `geometry`, `traffic`, `vehicleMix`, `demand`, `control`, `simulation`.
* `alternatives[]` — `id, label, strategy, isBaseline, patch, changesFromBase, fingerprint, warnings`.
* `results[]` — one per alternative × demand scale: `performance`, `safety`, `environmental`, `reliability` (each `{status, values{key:{mean,std,min,max,n,ciLow,ciHigh,unit,label,direction}}, unavailable[], note}`), `perApproach`, `perVehicleType`, `signalTiming` (null for a roundabout), `seriesBySeed`.
* `comparison.vsBaseline[]` — per alternative × scale × metric (`averageDelay`, `throughput`, `averageQueueLength`, `collisionCount`): `baselineMean, alternativeMean, delta, deltaPct, ciLow, ciHigh, n, reading (lower|higher|tie|inconclusive), verdict (better|worse|tie|inconclusive)`. Delay uses the V1.3 paired rule and tie tolerance.
* `reliability` — repetitions, seeds, `sampleAdequacy (single_run|small|adequate)`, `flags[]` (small sample, high variability, vehicle limit).
* `findings[]` — `{id, kind, statement, confidence, evidence[{path}], caveats[]}`. Every evidence path resolves into the result (`results[3].performance.values.averageDelay`).
* `limitations[]`, `validity`, `summary` (`recommendationBasis` is always "None…"), `report`, `meta`.
* `calibration` — null, or the attached V1.8 run: `runId, status, relation (fitted_scenario|original_scenario), scenarioFingerprint, fittedFingerprint, observationsFingerprint, appliedFit, compared, caveats`. Also summarised as `validity.fieldCalibration` (status string, or `"not_provided"`) and `validity.fieldCalibrationDetail`.
* `network` — the scenario in the V1.9 network model: `origin (derived_from_scenario|submitted)`, `status (representation_only|single_junction_run)`, `fingerprint`, counts, `plan`, the full `document`, and the network `limitations`. Nothing multi-junction is executed.
* `meta` — also `calibrationRunId`, `calibrationFingerprint` (observations), `networkFingerprint`; git commit, python, `inputFingerprint`, `resultFingerprint`, `scenarioFingerprints` per alternative, seeds, time step, duration, warm-up, `compiledConfigs`, and the original `request` for exact re-runs.

## Honest gaps

* Safety: only `collisionCount` is available from the comparison output today; `minTTC`/`ttcEventCount` are registered and report `unavailable` until the comparison output carries them (one-line registry change in `planning/indicators.py`). All safety is labelled exploratory.
* Environmental: stop-and-go and idling-delay **proxies** only. Fuel and CO2 are `unavailable`; findings make no environmental claim.
* Field calibration is attached only when the study names a V1.8 run; otherwise `validity.fieldCalibration = "not_provided"`. A calibration validates only the quantities it compared (see its `compared` and `caveats`), never the whole model.
* The network view is a representation of one junction; V1.9 does not run multi-junction simulations.
* Several metrics, alternatives and scales are read without multiple-comparison correction.

## Export

* JSON: the full result. Markdown: the `report` sections. CSV: long format, one row per alternative × scale × indicator, `status=unavailable` rows have empty numbers (never zero). PDF is not provided.
* `shared/schemas/v2/planning-{study,report}.schema.json` are generated by `python -m src.planning.export_schemas` and checked by a test.
