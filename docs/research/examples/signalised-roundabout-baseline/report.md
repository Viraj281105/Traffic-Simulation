# Planning report: W2 baseline: metered roundabout vs conventional, fixed-time and adaptive

## Executive summary

4 alternative(s) were compared for scenario 'W2 baseline junction (uneven peak demand)' (fingerprint cc8213f0df89d96f) at demand scale(s) x0.25, x0.5, x1 over 12 repetition(s). 38 finding(s) follow. This report presents evidence for this scenario only and does not name a universally better option.

- Metered-entry roundabout (28/14 s) had higher mean delay than Conventional roundabout at x0.25 demand (+10.01 s vs baseline, CI 7.81 to 12.21).
- Metered-entry roundabout (28/14 s) served fewer vehicles than Conventional roundabout at x0.25 demand (-2.17 vehicles vs baseline, CI -2.97 to -1.36).
- Metered-entry roundabout (28/14 s) had similar average queues compared with Conventional roundabout at x0.25 demand.
- Metered-entry roundabout (28/14 s) had similar safety indicators (simulated collisions) compared with Conventional roundabout at x0.25 demand.
- Metered-entry roundabout (28/14 s) had higher mean delay than Conventional roundabout at x0.5 demand (+13.18 s vs baseline, CI 10.68 to 15.67).
- Metered-entry roundabout (28/14 s) served fewer vehicles than Conventional roundabout at x0.5 demand (-7.25 vehicles vs baseline, CI -8.99 to -5.51).
- Metered-entry roundabout (28/14 s) had longer average queues than Conventional roundabout at x0.5 demand (+1.06 vehicles vs baseline, CI 0.92 to 1.21).
- Metered-entry roundabout (28/14 s) had similar safety indicators (simulated collisions) compared with Conventional roundabout at x0.5 demand.

## Scenario

*Arms*

| Arm | Lanes | Length (m) | Vehicles/h | Turning |
|---|---|---|---|---|
| north | 1 | 150.0 | 800.0 | {"left": 0.2, "right": 0.2, "straight": 0.6} |
| south | 1 | 150.0 | 800.0 | {"left": 0.2, "right": 0.2, "straight": 0.6} |
| east | 1 | 150.0 | 400.0 | {"left": 0.2, "right": 0.2, "straight": 0.6} |
| west | 1 | 150.0 | 400.0 | {"left": 0.2, "right": 0.2, "straight": 0.6} |

Vehicle mix: {"bus": 0.04, "car": 0.8, "motorcycle": 0.03, "suv": 0.08, "truck": 0.05}. Duration 240s, warm-up 30s.

## Alternatives

| Id | Label | Strategy | Baseline | Changes from scenario | Fingerprint |
|---|---|---|---|---|---|
| conventional | Conventional roundabout | Roundabout | yes | none | cc8213f0df89d96f |
| metered | Metered-entry roundabout (28/14 s) | Roundabout | no | roundabout.entryControl, roundabout.entryMetering | ed08c9d8f69b75cd |
| fixed_time | Fixed-time signal | Fixed-time signal | no | none | cc8213f0df89d96f |
| adaptive | Adaptive signal | Adaptive signal | no | none | cc8213f0df89d96f |

## Methodology

Each alternative is simulated under identical seeds, so per-seed differences against the baseline are paired. Intervals are two-sided Student-t at 95%. Paired per-seed differences in mean delay (first strategy minus second), Student-t interval on the mean difference. 'lower'/'higher' needs the interval to exclude zero and the means to differ by more than the tie tolerance; 'tie' means within the tolerance; otherwise 'inconclusive'. No multiple-comparison correction.

## Performance

*Performance indicators*

