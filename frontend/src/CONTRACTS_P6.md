# Resilience screens: API contracts (V4.7 to V5.4, package 2G)

The page `/app/resilience` (`src/respage/ResiliencePage.tsx`; tabs Incidents,
Resilience, Priority, Cooperation, Account; the tab is in `?tab=`) is built
against the shapes below, copied from the backend code named in each row. Each
feature folder has `types.ts` (the source of truth), `api.ts`, `fixtures.ts`
(contract fixtures used by `src/test/resilience.test.tsx`) and components.
Shared pieces are in `src/rescommon/` (bar chart with intervals, paired
per-seed chart, drop-down, load-on-mount hook); the line chart, number field,
action hook and styles are reused from `src/netcommon/`.

Transport: the `/api/v3` client of `services/v3/experiments.ts` through
`netcommon/api.ts` (bearer token, 120 s timeout, error envelope
`{"error": {"message", "details": {"errors": []}}}`; a failed request shows the
server's reason, `ExperimentsApiError.status` carries the HTTP status). The
`/api/v2` paths use the same transport. Every simulation result is in-model
only. A value that could not be computed is `null` and is shown as "Not
available" or in words ("never recovered"), never as `0`.

| Tab (folder)                         | Request                                      | Response type (file)                       | Backend source                                                     |
| ------------------------------------ | -------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------------ |
| Incidents, Resilience (`incidents/`) | `GET /api/v2/incidents/catalogue`            | `IncidentCatalogue` (`incidents/types.ts`) | `incidents/router.py`, `catalogue.py`                              |
| Incidents                            | `POST /api/v2/incidents/simulate`            | `SimulateResponse`                         | `router.py` `simulate`, `engine.py`, `resilience.py` `run_metrics` |
| Resilience                           | `POST /api/v2/incidents/resilience`          | `ResilienceResponse`                       | `router.py` `resilience`, `resilience.py`                          |
| Priority (`priority/`)               | `GET /api/v2/priority/catalogue`             | `PriorityCatalogue`                        | `priority/router.py` `catalogue`                                   |
|                                      | `POST /api/v2/priority/emergency-comparison` | `EmergencyComparison`                      | `router.py`, `comparison.py`                                       |
|                                      | `POST /api/v2/priority/transit-comparison`   | `TransitComparison`                        | `router.py`, `comparison.py`                                       |
| Cooperation (`v2x/`)                 | `POST /api/v2/v2x/experiment`                | `V2xExperiment`                            | `v2x/router.py`, `experiment.py`                                   |
| Account (`tenancy/`)                 | `GET /api/v2/tenancy/me`                     | `MeResponse`                               | `tenancy/router.py`, `deps.py` `quota_snapshot`                    |
|                                      | `GET /api/v2/tenancy/usage`                  | `UsageResponse`                            | `tenancy/router.py`, `limits.py`                                   |
| Account (`jobs/`)                    | `GET /api/v2/jobs/queue-stats`               | `QueueStats`                               | `jobs/router.py`                                                   |
|                                      | `POST /api/v2/jobs/enqueue-dry-run`          | `DryRunResponse`                           | `jobs/router.py`, `spec.py`                                        |

`GET /api/v2/v2x/schemas` exists but is not used by a screen.

## Incidents (`incidents/`)

- `GET /catalogue`: `{format, version, inModelOnly, disruptionTypes[{type, effect, defaultSpeedFactor?}], weather{fullSeverityFactors{kind: {speed, saturation, headway, discharge}}, status}, strategies["fixed_time","max_pressure"], scoreFormula{weights{recovery, throughput, peak, area}, peakScaleSeconds, areaScaleSeconds}, scenarios[Preset], stressLabExtension{note}}`.
  A `Preset` is `{id, family, title, description, network, scenario, duration}`;
  its `scenario` omits empty lists and defaults (the form fills them in:
  `incidents[{type, links, start, duration, lanesBlocked=1, policy="drain"}]`,
  `weather[{kind, severity=1, start=0, duration}]`,
  `surges[{origin|null, destination|null, start, duration, multiplier}]`,
  `reroute=true`).
- `POST /simulate` body: `{preset, scenario, duration, seed, strategy, compareBaseline, bucketSeconds}`
  (the preset supplies the network; `scenario` replaces the preset's). Response:
  `{network{name, nodes, links, flows[]}, scenario, duration, inModelOnly, run, baseline?, metrics?}`.
  `run` and `baseline` are `run_disruption` documents: counters, `series{bucketSeconds, time[], meanAccruedDelay[], active[], completed[], entered[], blocked[]}`,
  `segments[]`, `perLink`, `perNode`. `metrics` is `null` when the disruption
  ends within two buckets of the run end.
- `POST /resilience` body: `{preset, scenario, duration, strategies[], seeds[1..10], bucketSeconds, includeSeries}`.
  Response: `{format:"urbanflow-resilience", version, inModelOnly, duration, bucketSeconds, disruptionEnd, seeds[], tolerance{relative, absoluteSeconds, holdBuckets}, scoreFormula{weights, peakScaleSeconds, areaScaleSeconds, interval}, strategies{<name>: {score, scoreInterval|null, recoveredRuns, runs, recoveryTimeSeconds|null, peakDelaySeconds, peakExcessDelaySeconds, throughputLoss, areaUnderDelayCurve, excessDelayVehicleSeconds, perSeed[]}}, best, note, network, scenario}`.
- Score formula, shown on the screen: `R = 0.35 recovery + 0.25 throughput + 0.20 peak + 0.20 area`
  (weights taken from the response). Results are in-model only.

## Priority (`priority/`)

- Comparison requests: `{scenario{durationSeconds, arrivalRate}, numSeeds (2..20), baseSeed, method ("paired_t"|"paired_bootstrap"), confidence, emergencyVehicles[{kind, approach, turn, timeSeconds}] | lines[{lineId, approach, turn, headwaySeconds, trips}]}`.
- Responses: `{kind, inModelOnly, label, method, confidence, seeds[], droppedSeeds[{seed, reason}], perSeed{<arm>: {<metric>: number[]}}, comparison{<metric>: PriorityStat}, safety{<arm>: {collisions[], vehiclesConserved, signalAuditOk, signalViolations[], preemptions[]}}, runs{...}}`.
  Emergency arms `withPreemption`/`baseline`, metrics `emergencyTravelTime`,
  `emergencyDelay`, `emergencyWaitTime`, `collateralDelay`. Transit arms
  `withPriority`/`baseline`, metrics `busScheduleLateness`, `busTimeLost`,
  `personDelayPerPerson`, `vehicleDelay`, `otherVehicleDelay`. The `runs` key
  is not read by the screen.
- `PriorityStat` (`rescommon/types.ts`): the snake_case `PairedComparison`
  fields `{method, n_pairs, mean_a, mean_b, difference, ci_lower, ci_upper, confidence, p_value, alpha, significant, direction, statistic, cautions}`
  plus `{metric, label, verdict, lowerIsBetter, meanBaseline, meanWithPriority, changePercent|null}`.
  `a` is the arm with priority; `difference` = a minus b.

## Cooperation (`v2x/`)

- Request: `{grid{rows, cols (1..5), vehiclesPerHour}, duration, seeds[2..10], penetrations[], channel{latencyKind, latencyMs, lossProbability}, sensitivity?{penetration, latenciesMs[], lossProbabilities[]}, confidence, method}`.
- Response: `{format, version, baseline{perSeed[], mean}, sweep[{penetration, metrics{delaySeconds|stops|fuelLitres|co2Kg: {baseline, cooperative, change, changePct|null, paired: PairedStat|null}}, connectedVehicles, vehicles, stopsAvoided, reroutes, messageDeliveryRatio|null, meanMessageAgeAtUseSeconds|null, messagesAttempted, messagesDelivered, messagesUsed}], provenance{seeds, durationSeconds, penetrations, channel, behaviour, hazard|null, confidence, method, constants, assumptions[]}, sensitivity?{penetration, latenciesMs, lossProbabilities, note, cells[{latencyMs, lossProbability, delayBenefitSeconds, delayBenefitPct|null, stopsAvoidedPerVehicle, stopsReductionPct|null, deliveryRatio|null, meanAgeAtUseSeconds|null, delayPaired}]}}`.
  Cooperative minus baseline: negative change is a benefit; the heatmap shows
  `delayBenefitSeconds` (positive is better). The `provenance.assumptions` list
  is shown under the results.

## Account (`tenancy/`, `jobs/`)

- `GET /me`: `{identity{userId, email, issuer, tokenExpiresAt|null}, tenant{id}, role|null, roles[], permissions[], quota{requests{user{burst, remaining}, tenant{burst, remaining}, userPerMinute, tenantPerMinute}, dailyRuns{limit, used, remaining, resetsInSeconds}, concurrentRuns{limit, active, remaining}}}`.
- `GET /usage`: `{day, tenant{requestsTotal, rateLimitedTotal, runsToday, runsTotal, activeRuns}, user{same}, users|null}`; `users` only for tenant admins; needs `usage:read`.
- Both need an OIDC bearer token with a tenant claim: 401/403 without one,
  403 for a missing permission, 503 when tenancy is not configured or the
  provider keys are unavailable. The screen explains the sign-in requirement
  (and, for `/usage` alone, the missing `usage:read` permission).
- `GET /jobs/queue-stats`: `{backend:"sqs"|"memory", enqueueEnabled:false, visible, inFlight, deadLetter}`; 503 `queue unavailable: ...`.
- `POST /jobs/enqueue-dry-run` body (camelCase): `{run{kind:"multi-seed", geometry:"signal"|"roundabout", numSeeds (1..100), duration, baseSeed?, config?}, tenant, runId?, costTags{}, idempotencyKey?, visibilityTimeoutSeconds?, maxReceives?}`.
  Response `{enqueued:false, dryRun:true, message{schemaVersion, jobId, idempotencyKey, tenant, runId, run, costTags, visibilityTimeoutSeconds, maxReceives, enqueuedAt}, messageBytes}`;
  422 with a plain `detail` string (for example a missing mandatory cost tag
  `project`, `env`, `owner`). Nothing is ever enqueued from this screen.

## Metric names

New plain-words entries in `ANALYSIS_METRICS` (`metrics/catalog.ts`, listed in
`docs/product/metric-glossary.md`): `resilienceScore`, `recoveryTimeSeconds`,
`peakExcessDelaySeconds`, `throughputLoss`, `areaUnderDelayCurve`,
`emergencyTravelTime`, `collateralDelay`, `personDelayPerPerson`,
`busScheduleLateness`, `messageDeliveryRatio`, `delayBenefitSeconds`.
