# Metric glossary

<!-- Generated from frontend/src/metrics/catalog.ts by glossaryMarkdown() in
     frontend/src/metrics/glossary.ts. Do not edit by hand: change the catalog,
     then run `UPDATE_GLOSSARY=1 npx vitest run src/test/metricGlossary.test.tsx`. -->

Every measure UrbanFlow reports, in everyday words. Values always come from the
simulation; nothing here is a real-world measurement.

## Performance

Delay, service and speed of vehicles through the junction.

### Average delay (s)

`averageDelay`

Mean extra travel time of vehicles that exited after warm-up: actual travel time minus the time the same journey would take at the driver's own desired speed. It includes any slowing the layout itself forces (for example easing into a roundabout), so it is not the same as time spent queued; compare it with Average queued time.

- Counts only after the warm-up period.
- Shows “—” until a vehicle has exited after the warm-up.

### Median delay (s)

`medianDelay`

The middle driver's lost time: half of drivers lost less than this, half lost more.

- Counts only after the warm-up period.
- Shows “—” until a vehicle has exited after the warm-up.

### 95th percentile delay (s)

`p95Delay`

The time lost by the unluckiest 1 in 20 drivers, or more. It shows how bad a bad trip is, not a typical one.

- Counts only after the warm-up period.
- Shows “—” until a vehicle has exited after the warm-up.

### Average queued time (s)

`averageWaitTime`

Mean time per exited vehicle spent below the waiting-speed threshold (0.5 m/s), after warm-up. Not the same as delay: a vehicle that keeps rolling slowly is delayed but not queued.

- Counts only after the warm-up period.
- Shows “—” until a vehicle has exited after the warm-up.

### Vehicles served (veh)

`throughput`

Count of vehicles that exited the junction after warm-up.

- Counts only after the warm-up period.

### Throughput rate (veh/min)

`throughputRate`

Exits per minute over the most recent 60 s of simulated time (after warm-up).

- Counts only after the warm-up period.

### Current mean speed (m/s)

`averageTravelSpeed`

Mean instantaneous speed of the vehicles in the network right now (not a run average).

### Planning time index

`travelTimeReliability`

How much longer a bad trip takes than a normal one. 1.0 means bad trips are no slower than normal; 1.5 means 50% slower. Treat it with care when only a few vehicles have finished.

- Counts only after the warm-up period.
- Shows “—” until a vehicle has exited after the warm-up.
- Shows “N/A” when nothing has been observed.

## Traffic flow

Queues, stops and how evenly the approaches are served.

### Average queue per approach (veh)

`averageQueueLength`

Time-averaged queue on each approach, averaged across the four approaches (after warm-up).

- Counts only after the warm-up period.

### Maximum queue (veh)

`maxQueueLength`

Largest queue observed on any single approach after warm-up.

- Counts only after the warm-up period.

### Average total queue when queued (veh)

`activeAverageQueueLength`

How long the queue is whenever there is one, ignoring moments with no queue at all.

- Counts only after the warm-up period.

### Stops per vehicle

`averageStopsPerVehicle`

Mean number of stops (speed below 0.1 m/s) per vehicle that exited after warm-up.

- Counts only after the warm-up period.
- Shows “—” until a vehicle has exited after the warm-up.

### Total stops

`totalStops`

Stops made by vehicles that exited after warm-up (a count).

- Counts only after the warm-up period.

### Directional fairness

`directionalFairnessIndex`

Whether drivers on every approach wait about the same. 1.00 means equally; lower means some approaches wait much more than others. It wobbles when few vehicles have finished.

- Counts only after the warm-up period.
- Shows “—” until a vehicle has exited after the warm-up.

### Time congested (s)

`congestionRecoveryTime`

How long the junction held a sizeable queue (more than 5 vehicles in total) after the warm-up.

- Counts only after the warm-up period.

## Safety & Environment

