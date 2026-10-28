# Planning report: Preview study (medium, precomputed)

## Executive summary

3 alternative(s) were compared for scenario 'Demo junction' (fingerprint c8aa706a60df9df0) at demand scale(s) x0.8, x1, x1.2 over 3 repetition(s). 28 finding(s) follow. This report presents evidence for this scenario only and does not name a universally better option.

- Adaptive showed an inconclusive difference in mean delay compared with Fixed-time at x0.8 demand (3 seeds could not separate them).
- Adaptive served a similar number of vehicles compared with Fixed-time at x0.8 demand.
- Adaptive had similar average queues compared with Fixed-time at x0.8 demand.
- Adaptive had similar safety indicators (simulated collisions) compared with Fixed-time at x0.8 demand.
- Adaptive showed an inconclusive difference in mean delay compared with Fixed-time at x1 demand (3 seeds could not separate them).
- Adaptive served more vehicles than Fixed-time at x1 demand (+6.33 vehicles vs baseline, CI 1.16 to 11.5).
- Adaptive showed an inconclusive difference in average queue length compared with Fixed-time at x1 demand (3 seeds could not separate them).
- Adaptive had similar safety indicators (simulated collisions) compared with Fixed-time at x1 demand.

## Scenario

*Arms*

| Arm | Lanes | Length (m) | Vehicles/h | Turning |
|---|---|---|---|---|
| north | 1 | 200.0 | 300.0 | {"left": 0.2, "right": 0.2, "straight": 0.6} |
| south | 1 | 200.0 | 300.0 | {"left": 0.2, "right": 0.2, "straight": 0.6} |
| east | 1 | 200.0 | 300.0 | {"left": 0.2, "right": 0.2, "straight": 0.6} |
| west | 1 | 200.0 | 300.0 | {"left": 0.2, "right": 0.2, "straight": 0.6} |

Vehicle mix: {"car": 1.0} (default passenger-car population). Duration 300s, warm-up 30s.

## Alternatives

| Id | Label | Strategy | Baseline | Changes from scenario | Fingerprint |
|---|---|---|---|---|---|
| base | Fixed-time | Fixed-time signal | yes | none | c8aa706a60df9df0 |
| adaptive | Adaptive | Adaptive signal | no | none | c8aa706a60df9df0 |
| rbt | Roundabout | Roundabout | no | none | c8aa706a60df9df0 |

## Methodology

Each alternative is simulated under identical seeds, so per-seed differences against the baseline are paired. Intervals are two-sided Student-t at 95%. Paired per-seed differences in mean delay (first strategy minus second), Student-t interval on the mean difference. 'lower'/'higher' needs the interval to exclude zero and the means to differ by more than the tie tolerance; 'tie' means within the tolerance; otherwise 'inconclusive'. No multiple-comparison correction.

## Performance

*Performance indicators*