| Alternative | Demand scale | Indicator | Mean | Std | CI | n |
|---|---|---|---|---|---|---|
| Conventional roundabout | 0.25 | Mean delay | 12.51 | 2.07 | 11.2 to 13.82 | 12 |
| Conventional roundabout | 0.25 | Mean wait time | 1.24 | 0.72 | 0.79 to 1.69 | 12 |
| Conventional roundabout | 0.25 | Vehicles served | 37.5 | 4.21 | 34.82 to 40.18 | 12 |
| Conventional roundabout | 0.25 | Mean queue length | 0.06 | 0.03 | 0.04 to 0.08 | 12 |
| Conventional roundabout | 0.25 | Max queue length | 1.83 | 0.94 | 1.23 to 2.43 | 12 |
| Conventional roundabout | 0.25 | Stops per vehicle | 0.33 | 0.12 | 0.25 to 0.41 | 12 |
| Conventional roundabout | 0.5 | Mean delay | 24.44 | 5.17 | 21.16 to 27.72 | 12 |
| Conventional roundabout | 0.5 | Mean wait time | 5.98 | 2.34 | 4.49 to 7.47 | 12 |
| Conventional roundabout | 0.5 | Vehicles served | 63.75 | 4.97 | 60.59 to 66.91 | 12 |
| Conventional roundabout | 0.5 | Mean queue length | 0.64 | 0.28 | 0.46 to 0.82 | 12 |
| Conventional roundabout | 0.5 | Max queue length | 6.0 | 2.26 | 4.57 to 7.43 | 12 |
| Conventional roundabout | 0.5 | Stops per vehicle | 1.02 | 0.27 | 0.85 to 1.19 | 12 |
| Conventional roundabout | 1.0 | Mean delay | 52.94 | 5.88 | 49.21 to 56.67 | 12 |
| Conventional roundabout | 1.0 | Mean wait time | 18.43 | 3.73 | 16.06 to 20.8 | 12 |
| Conventional roundabout | 1.0 | Vehicles served | 74.83 | 4.24 | 72.14 to 77.52 | 12 |
| Conventional roundabout | 1.0 | Mean queue length | 3.31 | 0.65 | 2.89 to 3.73 | 12 |
| Conventional roundabout | 1.0 | Max queue length | 16.5 | 1.45 | 15.58 to 17.42 | 12 |
| Conventional roundabout | 1.0 | Stops per vehicle | 2.05 | 0.42 | 1.79 to 2.31 | 12 |
| Metered-entry roundabout (28/14 s) | 0.25 | Mean delay | 22.53 | 4.45 | 19.7 to 25.36 | 12 |
| Metered-entry roundabout (28/14 s) | 0.25 | Mean wait time | 8.18 | 3.49 | 5.96 to 10.4 | 12 |
| Metered-entry roundabout (28/14 s) | 0.25 | Vehicles served | 35.33 | 4.29 | 32.6 to 38.06 | 12 |
| Metered-entry roundabout (28/14 s) | 0.25 | Mean queue length | 0.42 | 0.17 | 0.31 to 0.53 | 12 |
| Metered-entry roundabout (28/14 s) | 0.25 | Max queue length | 3.67 | 0.98 | 3.04 to 4.3 | 12 |
| Metered-entry roundabout (28/14 s) | 0.25 | Stops per vehicle | 0.62 | 0.16 | 0.52 to 0.72 | 12 |
| Metered-entry roundabout (28/14 s) | 0.5 | Mean delay | 37.61 | 5.55 | 34.08 to 41.14 | 12 |
| Metered-entry roundabout (28/14 s) | 0.5 | Mean wait time | 17.03 | 3.34 | 14.91 to 19.15 | 12 |
| Metered-entry roundabout (28/14 s) | 0.5 | Vehicles served | 56.5 | 4.36 | 53.73 to 59.27 | 12 |
| Metered-entry roundabout (28/14 s) | 0.5 | Mean queue length | 1.7 | 0.4 | 1.45 to 1.95 | 12 |
| Metered-entry roundabout (28/14 s) | 0.5 | Max queue length | 8.92 | 2.02 | 7.64 to 10.2 | 12 |
| Metered-entry roundabout (28/14 s) | 0.5 | Stops per vehicle | 1.22 | 0.26 | 1.05 to 1.39 | 12 |
| Metered-entry roundabout (28/14 s) | 1.0 | Mean delay | 65.29 | 5.23 | 61.97 to 68.61 | 12 |
| Metered-entry roundabout (28/14 s) | 1.0 | Mean wait time | 32.64 | 3.78 | 30.24 to 35.04 | 12 |
| Metered-entry roundabout (28/14 s) | 1.0 | Vehicles served | 61.0 | 3.81 | 58.58 to 63.42 | 12 |
| Metered-entry roundabout (28/14 s) | 1.0 | Mean queue length | 5.42 | 0.69 | 4.98 to 5.86 | 12 |
| Metered-entry roundabout (28/14 s) | 1.0 | Max queue length | 16.83 | 1.11 | 16.12 to 17.54 | 12 |
| Metered-entry roundabout (28/14 s) | 1.0 | Stops per vehicle | 2.0 | 0.23 | 1.85 to 2.15 | 12 |
| Fixed-time signal | 0.25 | Mean delay | 21.96 | 4.84 | 18.89 to 25.03 | 12 |
| Fixed-time signal | 0.25 | Mean wait time | 14.44 | 4.08 | 11.85 to 17.03 | 12 |
| Fixed-time signal | 0.25 | Vehicles served | 34.33 | 3.58 | 32.06 to 36.6 | 12 |
| Fixed-time signal | 0.25 | Mean queue length | 0.77 | 0.28 | 0.59 to 0.95 | 12 |
| Fixed-time signal | 0.25 | Max queue length | 5.75 | 1.71 | 4.66 to 6.84 | 12 |
| Fixed-time signal | 0.25 | Stops per vehicle | 0.65 | 0.13 | 0.57 to 0.73 | 12 |
| Fixed-time signal | 0.5 | Mean delay | 41.83 | 4.33 | 39.08 to 44.58 | 12 |
| Fixed-time signal | 0.5 | Mean wait time | 31.52 | 4.39 | 28.73 to 34.31 | 12 |
| Fixed-time signal | 0.5 | Vehicles served | 50.58 | 3.7 | 48.23 to 52.93 | 12 |
| Fixed-time signal | 0.5 | Mean queue length | 3.24 | 0.66 | 2.82 to 3.66 | 12 |
| Fixed-time signal | 0.5 | Max queue length | 14.58 | 3.85 | 12.13 to 17.03 | 12 |
| Fixed-time signal | 0.5 | Stops per vehicle | 0.84 | 0.08 | 0.79 to 0.89 | 12 |
| Fixed-time signal | 1.0 | Mean delay | 57.9 | 5.7 | 54.28 to 61.52 | 12 |
| Fixed-time signal | 1.0 | Mean wait time | 45.82 | 4.94 | 42.68 to 48.96 | 12 |
| Fixed-time signal | 1.0 | Vehicles served | 60.17 | 3.43 | 57.99 to 62.35 | 12 |
| Fixed-time signal | 1.0 | Mean queue length | 8.01 | 1.07 | 7.33 to 8.69 | 12 |
| Fixed-time signal | 1.0 | Max queue length | 19.33 | 0.78 | 18.84 to 19.82 | 12 |
| Fixed-time signal | 1.0 | Stops per vehicle | 0.94 | 0.17 | 0.83 to 1.05 | 12 |
| Adaptive signal | 0.25 | Mean delay | 18.76 | 5.91 | 15.01 to 22.51 | 12 |
| Adaptive signal | 0.25 | Mean wait time | 10.99 | 4.78 | 7.95 to 14.03 | 12 |
| Adaptive signal | 0.25 | Vehicles served | 34.5 | 4.74 | 31.49 to 37.51 | 12 |
| Adaptive signal | 0.25 | Mean queue length | 0.6 | 0.26 | 0.43 to 0.77 | 12 |
| Adaptive signal | 0.25 | Max queue length | 4.58 | 1.73 | 3.48 to 5.68 | 12 |
| Adaptive signal | 0.25 | Stops per vehicle | 0.66 | 0.15 | 0.56 to 0.76 | 12 |
| Adaptive signal | 0.5 | Mean delay | 36.21 | 4.87 | 33.11 to 39.31 | 12 |
| Adaptive signal | 0.5 | Mean wait time | 25.66 | 3.99 | 23.13 to 28.19 | 12 |
| Adaptive signal | 0.5 | Vehicles served | 52.42 | 4.81 | 49.36 to 55.48 | 12 |
| Adaptive signal | 0.5 | Mean queue length | 2.98 | 0.4 | 2.72 to 3.24 | 12 |
| Adaptive signal | 0.5 | Max queue length | 14.58 | 3.9 | 12.1 to 17.06 | 12 |
| Adaptive signal | 0.5 | Stops per vehicle | 0.81 | 0.14 | 0.72 to 0.9 | 12 |
| Adaptive signal | 1.0 | Mean delay | 53.18 | 6.68 | 48.94 to 57.42 | 12 |
| Adaptive signal | 1.0 | Mean wait time | 40.52 | 6.67 | 36.28 to 44.76 | 12 |
| Adaptive signal | 1.0 | Vehicles served | 67.0 | 2.86 | 65.18 to 68.82 | 12 |
| Adaptive signal | 1.0 | Mean queue length | 8.0 | 0.72 | 7.54 to 8.46 | 12 |
| Adaptive signal | 1.0 | Max queue length | 19.25 | 1.22 | 18.48 to 20.02 | 12 |
| Adaptive signal | 1.0 | Stops per vehicle | 0.78 | 0.13 | 0.7 to 0.86 | 12 |

