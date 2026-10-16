"""Re-running a stored simulation run and judging whether it reproduced.

Framework-free: ``reproduce_run`` takes a decoded ``simulation_runs`` row and
returns the reproduction report; problems with the stored record raise
``ReproductionError`` (the router answers 400). Determinism here means the
key metrics agree within ``REPRO_*_TOLERANCE`` (absolute, unchanged from the
original endpoint), not bitwise equality of every value.
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, Optional

from src.controllers.factory import create_controller, derive_signals_state
from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.core.clock import Clock
from src.core.engine import SimulationEngine
from src.core.enums import SimulationStatus
from src.core.limits import MAX_SIMULATION_TICKS
from src.core.provenance import GIT_COMMIT_HASH, PYTHON_VERSION
from src.metrics.collector import MetricCollector
from src.metrics.readout import engine_metrics
from src.request_limits import MAX_STUDY_DURATION_SECONDS
from src.snapshot.dual_orchestrator import DualSimulationOrchestrator


class ReproductionError(ValueError):
    """The stored run cannot be reproduced as recorded."""


# Tolerances for the determinism check (unchanged from the original
# endpoint): absolute differences in seconds of delay and vehicles served.
REPRO_DELAY_TOLERANCE_S = 0.05
REPRO_THROUGHPUT_TOLERANCE_VEH = 0.1


def _reproduce_single(
    run_config: Dict[str, Any], time_step: float, duration: float, steps: int
) -> Dict[str, Any]:
    """Re-runs one engine headlessly for `steps` ticks; its final metrics."""
    clock = Clock(time_step=time_step)
    engine = SimulationEngine(clock, duration=duration, config=run_config)
    controller = create_controller(run_config, engine.network)
    engine.controller = controller
    collector = MetricCollector(run_config)

    def tick_callback() -> None:
        # engine.step() already calls controller.update() once per tick
        # (via engine.controller, set above) before running tick
        # callbacks — calling it again here would advance the
        # controller's phase/follow-up timing at double the rate of the
        # original run, breaking reproduction. Only read its resulting
        # state, exactly like build_tick_callback does for ordinary runs.
        #
        # conflict_manager mirrors build_tick_callback's own gating:
        # PET is only geometrically valid for fixed_time_signal (see
        # metrics/definitions/safety_conflicts.py).
        collector.update(
            clock.get_elapsed_time(),
            engine.pool.active_vehicles,
            engine.pool.exited_vehicles,
            derive_signals_state(controller),
            conflict_manager=(
                engine.conflict_manager
                if isinstance(controller, FixedTimeSignalController)
                else None
            ),
            signal_controller=(
                controller
                if isinstance(controller, FixedTimeSignalController)
                else None
            ),
        )

    engine.register_tick_callback(tick_callback)
    for _ in range(steps):
        if engine.status == SimulationStatus.COMPLETED:
            break
        engine.step()
    return dict(engine_metrics(engine, collector))


def _reproduce_dual(run_config: Dict[str, Any], steps: int) -> Dict[str, Any]:
    """Re-runs a signal-vs-roundabout comparison headlessly through the same
    DualSimulationOrchestrator the live comparison uses (one lockstep step
    per tick, as its run loop does); both sides' final metrics."""
    orch = DualSimulationOrchestrator(run_config)
    for _ in range(steps):
        if orch.engine_signal.status == SimulationStatus.COMPLETED:
            break
        orch.step()
    return {
        "signal": dict(engine_metrics(orch.engine_signal, orch.collector_signal)),
        "roundabout": dict(
            engine_metrics(orch.engine_roundabout, orch.collector_roundabout)
        ),
    }


def _compare_key_metrics(
    original: Dict[str, Any], reproduced: Dict[str, Any], prefix: str = ""
) -> tuple[list[str], list[str]]:
    """Compares delay and vehicles served; returns (compared, discrepancies).
    A metric is compared only when both sides actually have a value."""
    compared: list[str] = []
    discrepancies: list[str] = []
    orig_delay = original.get("averageDelay", original.get("averageWaitTime"))
    repro_delay = reproduced.get("averageDelay", reproduced.get("averageWaitTime"))
    if orig_delay is not None and repro_delay is not None:
        compared.append(f"{prefix}averageDelay")
        if abs(orig_delay - repro_delay) > REPRO_DELAY_TOLERANCE_S:
            discrepancies.append(
                f"{prefix}Delay mismatch: original={orig_delay}, "
                f"reproduced={repro_delay}"
            )
    orig_tp = original.get("throughput")
    repro_tp = reproduced.get("throughput")
    if orig_tp is not None and repro_tp is not None:
        compared.append(f"{prefix}throughput")
        if abs(orig_tp - repro_tp) > REPRO_THROUGHPUT_TOLERANCE_VEH:
            discrepancies.append(
                f"{prefix}Throughput mismatch: original={orig_tp}, "
                f"reproduced={repro_tp}"
            )
    return compared, discrepancies