| Alternative | Demand scale | Indicator | Mean | Std | CI | n |
|---|---|---|---|---|---|---|
| Fixed-time | 0.8 | Mean delay | 21.58 | 4.61 | 10.13 to 33.03 | 3 |
| Fixed-time | 0.8 | Mean wait time | 13.28 | 3.7 | 4.1 to 22.46 | 3 |
| Fixed-time | 0.8 | Vehicles served | 59.67 | 3.21 | 51.68 to 67.66 | 3 |
| Fixed-time | 0.8 | Mean queue length | 1.1 | 0.6 | -0.38 to 2.58 | 3 |
| Fixed-time | 0.8 | Max queue length | 7.0 | 2.65 | 0.43 to 13.57 | 3 |
| Fixed-time | 0.8 | Stops per vehicle | 0.58 | 0.11 | 0.31 to 0.85 | 3 |
| Fixed-time | 1.0 | Mean delay | 27.87 | 7.9 | 8.25 to 47.49 | 3 |
| Fixed-time | 1.0 | Mean wait time | 18.06 | 6.57 | 1.74 to 34.38 | 3 |
| Fixed-time | 1.0 | Vehicles served | 70.67 | 4.73 | 58.93 to 82.41 | 3 |
| Fixed-time | 1.0 | Mean queue length | 2.11 | 0.95 | -0.26 to 4.48 | 3 |
| Fixed-time | 1.0 | Max queue length | 13.0 | 2.65 | 6.43 to 19.57 | 3 |
| Fixed-time | 1.0 | Stops per vehicle | 0.7 | 0.06 | 0.56 to 0.84 | 3 |
| Fixed-time | 1.2 | Mean delay | 35.82 | 6.66 | 19.28 to 52.36 | 3 |
| Fixed-time | 1.2 | Mean wait time | 24.72 | 5.55 | 10.93 to 38.51 | 3 |
| Fixed-time | 1.2 | Vehicles served | 79.67 | 3.21 | 71.68 to 87.66 | 3 |
| Fixed-time | 1.2 | Mean queue length | 3.26 | 1.07 | 0.59 to 5.93 | 3 |
| Fixed-time | 1.2 | Max queue length | 15.33 | 3.51 | 6.61 to 24.05 | 3 |
| Fixed-time | 1.2 | Stops per vehicle | 0.85 | 0.08 | 0.65 to 1.05 | 3 |
| Adaptive | 0.8 | Mean delay | 17.93 | 5.79 | 3.55 to 32.31 | 3 |
| Adaptive | 0.8 | Mean wait time | 10.06 | 4.21 | -0.39 to 20.51 | 3 |
| Adaptive | 0.8 | Vehicles served | 62.67 | 5.69 | 48.54 to 76.8 | 3 |
| Adaptive | 0.8 | Mean queue length | 0.75 | 0.31 | -0.03 to 1.53 | 3 |
| Adaptive | 0.8 | Max queue length | 6.33 | 2.08 | 1.16 to 11.5 | 3 |
| Adaptive | 0.8 | Stops per vehicle | 0.56 | 0.14 | 0.21 to 0.91 | 3 |
| Adaptive | 1.0 | Mean delay | 22.04 | 3.97 | 12.19 to 31.89 | 3 |
| Adaptive | 1.0 | Mean wait time | 12.44 | 2.46 | 6.33 to 18.55 | 3 |
| Adaptive | 1.0 | Vehicles served | 77.0 | 2.65 | 70.43 to 83.57 | 3 |
| Adaptive | 1.0 | Mean queue length | 1.3 | 0.65 | -0.31 to 2.91 | 3 |
| Adaptive | 1.0 | Max queue length | 9.0 | 3.61 | 0.04 to 17.96 | 3 |
| Adaptive | 1.0 | Stops per vehicle | 0.62 | 0.06 | 0.48 to 0.76 | 3 |
| Adaptive | 1.2 | Mean delay | 32.4 | 3.64 | 23.36 to 41.44 | 3 |
| Adaptive | 1.2 | Mean wait time | 21.94 | 2.13 | 16.65 to 27.23 | 3 |
| Adaptive | 1.2 | Vehicles served | 82.0 | 8.0 | 62.13 to 101.87 | 3 |
| Adaptive | 1.2 | Mean queue length | 2.98 | 0.49 | 1.77 to 4.19 | 3 |
| Adaptive | 1.2 | Max queue length | 17.33 | 5.86 | 2.77 to 31.89 | 3 |
| Adaptive | 1.2 | Stops per vehicle | 0.64 | 0.16 | 0.23 to 1.05 | 3 |
| Roundabout | 0.8 | Mean delay | 15.99 | 1.07 | 13.33 to 18.65 | 3 |
| Roundabout | 0.8 | Mean wait time | 2.34 | 0.28 | 1.64 to 3.04 | 3 |
| Roundabout | 0.8 | Vehicles served | 65.33 | 6.81 | 48.42 to 82.24 | 3 |
| Roundabout | 0.8 | Mean queue length | 0.14 | 0.03 | 0.08 to 0.2 | 3 |
| Roundabout | 0.8 | Max queue length | 3.67 | 0.58 | 2.24 to 5.1 | 3 |
| Roundabout | 0.8 | Stops per vehicle | 0.4 | 0.03 | 0.32 to 0.48 | 3 |
| Roundabout | 1.0 | Mean delay | 20.73 | 4.7 | 9.06 to 32.4 | 3 |
| Roundabout | 1.0 | Mean wait time | 4.76 | 2.29 | -0.93 to 10.45 | 3 |
| Roundabout | 1.0 | Vehicles served | 78.0 | 3.46 | 69.39 to 86.61 | 3 |
| Roundabout | 1.0 | Mean queue length | 0.46 | 0.28 | -0.23 to 1.15 | 3 |
| Roundabout | 1.0 | Max queue length | 6.0 | 2.0 | 1.03 to 10.97 | 3 |
| Roundabout | 1.0 | Stops per vehicle | 0.66 | 0.21 | 0.15 to 1.17 | 3 |
| Roundabout | 1.2 | Mean delay | 27.78 | 6.01 | 12.85 to 42.71 | 3 |
| Roundabout | 1.2 | Mean wait time | 7.63 | 3.21 | -0.34 to 15.6 | 3 |
| Roundabout | 1.2 | Vehicles served | 90.0 | 1.73 | 85.7 to 94.3 | 3 |
| Roundabout | 1.2 | Mean queue length | 1.0 | 0.37 | 0.08 to 1.92 | 3 |
| Roundabout | 1.2 | Max queue length | 10.33 | 2.08 | 5.16 to 15.5 | 3 |
| Roundabout | 1.2 | Stops per vehicle | 0.94 | 0.34 | 0.09 to 1.79 | 3 |

