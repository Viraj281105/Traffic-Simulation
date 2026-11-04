"""Retraining pipeline for the network policy: train, evaluate, promote (F18).

Three stages that the Airflow DAG (``airflow/dags/rl_retrain.py``) runs as
separate tasks and that ``all`` runs in one go::

    python -m src.rl.retrain train    --work-dir W --registry-dir R --timesteps N --seed S
    python -m src.rl.retrain evaluate --work-dir W --registry-dir R --seeds 10
    python -m src.rl.retrain promote  --work-dir W --registry-dir R

* ``train`` registers a new candidate version (stage ``none``).
* ``evaluate`` runs the candidate, the current production model (if any) and
  both baselines on the same held-out seeds, writes ``W/eval.json`` (the
  ``urbanflow-rl-eval`` shape, with paired comparisons) and stores the
  held-out ``mean_wait_s`` on both registered versions.
* ``promote`` moves the candidate to production only if its held-out
  ``mean_wait_s`` is lower than the incumbent's (or there is no incumbent).
  A bad retrain therefore never replaces a good model.

State between stages lives in ``W/state.json``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.rl.network_env import demo_network
from src.rl.network_train import NETWORK_MODEL_NAME, train_network
from src.rl.tracking import ModelRegistry

METRIC = "mean_wait_s"
CANDIDATE = "rl_candidate"
INCUMBENT = "rl_production"


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, sort_keys=True, default=str)
        f.write("\n")


def _state(work: Path) -> Dict[str, Any]:
    data: Dict[str, Any] = json.loads((work / "state.json").read_text(encoding="utf-8"))
    return data


def stage_train(
    work_dir: Union[str, Path],
    registry_dir: Union[str, Path],
    timesteps: int,
    seed: int,
    env_kwargs: Optional[Dict[str, Any]] = None,
    model_name: str = NETWORK_MODEL_NAME,
    hyperparams: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    work = Path(work_dir)
    meta = train_network(
        timesteps,
        seed=seed,
        env_kwargs=env_kwargs,
        hyperparams=hyperparams,
        out_dir=work / "runs",
        registry_dir=registry_dir,
        model_name=model_name,
    )
    state = {
        "model_name": model_name,
        "candidate_version": meta["registry_version"],
        "seed": seed,
        "timesteps": timesteps,
    }
    _write(work / "state.json", state)
    return state


def stage_evaluate(
    work_dir: Union[str, Path],
    registry_dir: Union[str, Path],
    n_seeds: int = 10,
    env_kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from src.rl.network_eval import compare_network, held_out_seeds, sb3_network_policy

    work = Path(work_dir)
    state = _state(work)
    reg = ModelRegistry(registry_dir)
    name, cand = state["model_name"], int(state["candidate_version"])
    policies = {CANDIDATE: sb3_network_policy(reg.load_model(name, cand))}
    incumbent = reg.stage_version(name, "production")
    if incumbent is not None and incumbent != cand:
        policies[INCUMBENT] = sb3_network_policy(reg.load_model(name, incumbent))
    doc = compare_network(held_out_seeds(n_seeds), env_kwargs, policies)
    doc["registry"] = {"model": name, "candidate": cand, "incumbent": incumbent}
    _write(work / "eval.json", doc)
    for pname, version in ((CANDIDATE, cand), (INCUMBENT, incumbent)):
        if pname in doc["policies"] and version is not None:
            vals = doc["policies"][pname][METRIC]
            reg.update_metrics(
                name, version, {f"heldout_{METRIC}": sum(vals) / len(vals)}
            )
    state["evaluated"] = True
    _write(work / "state.json", state)
    return doc


def stage_promote(
    work_dir: Union[str, Path], registry_dir: Union[str, Path]
) -> Dict[str, Any]:
    work = Path(work_dir)
    state = _state(work)
    if not state.get("evaluated"):
        raise RuntimeError("evaluate must run before promote")
    reg = ModelRegistry(registry_dir)
    decision = reg.promote_if_better(
        state["model_name"],
        int(state["candidate_version"]),
        f"heldout_{METRIC}",
        lower_is_better=True,
    )
    decision["version"] = int(state["candidate_version"])
    _write(work / "promotion.json", decision)
    return decision


def _env_kwargs(args: argparse.Namespace) -> Dict[str, Any]:
    graph, flows = demo_network(args.rows, args.cols, vehicles_per_hour=args.vph)
    return {
        "graph": graph,
        "flows": flows,
        "episode_seconds": args.episode_seconds,
        "decision_interval": args.decision_interval,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Network policy retraining pipeline")
    ap.add_argument("stage", choices=("train", "evaluate", "promote", "all"))
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--registry-dir", required=True)
    ap.add_argument("--timesteps", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--seeds", type=int, default=10, help="held-out evaluation seeds")
    ap.add_argument("--rows", type=int, default=2)
    ap.add_argument("--cols", type=int, default=2)
    ap.add_argument("--vph", type=float, default=450.0)
    ap.add_argument("--episode-seconds", type=float, default=300.0)
    ap.add_argument("--decision-interval", type=float, default=5.0)
    args = ap.parse_args(argv)
    env_kwargs = _env_kwargs(args)
    if args.stage in ("train", "all"):
        print(
            stage_train(
                args.work_dir, args.registry_dir, args.timesteps, args.seed, env_kwargs
            )
        )
    if args.stage in ("evaluate", "all"):
        doc = stage_evaluate(args.work_dir, args.registry_dir, args.seeds, env_kwargs)
        print(f"evaluated {len(doc['seeds'])} seeds: {list(doc['policies'])}")
    if args.stage in ("promote", "all"):
        print(stage_promote(args.work_dir, args.registry_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