## Safety indicators (exploratory)

*Safety indicators*

| Alternative | Demand scale | Indicator | Mean | Std | CI | n |
|---|---|---|---|---|---|---|
| Conventional roundabout | 0.25 | Collisions | 0.0 | 0.0 | 0 to 0 | 12 |
| Conventional roundabout | 0.5 | Collisions | 0.0 | 0.0 | 0 to 0 | 12 |
| Conventional roundabout | 1.0 | Collisions | 0.0 | 0.0 | 0 to 0 | 12 |
| Metered-entry roundabout (28/14 s) | 0.25 | Collisions | 0.0 | 0.0 | 0 to 0 | 12 |
| Metered-entry roundabout (28/14 s) | 0.5 | Collisions | 0.0 | 0.0 | 0 to 0 | 12 |
| Metered-entry roundabout (28/14 s) | 1.0 | Collisions | 0.0 | 0.0 | 0 to 0 | 12 |
| Fixed-time signal | 0.25 | Collisions | 0.0 | 0.0 | 0 to 0 | 12 |
| Fixed-time signal | 0.5 | Collisions | 0.0 | 0.0 | 0 to 0 | 12 |
| Fixed-time signal | 1.0 | Collisions | 0.0 | 0.0 | 0 to 0 | 12 |
| Adaptive signal | 0.25 | Collisions | 0.0 | 0.0 | 0 to 0 | 12 |
| Adaptive signal | 0.5 | Collisions | 0.0 | 0.0 | 0 to 0 | 12 |
| Adaptive signal | 1.0 | Collisions | 0.0 | 0.0 | 0 to 0 | 12 |

