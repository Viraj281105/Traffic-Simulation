# Phase 3: Metrics & Snapshots Issues

## ISSUE-026: Metrics Collector Framework and Warmup Filter
- **Description**: Implement the `MetricCollector` base class in `backend/src/metrics/collector.py`.
- **Objective**: Manage the aggregation of simulation events, filter out pre-warmup records, and provide query interfaces for active metrics.
- **Technical Background**: The collector gathers data from the vehicle pool and intersection at configured update frequencies. It must ignore all ticks below `warmupTime` in final statistics to prevent startup data distortion.
- **Acceptance Criteria**:
  *   Implement `MetricCollector` tracking raw metrics arrays.
  *   Support configurable `updateFrequency` and `warmupTime`.
  *   Discard vehicle records (e.g. exit times, wait times) for vehicles spawned or exiting during the warmup duration.
  *   Unit tests verify that metrics are not logged when clock time is less than warmup threshold.
- **Dependencies**: ISSUE-009, ISSUE-017
- **Estimated Effort**: M
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 3`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.5.0 — Metrics`
- **Definition of Done**: Tests verify that warmup filter removes startup actions from calculations correctly.

---

## ISSUE-027: Average Wait Time Calculator
- **Description**: Implement the `average_wait_time` metric calculator inside `backend/src/metrics/definitions/wait_time.py`.
- **Objective**: Calculate the mean cumulative wait time across all exited vehicles.
- **Technical Background**: A vehicle is marked as waiting if its speed drops below `waitSpeedThreshold`. The cumulative seconds spent in this state are aggregated and averaged upon vehicle exit.
- **Acceptance Criteria**:
  *   Calculate average wait time matching formula: $\bar{W} = \frac{1}{N} \sum W_i$.
  *   Use configurable `waitSpeedThreshold` (default 0.5 m/s).
  *   Exclude active vehicles still in the simulation from the final output (but include them in a running metric preview).
  *   Handle edge cases: return `0.0` if no vehicles have exited.
- **Dependencies**: ISSUE-015, ISSUE-026
- **Estimated Effort**: S
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 3`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.5.0 — Metrics`
- **Definition of Done**: Math unit tests verify wait time aggregates match expected sample values.

---

## ISSUE-028: Throughput and Rolling Throughput Rate Tracker
- **Description**: Create the throughput tracker inside `backend/src/metrics/definitions/throughput.py`.
- **Objective**: Track the total count of exited vehicles and compute the rolling throughput rate in vehicles per minute.
- **Technical Background**: Throughput rate is computed over a sliding window (default 60s) using the formula:
  $$T_{rate} = \frac{T_{window}}{\Delta t_{window}} \times 60$$
- **Acceptance Criteria**:
  *   Increment total throughput counter when vehicles pass exit lanes.
  *   Maintain a rolling queue of exit timestamps.
  *   Compute the throughput rate dynamically using active window sizes.
  *   Expose outputs matching `metrics.schema.json`.
- **Dependencies**: ISSUE-017, ISSUE-026
- **Estimated Effort**: S
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 3`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.5.0 — Metrics`
- **Definition of Done**: Rolling calculations match sliding window test triggers exactly.

---

## ISSUE-029: Approach Queue Length Statistics Calculator
- **Description**: Implement queue tracking inside `backend/src/metrics/definitions/queue_length.py`.
- **Objective**: Calculate instantaneous, maximum, average, and 95th percentile queue lengths per approach arm.
- **Technical Background**: A queue is the number of vehicles on an approach arm with speed less than `waitSpeedThreshold`. Statistics are updated on every metrics tick to record time-averaged values.
- **Acceptance Criteria**:
  *   Track queue lengths per direction (North, South, East, West).
  *   Maintain history array to compute 95th percentile and maximum values.
  *   Compute time-averaged queue length: $\bar{Q} = \frac{1}{M} \sum Q(t)$.
  *   Ignore queue lengths logged during warmup.
- **Dependencies**: ISSUE-011, ISSUE-026
- **Estimated Effort**: M
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 3`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.5.0 — Metrics`
- **Definition of Done**: Statistical calculations (max, mean, 95th percentile) are verified against mock history data.

---

## ISSUE-030: Stop Count Metric with Speed Hysteresis
- **Description**: Implement stop-count tracking inside `backend/src/metrics/definitions/stop_count.py`.
- **Objective**: Calculate the average number of complete stops per vehicle using hysteresis to avoid double-counting.
- **Technical Background**: A stop event occurs when speed drops below `stopSpeedThreshold` (default 0.1 m/s). Hysteresis prevents oscillation errors (e.g. a vehicle crawling at 0.09-0.11 m/s should not trigger multiple stops).
- **Acceptance Criteria**:
  *   Implement stop counter on Vehicle objects.
  *   Require speed to exceed $2 \times \text{stopSpeedThreshold}$ before a subsequent stop can be logged (hysteresis limit).
  *   Aggregate and compute the mean stops per exited vehicle.