Collisions, surrogate safety measures (TTC, PET), and estimated environmental impact (fuel, CO₂). Thresholds are literature defaults; environmental metrics are simplified kinematic estimates, not real-world measurements.

### Collisions

`collisionCount`

How many times two simulated vehicles overlapped. In the model this should be zero; any other number points to a problem in the model.

### Minimum TTC (s)

`minTTC`

The closest call so far between two vehicles heading for each other from different lanes, as seconds before they would meet if nobody changed speed. Smaller is closer. A warning sign in the model, not a crash prediction.

- Counts only after the warm-up period.
- Shows “None observed” when nothing has been observed.

### Low-TTC raw hits

`ttcEventCount`

How many moments (tenths of a second) had a close call. One long close call counts many times, so this measures exposure, not separate incidents.

- Counts only after the warm-up period.

### Near-miss events

`nearMissCount`

How many separate close calls there were. A pair of vehicles counts once per few seconds, so one long close call is one event.

- Counts only after the warm-up period.

### Minimum PET (s)

`minPET`

The smallest gap between one vehicle leaving a crossing point and another arriving at it. Smaller is tighter. Signals only; a warning sign, not a crash prediction.

- Counts only after the warm-up period.
- Shows “None observed” when nothing has been observed.
- Measured for signals only.

### Low-PET events

`petEventCount`

How many times a vehicle reached a crossing point soon after another had left it. The cut-off is generous, so many ordinary crossings count. Signals only.

- Counts only after the warm-up period.
- Measured for signals only.

### Estimated fuel (L)

`estimatedFuelLitersTotal`

A rough estimate of fuel burnt, assuming ordinary petrol cars. Use it to compare runs, not as a real fuel figure.

- Counts only after the warm-up period.

### Estimated CO₂ (kg)

`estimatedCO2KgTotal`

A rough estimate of CO₂ from the fuel estimate. Use it to compare runs, not as a real emissions figure.

- Counts only after the warm-up period.

## Capacity & demand

Offered demand, served demand and capacity estimates.

### Vehicles admitted (veh)

`totalVehiclesSpawned`

All vehicles that entered the network since the run began, including warm-up. Not the offered demand: while an entry is full its next arrival waits at the edge and no further demand arrives on that approach, and generation also stops at the per-run vehicle limit.

### Wait to enter (s)

`averageEntryWait`

Mean time vehicles that exited after warm-up waited outside the network before entering, because their entry was full. Delay and wait time start at entry, so this is the part they cannot see. Near 0 unless the scenario queues arrivals outside the network (traffic.entryQueue).

- Counts only after the warm-up period.
- Shows “—” until a vehicle has exited after the warm-up.

### Unfinished after warm-up (%)

`unfinishedShare`

Of the vehicles that entered after the warm-up, the share still on the road when the run ended. The other measures only describe vehicles that finished, so this shows who they leave out.

- Counts only after the warm-up period.
- Shows “N/A” when nothing has been observed.

### Vehicles in network now (veh)

`activeVehicleCount`

Vehicles currently on the approaches or in the junction.

### Served-rate estimate (veh/s)

`criticalSaturationVolume`

A rough rate of vehicles served per second. It cannot be higher than the traffic you asked for, so it is not the junction's true capacity.

- Counts only after the warm-up period.

### Time with traffic moving (%)

`intersectionUtilization`

How often traffic was moving rather than standing. It stays near 100% whenever traffic flows, so it does not say how full the junction is.

- Counts only after the warm-up period.

### Idle green loss (%)

`idleOpportunityLoss`

How often a red approach had a queue while every green approach was empty: green time that served nobody. Signals only (and metered roundabouts).

- Counts only after the warm-up period.
- Measured for signals only.

### Junction footprint (m²)

`spaceFootprintConsumed`

The ground area the junction layout covers, worked out differently for each layout. Use it for context, not as a like-for-like land comparison.

## Distribution & diagnostics

Spread statistics and research indices behind the headline values.

### Minimum delay (s)

`minDelay`

The least time any driver lost.