## Safety indicators (exploratory)

*Safety indicators*

| Alternative | Demand scale | Indicator | Mean | Std | CI | n |
|---|---|---|---|---|---|---|
| Fixed-time | 0.8 | Collisions | 0.0 | 0.0 | 0 to 0 | 3 |
| Fixed-time | 1.0 | Collisions | 0.0 | 0.0 | 0 to 0 | 3 |
| Fixed-time | 1.2 | Collisions | 0.0 | 0.0 | 0 to 0 | 3 |
| Adaptive | 0.8 | Collisions | 0.0 | 0.0 | 0 to 0 | 3 |
| Adaptive | 1.0 | Collisions | 0.0 | 0.0 | 0 to 0 | 3 |
| Adaptive | 1.2 | Collisions | 0.0 | 0.0 | 0 to 0 | 3 |
| Roundabout | 0.8 | Collisions | 0.0 | 0.0 | 0 to 0 | 3 |
| Roundabout | 1.0 | Collisions | 0.0 | 0.0 | 0 to 0 | 3 |
| Roundabout | 1.2 | Collisions | 0.0 | 0.0 | 0 to 0 | 3 |

Exploratory: simulated collisions/conflicts are rare-event proxies, not validated crash predictions.

## Environmental indicators (proxies)

*Environmental proxies*