Exploratory: simulated collisions/conflicts are rare-event proxies, not validated crash predictions.

## Environmental indicators (proxies)

*Environmental proxies*

| Alternative | Demand scale | Indicator | Mean | Std | CI | n |
|---|---|---|---|---|---|---|
| Conventional roundabout | 0.25 | Stops per vehicle (stop-and-go proxy) | 0.33 | 0.12 | 0.25 to 0.41 | 12 |
| Conventional roundabout | 0.25 | Mean delay (idling-exposure proxy) | 12.51 | 2.07 | 11.2 to 13.82 | 12 |
| Conventional roundabout | 0.5 | Stops per vehicle (stop-and-go proxy) | 1.02 | 0.27 | 0.85 to 1.19 | 12 |
| Conventional roundabout | 0.5 | Mean delay (idling-exposure proxy) | 24.44 | 5.17 | 21.16 to 27.72 | 12 |
| Conventional roundabout | 1.0 | Stops per vehicle (stop-and-go proxy) | 2.05 | 0.42 | 1.79 to 2.31 | 12 |
| Conventional roundabout | 1.0 | Mean delay (idling-exposure proxy) | 52.94 | 5.88 | 49.21 to 56.67 | 12 |
| Metered-entry roundabout (28/14 s) | 0.25 | Stops per vehicle (stop-and-go proxy) | 0.62 | 0.16 | 0.52 to 0.72 | 12 |
| Metered-entry roundabout (28/14 s) | 0.25 | Mean delay (idling-exposure proxy) | 22.53 | 4.45 | 19.7 to 25.36 | 12 |
| Metered-entry roundabout (28/14 s) | 0.5 | Stops per vehicle (stop-and-go proxy) | 1.22 | 0.26 | 1.05 to 1.39 | 12 |
| Metered-entry roundabout (28/14 s) | 0.5 | Mean delay (idling-exposure proxy) | 37.61 | 5.55 | 34.08 to 41.14 | 12 |
| Metered-entry roundabout (28/14 s) | 1.0 | Stops per vehicle (stop-and-go proxy) | 2.0 | 0.23 | 1.85 to 2.15 | 12 |
| Metered-entry roundabout (28/14 s) | 1.0 | Mean delay (idling-exposure proxy) | 65.29 | 5.23 | 61.97 to 68.61 | 12 |
| Fixed-time signal | 0.25 | Stops per vehicle (stop-and-go proxy) | 0.65 | 0.13 | 0.57 to 0.73 | 12 |
| Fixed-time signal | 0.25 | Mean delay (idling-exposure proxy) | 21.96 | 4.84 | 18.89 to 25.03 | 12 |
| Fixed-time signal | 0.5 | Stops per vehicle (stop-and-go proxy) | 0.84 | 0.08 | 0.79 to 0.89 | 12 |
| Fixed-time signal | 0.5 | Mean delay (idling-exposure proxy) | 41.83 | 4.33 | 39.08 to 44.58 | 12 |
| Fixed-time signal | 1.0 | Stops per vehicle (stop-and-go proxy) | 0.94 | 0.17 | 0.83 to 1.05 | 12 |
| Fixed-time signal | 1.0 | Mean delay (idling-exposure proxy) | 57.9 | 5.7 | 54.28 to 61.52 | 12 |
| Adaptive signal | 0.25 | Stops per vehicle (stop-and-go proxy) | 0.66 | 0.15 | 0.56 to 0.76 | 12 |
| Adaptive signal | 0.25 | Mean delay (idling-exposure proxy) | 18.76 | 5.91 | 15.01 to 22.51 | 12 |
| Adaptive signal | 0.5 | Stops per vehicle (stop-and-go proxy) | 0.81 | 0.14 | 0.72 to 0.9 | 12 |
| Adaptive signal | 0.5 | Mean delay (idling-exposure proxy) | 36.21 | 4.87 | 33.11 to 39.31 | 12 |
| Adaptive signal | 1.0 | Stops per vehicle (stop-and-go proxy) | 0.78 | 0.13 | 0.7 to 0.86 | 12 |
| Adaptive signal | 1.0 | Mean delay (idling-exposure proxy) | 53.18 | 6.68 | 48.94 to 57.42 | 12 |

