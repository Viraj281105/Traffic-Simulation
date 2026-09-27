import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from src.core.limits import demand_vehicle_limit
from src.core.provenance import build_run_provenance
from src.database.dao import (
    RunMetricsDAO,
    SimulationRunDAO,
    SweepSessionDAO,
)
from src.database.db import DB_PATH, get_db_connection, init_db  # noqa: F401
from src.snapshot.dual_orchestrator import DualSimulationOrchestrator
from src.study.calibration import calibration_status, study_warmup, sweep_rates
from src.study.tolerances import delays_are_tied, tie_tolerance

logger = logging.getLogger(__name__)

# 20%-160% of the measured 1-lane reference capacity (study/calibration.py).
DEFAULT_ARRIVAL_RATES = sweep_rates(1)

# Fewer exited vehicles than this on either side and a tier's mean delay rests
# on too few drivers to call a direction (same convention as the planning
# time index's low-sample flag, metrics/definitions/travel_time.py).
MIN_TIER_SAMPLE = 20


def find_delay_crossover(runs: List[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    """The first change of which control had the lower mean delay.

    Only tiers with a decided winner take part: a tie or an inconclusive tier
    (too few vehicles, or demand truncated by the vehicle limit) neither
    starts nor ends a change, so noise inside the tie band can never create a
    crossover. Runs are ordered by arrival rate first.

    Returns ``{"lowerRate", "upperRate"}`` -- the arrival rates of the two
    adjacent decided tiers whose winners differ -- or None. The crossover lies
    somewhere in that bracket; it is not interpolated.
    """
    decided = sorted(
        (r for r in runs if r.get("winner") in ("signal", "roundabout")),
        key=lambda r: r["arrivalRate"],
    )
    for prev, curr in zip(decided, decided[1:]):
        if prev["winner"] != curr["winner"]:
            return {"lowerRate": prev["arrivalRate"], "upperRate": curr["arrivalRate"]}
    return None


def run_volume_sweep_experiment(
    arrival_rates: Optional[List[float]] = None,
    duration: float = 60.0,
    time_step: float = 0.1,
    random_seed: int = 42,
    custom_config: Optional[Dict[str, Any]] = None,
    name: str = "Comparative Volume Sweep",
) -> Dict[str, Any]:
    """
    Executes an automated multi-volume parameter sweep comparing Fixed-Time Signals
    and Modern Roundabouts across specified vehicle arrival rates under identical seeds.
    """
    init_db()

    rates = (
        arrival_rates
        if arrival_rates and len(arrival_rates) > 0
        else DEFAULT_ARRIVAL_RATES
    )
    session_id = str(uuid.uuid4())

    base_config: Dict[str, Any] = {
        "simulation": {
            "timeStep": time_step,
            "duration": duration,
            "warmupTime": study_warmup(duration),
            "randomSeed": random_seed,
        },
        "roads": {
            "approachLength": 200.0,
            "laneWidth": 3.5,
            # One lane per approach: the calibrated comparison
            # (see study/calibration.py). Callers may override through
            # customConfig; the result then reports itself as exploratory.
            "lanesPerApproach": {
                "north": 1,
                "south": 1,
                "east": 1,
                "west": 1,
            },
        },
        "traffic": {
            "arrivalRate": 0.3,
            "arrivalDistribution": "poisson",
        },
        "vehicleGeneration": {
            "stopSpeedThreshold": 0.1,
            "waitSpeedThreshold": 0.5,
            # Acceleration, braking and desired speed are the engine defaults
            # (IDM a = 2.0, b = 3.0 m/s^2; desired speed from roads.speedLimit),
            # i.e. the same vehicles as the calibrated capacity study.
        },
    }

    if custom_config:
        # Merge custom configs
        for k, v in custom_config.items():
            if isinstance(v, dict) and k in base_config:
                base_config[k].update(v)
            else:
                base_config[k] = v

    # The request's duration is the authoritative one (it is the bounded,
    # validated field). A customConfig that also set simulation.duration used
    # to win in the engine while the loop below still counted the request's
    # duration — a shorter one completed the engine mid-loop and the next step
    # raised (HTTP 500).
    base_config["simulation"]["duration"] = duration
    runs_data: List[Dict[str, Any]] = []

    signal_delays: List[float] = []
    roundabout_delays: List[float] = []
    signal_delay_stds: List[float] = []
    roundabout_delay_stds: List[float] = []
    signal_delay_mins: List[float] = []
    roundabout_delay_mins: List[float] = []
    signal_delay_maxs: List[float] = []
    roundabout_delay_maxs: List[float] = []
    signal_throughputs: List[float] = []
    roundabout_throughputs: List[float] = []
    signal_queues: List[float] = []
    roundabout_queues: List[float] = []
    signal_queue_stds: List[float] = []
    roundabout_queue_stds: List[float] = []
    signal_queue_maxs: List[float] = []
    roundabout_queue_maxs: List[float] = []

    used_rate_labels: set[str] = set()

    with get_db_connection() as conn:
        for rate_index, rate in enumerate(rates):
            step_config = json.loads(json.dumps(base_config))
            step_config["traffic"]["arrivalRate"] = rate
            # Size the vehicle limit to this tier (unless the caller set one)
            # so the default cap cannot silently truncate high-demand tiers.
            step_config["traffic"].setdefault(
                "totalVehicles", demand_vehicle_limit(rate, duration)
            )
            step_config["simulation"]["randomSeed"] = random_seed

            orchestrator = DualSimulationOrchestrator(step_config)
            # Counted with the engines' own clock, so a configured timeStep
            # (see DualSimulationOrchestrator) runs the same simulated time.
            steps_to_run = orchestrator.clock_signal.ticks_for_duration(duration)

            # Fast headless simulation execution
            for _ in range(steps_to_run):
                orchestrator.engine_signal.step()
                orchestrator.engine_roundabout.step()

            # Collect metrics
            elapsed_sig = orchestrator.clock_signal.get_elapsed_time()
            sig_metrics = orchestrator.collector_signal.get_metrics(
                elapsed_sig,
                orchestrator.engine_signal.pool.active_vehicles,
                orchestrator.engine_signal.pool.exited_vehicles,
                orchestrator.engine_signal.spawner.spawned_count
                if orchestrator.engine_signal.spawner
                else 0,
                orchestrator.engine_signal.pool.collision_count,
            )

            elapsed_round = orchestrator.clock_roundabout.get_elapsed_time()
            round_metrics = orchestrator.collector_roundabout.get_metrics(
                elapsed_round,
                orchestrator.engine_roundabout.pool.active_vehicles,
                orchestrator.engine_roundabout.pool.exited_vehicles,
                orchestrator.engine_roundabout.spawner.spawned_count
                if orchestrator.engine_roundabout.spawner
                else 0,
                orchestrator.engine_roundabout.pool.collision_count,
            )

            sig_delay = round(
                sig_metrics.get(
                    "averageDelay", sig_metrics.get("averageWaitTime", 0.0)
                ),
                2,
            )
            round_delay = round(
                round_metrics.get(
                    "averageDelay", round_metrics.get("averageWaitTime", 0.0)
                ),
                2,
            )
            sig_delay_std = round(sig_metrics.get("delayStdDev", 0.0), 2)
            round_delay_std = round(round_metrics.get("delayStdDev", 0.0), 2)
            sig_delay_min = round(sig_metrics.get("minDelay", 0.0), 2)
            round_delay_min = round(round_metrics.get("minDelay", 0.0), 2)
            sig_delay_max = round(sig_metrics.get("maxDelay", sig_delay), 2)
            round_delay_max = round(round_metrics.get("maxDelay", round_delay), 2)
            sig_delay_med = round(sig_metrics.get("medianDelay", sig_delay), 2)
            round_delay_med = round(round_metrics.get("medianDelay", round_delay), 2)
            sig_delay_p95 = round(sig_metrics.get("p95Delay", sig_delay), 2)
            round_delay_p95 = round(round_metrics.get("p95Delay", round_delay), 2)

            sig_tp = round(sig_metrics.get("throughput", 0.0), 1)
            round_tp = round(round_metrics.get("throughput", 0.0), 1)
            sig_tp_rate = round(sig_metrics.get("throughputRate", 0.0), 2)
            round_tp_rate = round(round_metrics.get("throughputRate", 0.0), 2)

            sig_q = round(sig_metrics.get("averageQueueLength", 0.0), 1)
            round_q = round(round_metrics.get("averageQueueLength", 0.0), 1)
            sig_q_max = round(sig_metrics.get("maxQueueLength", sig_q), 1)
            round_q_max = round(round_metrics.get("maxQueueLength", round_q), 1)
            sig_q_std = round(sig_metrics.get("queueStdDev", 0.0), 2)
            round_q_std = round(round_metrics.get("queueStdDev", 0.0), 2)

            signal_delays.append(sig_delay)
            roundabout_delays.append(round_delay)
            signal_delay_stds.append(sig_delay_std)
            roundabout_delay_stds.append(round_delay_std)
            signal_delay_mins.append(sig_delay_min)
            roundabout_delay_mins.append(round_delay_min)
            signal_delay_maxs.append(sig_delay_max)
            roundabout_delay_maxs.append(round_delay_max)

            signal_throughputs.append(sig_tp)
            roundabout_throughputs.append(round_tp)
            signal_queues.append(sig_q)
            roundabout_queues.append(round_q)
            signal_queue_stds.append(sig_q_std)
            roundabout_queue_stds.append(round_q_std)
            signal_queue_maxs.append(sig_q_max)
            roundabout_queue_maxs.append(round_q_max)

            # Save to database.
            #
            # The id used to end in int(rate * 100): truncation, so 0.29 was
            # labelled "_28", and any two rates in the same hundredth (0.285
            # and 0.289, or a rate listed twice) got the same id — and
            # INSERT OR REPLACE then silently overwrote the earlier run. The
            # label is now rounded, and a clash gets the rate's position
            # appended, so every run in the sweep keeps its own row.
            rate_label = str(int(round(rate * 100)))
            if rate_label in used_rate_labels:
                rate_label = f"{rate_label}_{rate_index}"
            used_rate_labels.add(rate_label)
            sig_run_id = f"sweep_{session_id[:8]}_sig_{rate_label}"
            round_run_id = f"sweep_{session_id[:8]}_rnd_{rate_label}"

            # Each stored run carries the exact config its own engine ran
            # with (the orchestrator's per-geometry copy, including the
            # controller settings it injects), so the run can be reproduced
            # on its own. Timing is read from the engines, not the request:
            # the orchestrator's clocks step at their own fixed time step.
            sig_config = json.loads(json.dumps(orchestrator.config_signal))
            round_config = json.loads(json.dumps(orchestrator.config_roundabout))
            sig_provenance = build_run_provenance(
                config_source="engine",
                run_mode="single",
                time_step=orchestrator.clock_signal.time_step,
                duration=orchestrator.engine_signal.duration,
                warmup_time=orchestrator.collector_signal.warmup_time,
            )
            round_provenance = build_run_provenance(
                config_source="engine",
                run_mode="single",
                time_step=orchestrator.clock_roundabout.time_step,
                duration=orchestrator.engine_roundabout.duration,
                warmup_time=orchestrator.collector_roundabout.warmup_time,
            )

            SimulationRunDAO.save(
                conn,
                sig_run_id,
                "completed",
                elapsed_sig,
                intersection_type="fixed_time_signal",
                random_seed=random_seed,
                arrival_rate=rate,
                duration=duration,
                batch_id=session_id,
                config=sig_config,
                summary_metrics=sig_metrics,
                provenance=sig_provenance,
            )
            RunMetricsDAO.save(conn, sig_run_id, steps_to_run, sig_metrics)

            SimulationRunDAO.save(
                conn,
                round_run_id,
                "completed",
                elapsed_round,
                intersection_type="roundabout",
                random_seed=random_seed,
                arrival_rate=rate,
                duration=duration,
                batch_id=session_id,
                config=round_config,
                summary_metrics=round_metrics,
                provenance=round_provenance,
            )
            RunMetricsDAO.save(conn, round_run_id, steps_to_run, round_metrics)

            # Symmetric percentage deltas (descriptive; positive = roundabout higher)
            delay_delta_pct = (
                round(((round_delay - sig_delay) / max(sig_delay, 0.01)) * 100, 1)
                if sig_delay > 0
                else 0.0
            )
            tp_delta_pct = (
                round(((round_tp - sig_tp) / max(sig_tp, 1.0)) * 100, 1)
                if sig_tp > 0
                else 0.0
            )
            queue_delta_pct = (
                round(((round_q - sig_q) / max(sig_q, 0.1)) * 100, 1)
                if sig_q > 0
                else 0.0
            )

            # Same "about the same" rule everywhere (study/tolerances.py).
            # A tier is inconclusive, rather than won, when either side had
            # too few exited vehicles or generation hit the vehicle limit
            # (later demand was cut off, and not necessarily identically).
            limit_reached = bool(
                sig_metrics.get("vehicleLimitReached")
                or round_metrics.get("vehicleLimitReached")
            )
            low_sample = min(sig_tp, round_tp) < MIN_TIER_SAMPLE
            inconclusive_reason: Optional[str] = None
            if limit_reached:
                inconclusive_reason = "vehicle_limit_reached"
            elif low_sample:
                inconclusive_reason = "low_sample"

            if inconclusive_reason is not None:
                winner = "inconclusive"
            elif delays_are_tied(round_delay, sig_delay):
                winner = "tie"
            elif round_delay < sig_delay:
                winner = "roundabout"
            else:
                winner = "signal"

            runs_data.append(
                {
                    "arrivalRate": rate,
                    # arrivalRate is the whole junction's rate (the
                    # spawner splits it across the four approaches), so
                    # offered demand is rate x 3600 -- the same convention as
                    # docs/reports/comparative_report.md. This previously
                    # multiplied by 4 again, overstating demand four-fold.
                    "hourlyVolumeVehPerHour": int(round(rate * 3600)),
                    "signal": {
                        "runId": sig_run_id,
                        "delay": sig_delay,
                        "delayMedian": sig_delay_med,
                        "delayStdDev": sig_delay_std,
                        "delayMin": sig_delay_min,
                        "delayMax": sig_delay_max,
                        "delayP95": sig_delay_p95,
                        "throughput": sig_tp,
                        "throughputRate": sig_tp_rate,
                        "queue": sig_q,
                        "queueMax": sig_q_max,
                        "queueStdDev": sig_q_std,
                        "metrics": sig_metrics,
                    },
                    "roundabout": {
                        "runId": round_run_id,
                        "delay": round_delay,
                        "delayMedian": round_delay_med,
                        "delayStdDev": round_delay_std,
                        "delayMin": round_delay_min,
                        "delayMax": round_delay_max,
                        "delayP95": round_delay_p95,
                        "throughput": round_tp,
                        "throughputRate": round_tp_rate,
                        "queue": round_q,
                        "queueMax": round_q_max,
                        "queueStdDev": round_q_std,
                        "metrics": round_metrics,
                    },
                    "winner": winner,
                    "inconclusiveReason": inconclusive_reason,
                    "vehicleLimitReached": limit_reached,
                    "delayDeltaPercent": delay_delta_pct,
                    "throughputDeltaPercent": tp_delta_pct,
                    "queueDeltaPercent": queue_delta_pct,
                }
            )

        crossover = find_delay_crossover(runs_data)
        summary_curves = {
            "rates": rates,
            "volumesVehPerHour": [int(round(r * 3600)) for r in rates],
            "signal": {
                "delays": signal_delays,
                "delayStds": signal_delay_stds,
                "delayMins": signal_delay_mins,
                "delayMaxs": signal_delay_maxs,
                "throughputs": signal_throughputs,
                "queues": signal_queues,
                "queueStds": signal_queue_stds,
                "queueMaxs": signal_queue_maxs,
            },
            "roundabout": {
                "delays": roundabout_delays,
                "delayStds": roundabout_delay_stds,
                "delayMins": roundabout_delay_mins,
                "delayMaxs": roundabout_delay_maxs,
                "throughputs": roundabout_throughputs,
                "queues": roundabout_queues,
                "queueStds": roundabout_queue_stds,
                "queueMaxs": roundabout_queue_maxs,
            },
            "crossoverArrivalRate": crossover["upperRate"] if crossover else None,
            "crossoverHourlyVolume": int(round(crossover["upperRate"] * 3600))
            if crossover
            else None,
            # The change lies between these two decided tiers (not
            # interpolated): the last tier before it and the first after.
            "crossoverBracketArrivalRates": (
                [crossover["lowerRate"], crossover["upperRate"]] if crossover else None
            ),
        }

        sweep_result = {
            "sessionId": session_id,
            "name": name,
            "duration": duration,
            "randomSeed": random_seed,
            "seedsPerTier": 1,
            "tieTolerance": tie_tolerance(),
            "calibration": calibration_status(base_config),
            "curves": summary_curves,
            "runs": runs_data,
        }

        # Persist session in DB
        SweepSessionDAO.save(conn, session_id, name, base_config, sweep_result)
        conn.commit()

    return sweep_result