- Counts only after the warm-up period.
- Shows “—” until a vehicle has exited after the warm-up.

### Maximum delay (s)

`maxDelay`

The most time any driver lost.

- Counts only after the warm-up period.
- Shows “—” until a vehicle has exited after the warm-up.

### Delay standard deviation (s)

`delayStdDev`

How widely the time lost varies from driver to driver. Larger means less predictable trips.

- Counts only after the warm-up period.
- Shows “—” until a vehicle has exited after the warm-up.

### Queue standard deviation (veh)

`queueStdDev`

How much the total queue size swings up and down.

- Counts only after the warm-up period.

### Queue stability index

`queueStabilityIndex`

How much the queue swings compared with its usual size. High means it surges and drains; it does not say whether the queue is growing, and it is very large when queues are near zero.

- Counts only after the warm-up period.

### Speed variance index

`speedVarianceIndex`

How uneven vehicle speeds are at the same moment. Higher means more stop-and-go mixing.

- Counts only after the warm-up period.

### TTC observations

`ttcSampleCount`

How many vehicle-pair moments the close-call measure looked at. It depends on how crowded the junction is, so it is not a risk score.

- Counts only after the warm-up period.

### PET observations

`petSampleCount`

How many successive crossings the crossing-gap measure looked at. Signals only.

- Counts only after the warm-up period.
- Measured for signals only.

### Fixed-weight composite (same layout only) (/100)

`masterEfficiencyScore`

A single score out of 100 from throughput, queued time, stops, fairness and idle green, with fixed weights. Only compare it between runs of the same layout and scenario; it does not rank a signal against a roundabout.

- Counts only after the warm-up period.
- Shows “—” until a vehicle has exited after the warm-up.
- Compare only between runs of the same layout and scenario.

## Trip, safety and comparison analysis

Measures worked out from per-vehicle records or from several seeded runs. Fuel and CO₂ are model estimates and time-to-collision is a proxy; none of these is a real-world measurement.

### Total delay (vehicle-h)

`totalDelayVehicleHours`

All the lost time of all vehicles added up, in vehicle-hours. Ten vehicles each losing six minutes make one vehicle-hour. It rises with traffic volume as well as with congestion, so compare it only between runs with the same demand.

### Delay ratio

`delayRatio`

The fraction of everyone's travel time that was lost. 0.25 means a quarter of all time on the road was delay. It does not depend on how many vehicles there were.

### Planning time index

`planningTimeIndex`

How much extra time a careful traveller should allow. 1.5 means that to be on time 19 days out of 20 you need half as long again as a typical trip. Closer to 1 is more predictable. Shaky with fewer than 20 trips.

### 95th-percentile travel time (s)

`p95TravelTimeS`

A slow-day travel time: 19 in 20 trips were faster than this. It shows the bad end of the spread that an average hides. Shaky with fewer than 20 trips.

### Fuel used (estimate) (L)

`fuelLiters`

A rough model estimate of fuel burnt, assuming ordinary petrol cars. Use it to compare runs, not as a real fuel figure.

### CO₂ (estimate) (kg)

`co2Kg`

A rough model estimate of CO₂, worked out from the fuel estimate. Use it to compare runs, not as a real emissions figure.

### Idle share

`idleShare`

The fraction of vehicle time spent standing still. 0.2 means vehicles were stopped a fifth of the time they were in the simulation. Idling is also where the fuel estimate burns fuel for no distance.

### Time-to-collision (proxy) (s)

`minTtcS`

How many seconds until a following vehicle would hit the one ahead if neither changed speed. Smaller is closer. It is a warning sign used to compare runs, not a prediction that a crash will happen.

### Time exposed to low TTC (s)

`timeExposedTtcS`

How long, in total, vehicles spent in close-following situations. It measures how much time was spent near the edge, not how many separate close calls there were.

### Time-integrated TTC (s²)

`timeIntegratedTtcS`

