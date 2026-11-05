# Network screens: API contracts (V4.1 to V4.6, package 1F)

The page `/app/network` (`src/netpage/NetworkPage.tsx`, tabs Map, Congestion,
Metrics, Calibration, RL, Twin, Load tests; the tab is in `?tab=`) is built
against the shapes below. Each feature folder has its `types.ts` (the source
of truth), `api.ts`, `fixtures.ts` (contract fixtures used by the tests in
`src/test/network*.test.tsx`) and components. The shapes were copied from the
backend code, named in each row; nothing here is invented except the
load-test summary, which this frontend defines (last section).

Transport: the `/api/v3` client of `services/v3/experiments.ts` through
`netcommon/api.ts` (bearer token, 120 s timeout, error envelope
`{"error": {"message", "details": {"errors": []}}}`; a failed request shows the
server's reason). `/api/v2` paths use the same transport. All three
network-metrics endpoints are stateless. The mesoscopic model is uncalibrated
(`inModelOnly: true`): numbers compare scenarios, they are not predictions.
A value that could not be computed is `null` and is shown as "Not available",
never `0`.

| Screen (folder)              | Request                                                                  | Response type (file)                     | Backend source                                         |
| ---------------------------- | ------------------------------------------------------------------------ | ---------------------------------------- | ------------------------------------------------------ |
| Map (`mapview/`)             | `GET /api/v2/network-metrics/grid?preset=\|rows=&cols=&vehiclesPerHour=` | `GridResponse` (`mapview/types.ts`)      | `netmetrics/router.py` `grid`, `mapdata.py`            |
| Map, Metrics (`netmetrics/`) | `POST /api/v2/network-metrics/simulate`                                  | `NetworkMetrics` (`netmetrics/types.ts`) | `router.py` `simulate`, `metrics.py` `compute_metrics` |
| Congestion (`congestion/`)   | `POST /api/v2/network-metrics/congestion`                                | `CongestionResult`                       | `router.py` `congestion`, `congestion.py`              |
| Calibration (`calibration/`) | `POST /api/v2/calibration/network-fit`                                   | `CalibrationReport`                      | `network_calibration_router.py`, `network_fit.py`      |
|                              | `POST /api/v2/calibration/network-fit/recalibrate`                       | `CalibrationReport` + `recalibration`    | `network_recalibration.py`                             |
|                              | `POST /api/v2/calibration/network-fit/validate-counts`                   | `CountsValidation`                       | `network_calibration_router.py`                        |
| RL (`netrl/`)                | none: opens the JSON of `compare_network` from a file or paste           | `RlEvalDocument` (`urbanflow-rl-eval`)   | `rl/network_eval.py`                                   |
|                              | `GET /api/v3/rl/comparisons/{id}`                                        | `RlComparison` (`rlcompare/types.ts`)    | `insights/rl_view.py`                                  |
| Twin (`twinview/`)           | `POST /api/v2/twin/compare`                                              | `TwinState`                              | `twin/router.py`, `runner.py` `state`, `compare.py`    |
|                              | `POST /api/v2/twin/whatif`                                               | `WhatIfResult`                           | `twin/whatif.py`                                       |
| Load tests (`loadtest/`)     | `GET /api/v3/loadtests/latest` (defined here, see below)                 | `LoadTestSummary`                        | none yet                                               |

## Network-metrics requests

`simulate`, `congestion` take a `RunRequest` body: give `graph` (an
`urbanflow-graph`) with `flows`, or a `grid`; with neither a 3x3 grid runs.
The screens send a grid: `{grid: {preset: "3x3" | "12-junction"} | {rows, cols}

- vehiclesPerHour, duration (30 to 3600 s), seed, bucketSeconds: 30,
  includeMap: true}`. `congestion`adds`threshold`(0 to 1, default 0.3),`minHoldSeconds`, `minSpillbackSeconds`. A refused request answers 422 with a
  list of reasons (for example more than 400 nodes).

### Map data (`map`, from `includeMap` and `/grid`)

`{format: "urbanflow-map-data", version, name, hasGeo, boundsLocal {minX, maxX,
minY, maxY}, boundsLatLon? (only when hasGeo), nodes [{id, kind: "junction" |
"gate", signal, x, y, lat?, lon?}], links [{id, from, to, name, length, lanes,
speed, path [[x, y], [x, y]], bearingDegrees, pathLatLon?, value?}],
valueLabel?}`. x east and y north in metres. `value` is the metric the request
attached: mean occupancy ratio for `simulate`, peak occupancy ratio for
`congestion`; `valueLabel` names it. The viewer needs no tiles and works with
`hasGeo: false`.

### `simulate` response

`{format: "urbanflow-network-metrics", version, seed, duration, bucketSeconds,
inModelOnly, network {generated, entered, blockedAtEntry, completed, active,
conserved, throughputVph, totalDelaySeconds, totalDelayHours, meanDelaySeconds
(null when nothing completed), meanTravelSeconds (null), totalTravelSeconds,
meanVehiclesInNetwork, meanQueuedVehicles, blockedLinkSeconds, unroutable},
perLink {id: {passed, flowVph, capacity, meanOccupancy, peakOccupancy,
meanOccupancyRatio, meanQueue, peakQueue, densityVehPerKmLane,
blockedSeconds}}, perNode {id: {kind, passed, throughputVph, meanOccupancy,
peakOccupancy, meanQueue, peakQueue}}, series [{tStart, vehiclesInNetwork,
queuedVehicles, exitedVehicles}], fundamentalDiagram {bucketSeconds, points
[{tStart, densityVehPerKmLane, flowVehPerHourLane}], peakFlow {...} | null,
perLink? (only with perLinkDiagram)}, notes [], map?}`. Delay counts finished
trips only.

### `congestion` response

`{format: "urbanflow-congestion", version, seed, duration, threshold,
minHoldSeconds, inModelOnly, run {generated, entered, completed, active,
blockedAtEntry, conserved}, links [{id, from, to, name, length, lanes,
capacity, onsetSeconds | null, rank | null, peakOccupancyRatio}], heatmap
{metric: "occupancyRatio", bucketSeconds, bucketStarts [], linkIds [] (rows in
congestion order, never-congested links last), values [[row][bucket]], queue,
blockedFraction}, spillback {events [{link, blockedBy, startSeconds,
endSeconds, durationSeconds, peakOccupancyRatio, chainLength}], summary
{events, linksAffected, links, totalBlockedSeconds, longestSeconds,
maxChainLength, firstStartSeconds | null}}, spread {congestedLinks, totalLinks,
origin | null, order [{link, rank, onsetSeconds, parent | null, direction:
"upstream" | "downstream" | "lateral" | null, hops, speedMps | null}],
durationSeconds, maxHops, meanSpeedMps | null, upstreamSpeedMps | null,
downstreamSpeedMps | null, maxDistanceFromOriginMeters}, map?}`.
The plain-words spread summary (`congestion/spreadText.ts`) only restates these
fields.

## Calibration

Request (`NetworkFitRequest`, camelCase aliases): `{graph, flows [{origin,
destination, vehiclesPerHour}] (1 to 60), countsCsv, intervalSeconds?, options
{budget (2 to 300, default 150), seed, calibrateDemand, calibrateSpeed,
speedGroups?, minObservedVph, criteria {gehLimit, minFraction, maxMape?,
maxRmse?}}, sim {duration (to 1800), seed}, source}`. Recalibrate adds
`previous` (a report's `parameters.fitted`), `windowIntervals?`,
`driftThreshold` (default 0.15). The counts CSV has the header `link_id,
interval_start, count[, sensor_id]`; `interval_start` is seconds or ISO 8601.
`validate-counts` takes `{graph, countsCsv, intervalSeconds?}` and answers
`{valid, errors [], warnings [], provenance, linkFlowsVph {link: veh/h}}`
(always 200 once the graph parses). A bad graph or unusable inputs answer 400.

Report (`calibrate_network`): `{format: "urbanflow-network-calibration",
version, status: "PASS" | "FAIL", gate: "G-CAL", before, after (each {metrics
{links, rmseVph, mapePercent | null, r2 | null, meanGeh, gehUnderLimitFraction,
mapeLinks, mapeSkippedLinks, minObservedVph}, gCal {passed, criteria {geh_limit,
min_fraction, max_mape, max_rmse}, linksChecked, linksPassingGeh, gehFraction,
reasons []}, objective}), parameters {fitted, start, bounds, speedGroups,
fittedDemandVph}, perLink [{linkId, observedVph, before {simulatedVph,
residualVph, geh, percentError | null}, after {...}}], optimiser {method, seed,
budget, evaluations, sweeps, stopReason, finalStep, trace []}, simulation,
provenance {counts {source, sha256, rows, links, sensors, intervals,
intervalSeconds, intervalSecondsInferred, firstIntervalStart,
lastIntervalStart, warnings []}, network {name, source, nodes, links},
countedLinks, linksWithoutCounts}, thresholds {gCal, minObservedVph, gehNote},
manifest {version, hash, graphSha256, note}, notes []}`. The criteria keys are
snake_case in the report. The default G-CAL rule (GEH below 5 on at least 85%
of links) is a placeholder for the agreed error (decision D1); the screen shows
the criteria the server applied. `recalibration` (recalibrate only): `{windowIntervals,
windowFirstIntervalStart, windowLastIntervalStart, warmStartFrom,
previousParametersGCalPassed, drift {threshold, maxAbsRelativeChange | null,
flagged [], drifted, parameters [{name, previous, current, relativeChange |
null, flag}]}}`; a drifted parameter is the cue to recalibrate.

## Network RL

`policies[name][metric]` is one value per held-out seed (`wall_seconds` is a
single number). All keys are snake_case. Document: `{format:
"urbanflow-rl-eval", version, kind: "network", seeds [], env, signal_nodes [],
baseline_fixed_green_s, metrics [], lower_is_better [], policies,
paired_comparisons [{rl, baseline, metric, lower_is_better, comparison
{method, n_pairs, mean_a, mean_b, difference (RL minus baseline), ci_lower,
ci_upper, confidence, p_value, alpha, significant, direction: "a_lower" |
"a_higher" | "none", statistic | null, cautions []}, verdict}],
comparison_method, confidence, cautions [], environment}`. The compared metrics
are `mean_wait_s`, `mean_queue`, `throughput`. The UI shows the server's
`verdict`, interval and p-value and never recomputes them. **Caveat shown with
every wait figure: `mean_wait_s` is stopped vehicle-seconds per entered
vehicle, not the delay of a finished trip.** There is no endpoint serving this
document yet; the screen opens the JSON file. The junction-level comparison is
`GET /api/v3/rl/comparisons/{id}` (see `src/CONTRACTS.md`).

## Digital twin

`compare` body (`TwinRequest`): `{observations [{linkId, timestamp (s), count,
meanSpeed?}] (up to 20000), graph?, flows? (both default to the two-junction
corridor), intervalSeconds (default 60), warmupSeconds (120), start (0), seed
(1), alertThresholdPct (25)}`. State response: `{format: "urbanflow-twin-state",
version, graph (name), intervalSeconds, warmupSeconds, seed, start,
latestWindow | null, currentFlows [], timeline [{window, time, predicted
{link: n}, observed {link: n}, observedSpeed}], comparison {network {n, mae,
mape | null, bias, lagWindows, lagSeconds}, perLink {link: {n, mae, mape,
bias}}, series [{window, predicted, observed, error, errorPct | null}],
alertThresholdPct, alert, alerts [{window | null, kind: "window" | "overall",
errorPct, thresholdPct}]}}`. MAE and bias are vehicles per window; MAPE is
percent over windows with an observation above zero; bias is predicted minus
observed.

`whatif` body: the same fields plus `scenario {closeLinks [], demandScale (0 to
10), lanes {link: n}, speedFactors {link: x}}` and `horizonWindows` (1 to 12).
Response: `{window, horizonWindows, scenario, baseline {completed,
meanDelaySeconds | null, meanTravelSeconds | null}, variant {same +
unroutable}, delta {completed, meanDelaySeconds | null, meanTravelSeconds |
null}, perLink {link: {baseline, variant | null (closed), delta | null,
peakOccupancyDelta | null}}}`. An unknown link id answers 400.

## Load-test summary (defined by the frontend)

No backend produces this yet. Document `urbanflow-loadtest-summary` v1
(`loadtest/types.ts`), written by a k6 `handleSummary(data)`:

```
{format, version: 1, generatedAt (ISO), tool, toolVersion?, target, scenario,
 durationSeconds, vus {peak, max},
 requests {total, ratePerSecond | null, failed, errorRate | null (0..1)},
 latencyMs {avg, min, med, p90, p95, p99, max} (each number | null),
 checks {passes, fails},
 thresholds [{name, metric, expression, passed}],
 endpoints? [{name, requests, p95Ms | null, errorRate | null}]}
```

k6 mapping: `vus.peak` = `vus_max` value, `vus.max` = the scenario limit;
`requests.total` = `http_reqs.count`, `ratePerSecond` = `http_reqs.rate`,
`errorRate` = `http_req_failed.rate`, `failed` = `http_req_failed.passes`;
`latencyMs` = `http_req_duration` `avg, min, med, p(90), p(95), p(99), max`;
`checks` = `checks.passes/fails`; each `thresholds` entry is a k6 threshold
(`metric`, `expression`, `passed` = `ok`). Delivery, either:

1. the API serves the newest summary at `GET /api/v3/loadtests/latest` (body =
   the document; `404` = none published yet, shown as "No load test yet"; same
   bearer token and error envelope), or
2. the person opens the `loadtest-summary.json` file in the Load tests tab.

## Wiring

`routing.ts` (`VIEW_ROUTES.network = "/app/network"`),
`templates/default.conf.template` (SPA fallback list),
`components/shell/sections.ts` (Experiments section, "Networks") and a lazy
route in `App.tsx`. New tests live under `src/test/` only (`network*.test.tsx`,
`netApi.ts`); no non-test source imports vitest or `../test`.
