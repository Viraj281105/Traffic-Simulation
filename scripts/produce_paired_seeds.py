"""Write ``experiments/<id>/paired.json`` (urbanflow-paired-seeds) from a real multi-seed run per alternative.

Each alternative is one geometry plus optional config overrides. All alternatives run over the same seeds
(the same ``--base-seed``), so values pair by seed::

    python scripts/produce_paired_seeds.py --experiment-id demo \
        --alt fixed=signal --alt adaptive=signal \
        --override 'adaptive={"controller":{"signalControl":"adaptive"}}' \
        --baseline fixed --num-seeds 10 --duration 120 --base-seed 42 --save-runs

``--label ID=TEXT`` names an alternative. ``--save-runs`` also stores each alternative's per-seed rows in the
Parquet run store as run ``<experiment id>-<alternative id>``; the baseline's run is named as
``metricsRunId``. Those rows are per-seed summaries, not per-trip rows, so the run metrics screen shows
no trip values for them (null, not zero).
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import produce_common as common  # noqa: E402

PAIRED_FORMAT = "urbanflow-paired-seeds"
# metric id -> multi-seed result key, label, unit, direction
METRICS: Dict[str, Dict[str, Any]] = {
    "mean_delay_s": {"key": "delay", "label": "Mean delay", "unit": "s", "lowerIsBetter": True},
    "throughput": {"key": "throughput", "label": "Throughput", "unit": "veh", "lowerIsBetter": False},
    "mean_queue": {"key": "queue", "label": "Mean queue length", "unit": "veh", "lowerIsBetter": True},
}


def deep_merge(base: Mapping[str, Any], over: Mapping[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(dict(base))
    for key, value in over.items():
        if isinstance(value, Mapping) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def build_paired_doc(
    runs: Mapping[str, Mapping[str, Any]],
    *,
    baseline: str,
    labels: Optional[Mapping[str, str]] = None,
    primary_metric: str = "mean_delay_s",
    metrics_run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """The paired-seeds document from ``{alternative id: run_multi_seed result}``.

    Pure: no simulation, no file. Every alternative must have the same seeds in the same order."""
    if len(runs) < 2:
        raise ValueError("at least two alternatives are needed to pair")
    if baseline not in runs:
        raise ValueError(f"baseline {baseline!r} is not one of {sorted(runs)}")
    if primary_metric not in METRICS:
        raise ValueError(f"primary metric must be one of {sorted(METRICS)}")
    if len({tuple(r["seeds"]) for r in runs.values()}) != 1:
        raise ValueError("alternatives must be run over the same seeds")
    labels = labels or {}
    alternatives: Dict[str, Any] = {}
    for alt, result in runs.items():
        common.require_id(alt, "alternative id")
        rows = result["seedRuns"]
        alternatives[alt] = {
            "label": labels.get(alt, alt),
            "seeds": [int(s) for s in result["seeds"]],
            "values": {
                mid: [float(row[info["key"]]) for row in rows] for mid, info in METRICS.items()
            },
        }
    doc: Dict[str, Any] = {
        "format": PAIRED_FORMAT,
        "version": 1,
        "primaryMetric": primary_metric,
        "baseline": baseline,
        "metrics": {
            mid: {k: info[k] for k in ("label", "unit", "lowerIsBetter")}
            for mid, info in METRICS.items()
        },
        "alternatives": alternatives,
    }
    if metrics_run_id is not None:
        doc["metricsRunId"] = common.require_id(metrics_run_id, "metricsRunId")
    return doc


def save_alternative_run(
    store: Any, experiment_id: str, alt: str, label: str, result: Mapping[str, Any]
) -> str:
    """Store one alternative's per-seed rows and manifest; returns the run id."""
    manifest = dict(result["manifest"])
    manifest["label"] = label
    run_id = common.require_id(f"{experiment_id}-{alt}", "run id")
    records = [dict(row) for row in result["seedRuns"]]
    return str(store.save_run(manifest, records, run_id=run_id, overwrite=True))


