import json
import math
import random
from typing import Any, Dict, List, Optional

from src.core.limits import demand_vehicle_limit
from src.snapshot.dual_orchestrator import DualSimulationOrchestrator
from src.study.calibration import calibration_status

# Confidence levels the study accepts. The significance threshold is always
# alpha = 1 - confidence, so a confidence interval and the significance flag
# reported next to it are for the same level.
SUPPORTED_CONFIDENCE_LEVELS = (0.90, 0.95, 0.99)
DEFAULT_CONFIDENCE_LEVEL = 0.95


def _t_critical(degrees_of_freedom: float, confidence: float) -> float:
    """Two-sided Student-t critical value: the t with P(|T| > t) = 1 - confidence.

    Found by bisection on the two-tailed p-value below, so the interval
    multiplier and the significance test are computed from the same
    t-distribution. Deterministic (fixed iteration count).
    """
    if degrees_of_freedom <= 0:
        return 0.0
    target = 1.0 - confidence
    lo, hi = 0.0, 1000.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if _student_t_two_tailed_p_value(mid, degrees_of_freedom) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _calculate_stats(
    values: List[float], confidence: float = DEFAULT_CONFIDENCE_LEVEL
) -> Dict[str, float]:
    """Mean, sample standard deviation, min, max and a Student-t confidence
    interval for the mean.

    Confidence interval: ``mean +/- t * s / sqrt(n)`` with ``t`` the two-sided
    Student-t critical value at ``confidence`` and ``n - 1`` degrees of
    freedom. The t-distribution (not the normal 1.96) is used because the
    studies run 3-10 seeds: at n = 5 the 95 % multiplier is 2.776, so a
    normal-based interval would be about 29 % too narrow. It is the same
    distribution the Welch p-value in ``_compare_groups`` uses, so an interval
    and a significance flag at the same level agree in kind.

    ``ci`` is the half-width at the requested confidence; ``ci95`` is always
    the 95 % half-width (kept as the stable key reports and exports read).
    A single value has no spread estimate: the half-widths are 0.0 and
    ``ciDegreesOfFreedom`` is 0 (no interval).
    """
    if not values:
        return {
            "mean": 0.0,
            "std": 0.0,
            "min": 0.0,
            "max": 0.0,
            "ci95": 0.0,
            "ci": 0.0,
            "ciConfidence": confidence,
            "ciDegreesOfFreedom": 0,
            "ciCriticalValue": 0.0,
        }

    n = len(values)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1) if n > 1 else 0.0
    std = math.sqrt(variance)
    se = std / math.sqrt(n) if n > 1 else 0.0
    df = n - 1
    t_at_level = _t_critical(df, confidence) if n > 1 else 0.0
    t_95 = _t_critical(df, 0.95) if n > 1 else 0.0

    return {
        "mean": round(mean, 2),
        "std": round(std, 2),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "ci95": round(t_95 * se, 2),
        "ci": round(t_at_level * se, 2),
        "ciConfidence": confidence,
        "ciDegreesOfFreedom": df,
        "ciCriticalValue": round(t_at_level, 4),
    }