- **Dependencies**: ISSUE-015, ISSUE-026
- **Estimated Effort**: S
- **Priority**: Medium
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 3`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.5.0 — Metrics`
- **Definition of Done**: Unit tests verify that velocity oscillations near the threshold only trigger 1 stop.

---

## ISSUE-031: Speed Variance Index and Travel Time Reliability Calculator
- **Description**: Implement traffic quality metrics inside `backend/src/metrics/definitions/speed_variance.py` and `travel_time.py`.
- **Objective**: Compute the speed coefficient of variation and the Planning Time Index (95th percentile / median travel time).
- **Technical Background**: Speed variance captures flow turbulence. Travel time reliability computes the ratio between worst-case travel time (95th percentile) and normal travel time (50th percentile) for exited vehicles.
- **Acceptance Criteria**:
  *   Compute active speed Coefficient of Variation (CV) on every metrics tick.
  *   Track total travel times (exit time - spawn time) for all exited vehicles.
  *   Compute the Planning Time Index (PTI) ratio.
  *   Verify calculations return `1.0` if speed or travel time variance is zero.
- **Dependencies**: ISSUE-017, ISSUE-026
- **Estimated Effort**: M
- **Priority**: Medium
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 3`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.5.0 — Metrics`
- **Definition of Done**: Math checks on test arrays match target coefficients and median/percentile ratios.

---

## ISSUE-032: Idle Opportunity Loss and Directional Fairness Index Calculator
- **Description**: Implement system efficiency and fairness metrics in `backend/src/metrics/definitions/idle_loss.py` and `fairness.py`.
- **Objective**: Calculate the intersection's idle capacity wastage and Jain's Fairness Index across approach queue distributions.
- **Technical Background**: Idle loss is the fraction of time a controller restricts a movement when no competing traffic is present. Jain's Fairness Index is computed as:
  $$\mathcal{J}(x_1, x_2, \dots, x_n) = \frac{(\sum x_i)^2}{n \sum x_i^2}$$
  Where $x_i$ represents the average wait time on approach $i$.
- **Acceptance Criteria**:
  *   Calculate idle opportunity loss percentage (0.0 to 1.0).
  *   Calculate Jain's Fairness Index across wait times of the 4 approach arms.
  *   Expose metrics according to schema models.
- **Dependencies**: ISSUE-022, ISSUE-026, ISSUE-029
- **Estimated Effort**: M
- **Priority**: Medium
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 3`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.5.0 — Metrics`
- **Definition of Done**: Fairness index equals `1.0` for uniform queues and drops appropriately under asymmetric demand.

---

## ISSUE-033: Snapshot Builder and Serializer
- **Description**: Build the `SnapshotBuilder` and `Serializer` classes inside `backend/src/snapshot/builder.py` and `serializer.py`.
- **Objective**: Assemble a complete simulation state snapshot dictionary from active engines and serialize it to JSON.
- **Technical Background**: Conforms to the `snapshot.schema.json` contract. Aggregates values from clock, vehicles, intersection state, active controller, and collector, converting outputs to native types.
- **Acceptance Criteria**:
  *   Implement `SnapshotBuilder` grouping all system components.
  *   Assemble snapshot dictionaries conforming to fields of `snapshot.schema.json`.
  *   Implement `Serializer` parsing dictionary to JSON strings.
  *   Include validation check: validate generated dictionary against `snapshot.schema.json` in debug mode.
- **Dependencies**: ISSUE-010, ISSUE-017, ISSUE-025, ISSUE-026
- **Estimated Effort**: M
- **Priority**: Critical
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 3`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.2.0 — Backend Core`
- **Definition of Done**: Serializer output validates successfully against schema and runs under 5ms per call.

---

## ISSUE-034: Snapshot History Buffer
- **Description**: Implement the `SnapshotBuffer` class in `backend/src/snapshot/buffer.py` to cache past states.
- **Objective**: Store a rolling history of snapshots during a run, enabling playback controls and rewind capabilities.
- **Technical Background**: The buffer holds a chronological array of serialized snapshots. It must support size limits to avoid memory leaks during long runs.
- **Acceptance Criteria**:
  *   Implement `SnapshotBuffer` with configurable maximum frame limits.
  *   Provide methods: `append(snapshot)`, `get_frame(tick) -> Snapshot`, `clear()`, `get_all() -> list[Snapshot]`.
  *   Implement export to file options (saving run history as a single JSON file).
- **Dependencies**: ISSUE-033
- **Estimated Effort**: S
- **Priority**: High
- **Suggested Labels**: `type: feature`, `scope: backend`, `phase: 3`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.2.0 — Backend Core`
- **Definition of Done**: Caching and retrieving operations are verified with unit tests, proving that buffer respects size constraints.
