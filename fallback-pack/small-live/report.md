# Planning report: Preview study (small, live-capable)

## Executive summary

3 alternative(s) were compared for scenario 'Demo junction' (fingerprint c87df2abfdd786dd) at demand scale(s) x1 over 3 repetition(s). 10 finding(s) follow. This report presents evidence for this scenario only and does not name a universally better option.

- Adaptive showed an inconclusive difference in mean delay compared with Fixed-time at x1 demand (3 seeds could not separate them).
- Adaptive served a similar number of vehicles compared with Fixed-time at x1 demand.
- Adaptive had similar average queues compared with Fixed-time at x1 demand.
- Adaptive had similar safety indicators (simulated collisions) compared with Fixed-time at x1 demand.
- Roundabout showed an inconclusive difference in mean delay compared with Fixed-time at x1 demand (3 seeds could not separate them).
- Roundabout served a similar number of vehicles compared with Fixed-time at x1 demand.
- Roundabout had similar average queues compared with Fixed-time at x1 demand.
- Roundabout had similar safety indicators (simulated collisions) compared with Fixed-time at x1 demand.

## Scenario

*Arms*

| Arm | Lanes | Length (m) | Vehicles/h | Turning |
|---|---|---|---|---|
| north | 1 | 200.0 | 300.0 | {"left": 0.2, "right": 0.2, "straight": 0.6} |
| south | 1 | 200.0 | 300.0 | {"left": 0.2, "right": 0.2, "straight": 0.6} |
| east | 1 | 200.0 | 300.0 | {"left": 0.2, "right": 0.2, "straight": 0.6} |
| west | 1 | 200.0 | 300.0 | {"left": 0.2, "right": 0.2, "straight": 0.6} |

Vehicle mix: {"car": 1.0} (default passenger-car population). Duration 60s, warm-up 10s.

## Alternatives

| Id | Label | Strategy | Baseline | Changes from scenario | Fingerprint |
|---|---|---|---|---|---|
| base | Fixed-time | Fixed-time signal | yes | none | c87df2abfdd786dd |
| adaptive | Adaptive | Adaptive signal | no | none | c87df2abfdd786dd |
| rbt | Roundabout | Roundabout | no | none | c87df2abfdd786dd |

## Methodology

Each alternative is simulated under identical seeds, so per-seed differences against the baseline are paired. Intervals are two-sided Student-t at 95%. Paired per-seed differences in mean delay (first strategy minus second), Student-t interval on the mean difference. 'lower'/'higher' needs the interval to exclude zero and the means to differ by more than the tie tolerance; 'tie' means within the tolerance; otherwise 'inconclusive'. No multiple-comparison correction.

## Performance

*Performance indicators*

| Alternative | Demand scale | Indicator | Mean | Std | CI | n |
|---|---|---|---|---|---|---|
| Fixed-time | 1.0 | Mean delay | 6.28 | 5.4 | -7.14 to 19.7 | 3 |
| Fixed-time | 1.0 | Mean wait time | 3.25 | 3.92 | -6.48 to 12.98 | 3 |
| Fixed-time | 1.0 | Vehicles served | 5.0 | 3.0 | -2.45 to 12.45 | 3 |
| Fixed-time | 1.0 | Mean queue length | 0.38 | 0.16 | -0.01 to 0.77 | 3 |
| Fixed-time | 1.0 | Max queue length | 5.0 | 1.73 | 0.7 to 9.3 | 3 |
| Fixed-time | 1.0 | Stops per vehicle | 0.25 | 0.25 | -0.37 to 0.87 | 3 |
| Adaptive | 1.0 | Mean delay | 1.98 | 0.65 | 0.38 to 3.58 | 3 |
| Adaptive | 1.0 | Mean wait time | 0.05 | 0.09 | -0.18 to 0.28 | 3 |
| Adaptive | 1.0 | Vehicles served | 5.67 | 2.31 | -0.07 to 11.41 | 3 |
| Adaptive | 1.0 | Mean queue length | 0.34 | 0.14 | -0.02 to 0.7 | 3 |
| Adaptive | 1.0 | Max queue length | 3.67 | 1.53 | -0.12 to 7.46 | 3 |
| Adaptive | 1.0 | Stops per vehicle | 0.0 | 0.0 | 0 to 0 | 3 |
| Roundabout | 1.0 | Mean delay | 10.92 | 1.93 | 6.12 to 15.72 | 3 |
| Roundabout | 1.0 | Mean wait time | 1.31 | 1.03 | -1.24 to 3.86 | 3 |
| Roundabout | 1.0 | Vehicles served | 4.0 | 1.0 | 1.52 to 6.48 | 3 |
| Roundabout | 1.0 | Mean queue length | 0.13 | 0.11 | -0.13 to 0.39 | 3 |
| Roundabout | 1.0 | Max queue length | 3.0 | 1.0 | 0.52 to 5.48 | 3 |
| Roundabout | 1.0 | Stops per vehicle | 0.37 | 0.26 | -0.27 to 1.01 | 3 |