| Alternative | Demand scale | Indicator | Mean | Std | CI | n |
|---|---|---|---|---|---|---|
| Fixed-time | 0.8 | Stops per vehicle (stop-and-go proxy) | 0.58 | 0.11 | 0.31 to 0.85 | 3 |
| Fixed-time | 0.8 | Mean delay (idling-exposure proxy) | 21.58 | 4.61 | 10.13 to 33.03 | 3 |
| Fixed-time | 1.0 | Stops per vehicle (stop-and-go proxy) | 0.7 | 0.06 | 0.56 to 0.84 | 3 |
| Fixed-time | 1.0 | Mean delay (idling-exposure proxy) | 27.87 | 7.9 | 8.25 to 47.49 | 3 |
| Fixed-time | 1.2 | Stops per vehicle (stop-and-go proxy) | 0.85 | 0.08 | 0.65 to 1.05 | 3 |
| Fixed-time | 1.2 | Mean delay (idling-exposure proxy) | 35.82 | 6.66 | 19.28 to 52.36 | 3 |
| Adaptive | 0.8 | Stops per vehicle (stop-and-go proxy) | 0.56 | 0.14 | 0.21 to 0.91 | 3 |
| Adaptive | 0.8 | Mean delay (idling-exposure proxy) | 17.93 | 5.79 | 3.55 to 32.31 | 3 |
| Adaptive | 1.0 | Stops per vehicle (stop-and-go proxy) | 0.62 | 0.06 | 0.48 to 0.76 | 3 |
| Adaptive | 1.0 | Mean delay (idling-exposure proxy) | 22.04 | 3.97 | 12.19 to 31.89 | 3 |
| Adaptive | 1.2 | Stops per vehicle (stop-and-go proxy) | 0.64 | 0.16 | 0.23 to 1.05 | 3 |
| Adaptive | 1.2 | Mean delay (idling-exposure proxy) | 32.4 | 3.64 | 23.36 to 41.44 | 3 |
| Roundabout | 0.8 | Stops per vehicle (stop-and-go proxy) | 0.4 | 0.03 | 0.32 to 0.48 | 3 |
| Roundabout | 0.8 | Mean delay (idling-exposure proxy) | 15.99 | 1.07 | 13.33 to 18.65 | 3 |
| Roundabout | 1.0 | Stops per vehicle (stop-and-go proxy) | 0.66 | 0.21 | 0.15 to 1.17 | 3 |
| Roundabout | 1.0 | Mean delay (idling-exposure proxy) | 20.73 | 4.7 | 9.06 to 32.4 | 3 |
| Roundabout | 1.2 | Stops per vehicle (stop-and-go proxy) | 0.94 | 0.34 | 0.09 to 1.79 | 3 |
| Roundabout | 1.2 | Mean delay (idling-exposure proxy) | 27.78 | 6.01 | 12.85 to 42.71 | 3 |

Proxies only (stop-and-go and idling exposure). No emissions or fuel model exists in this build.

- Fuel consumption: No emissions model in this build
- CO2 emissions: No emissions model in this build

## Reliability

3 repetition(s), seeds [1, 2, 3], sample adequacy: small.

- 3 repetitions: indicative only; 5+ recommended.
- Mean delay varies strongly across seeds (CV 0.32).

## Findings

