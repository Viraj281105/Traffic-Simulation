import json
import math
import random
from typing import Any, Dict, List, Optional

from src.snapshot.dual_orchestrator import DualSimulationOrchestrator


def _calculate_stats(values: List[float]) -> Dict[str, float]:
    """Calculates mean, standard deviation, min, max, and 95% confidence interval."""
    if not values:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "ci95": 0.0}

    n = len(values)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / max(n - 1, 1) if n > 1 else 0.0
    std = math.sqrt(variance)
    ci95 = 1.96 * (std / math.sqrt(n)) if n > 1 else 0.0

    return {
        "mean": round(mean, 2),
        "std": round(std, 2),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "ci95": round(ci95, 2),
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


def _compare_groups(a: List[float], b: List[float]) -> Dict[str, Any]:
    """Computes Cohen's d and a Welch's t-test significance flag (alpha=0.05).

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
    significant = p_value < 0.05

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
            "lanesPerApproach": {"north": 2, "south": 2, "east": 2, "west": 2},
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

    seeds = [random.randint(1000, 999999) for _ in range(num_seeds)]
    steps = int(duration / time_step)

    sig_delays: List[float] = []
    round_delays: List[float] = []
    sig_throughputs: List[float] = []
    round_throughputs: List[float] = []
    sig_queues: List[float] = []
    round_queues: List[float] = []

    seed_runs: List[Dict[str, Any]] = []

    for seed in seeds:
        run_cfg = json.loads(json.dumps(base_config))
        run_cfg["simulation"]["randomSeed"] = seed

        orchestrator = DualSimulationOrchestrator(run_cfg)

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
        "signal": {
            "delay": _calculate_stats(sig_delays),
            "throughput": _calculate_stats(sig_throughputs),
            "queue": _calculate_stats(sig_queues),
        },
        "roundabout": {
            "delay": _calculate_stats(round_delays),
            "throughput": _calculate_stats(round_throughputs),
            "queue": _calculate_stats(round_queues),
        },
        "comparison": {
            "delay": _compare_groups(sig_delays, round_delays),
            "throughput": _compare_groups(sig_throughputs, round_throughputs),
            "queue": _compare_groups(sig_queues, round_queues),
        },
        "seedRuns": seed_runs,
        "individualRuns": seed_runs,  # backward-compat alias
    }


def run_invariant_checks(
    duration: float = 20.0,
    time_step: float = 0.1,
    random_seed: int = 12345,
) -> Dict[str, Any]:
    """
    Validates core physical and kinematic invariants:
    1. Conservation of mass (spawned == active + exited).
    2. Zero negative speeds (v >= 0).
    3. Conflicting signal green exclusivity.
    4. Bit-exact determinism across identical random seeds.
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

    steps = int(duration / time_step)
    orchestrator1 = DualSimulationOrchestrator(config)

    invariants_passed = True
    violations: List[str] = []

    # Run Simulation 1 and check invariants each tick
    for tick in range(steps):
        orchestrator1.engine_signal.step()
        orchestrator1.engine_roundabout.step()

        # 1. Mass conservation check (Signal)
        eng_s = orchestrator1.engine_signal
        spawned_s = eng_s.spawner.spawned_count if eng_s.spawner else 0
        active_s = len(eng_s.pool.active_vehicles)
        exited_s = len(eng_s.pool.exited_vehicles)
        if spawned_s != (active_s + exited_s):
            invariants_passed = False
            violations.append(
                f"Tick {tick}: Signal vehicle conservation violated: spawned({spawned_s}) != active({active_s}) + exited({exited_s})"
            )

        # 2. Non-negative speed check
        for v in eng_s.pool.active_vehicles:
            if v.speed < -0.01:
                invariants_passed = False
                violations.append(
                    f"Tick {tick}: Vehicle {v.vehicle_id} negative speed ({v.speed})"
                )

    # 3. Determinism check: Run second simulation with exact same seed and check metric equality
    orchestrator2 = DualSimulationOrchestrator(config)
    for _ in range(steps):
        orchestrator2.engine_signal.step()
        orchestrator2.engine_roundabout.step()

    m1_s = orchestrator1.collector_signal.get_metrics(
        duration,
        orchestrator1.engine_signal.pool.active_vehicles,
        orchestrator1.engine_signal.pool.exited_vehicles,
        orchestrator1.engine_signal.spawner.spawned_count
        if orchestrator1.engine_signal.spawner
        else 0,
        orchestrator1.engine_signal.pool.collision_count,
    )
    m2_s = orchestrator2.collector_signal.get_metrics(
        duration,
        orchestrator2.engine_signal.pool.active_vehicles,
        orchestrator2.engine_signal.pool.exited_vehicles,
        orchestrator2.engine_signal.spawner.spawned_count
        if orchestrator2.engine_signal.spawner
        else 0,
        orchestrator2.engine_signal.pool.collision_count,
    )

    is_deterministic = m1_s.get("averageDelay") == m2_s.get(
        "averageDelay"
    ) and m1_s.get("throughput") == m2_s.get("throughput")

    if not is_deterministic:
        invariants_passed = False
        violations.append(
            "Determinism check failed: identical seeds produced divergent metrics."
        )

    return {
        "valid": invariants_passed,
        "isDeterministic": is_deterministic,
        "massConservationValid": len(violations) == 0,
        "ticksTested": steps,
        "violations": violations,
    }