def _reproduction_limitations(
    provenance: Optional[Dict[str, Any]], compared: list[str]
) -> list[str]:
    """Every reason a reproduction result should be read with care."""
    limitations: list[str] = []
    if provenance is None:
        limitations.append(
            "This run was saved before provenance was recorded: its code "
            "version, timing and configuration source are unknown, and it is "
            "re-run to its full duration."
        )
    elif provenance.get("configSource") != "engine":
        limitations.append(
            "The stored configuration is the dashboard's summary, not the "
            "exact engine configuration; anything it omits is re-run with "
            "backend defaults."
        )
    recorded = (provenance or {}).get("gitCommitHash")
    if recorded == "unknown" or (recorded and GIT_COMMIT_HASH == "unknown"):
        limitations.append(
            "The code version of the recording or of this server is unknown, "
            "so it cannot be confirmed that both ran the same code."
        )
    elif recorded and recorded != GIT_COMMIT_HASH:
        limitations.append(
            f"The run was recorded at commit {recorded[:12]}; this server runs "
            f"{GIT_COMMIT_HASH[:12]}. Code changes can explain differences."
        )
    if not compared:
        limitations.append(
            "The stored run has no delay or throughput values to compare "
            "against, so determinism was not assessed."
        )
    return limitations


def reproduce_run(run: Dict[str, Any]) -> Dict[str, Any]:
    """Re-executes a stored run headlessly from its stored configuration and
    seed, up to its recorded elapsed time, and compares key metrics.

    Never modifies the stored run. ``isDeterministic`` is null when there
    was nothing to compare, and ``limitations`` lists every reason a match
    (or mismatch) should be read with care, rather than claiming more than
    the stored record supports.
    """
    run_id = run.get("id")
    config = run.get("config")
    if not config or not isinstance(config, dict) or len(config) == 0:
        raise ReproductionError(
            f"Run '{run_id}' does not have a saved configuration to reproduce."
        )

    provenance = run.get("provenance")
    mode = (provenance or {}).get("runMode") or "single"
    original_metrics = run.get("summary_metrics", {})
    if mode == "dual" and not (
        isinstance(original_metrics.get("signal"), dict)
        and isinstance(original_metrics.get("roundabout"), dict)
    ):
        raise ReproductionError(
            f"Run '{run_id}' is a comparison but has no per-geometry "
            "metrics to compare against."
        )

    random_seed = run.get("random_seed", 0)
    timing = (provenance or {}).get("timing") or {}
    time_step = timing.get("timeStep") or config.get("simulation", {}).get(
        "timeStep", 0.1
    )
    duration = timing.get("duration") or run.get("duration") or run.get("elapsed", 30.0)
    elapsed = run.get("elapsed") or 0.0

    # A run saved without a live engine stores the duration and time step the
    # client sent, so they are untrusted: the re-run is synchronous, and an
    # unbounded one would hold a server worker indefinitely. The bound is the
    # ceiling every scenario and study already enforces.
    if not _positive_number(time_step) or not _positive_number(duration):
        raise ReproductionError(
            f"Run '{run_id}' has no usable time step or duration to re-run."
        )
    if (
        duration > MAX_STUDY_DURATION_SECONDS
        or duration / time_step > MAX_SIMULATION_TICKS
    ):
        raise ReproductionError(
            f"Run '{run_id}' is outside the reproducible range (duration up to "
            f"{MAX_STUDY_DURATION_SECONDS:g} s and at most "
            f"{MAX_SIMULATION_TICKS:,} time steps)."
        )

    # Runs with recorded provenance also recorded the engine's true elapsed
    # time, so a run saved part-way through is reproduced to that instant.
    # Older runs did not (replay saves stored the duration there), so they
    # keep the original full-duration behaviour.
    if provenance is not None and 0 < elapsed < duration:
        target_elapsed = elapsed
        steps = int(round(elapsed / time_step))
    else:
        target_elapsed = duration
        steps = Clock(time_step).ticks_for_duration(duration)

    # Clone config and ensure seed, timeStep, duration match
    run_config = json.loads(json.dumps(config))
    if "simulation" not in run_config:
        run_config["simulation"] = {}
    run_config["simulation"]["randomSeed"] = random_seed
    run_config["simulation"]["timeStep"] = time_step
    run_config["simulation"]["duration"] = duration

    compared: list[str] = []
    discrepancies: list[str] = []
    if mode == "dual":
        reproduced_metrics = _reproduce_dual(run_config, steps)
        for side in ("signal", "roundabout"):
            c, d = _compare_key_metrics(
                original_metrics[side], reproduced_metrics[side], f"{side}."
            )
            compared += c
            discrepancies += d
    else:
        reproduced_metrics = _reproduce_single(run_config, time_step, duration, steps)
        compared, discrepancies = _compare_key_metrics(
            original_metrics, reproduced_metrics
        )

    return {
        "runId": run_id,
        "mode": mode,
        "seed": random_seed,
        "intersectionType": run.get("intersection_type"),
        "duration": duration,
        "reproducedElapsed": round(target_elapsed, 6),
        "isDeterministic": (len(discrepancies) == 0) if compared else None,
        "comparedMetrics": compared,
        "tolerances": {
            "averageDelaySeconds": REPRO_DELAY_TOLERANCE_S,
            "throughputVehicles": REPRO_THROUGHPUT_TOLERANCE_VEH,
        },
        "originalMetrics": original_metrics,
        "reproducedMetrics": reproduced_metrics,
        "discrepancies": discrepancies,
        "limitations": _reproduction_limitations(provenance, compared),
        "recordedGitCommitHash": (provenance or {}).get("gitCommitHash"),
        # Best-effort provenance (src/core/provenance.py): "unknown"
        # rather than a failure wherever .git isn't available, e.g. the
        # production Docker image.
        "provenance": {
            "gitCommitHash": GIT_COMMIT_HASH,
            "pythonVersion": PYTHON_VERSION,
        },
    }


def _positive_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )
