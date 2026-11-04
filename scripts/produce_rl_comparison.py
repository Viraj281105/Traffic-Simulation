"""Write ``rl/<id>.json`` (urbanflow-rl-comparison) from one or more ``scripts/rl_evaluate.py`` outputs.

    python scripts/rl_evaluate.py --model rl_runs/dqn-s0-t20000/model.zip --algo dqn --vph 400 --out low.json
    python scripts/rl_evaluate.py --model rl_runs/dqn-s0-t20000/model.zip --algo dqn --vph 800 --out high.json
    python scripts/produce_rl_comparison.py --id dqn-four-way --junction "Four-way, one lane" \
        --scenario low="400 veh/h"=low.json --scenario high="800 veh/h"=high.json \
        --rl-policy rl_dqn --rl-label DQN --policy-id signal-control/3 --algorithm DQN --training-steps 20000

Nothing is computed here: the eval documents are copied in whole, and the endpoint does the statistics.
Every scenario must hold the fixed-time policy and the RL policy with the same number of seeds (at least two).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import produce_common as common  # noqa: E402

COMPARISON_FORMAT = "urbanflow-rl-comparison"
EVAL_FORMAT = "urbanflow-rl-eval"
FIXED_POLICY = "fixed_time"


def build_rl_doc(
    *,
    junction: str,
    metric: str,
    rl_policy: str,
    rl_label: str,
    policy_id: str,
    algorithm: str,
    training_steps: int,
    scenarios: Sequence[Tuple[str, str, Mapping[str, Any]]],
    fixed_label: str = "Fixed time, 30 s green",
    caveats: Sequence[str] = (),
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """The comparison document from ``(scenario id, label, eval document)`` triples. Pure."""
    if not scenarios:
        raise ValueError("at least one scenario is needed")
    seen = set()
    for sid, _label, ev in scenarios:
        common.require_id(sid, "scenario id")
        if sid in seen:
            raise ValueError(f"duplicate scenario id {sid!r}")
        seen.add(sid)
        if ev.get("format") != EVAL_FORMAT:
            raise ValueError(f"scenario {sid!r}: not an {EVAL_FORMAT} document")
        policies = ev.get("policies") or {}
        for name in (FIXED_POLICY, rl_policy):
            if name not in policies:
                raise ValueError(f"scenario {sid!r}: policy {name!r} not in {sorted(policies)}")
            vals = policies[name].get(metric)
            if not isinstance(vals, list) or len(vals) < 2:
                raise ValueError(f"scenario {sid!r}: {name} needs at least two {metric} values")
        if len(policies[FIXED_POLICY][metric]) != len(policies[rl_policy][metric]):
            raise ValueError(f"scenario {sid!r}: policies have different numbers of seeds")
    return {
        "format": COMPARISON_FORMAT,
        "version": 1,
        "generatedAt": generated_at or common.utc_now_iso(),
        "junction": junction,
        "metric": metric,
        "fixedPolicy": FIXED_POLICY,
        "fixedLabel": fixed_label,
        "rl": {
            "policy": rl_policy,
            "label": rl_label,
            "policyId": policy_id,
            "algorithm": algorithm,
            "trainingSteps": int(training_steps),
        },
        "caveats": list(caveats),
        "scenarios": [
            {"scenarioId": sid, "label": label, "eval": dict(ev)} for sid, label, ev in scenarios
        ],
    }


def parse_scenario(item: str) -> Tuple[str, str, Dict[str, Any]]:
    """``ID=LABEL=PATH`` to (id, label, eval document)."""
    sid, _, rest = item.partition("=")
    label, sep, path = rest.rpartition("=")
    if not sid or not sep or not label or not path:
        raise ValueError(f"--scenario must look like ID=LABEL=PATH, got {item!r}")
    try:
        ev = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read eval file {path!r}: {exc}") from None
    if not isinstance(ev, dict):
        raise ValueError(f"eval file {path!r} is not a JSON object")
    return sid, label, ev


def produce(
    comparison_id: str,
    results_dir: "Optional[Path | str]" = None,
    **doc_kwargs: Any,
) -> Path:
    common.require_id(comparison_id, "comparison id")
    path = common.locations(results_dir).rl_file(comparison_id)
    assert path is not None
    return common.write_json_atomic(path, build_rl_doc(**doc_kwargs))


def main(argv: "Optional[List[str]]" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--id", required=True)
    ap.add_argument("--junction", required=True)
    ap.add_argument("--scenario", action="append", default=[], required=True, metavar="ID=LABEL=PATH")
    ap.add_argument("--metric", default="mean_wait_s")
    ap.add_argument("--rl-policy", default="rl_dqn", help="policy name inside the eval files")
    ap.add_argument("--rl-label", required=True)
    ap.add_argument("--policy-id", required=True)
    ap.add_argument("--algorithm", required=True)
    ap.add_argument("--training-steps", type=int, required=True)
    ap.add_argument("--fixed-label", default="Fixed time, 30 s green")
    ap.add_argument("--caveat", action="append", default=[])
    ap.add_argument("--results-dir", default=None)
    args = ap.parse_args(argv)
    try:
        path = produce(
            args.id,
            args.results_dir,
            junction=args.junction,
            metric=args.metric,
            rl_policy=args.rl_policy,
            rl_label=args.rl_label,
            policy_id=args.policy_id,
            algorithm=args.algorithm,
            training_steps=args.training_steps,
            scenarios=[parse_scenario(s) for s in args.scenario],
            fixed_label=args.fixed_label,
            caveats=args.caveat,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