def produce(
    experiment_id: str,
    alternatives: Mapping[str, Mapping[str, Any]],
    *,
    baseline: str,
    num_seeds: int,
    duration: float,
    base_seed: int,
    labels: Optional[Mapping[str, str]] = None,
    primary_metric: str = "mean_delay_s",
    results_dir: "Optional[Path | str]" = None,
    save_runs: bool = False,
) -> Path:
    """Run every alternative over the shared seeds and write paired.json. Returns its path.

    ``alternatives`` is ``{id: {"geometry": "signal", "overrides": {...}}}``."""
    from src.study.multiseed import default_study_config, run_multi_seed

    common.require_id(experiment_id, "experiment id")
    where = common.locations(results_dir)
    path = where.experiment_file(experiment_id, "paired.json")
    assert path is not None
    runs: Dict[str, Dict[str, Any]] = {}
    for alt, spec in alternatives.items():
        config = deep_merge(default_study_config(duration), spec.get("overrides") or {})
        print(f"running {alt} ({spec['geometry']}) over {num_seeds} seeds", flush=True)
        runs[alt] = run_multi_seed(
            config=config,
            geometry=spec["geometry"],
            num_seeds=num_seeds,
            duration=duration,
            base_seed=base_seed,
        )
    metrics_run_id: Optional[str] = None
    if save_runs:
        from src.runstore import LocalFileBackend, RunStore

        store = RunStore(LocalFileBackend(where.root))
        ids = {
            alt: save_alternative_run(store, experiment_id, alt, (labels or {}).get(alt, alt), r)
            for alt, r in runs.items()
        }
        metrics_run_id = ids.get(baseline)
    doc = build_paired_doc(
        runs,
        baseline=baseline,
        labels=labels,
        primary_metric=primary_metric,
        metrics_run_id=metrics_run_id,
    )
    return common.write_json_atomic(path, doc)


def parse_alternatives(
    alts: Sequence[str], overrides: Sequence[str]
) -> Dict[str, Dict[str, Any]]:
    geoms = common.parse_pairs(list(alts), "--alt")
    over = common.parse_pairs(list(overrides), "--override")
    for key in over:
        if key not in geoms:
            raise ValueError(f"--override for unknown alternative {key!r}")
    out: Dict[str, Dict[str, Any]] = {}
    for alt, geometry in geoms.items():
        if geometry not in ("signal", "roundabout"):
            raise ValueError(f"geometry for {alt!r} must be signal or roundabout")
        try:
            parsed = json.loads(over[alt]) if alt in over else {}
        except ValueError:
            raise ValueError(f"--override for {alt!r} is not valid JSON") from None
        if not isinstance(parsed, dict):
            raise ValueError(f"--override for {alt!r} must be a JSON object")
        out[alt] = {"geometry": geometry, "overrides": parsed}
    return out


def main(argv: "Optional[List[str]]" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--experiment-id", required=True)
    ap.add_argument("--alt", action="append", default=[], required=True, metavar="ID=GEOMETRY")
    ap.add_argument("--override", action="append", default=[], metavar="ID=JSON")
    ap.add_argument("--label", action="append", default=[], metavar="ID=TEXT")
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--primary-metric", default="mean_delay_s", choices=sorted(METRICS))
    ap.add_argument("--num-seeds", type=int, default=10)
    ap.add_argument("--duration", type=float, default=120.0)
    ap.add_argument("--base-seed", type=int, default=42)
    ap.add_argument("--results-dir", default=None)
    ap.add_argument("--save-runs", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.num_seeds < 2 or args.duration <= 0:
            raise ValueError("--num-seeds must be at least 2 (pairs need two seeds) and --duration > 0")
        alternatives = parse_alternatives(args.alt, args.override)
        path = produce(
            args.experiment_id,
            alternatives,
            baseline=args.baseline,
            num_seeds=args.num_seeds,
            duration=args.duration,
            base_seed=args.base_seed,
            labels=common.parse_pairs(args.label, "--label"),
            primary_metric=args.primary_metric,
            results_dir=args.results_dir,
            save_runs=args.save_runs,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