def _log_beta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def _betacf(a: float, b: float, x: float) -> float:
    """Continued-fraction evaluation used by the regularized incomplete beta
    function (the standard algorithm; see e.g. Numerical Recipes §6.4)."""
    max_iterations = 200
    eps = 3e-12
    fpmin = 1e-300

    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d

    for m in range(1, max_iterations + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c

        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta

        if abs(delta - 1.0) < eps:
            break

    return h


def _regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    """I_x(a, b): the regularized incomplete beta function, restricted to
    the domain this module needs it for (0 <= x <= 1, a, b > 0)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0

    log_front = -_log_beta(a, b) + a * math.log(x) + b * math.log(1.0 - x)
    front = math.exp(log_front)

    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def _student_t_two_tailed_p_value(t_stat: float, degrees_of_freedom: float) -> float:
    """Two-tailed p-value for Student's t-distribution.

    Uses the standard identity P(|T| > t) = I_{df/(df+t^2)}(df/2, 1/2)
    (Abramowitz & Stegun 26.7.5), evaluated with the regularized incomplete
    beta function above -- a textbook closed form, not new statistical
    machinery. This lets small-sample comparisons (this project's Monte
    Carlo studies commonly run 5 seeds per condition) use the correct
    fatter-tailed distribution instead of a normal-distribution
    approximation that understates the p-value at low n.
    """
    if degrees_of_freedom <= 0:
        return 1.0
    x = degrees_of_freedom / (degrees_of_freedom + t_stat * t_stat)
    return _regularized_incomplete_beta(degrees_of_freedom / 2.0, 0.5, x)


def _compare_groups(
    a: List[float], b: List[float], alpha: float = 0.05
) -> Dict[str, Any]:
    """Computes Cohen's d and a Welch's t-test significance flag (default
    alpha = 0.05; the studies pass 1 - the requested confidence level).

    The test is unpaired even though both controls run on the same seeds; it
    is the conservative choice and is what the reported p-values and
    degrees of freedom mean.

    Historically this used a normal-distribution (z) approximation, which is
    only valid for large n per group. This project's default seed count is
    5 (see run_statistical_validation's num_seeds default), so the
    small-sample-correct approach is used instead: Student's t-distribution
    with Welch-Satterthwaite degrees of freedom, which has fatter tails than
    the normal approximation and therefore does not understate p-values at
    low n. At large n the two converge, so this does not change behaviour
    for studies that already run with many seeds.
    """
    n_a, n_b = len(a), len(b)
    if n_a < 2 or n_b < 2:
        return {"cohensD": 0.0, "pValue": None, "significant": False}

    mean_a = sum(a) / n_a
    mean_b = sum(b) / n_b
    var_a = sum((x - mean_a) ** 2 for x in a) / (n_a - 1)
    var_b = sum((x - mean_b) ** 2 for x in b) / (n_b - 1)

    pooled_std = math.sqrt((var_a + var_b) / 2.0)
    cohens_d = (mean_a - mean_b) / pooled_std if pooled_std > 0 else 0.0

    se_sq_a = var_a / n_a
    se_sq_b = var_b / n_b
    se = math.sqrt(se_sq_a + se_sq_b)
    if se == 0:
        return {"cohensD": round(cohens_d, 3), "pValue": 1.0, "significant": False}
    t_stat = abs(mean_a - mean_b) / se

    # Welch-Satterthwaite degrees of freedom.
    denom = 0.0
    if n_a > 1:
        denom += (se_sq_a**2) / (n_a - 1)
    if n_b > 1:
        denom += (se_sq_b**2) / (n_b - 1)
    degrees_of_freedom = (
        ((se_sq_a + se_sq_b) ** 2) / denom if denom > 0 else float(n_a + n_b - 2)
    )

    p_value = _student_t_two_tailed_p_value(t_stat, degrees_of_freedom)
    significant = p_value < alpha

    return {
        "cohensD": round(cohens_d, 3),
        "pValue": round(p_value, 4),
        "significant": significant,
        "degreesOfFreedom": round(degrees_of_freedom, 2),
    }


def run_statistical_validation(
    config: Optional[Dict[str, Any]] = None,
    num_seeds: int = 5,
    duration: float = 30.0,
    time_step: float = 0.1,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
) -> Dict[str, Any]:
    """
    Executes a multi-seed Monte Carlo experiment across N randomized seeds to compute
    robust confidence intervals and statistical repeatability for both Signal and Roundabout.
    """
    base_config = config or {
        "simulation": {"timeStep": time_step, "duration": duration, "warmupTime": 5.0},
        "roads": {
            "approachLength": 200.0,
            "laneWidth": 3.5,
            # One lane per approach: the calibrated comparison
            # (study/calibration.py).
            "lanesPerApproach": {"north": 1, "south": 1, "east": 1, "west": 1},
        },
        "traffic": {"arrivalRate": 0.35, "arrivalDistribution": "poisson"},
        "vehicleGeneration": {
            "stopSpeedThreshold": 0.1,
            "waitSpeedThreshold": 0.5,
            "maxAcceleration": 3.0,
            "comfortDeceleration": 3.5,
            "desiredSpeed": {"min": 18.0, "max": 25.0},
        },
    }

    if confidence_level not in SUPPORTED_CONFIDENCE_LEVELS:
        raise ValueError(
            f"confidence_level must be one of {SUPPORTED_CONFIDENCE_LEVELS}"
        )
    alpha = round(1.0 - confidence_level, 2)

    # Fresh random seeds each call (recorded in the result, not user-settable).
    seeds = [random.randint(1000, 999999) for _ in range(num_seeds)]
    vehicle_limit_seeds: List[int] = []

    sig_delays: List[float] = []
    round_delays: List[float] = []
    sig_throughputs: List[float] = []
    round_throughputs: List[float] = []
    sig_queues: List[float] = []
    round_queues: List[float] = []

    seed_runs: List[Dict[str, Any]] = []

    for seed in seeds:
        run_cfg = json.loads(json.dumps(base_config))
        run_cfg.setdefault("simulation", {})
        run_cfg["simulation"]["randomSeed"] = seed
        # As in the volume sweep: the validated request duration is the one
        # the engines run, and ticks are counted on their own clock.
        run_cfg["simulation"]["duration"] = duration
        # Size the vehicle limit to the scenario (unless set) so the default
        # cap cannot silently truncate the demand being repeated.
        run_traffic = run_cfg.setdefault("traffic", {})
        run_traffic.setdefault(
            "totalVehicles",
            demand_vehicle_limit(float(run_traffic.get("arrivalRate", 0.5)), duration),
        )

        orchestrator = DualSimulationOrchestrator(run_cfg)
        steps = orchestrator.clock_signal.ticks_for_duration(duration)

        for _ in range(steps):
            orchestrator.engine_signal.step()
            orchestrator.engine_roundabout.step()

        elapsed_sig = orchestrator.clock_signal.get_elapsed_time()
        m_sig = orchestrator.collector_signal.get_metrics(
            elapsed_sig,
            orchestrator.engine_signal.pool.active_vehicles,
            orchestrator.engine_signal.pool.exited_vehicles,
            orchestrator.engine_signal.spawner.spawned_count
            if orchestrator.engine_signal.spawner
            else 0,
            orchestrator.engine_signal.pool.collision_count,
        )

        elapsed_round = orchestrator.clock_roundabout.get_elapsed_time()
        m_round = orchestrator.collector_roundabout.get_metrics(
            elapsed_round,
            orchestrator.engine_roundabout.pool.active_vehicles,
            orchestrator.engine_roundabout.pool.exited_vehicles,
            orchestrator.engine_roundabout.spawner.spawned_count
            if orchestrator.engine_roundabout.spawner
            else 0,
            orchestrator.engine_roundabout.pool.collision_count,
        )

        d_sig = m_sig.get("averageDelay", m_sig.get("averageWaitTime", 0.0))
        d_round = m_round.get("averageDelay", m_round.get("averageWaitTime", 0.0))
        tp_sig = m_sig.get("throughput", 0.0)
        tp_round = m_round.get("throughput", 0.0)
        q_sig = m_sig.get("averageQueueLength", 0.0)
        q_round = m_round.get("averageQueueLength", 0.0)

        if m_sig.get("vehicleLimitReached") or m_round.get("vehicleLimitReached"):
            vehicle_limit_seeds.append(seed)

        sig_delays.append(d_sig)
        round_delays.append(d_round)
        sig_throughputs.append(tp_sig)
        round_throughputs.append(tp_round)
        sig_queues.append(q_sig)
        round_queues.append(q_round)

        seed_runs.append(
            {
                "seed": seed,
                "signal": {
                    "delay": round(d_sig, 2),
                    "throughput": round(tp_sig, 1),
                    "queue": round(q_sig, 1),
                },
                "roundabout": {
                    "delay": round(d_round, 2),
                    "throughput": round(tp_round, 1),
                    "queue": round(q_round, 1),
                },
            }
        )

    return {
        "numSeeds": num_seeds,
        "seeds": seeds,
        "duration": duration,
        "confidenceLevel": confidence_level,
        "alpha": alpha,
        "method": {
            "confidenceInterval": "mean +/- t(n-1) * s / sqrt(n), two-sided Student-t",
            "significanceTest": "Welch two-sample t-test (unpaired), two-sided",
            "effectSize": "Cohen's d, pooled SD; positive = signal higher",
            "note": (
                "Three metrics are tested separately with no multiple-"
                "comparison correction; with few seeds a non-significant "
                "result means the study cannot distinguish the controls, "
                "not that they are equal."
            ),
        },
        "calibration": calibration_status(base_config),
        # Seeds whose run hit the vehicle-generation cap: their demand was
        # truncated, so those seeds are not full-demand samples.
        "vehicleLimitReachedSeeds": vehicle_limit_seeds,
        "signal": {
            "delay": _calculate_stats(sig_delays, confidence_level),
            "throughput": _calculate_stats(sig_throughputs, confidence_level),
            "queue": _calculate_stats(sig_queues, confidence_level),
        },
        "roundabout": {
            "delay": _calculate_stats(round_delays, confidence_level),
            "throughput": _calculate_stats(round_throughputs, confidence_level),
            "queue": _calculate_stats(round_queues, confidence_level),
        },
        "comparison": {
            "delay": _compare_groups(sig_delays, round_delays, alpha),
            "throughput": _compare_groups(sig_throughputs, round_throughputs, alpha),
            "queue": _compare_groups(sig_queues, round_queues, alpha),
        },
        "seedRuns": seed_runs,
        "individualRuns": seed_runs,  # backward-compat alias
    }


_GEOMETRIES = ("signal", "roundabout")

# Perpendicular signal groups: a north/south approach and an east/west approach
# must never both show green.
_NS = {"north", "south"}
_EW = {"east", "west"}


def _engine_parts(orch: DualSimulationOrchestrator, geometry: str) -> Any:
    if geometry == "signal":
        return orch.engine_signal, orch.collector_signal, orch.clock_signal
    return orch.engine_roundabout, orch.collector_roundabout, orch.clock_roundabout


def _final_metrics(orch: DualSimulationOrchestrator, geometry: str) -> Dict[str, Any]:
    engine, collector, clock = _engine_parts(orch, geometry)
    metrics: Dict[str, Any] = collector.get_metrics(
        clock.get_elapsed_time(),
        engine.pool.active_vehicles,
        engine.pool.exited_vehicles,
        engine.spawner.spawned_count if engine.spawner else 0,
        engine.pool.collision_count,
    )
    return metrics


def run_invariant_checks(
    duration: float = 20.0,
    time_step: float = 0.1,
    random_seed: int = 12345,
) -> Dict[str, Any]:
    """
    Validates core physical and kinematic invariants on BOTH geometries:
    1. Conservation of mass (spawned == active + exited), every tick, for the
       signal and the roundabout engine.
    2. Zero negative speeds (v >= 0), every tick, for both engines.
    3. Conflicting signal green exclusivity (signal only: a north/south and an
       east/west approach are never green together), every tick.
    4. Same-seed determinism: a second identical run must reproduce
       ``averageDelay`` and ``throughput`` on each geometry.

    The result reports each geometry separately (``geometries``) so a pass on
    one can never be read as a pass on both; the top-level ``valid`` /
    ``isDeterministic`` are true only when every geometry passed.
    """
    config: Dict[str, Any] = {
        "simulation": {
            "timeStep": time_step,
            "duration": duration,
            "warmupTime": 2.0,
            "randomSeed": random_seed,
        },
        "roads": {
            "approachLength": 200.0,
            "laneWidth": 3.5,
            # Two lanes, as before: the check exercises the harder geometry.
            "lanesPerApproach": {"north": 2, "south": 2, "east": 2, "west": 2},
        },
        "traffic": {"arrivalRate": 0.4, "arrivalDistribution": "poisson"},
        "vehicleGeneration": {
            "stopSpeedThreshold": 0.1,
            "waitSpeedThreshold": 0.5,
            "maxAcceleration": 3.0,
            "comfortDeceleration": 3.5,
            "desiredSpeed": {"min": 18.0, "max": 25.0},
        },
    }

    orchestrator1 = DualSimulationOrchestrator(config)
    steps = orchestrator1.clock_signal.ticks_for_duration(duration)

    violations: Dict[str, List[str]] = {
        "massConservation": [],
        "negativeSpeed": [],
        "greenExclusivity": [],
    }
    per_geometry_violations: Dict[str, List[str]] = {g: [] for g in _GEOMETRIES}

    def record(kind: str, geometry: str, message: str) -> None:
        violations[kind].append(message)
        per_geometry_violations[geometry].append(message)

    for tick in range(steps):
        orchestrator1.engine_signal.step()
        orchestrator1.engine_roundabout.step()

        for geometry in _GEOMETRIES:
            engine, _collector, _clock = _engine_parts(orchestrator1, geometry)
            spawned = engine.spawner.spawned_count if engine.spawner else 0
            active = len(engine.pool.active_vehicles)
            exited = len(engine.pool.exited_vehicles)
            if spawned != (active + exited):
                record(
                    "massConservation",
                    geometry,
                    f"Tick {tick}: {geometry} vehicle conservation violated: "
                    f"spawned({spawned}) != active({active}) + exited({exited})",
                )
            for v in engine.pool.active_vehicles:
                if v.speed < -0.01:
                    record(
                        "negativeSpeed",
                        geometry,
                        f"Tick {tick}: {geometry} vehicle {v.vehicle_id} "
                        f"negative speed ({v.speed})",
                    )

        greens = {
            sig["direction"].lower()
            for sig in orchestrator1.controller_signal.get_state().get("signals", [])
            if sig.get("color") == "green"
        }
        if greens & _NS and greens & _EW:
            record(
                "greenExclusivity",
                "signal",
                f"Tick {tick}: conflicting signal greens together: {sorted(greens)}",
            )

    # Determinism: an identical second run must reproduce each geometry.
    orchestrator2 = DualSimulationOrchestrator(config)
    for _ in range(steps):
        orchestrator2.engine_signal.step()
        orchestrator2.engine_roundabout.step()

    deterministic: Dict[str, bool] = {}
    for geometry in _GEOMETRIES:
        m1 = _final_metrics(orchestrator1, geometry)
        m2 = _final_metrics(orchestrator2, geometry)
        deterministic[geometry] = m1.get("averageDelay") == m2.get(
            "averageDelay"
        ) and m1.get("throughput") == m2.get("throughput")
        if not deterministic[geometry]:
            per_geometry_violations[geometry].append(
                f"Determinism check failed on {geometry}: identical seeds "
                "produced divergent metrics."
            )

    is_deterministic = all(deterministic.values())
    all_violations = [v for g in _GEOMETRIES for v in per_geometry_violations[g]]

    return {
        "valid": not all_violations,
        "isDeterministic": is_deterministic,
        "massConservationValid": not violations["massConservation"],
        "nonNegativeSpeedsValid": not violations["negativeSpeed"],
        "signalGreenExclusivityValid": not violations["greenExclusivity"],
        "geometries": {
            g: {
                "valid": not per_geometry_violations[g],
                "isDeterministic": deterministic[g],
                "violations": per_geometry_violations[g],
            }
            for g in _GEOMETRIES
        },
        "checked": [
            "vehicle conservation (both geometries)",
            "non-negative speeds (both geometries)",
            "conflicting signal greens (signal)",
            "same-seed reproduction of delay and throughput (both geometries)",
        ],
        "ticksTested": steps,
        "violations": all_violations,
    }