Proxies only (stop-and-go and idling exposure). No emissions or fuel model exists in this build.

- Fuel consumption: No emissions model in this build
- CO2 emissions: No emissions model in this build

## Reliability

12 repetition(s), seeds [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112], sample adequacy: adequate.

- Mean delay varies strongly across seeds (CV 0.32).

## Findings

| Id | Kind | Statement | Confidence |
|---|---|---|---|
| F1 | delay | Metered-entry roundabout (28/14 s) had higher mean delay than Conventional roundabout at x0.25 demand (+10.01 s vs baseline, CI 7.81 to 12.21). | high |
| F2 | throughput | Metered-entry roundabout (28/14 s) served fewer vehicles than Conventional roundabout at x0.25 demand (-2.17 vehicles vs baseline, CI -2.97 to -1.36). | high |
| F3 | queue | Metered-entry roundabout (28/14 s) had similar average queues compared with Conventional roundabout at x0.25 demand. | moderate |
| F4 | safety | Metered-entry roundabout (28/14 s) had similar safety indicators (simulated collisions) compared with Conventional roundabout at x0.25 demand. | moderate |
| F5 | delay | Metered-entry roundabout (28/14 s) had higher mean delay than Conventional roundabout at x0.5 demand (+13.18 s vs baseline, CI 10.68 to 15.67). | high |
| F6 | throughput | Metered-entry roundabout (28/14 s) served fewer vehicles than Conventional roundabout at x0.5 demand (-7.25 vehicles vs baseline, CI -8.99 to -5.51). | high |
| F7 | queue | Metered-entry roundabout (28/14 s) had longer average queues than Conventional roundabout at x0.5 demand (+1.06 vehicles vs baseline, CI 0.92 to 1.21). | high |
| F8 | safety | Metered-entry roundabout (28/14 s) had similar safety indicators (simulated collisions) compared with Conventional roundabout at x0.5 demand. | moderate |
| F9 | delay | Metered-entry roundabout (28/14 s) had higher mean delay than Conventional roundabout at x1 demand (+12.35 s vs baseline, CI 9.34 to 15.37). | high |
| F10 | throughput | Metered-entry roundabout (28/14 s) served fewer vehicles than Conventional roundabout at x1 demand (-13.83 vehicles vs baseline, CI -15.8 to -11.86). | high |
| F11 | queue | Metered-entry roundabout (28/14 s) had longer average queues than Conventional roundabout at x1 demand (+2.11 vehicles vs baseline, CI 1.77 to 2.44). | high |
| F12 | safety | Metered-entry roundabout (28/14 s) had similar safety indicators (simulated collisions) compared with Conventional roundabout at x1 demand. | moderate |
| F13 | delay | Fixed-time signal had higher mean delay than Conventional roundabout at x0.25 demand (+9.45 s vs baseline, CI 5.99 to 12.91). | high |
| F14 | throughput | Fixed-time signal served fewer vehicles than Conventional roundabout at x0.25 demand (-3.17 vehicles vs baseline, CI -4.54 to -1.79). | high |
| F15 | queue | Fixed-time signal had longer average queues than Conventional roundabout at x0.25 demand (+0.71 vehicles vs baseline, CI 0.53 to 0.89). | high |
| F16 | safety | Fixed-time signal had similar safety indicators (simulated collisions) compared with Conventional roundabout at x0.25 demand. | moderate |
| F17 | delay | Fixed-time signal had higher mean delay than Conventional roundabout at x0.5 demand (+17.39 s vs baseline, CI 13.44 to 21.34). | high |
| F18 | throughput | Fixed-time signal served fewer vehicles than Conventional roundabout at x0.5 demand (-13.17 vehicles vs baseline, CI -15.94 to -10.39). | high |
| F19 | queue | Fixed-time signal had longer average queues than Conventional roundabout at x0.5 demand (+2.61 vehicles vs baseline, CI 2.24 to 2.97). | high |
| F20 | safety | Fixed-time signal had similar safety indicators (simulated collisions) compared with Conventional roundabout at x0.5 demand. | moderate |
| F21 | delay | Fixed-time signal had higher mean delay than Conventional roundabout at x1 demand (+4.96 s vs baseline, CI 0.43 to 9.49). | high |
| F22 | throughput | Fixed-time signal served fewer vehicles than Conventional roundabout at x1 demand (-14.67 vehicles vs baseline, CI -17.35 to -11.98). | high |
| F23 | queue | Fixed-time signal had longer average queues than Conventional roundabout at x1 demand (+4.7 vehicles vs baseline, CI 4.28 to 5.12). | high |
| F24 | safety | Fixed-time signal had similar safety indicators (simulated collisions) compared with Conventional roundabout at x1 demand. | moderate |
| F25 | delay | Adaptive signal had higher mean delay than Conventional roundabout at x0.25 demand (+6.25 s vs baseline, CI 2.96 to 9.53). | high |
| F26 | throughput | Adaptive signal served fewer vehicles than Conventional roundabout at x0.25 demand (-3 vehicles vs baseline, CI -4.18 to -1.82). | high |
| F27 | queue | Adaptive signal had longer average queues than Conventional roundabout at x0.25 demand (+0.55 vehicles vs baseline, CI 0.38 to 0.71). | high |
| F28 | safety | Adaptive signal had similar safety indicators (simulated collisions) compared with Conventional roundabout at x0.25 demand. | moderate |
| F29 | delay | Adaptive signal had higher mean delay than Conventional roundabout at x0.5 demand (+11.78 s vs baseline, CI 7.65 to 15.91). | high |
| F30 | throughput | Adaptive signal served fewer vehicles than Conventional roundabout at x0.5 demand (-11.33 vehicles vs baseline, CI -12.97 to -9.7). | high |
| F31 | queue | Adaptive signal had longer average queues than Conventional roundabout at x0.5 demand (+2.34 vehicles vs baseline, CI 2.16 to 2.53). | high |
| F32 | safety | Adaptive signal had similar safety indicators (simulated collisions) compared with Conventional roundabout at x0.5 demand. | moderate |
| F33 | delay | Adaptive signal had a similar mean delay compared with Conventional roundabout at x1 demand. | moderate |
| F34 | throughput | Adaptive signal served fewer vehicles than Conventional roundabout at x1 demand (-7.83 vehicles vs baseline, CI -9.69 to -5.98). | high |
| F35 | queue | Adaptive signal had longer average queues than Conventional roundabout at x1 demand (+4.69 vehicles vs baseline, CI 4.39 to 5). | high |
| F36 | safety | Adaptive signal had similar safety indicators (simulated collisions) compared with Conventional roundabout at x1 demand. | moderate |
| F37 | demand_sensitivity | The result for Adaptive signal on mean delay depends on demand (x0.25 demand: worse; x0.5 demand: worse; x1 demand: tie). It should not be read as holding outside the tested demand levels. | moderate |
| F38 | note | No emissions or fuel model is available; environmental indicators are stop-and-go and idling proxies only, and no environmental claim is made. | high |

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
| Git commit | b79016725beda59f838e7639eb482b43f63c5f9f |
| Python | 3.14.7 |
| Input fingerprint | a8565e4c6e075a03 |
| Scenario fingerprint | cc8213f0df89d96f |
| Result fingerprint | 678783e6bbf53d53 |
| Calibration run | not provided |
| Observations fingerprint | not provided |
| Network fingerprint | 41a35089d19ed681 |
| Seeds | 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112 |
| Time step (s) | 0.1 |
| Engine model | UrbanFlow V1.5 core |
