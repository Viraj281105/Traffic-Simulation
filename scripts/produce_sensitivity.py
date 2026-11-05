"""Write ``experiments/<id>/sensitivity.json`` (urbanflow-sensitivity) from a ``sobol_lite`` run of the simulation.

    python scripts/produce_sensitivity.py --experiment-id demo \
        --input arrivalRate=0.1:0.5 --input greenTime=15:60 \
        --metric mean_delay_s --samples 16 --num-seeds 3 --duration 60 --seed 7

Cost is ``samples * (inputs + 2) * num-seeds`` simulations. Inputs are the names in
``src.study.sensitivity.PARAMETER_PATHS`` (arrivalRate is vehicles per second, greenTime seconds,
speedLimit m/s, approachLength m, lanesPerApproach a count). Each input is uniform on its range.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import produce_common as common  # noqa: E402

SENSITIVITY_FORMAT = "urbanflow-sensitivity"
# metric id -> engine metric names (tried in order), label, unit
METRICS: Dict[str, Dict[str, Any]] = {
    "mean_delay_s": {"names": ("averageDelay", "averageWaitTime"), "label": "Mean delay", "unit": "s"},
    "throughput": {"names": ("throughput",), "label": "Throughput", "unit": "veh"},
    "mean_queue": {"names": ("averageQueueLength",), "label": "Mean queue length", "unit": "veh"},
}
# Display names and units of the supported inputs.
INPUT_INFO: Dict[str, Dict[str, str]] = {
    "arrivalRate": {"label": "Arrival rate", "unit": "veh/s"},
    "greenTime": {"label": "Green time", "unit": "s"},
    "speedLimit": {"label": "Speed limit", "unit": "m/s"},
    "approachLength": {"label": "Approach length", "unit": "m"},
    "lanesPerApproach": {"label": "Lanes per approach", "unit": "lanes"},
}


def build_sensitivity_doc(metric_id: str, result: Mapping[str, Any]) -> Dict[str, Any]:
    """Wrap a ``sobol_lite`` result. Pure."""
    if metric_id not in METRICS:
        raise ValueError(f"metric must be one of {sorted(METRICS)}")
    if result.get("method") != "sobol-lite":
        raise ValueError("only a sobol-lite result can be wrapped")
    info = METRICS[metric_id]
    names = [row["input"] for row in result["ranking"]]
    return {
        "format": SENSITIVITY_FORMAT,
        "version": 1,
        "metric": {"id": metric_id, "label": info["label"], "unit": info["unit"]},
        "inputs": {n: dict(INPUT_INFO[n]) for n in names if n in INPUT_INFO},
        "result": dict(result),
    }


def parse_bounds(items: Sequence[str]) -> Dict[str, Tuple[float, float]]:
    from src.study.sensitivity import PARAMETER_PATHS

    out: Dict[str, Tuple[float, float]] = {}
    for item in items:
        name, sep, rng = item.partition("=")
        lo, sep2, hi = rng.partition(":")
        if not sep or not sep2:
            raise ValueError(f"--input must look like NAME=LOW:HIGH, got {item!r}")
        if name not in PARAMETER_PATHS:
            raise ValueError(f"unsupported input {name!r}; choose from {sorted(PARAMETER_PATHS)}")
        try:
            out[name] = (float(lo), float(hi))
        except ValueError:
            raise ValueError(f"--input range for {name!r} must be numbers") from None
    return out


def produce(
    experiment_id: str,
    bounds: Mapping[str, Tuple[float, float]],
    *,
    metric_id: str = "mean_delay_s",
    geometry: str = "signal",
    samples: int = 16,
    num_seeds: int = 3,
    duration: float = 60.0,
    seed: int = 0,
    results_dir: "Optional[Path | str]" = None,
    evaluate_many: Any = None,
) -> Path:
    """Run ``sobol_lite`` and write sensitivity.json. ``evaluate_many`` replaces the simulation (tests)."""
    from src.study.multiseed import default_study_config
    from src.study.sensitivity import simulation_evaluator, sobol_lite

    common.require_id(experiment_id, "experiment id")
    if metric_id not in METRICS:
        raise ValueError(f"metric must be one of {sorted(METRICS)}")
    path = common.locations(results_dir).experiment_file(experiment_id, "sensitivity.json")
    assert path is not None
    if evaluate_many is None:
        evaluate_many = simulation_evaluator(
            default_study_config(duration),
            geometry,
            duration,
            METRICS[metric_id]["names"],
            num_seeds,
            seed,
        )
    result = sobol_lite(evaluate_many, dict(bounds), n_samples=samples, seed=seed)
    return common.write_json_atomic(path, build_sensitivity_doc(metric_id, result))


def main(argv: "Optional[List[str]]" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--experiment-id", required=True)
    ap.add_argument("--input", action="append", default=[], required=True, metavar="NAME=LOW:HIGH")
    ap.add_argument("--metric", default="mean_delay_s", choices=sorted(METRICS))
    ap.add_argument("--geometry", default="signal", choices=("signal", "roundabout"))
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--num-seeds", type=int, default=3)
    ap.add_argument("--duration", type=float, default=60.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--results-dir", default=None)
    args = ap.parse_args(argv)
    try:
        path = produce(
            args.experiment_id,
            parse_bounds(args.input),
            metric_id=args.metric,
            geometry=args.geometry,
            samples=args.samples,
            num_seeds=args.num_seeds,
            duration=args.duration,
            seed=args.seed,
            results_dir=args.results_dir,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
