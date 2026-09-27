import itertools
import math
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.core.enums import Direction
from src.core.limits import DEFAULT_TOTAL_VEHICLES
from src.metrics.definitions.derived_metrics import (
    calculate_average_travel_speed,
    calculate_critical_saturation_volume,
    calculate_space_footprint_consumed,
)
from src.metrics.definitions.fairness import calculate_directional_fairness
from src.metrics.definitions.idle_loss import calculate_idle_loss_tick
from src.metrics.definitions.queue_length import get_current_queue_lengths
from src.metrics.definitions.safety_conflicts import (
    ConflictZoneOccupancyTracker,
    find_ttc_events,
)
from src.metrics.definitions.speed_variance import calculate_speed_variance_index
from src.metrics.definitions.stop_count import update_vehicle_stops
from src.metrics.definitions.throughput import (
    calculate_throughput,
    calculate_throughput_rate,
)
from src.metrics.definitions.travel_time import (
    MIN_RELIABLE_SAMPLE_SIZE,
    calculate_travel_time_reliability,
)
from src.metrics.definitions.wait_time import calculate_average_wait_time
from src.metrics.efficiency import calculate_master_efficiency_score
from src.vehicles.vehicle import Vehicle

if TYPE_CHECKING:
    from src.intersection.conflict_manager import ConflictManager

_DIRECTIONS = ("north", "south", "east", "west")


def resolve_speed_threshold(config: Dict[str, Any], key: str, default: float) -> float:
    """Read ``waitSpeedThreshold`` / ``stopSpeedThreshold`` from a config.

    The scenario contract, the JSON schema and the typed ``MetricsSection``
    all place these under ``metrics``; the runtime used to read them only from
    ``vehicleGeneration``, so a value set where the contract says to set it was
    silently ignored (and on the typed route, where ``VehicleGenerationSection``
    has no such fields, there was no way to set it at all). ``metrics`` now
    wins; ``vehicleGeneration`` is still honoured as the legacy location the
    dashboard and study presets use.
    """
    metrics_cfg = config.get("metrics") or {}
    if key in metrics_cfg and metrics_cfg[key] is not None:
        return float(metrics_cfg[key])
    veh_gen = config.get("vehicleGeneration") or {}
    return float(veh_gen.get(key, default))