| Id | Kind | Statement | Confidence |
|---|---|---|---|
| F1 | delay | Adaptive showed an inconclusive difference in mean delay compared with Fixed-time at x0.8 demand (3 seeds could not separate them). | low |
| F2 | throughput | Adaptive served a similar number of vehicles compared with Fixed-time at x0.8 demand. | moderate |
| F3 | queue | Adaptive had similar average queues compared with Fixed-time at x0.8 demand. | moderate |
| F4 | safety | Adaptive had similar safety indicators (simulated collisions) compared with Fixed-time at x0.8 demand. | moderate |
| F5 | delay | Adaptive showed an inconclusive difference in mean delay compared with Fixed-time at x1 demand (3 seeds could not separate them). | low |
| F6 | throughput | Adaptive served more vehicles than Fixed-time at x1 demand (+6.33 vehicles vs baseline, CI 1.16 to 11.5). | moderate |
| F7 | queue | Adaptive showed an inconclusive difference in average queue length compared with Fixed-time at x1 demand (3 seeds could not separate them). | low |
| F8 | safety | Adaptive had similar safety indicators (simulated collisions) compared with Fixed-time at x1 demand. | moderate |
| F9 | delay | Adaptive showed an inconclusive difference in mean delay compared with Fixed-time at x1.2 demand (3 seeds could not separate them). | low |
| F10 | throughput | Adaptive served a similar number of vehicles compared with Fixed-time at x1.2 demand. | moderate |
| F11 | queue | Adaptive had similar average queues compared with Fixed-time at x1.2 demand. | moderate |
| F12 | safety | Adaptive had similar safety indicators (simulated collisions) compared with Fixed-time at x1.2 demand. | moderate |
| F13 | delay | Roundabout showed an inconclusive difference in mean delay compared with Fixed-time at x0.8 demand (3 seeds could not separate them). | low |
| F14 | throughput | Roundabout showed an inconclusive difference in vehicles served compared with Fixed-time at x0.8 demand (3 seeds could not separate them). | low |
| F15 | queue | Roundabout showed an inconclusive difference in average queue length compared with Fixed-time at x0.8 demand (3 seeds could not separate them). | low |
| F16 | safety | Roundabout had similar safety indicators (simulated collisions) compared with Fixed-time at x0.8 demand. | moderate |
| F17 | delay | Roundabout showed an inconclusive difference in mean delay compared with Fixed-time at x1 demand (3 seeds could not separate them). | low |
| F18 | throughput | Roundabout served more vehicles than Fixed-time at x1 demand (+7.33 vehicles vs baseline, CI 3.54 to 11.13). | moderate |
| F19 | queue | Roundabout showed an inconclusive difference in average queue length compared with Fixed-time at x1 demand (3 seeds could not separate them). | low |
| F20 | safety | Roundabout had similar safety indicators (simulated collisions) compared with Fixed-time at x1 demand. | moderate |
| F21 | delay | Roundabout showed an inconclusive difference in mean delay compared with Fixed-time at x1.2 demand (3 seeds could not separate them). | low |
| F22 | throughput | Roundabout served more vehicles than Fixed-time at x1.2 demand (+10.33 vehicles vs baseline, CI 2.74 to 17.92). | moderate |
| F23 | queue | Roundabout had shorter average queues than Fixed-time at x1.2 demand (-2.27 vehicles vs baseline, CI -4.02 to -0.52). | moderate |
| F24 | safety | Roundabout had similar safety indicators (simulated collisions) compared with Fixed-time at x1.2 demand. | moderate |
| F25 | demand_sensitivity | The result for Adaptive on vehicles served depends on demand (x0.8 demand: tie; x1 demand: better; x1.2 demand: tie). It should not be read as holding outside the tested demand levels. | moderate |
| F26 | demand_sensitivity | The result for Roundabout on vehicles served depends on demand (x0.8 demand: inconclusive; x1 demand: better; x1.2 demand: better). It should not be read as holding outside the tested demand levels. | moderate |
| F27 | reliability | 3 repetitions were run; intervals are wide and readings should be treated as indicative. | moderate |
| F28 | note | No emissions or fuel model is available; environmental indicators are stop-and-go and idling proxies only, and no environmental claim is made. | high |

## Limitations

- Results describe this scenario and these demand levels; they do not transfer to other junctions or conditions.
- Readings are per metric and per demand scale; there is no overall winner.
- Several metrics, alternatives and scales are read without multiple-comparison correction.
- Safety indicators are exploratory rare-event proxies, not crash predictions.
- Environmental indicators are stop-and-go/idling proxies; no emissions model exists.
- No field data calibration is attached to this study.
- Network model: the scenario is represented as a single-junction network; multi-junction execution is not part of this study.

## Reproducibility

| Item | Value |
|---|---|
| Git commit | 886742fed0ccd464d74c9e331b9ce5dcac537e25 |
| Python | 3.14.7 |
| Input fingerprint | 706f276ec287209b |
| Scenario fingerprint | c8aa706a60df9df0 |
| Result fingerprint | b0ea6c688d52ee48 |
| Calibration run | not provided |
| Observations fingerprint | not provided |
| Network fingerprint | a9754f446bdb4fd8 |
| Seeds | 1, 2, 3 |
| Time step (s) | 0.1 |
| Engine model | UrbanFlow V1.5 core |