## Safety indicators (exploratory)

*Safety indicators*

| Alternative | Demand scale | Indicator | Mean | Std | CI | n |
|---|---|---|---|---|---|---|
| Fixed-time | 1.0 | Collisions | 0.0 | 0.0 | 0 to 0 | 3 |
| Adaptive | 1.0 | Collisions | 0.0 | 0.0 | 0 to 0 | 3 |
| Roundabout | 1.0 | Collisions | 0.0 | 0.0 | 0 to 0 | 3 |

Exploratory: simulated collisions/conflicts are rare-event proxies, not validated crash predictions.

## Environmental indicators (proxies)

*Environmental proxies*

| Alternative | Demand scale | Indicator | Mean | Std | CI | n |
|---|---|---|---|---|---|---|
| Fixed-time | 1.0 | Stops per vehicle (stop-and-go proxy) | 0.25 | 0.25 | -0.37 to 0.87 | 3 |
| Fixed-time | 1.0 | Mean delay (idling-exposure proxy) | 6.28 | 5.4 | -7.14 to 19.7 | 3 |
| Adaptive | 1.0 | Stops per vehicle (stop-and-go proxy) | 0.0 | 0.0 | 0 to 0 | 3 |
| Adaptive | 1.0 | Mean delay (idling-exposure proxy) | 1.98 | 0.65 | 0.38 to 3.58 | 3 |
| Roundabout | 1.0 | Stops per vehicle (stop-and-go proxy) | 0.37 | 0.26 | -0.27 to 1.01 | 3 |
| Roundabout | 1.0 | Mean delay (idling-exposure proxy) | 10.92 | 1.93 | 6.12 to 15.72 | 3 |

Proxies only (stop-and-go and idling exposure). No emissions or fuel model exists in this build.

- Fuel consumption: No emissions model in this build
- CO2 emissions: No emissions model in this build

## Reliability

3 repetition(s), seeds [1, 2, 3], sample adequacy: small.

- 3 repetitions: indicative only; 5+ recommended.
- Mean delay varies strongly across seeds (CV 0.86).
- Mean delay varies strongly across seeds (CV 0.33).

## Findings

| Id | Kind | Statement | Confidence |
|---|---|---|---|
| F1 | delay | Adaptive showed an inconclusive difference in mean delay compared with Fixed-time at x1 demand (3 seeds could not separate them). | low |
| F2 | throughput | Adaptive served a similar number of vehicles compared with Fixed-time at x1 demand. | moderate |
| F3 | queue | Adaptive had similar average queues compared with Fixed-time at x1 demand. | moderate |
| F4 | safety | Adaptive had similar safety indicators (simulated collisions) compared with Fixed-time at x1 demand. | moderate |
| F5 | delay | Roundabout showed an inconclusive difference in mean delay compared with Fixed-time at x1 demand (3 seeds could not separate them). | low |
| F6 | throughput | Roundabout served a similar number of vehicles compared with Fixed-time at x1 demand. | moderate |
| F7 | queue | Roundabout had similar average queues compared with Fixed-time at x1 demand. | moderate |
| F8 | safety | Roundabout had similar safety indicators (simulated collisions) compared with Fixed-time at x1 demand. | moderate |
| F9 | reliability | 3 repetitions were run; intervals are wide and readings should be treated as indicative. | moderate |
| F10 | note | No emissions or fuel model is available; environmental indicators are stop-and-go and idling proxies only, and no environmental claim is made. | high |

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
| Input fingerprint | cc891681ac3ce984 |
| Scenario fingerprint | c87df2abfdd786dd |
| Result fingerprint | 486579ee73642f07 |
| Calibration run | not provided |
| Observations fingerprint | not provided |
| Network fingerprint | 3753955d0a2d312e |
| Seeds | 1, 2, 3 |
| Time step (s) | 0.1 |
| Engine model | UrbanFlow V1.5 core |