Like time exposed to low TTC, but a very close approach counts for more than a mild one. Larger means more time spent closer to a collision. A proxy for comparing runs.

### Conflict events

`conflictEvents`

How many separate close calls there were. One long close call counts once, unlike the raw count of moments.

### Confidence interval

`confidenceInterval`

A range for the true difference rather than a single number. A narrow range means the result is well pinned down; a wide one means more runs are needed. If it includes zero, the data cannot tell the two apart.

### p-value

`pValue`

How surprising the result would be if there were no real difference. Small values (below 0.05, say) mean it is unlikely to be chance. It does not say the difference is big or useful: read it with the confidence interval.

### Paired comparison

`pairedComparison`

Comparing two strategies on identical random traffic, seed by seed, and looking at the differences. Because both face the same traffic, the difference is much less muddied by luck.

### Sensitivity (first-order / total index)

`sensitivityIndex`

Which input changes the result most. The first-order index is the share of the result's variation one input explains on its own; the total index also counts its effects in combination with other inputs. With few samples the figures are rough, so use them for ranking.

### Network throughput (veh/h)

`throughputVph`

How many vehicles got all the way through the network, per hour. Vehicles still travelling at the end of the run are not counted.

### Vehicles in the network (vehicles)

`meanVehiclesInNetwork`

How many vehicles were on the roads at a typical moment of the run. More vehicles means a busier network.

### Queued vehicles (vehicles)

`meanQueuedVehicles`

How many vehicles were waiting in queues at a typical moment, added up over every road in the network.

### Blocked link time (link-s)

`blockedLinkSeconds`

Time that roads could not let vehicles through because the road ahead was full. Two roads blocked for ten seconds each count as twenty link-seconds.

### Link fullness (fraction)

`meanOccupancyRatio`

How full a road was: 0 is empty and 1 is packed. The congestion screens colour roads and cells by this.

### Density (veh/km/lane)

`densityVehPerKmLane`

How closely packed the vehicles were, per kilometre of lane. The sideways axis of the fundamental diagram.

### Flow per lane (veh/h/lane)

`flowVehPerHourLane`

How many vehicles moved through each lane per hour. The upward axis of the fundamental diagram; its highest dot shows the busiest the network got.

### Congestion onset (s)

`congestionOnsetSeconds`

The moment a road first became congested, counted from the start of the run. Roads are listed in the order they congested.

### Spillback time (s)

`spillbackSeconds`

How long a queue was backed up into the road behind it because the road ahead had no room.

### GEH

`geh`

A traffic-engineering score for how well the modelled flow on a road matches the count. Below 5 is generally accepted as a good match; larger is a miss.

### Flow error (RMSE) (veh/h)

`rmseVph`

The typical size of the miss between modelled and counted flow, in vehicles per hour. Big misses count extra.

### Flow error (MAPE) (%)

`mapePercent`

How far off the model is on average, as a percentage of the counted flow. Roads with very small counts are left out because a tiny denominator would give a meaningless percentage.

### Twin error (MAE) (vehicles / window)

`twinMae`

On average, how many vehicles per time window the twin predicted wrongly, whether too many or too few.

### Twin error (MAPE) (%)

`twinMape`

How wrong the twin was as a share of what really happened. Windows where nothing was observed are skipped.

### Twin bias (vehicles / window)

`twinBias`

Whether the twin leans one way. A negative number means it usually predicts fewer vehicles than were seen; a positive number means more.

### Mean wait per entered vehicle (network RL) (s)

`mean_wait_s`

Total time vehicles spent stopped, divided by the vehicles that entered the network. It is not the delay of a finished trip, so do not compare it with delay figures from other screens.

### Response time, 95th percentile (ms)

`loadTestP95Ms`

How long the slowest 5% of requests took at least. If this is 400 ms, nineteen in twenty requests were faster than that.

### Load-test error rate (fraction)

`loadTestErrorRate`

The fraction of requests that failed during the load test. 0.01 means one in a hundred.