class MetricCollector:
    """Manages the periodic aggregation of simulation operational metrics."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config: Dict[str, Any] = config
        sim_cfg = config.get("simulation", {})
        # Fallback of 30.0 matches the documented/canonical default
        # (docs/architecture/06-scenario-configuration-contract.md §2.1,
        # SimulationSection.warmupTime, CONFIG_SCHEMA) — a config that omits
        # warmupTime entirely (e.g. a raw-dict /api/v1/simulations request,
        # which is not defaults-filled by jsonschema validation) must
        # exclude the same initial approach period as the typed path, where
        # Pydantic's own default always fills this key in before it reaches
        # here.
        self.warmup_time: float = sim_cfg.get("warmupTime", 30.0)
        self.time_step: float = sim_cfg.get("timeStep", 0.1)

        # Hysteresis configuration
        self.stop_speed_threshold: float = resolve_speed_threshold(
            config, "stopSpeedThreshold", 0.1
        )
        self.wait_speed_threshold: float = resolve_speed_threshold(
            config, "waitSpeedThreshold", 0.5
        )

        # TTC/PET configuration (see metrics/definitions/safety_conflicts.py).
        # Measurement-only: these thresholds only affect which observed
        # TTC/PET values get counted as "events" for reporting purposes,
        # never simulation/vehicle behaviour.
        #
        # Threshold defaults are commonly-cited conservative values from
        # the surrogate-safety-measure literature (TTC: Hayward 1972 and
        # widely reused since as a critical/conservative cutoff; PET:
        # commonly used in SSAM-style conflict studies), not values this
        # project has itself validated -- see get_metrics()'s "not yet
        # validated" note on the resulting counts.
        metrics_cfg = config.get("metrics", {})
        self.ttc_threshold_seconds: float = metrics_cfg.get("ttcThresholdSeconds", 1.5)
        self.pet_threshold_seconds: float = metrics_cfg.get("petThresholdSeconds", 5.0)
        self.ttc_search_radius: float = metrics_cfg.get("ttcSearchRadius", 50.0)

        # The spawner's per-run vehicle cap (same key, same default), so a
        # run whose demand was truncated by it can be flagged (see
        # core/limits.py).
        traffic_cfg = config.get("traffic") or {}
        self.vehicle_limit: int = int(
            traffic_cfg.get("totalVehicles", DEFAULT_TOTAL_VEHICLES)
        )

        self.reset()

    def reset(self) -> None:
        self.idle_loss_ticks: int = 0
        self.total_ticks_post_warmup: int = 0
        self.congestion_recovery_time: float = 0.0
        self.demand_ticks: int = 0
        self.service_ticks: int = 0

        # Maintain list of queue lengths over time to compute time-average and max
        self.queue_history: List[Dict[str, int]] = []
        # Running aggregates of queue_history, kept alongside it so
        # get_metrics() never has to rescan the history. It used to, on every
        # call — and SnapshotBuilder calls it every tick of a
        # /api/v1/simulations run, so the per-tick cost grew linearly with
        # elapsed time (4 ms/tick at the start, ~37 ms by 20 simulated
        # minutes, past the 100 ms real-time budget well before an hour).
        # All integer, so the aggregates are exact and every derived value is
        # identical to the rescanning computation.
        self._q_dir_sum: Dict[str, int] = {d: 0 for d in _DIRECTIONS}
        self._q_dir_max: Dict[str, int] = {d: 0 for d in _DIRECTIONS}
        self._q_total_sum: int = 0
        self._q_total_sumsq: int = 0
        self._q_nonzero_count: int = 0
        self._q_nonzero_sum: int = 0

        # Per-tick speed CV history (see speed_variance.py) for computing
        # the time-averaged SVI = (1/T) * sum(CV(t)) per the metric contract.
        self.speed_cv_history: List[float] = []

        # Per-vehicle wait_time/stop_count snapshot taken at the moment
        # warmup ends, so a vehicle already active at that point doesn't
        # have its pre-warmup wait/stops leak into post-warmup averages
        # (mirrors how averageDelay clips via effective_spawn_t below).
        self._warmup_baseline_wait: Dict[str, float] = {}
        self._warmup_baseline_stops: Dict[str, int] = {}
        self._warmup_baseline_captured: bool = False

        # TTC/PET accumulators (post-warmup only, matching every other
        # per-tick metric). Min values are None until at least one
        # observation exists -- see get_metrics() for how that's reported.
        self._min_ttc: Optional[float] = None
        self._ttc_event_count: int = 0
        self._ttc_sample_count: int = 0

        self._min_pet: Optional[float] = None
        self._pet_event_count: int = 0
        self._pet_sample_count: int = 0
        self._pet_applicable: bool = False
        self._zone_tracker: ConflictZoneOccupancyTracker = (
            ConflictZoneOccupancyTracker()
        )

    def update(
        self,
        current_time: float,
        active_vehicles: List[Vehicle],
        exited_vehicles: List[Vehicle],
        signals_state: Dict[Direction, str],
        conflict_manager: Optional["ConflictManager"] = None,
    ) -> None:
        """Ticks the metrics state checks (e.g. updating vehicle stop count hysteresis).

        ``conflict_manager`` is optional and additive: when supplied (only
        meaningful for fixed_time_signal geometry -- see
        metrics/definitions/safety_conflicts.py), PET is measured using its
        existing pre-computed conflict points. Omitting it (the default)
        simply means PET stays unmeasured for this run, exactly as it was
        before this parameter existed; TTC is unaffected either way, since
        it needs no conflict-manager geometry.
        """
        # Always update stop count states regardless of warmup to keep vehicle state correct
        for v in active_vehicles:
            update_vehicle_stops(v, self.stop_speed_threshold)

        # Discard metrics check during warmup
        if current_time < self.warmup_time:
            return

        if not self._warmup_baseline_captured:
            # First post-warmup tick: snapshot the cumulative wait_time/
            # stop_count of every vehicle still active right now, so their
            # pre-warmup contribution can be subtracted later in
            # get_metrics() for any of them that exits post-warmup.
            for v in active_vehicles:
                self._warmup_baseline_wait[v.vehicle_id] = v.wait_time
                self._warmup_baseline_stops[v.vehicle_id] = v.stop_count
            self._warmup_baseline_captured = True

        # Increment post-warmup simulation ticks count
        self.total_ticks_post_warmup += 1

        if active_vehicles:
            self.demand_ticks += 1
            avg_speed = sum(v.speed for v in active_vehicles) / len(active_vehicles)
            if avg_speed > self.wait_speed_threshold:
                self.service_ticks += 1

        # Speed Variance Index: accumulate this tick's CV(t) into the
        # history used for the time-averaged SVI in get_metrics(). Per the
        # metric contract, ticks with fewer than 2 active vehicles are
        # skipped entirely rather than contributing a value.
        if len(active_vehicles) >= 2:
            self.speed_cv_history.append(
                calculate_speed_variance_index(active_vehicles)
            )

        # Track idle opportunity loss
        if calculate_idle_loss_tick(
            active_vehicles, signals_state, self.wait_speed_threshold
        ):
            self.idle_loss_ticks += 1

        # Save queue history
        current_queues = get_current_queue_lengths(
            active_vehicles, self.wait_speed_threshold
        )
        self.queue_history.append(current_queues)
        total_q = 0
        for d in _DIRECTIONS:
            q = current_queues.get(d, 0)
            total_q += q
            self._q_dir_sum[d] += q
            if q > self._q_dir_max[d]:
                self._q_dir_max[d] = q
        self._q_total_sum += total_q
        self._q_total_sumsq += total_q * total_q
        if total_q > 0:
            self._q_nonzero_count += 1
            self._q_nonzero_sum += total_q

        # Congestion Recovery: increment recovery time if total queue length across all approaches > 5
        if sum(current_queues.values()) > 5:
            self.congestion_recovery_time += self.time_step

        # TTC: computed every tick regardless of geometry (needs only
        # vehicle kinematics). See safety_conflicts.py for the candidate
        # pair filter and formula.
        for _va_id, _vb_id, ttc in find_ttc_events(
            active_vehicles, self.ttc_search_radius
        ):
            self._ttc_sample_count += 1
            if self._min_ttc is None or ttc < self._min_ttc:
                self._min_ttc = ttc
            if ttc <= self.ttc_threshold_seconds:
                self._ttc_event_count += 1

        # PET: only measurable where real conflict-point geometry exists
        # (fixed_time_signal). A None/absent conflict_manager leaves PET
        # unmeasured for this tick and this run -- see get_metrics()'s
        # petApplicable flag.
        if conflict_manager is not None:
            self._pet_applicable = True
            for pet in self._zone_tracker.update(
                current_time,
                active_vehicles,
                conflict_manager.get_all_conflict_points(),
                conflict_manager.ZONE_RADIUS,
            ):
                self._pet_sample_count += 1
                if self._min_pet is None or pet < self._min_pet:
                    self._min_pet = pet
                if pet <= self.pet_threshold_seconds:
                    self._pet_event_count += 1

    def get_metrics(
        self,
        current_time: float,
        active_vehicles: List[Vehicle],
        exited_vehicles: List[Vehicle],
        total_spawned: int,
        collision_count: int = 0,
    ) -> Dict[str, Any]:
        """Calculates and aggregates the complete metrics snapshot.

        ``collision_count`` is the caller-supplied running total from
        ``VehiclePool.collision_count`` (see pool.py's debounced
        ``_collision_audit``) — this collector has no direct reference to
        the pool, so it is passed in rather than read internally. Defaults
        to 0 so existing callers that don't pass it (e.g. internal
        study/validation tooling) still get a well-defined, honest value
        rather than a missing key.
        """
        # Filter exited vehicles that completed their journey post-warmup
        post_warmup_exited = [
            v
            for v in exited_vehicles
            if (v.exit_time is not None and v.exit_time >= self.warmup_time)
            or (v.exit_time is None and v.spawn_time >= self.warmup_time)
        ]

        # V_spawned for criticalSaturationVolume (metric contract
        # §4.2: "total vehicles spawned (post-warmup)") — distinct from
        # totalVehiclesSpawned below, which is the all-time spawner count
        # and has no documented warmup exclusion. Exited vehicles are never
        # evicted from the pool (see VehiclePool), so active+exited here is
        # every vehicle spawned so far, letting this be derived directly
        # from spawn_time rather than requiring separate tick-level
        # tracking.
        post_warmup_spawned_count = sum(
            1
            for v in itertools.chain(active_vehicles, exited_vehicles)
            if getattr(v, "spawn_time", 0.0) >= self.warmup_time
        )

        # Calculate current queue lengths
        curr_queues = get_current_queue_lengths(
            active_vehicles, self.wait_speed_threshold
        )

        # Compute max/time-averaged queue length per the metric contract
        # (docs/architecture/07-metric-contract.md §2.3): per-direction
        # time-average/maximum first, then averageQueueLength = mean of the
        # 4 per-direction averages and maxQueueLength = max over all
        # directions and ticks. (activeAverageQueueLength/queueStdDev remain
        # based on the intersection-wide total queue per tick — they are
        # undocumented, separate derived stats and are left unchanged.)
        n_q = len(self.queue_history)
        qsi = 0.0
        if n_q:
            per_direction_avg = {d: self._q_dir_sum[d] / n_q for d in _DIRECTIONS}
            avg_q = round(sum(per_direction_avg.values()) / len(_DIRECTIONS), 2)
            max_q = max(self._q_dir_max.values())

            active_avg_q = (
                round(self._q_nonzero_sum / self._q_nonzero_count, 2)
                if self._q_nonzero_count
                else 0.0
            )
            if n_q > 1:
                # Sample variance from exact integer sums:
                # (n*sum(x^2) - (sum x)^2) / (n*(n-1)).
                var_numerator = n_q * self._q_total_sumsq - self._q_total_sum**2
                var_q = var_numerator / (n_q * (n_q - 1))
                sd_raw = math.sqrt(max(0.0, var_q))
                sd_q = round(sd_raw, 2)
                # Queue Stability Index, as calculate_queue_stability_index.
                mean_total = self._q_total_sum / n_q
                if mean_total != 0:
                    qsi = float(round(sd_raw / mean_total, 3))
            else:
                sd_q = 0.0
        else:
            max_q = 0
            avg_q = 0.0
            active_avg_q = 0.0
            sd_q = 0.0

        # Compute control delay distribution (actual travel time minus free-flow time)
        delays: List[float] = []
        for v in post_warmup_exited:
            spawn_t = getattr(v, "spawn_time", 0.0)
            exit_t = getattr(v, "exit_time", None)
            if exit_t is not None and exit_t > spawn_t:
                effective_spawn_t = max(spawn_t, self.warmup_time)
                actual_travel_time = max(0.0, exit_t - effective_spawn_t)
                total_duration = exit_t - spawn_t
                if getattr(v, "route", None):
                    route_len = sum(
                        lane.length for lane in v.route if hasattr(lane, "length")
                    )
                    free_flow_time = route_len / max(
                        getattr(v, "desired_speed", 15.0), 1.0
                    )
                    # If spawned during warmup, scale free-flow time to post-warmup duration fraction
                    if spawn_t < self.warmup_time and total_duration > 0:
                        free_flow_time *= actual_travel_time / total_duration
                else:
                    free_flow_time = 0.0
                delays.append(max(0.0, actual_travel_time - free_flow_time))
            else:
                delays.append(getattr(v, "wait_time", 0.0))

        if delays:
            avg_delay = round(sum(delays) / len(delays), 2)
            sorted_d = sorted(delays)
            n_d = len(sorted_d)
            med_delay = round(
                sorted_d[n_d // 2]
                if n_d % 2 == 1
                else (sorted_d[n_d // 2 - 1] + sorted_d[n_d // 2]) / 2.0,
                2,
            )
            min_delay = round(sorted_d[0], 2)
            max_delay = round(sorted_d[-1], 2)
            k_d = (n_d - 1) * 0.95
            f_d = math.floor(k_d)
            c_d = math.ceil(k_d)
            p95_delay = round(
                sorted_d[int(f_d)]
                + (sorted_d[int(c_d)] - sorted_d[int(f_d)]) * (k_d - f_d),
                2,
            )
            if n_d > 1:
                var_d = sum((x - avg_delay) ** 2 for x in delays) / (n_d - 1)
                sd_delay = round(math.sqrt(var_d), 2)
            else:
                sd_delay = 0.0
        else:
            avg_delay = round(calculate_average_wait_time(post_warmup_exited), 2)
            med_delay = 0.0
            min_delay = 0.0
            max_delay = 0.0
            p95_delay = 0.0
            sd_delay = 0.0

        # average_wait_time / averageStopsPerVehicle / totalStops: subtract
        # each vehicle's warmup-boundary baseline (captured in update()) so
        # a vehicle that was already active when warmup ended doesn't have
        # its pre-warmup wait time / stops counted here — mirrors how
        # avg_delay above clips via effective_spawn_t. Vehicles that
        # spawned after warmup have no baseline entry (default 0), so
        # their full wait_time/stop_count counts as-is.
        #
        # totalStops previously subtracted a single scalar
        # (stops of vehicles that had *already exited* during warmup) from
        # the sum of stops of `post_warmup_exited` vehicles — a set that,
        # by construction, never includes those already-exited vehicles.
        # That scalar had no relationship to the quantity it was subtracted
        # from. Using the same per-vehicle baseline clip as
        # averageStopsPerVehicle makes totalStops == sum(clipped_stops),
        # i.e. consistent with avg_stops_per_vehicle * len(post_warmup_exited).
        clipped_waits: List[float] = []
        clipped_stops: List[int] = []
        for v in post_warmup_exited:
            baseline_wait = self._warmup_baseline_wait.get(v.vehicle_id, 0.0)
            baseline_stops = self._warmup_baseline_stops.get(v.vehicle_id, 0)
            clipped_waits.append(max(0.0, v.wait_time - baseline_wait))
            clipped_stops.append(max(0, v.stop_count - baseline_stops))

        avg_wait_time = (
            round(sum(clipped_waits) / len(clipped_waits), 2) if clipped_waits else 0.0
        )
        avg_stops_per_vehicle = (
            round(sum(clipped_stops) / len(clipped_stops), 2) if clipped_stops else 0.0
        )
        total_stops_exited = sum(clipped_stops)

        # Idle opportunity loss
        idle_loss = 0.0
        if self.total_ticks_post_warmup > 0:
            idle_loss = self.idle_loss_ticks / self.total_ticks_post_warmup

        # Extract active lane lengths for QSI calculation
        lane_lengths = {}
        for v in active_vehicles:
            if v.lane:
                lane_lengths[v.lane.lane_id] = v.lane.length

        throughput_val = calculate_throughput(post_warmup_exited)
        throughput_rate_val = calculate_throughput_rate(
            post_warmup_exited, current_time, warmup_time=self.warmup_time
        )

        # Time-averaged Speed Variance Index: SVI = (1/T) * sum(CV(t)) over
        # post-warmup ticks with >=2 active vehicles (see update() above).
        speed_variance_index = (
            round(sum(self.speed_cv_history) / len(self.speed_cv_history), 3)
            if self.speed_cv_history
            else 0.0
        )

        travel_time_reliability, travel_time_sample_size = (
            calculate_travel_time_reliability(post_warmup_exited)
        )

        base_metrics = {
            "averageWaitTime": avg_wait_time,
            "averageDelay": avg_delay,
            "medianDelay": med_delay,
            "minDelay": min_delay,
            "maxDelay": max_delay,
            "p95Delay": p95_delay,
            "delayStdDev": sd_delay,
            "throughput": throughput_val,
            "throughputRate": throughput_rate_val,
            "currentQueueLengths": curr_queues,
            "maxQueueLength": max_q,
            "averageQueueLength": avg_q,
            "activeAverageQueueLength": active_avg_q,
            "queueStdDev": sd_q,
            "totalStops": total_stops_exited,
            "averageStopsPerVehicle": avg_stops_per_vehicle,
            "speedVarianceIndex": speed_variance_index,
            "travelTimeReliability": travel_time_reliability,
            "travelTimeReliabilityLowSampleSize": travel_time_sample_size
            < MIN_RELIABLE_SAMPLE_SIZE,
            "idleOpportunityLoss": idle_loss,
            "directionalFairnessIndex": calculate_directional_fairness(
                post_warmup_exited, self._warmup_baseline_wait
            ),
            "activeVehicleCount": len(active_vehicles),
            "totalVehiclesSpawned": total_spawned,
            # The generation cap and whether it was hit. When reached, no
            # further vehicles were offered, so demand after that moment was
            # truncated and totalVehiclesSpawned is not the offered demand.
            "vehicleLimit": self.vehicle_limit,
            "vehicleLimitReached": total_spawned >= self.vehicle_limit,
            "averageTravelSpeed": calculate_average_travel_speed(active_vehicles),
            "queueStabilityIndex": qsi,
            "congestionRecoveryTime": round(self.congestion_recovery_time, 2),
            "spaceFootprintConsumed": calculate_space_footprint_consumed(self.config),
            "intersectionUtilization": round(
                (self.service_ticks / self.demand_ticks * 100)
                if self.demand_ticks > 0
                else 0.0,
                1,
            ),
            "criticalSaturationVolume": calculate_critical_saturation_volume(
                self.config,
                throughput_val,
                throughput_rate_val,
                post_warmup_spawned_count,
            ),
            "collisionCount": collision_count,
            # Surrogate safety metrics (measurement-only; see
            # metrics/definitions/safety_conflicts.py). Thresholds are
            # commonly-cited literature defaults, not values this project
            # has validated -- event counts below are exploratory
            # measurements, not a validated safety comparison between
            # geometries. min*=None means zero observations were made
            # (never a synonym for "zero risk").
            "minTTC": self._min_ttc,
            "ttcEventCount": self._ttc_event_count,
            "ttcSampleCount": self._ttc_sample_count,
            "ttcThresholdSeconds": self.ttc_threshold_seconds,
            "minPET": self._min_pet,
            "petEventCount": self._pet_event_count,
            "petSampleCount": self._pet_sample_count,
            "petThresholdSeconds": self.pet_threshold_seconds,
            # False for roundabout geometry (no validated conflict-area
            # geometry exists there yet -- see module docstring): PET
            # fields above are "not measured" on those runs, not "no
            # conflicts found".
            "petApplicable": self._pet_applicable,
        }
        base_metrics["masterEfficiencyScore"] = calculate_master_efficiency_score(
            base_metrics
        )
        return base_metrics
