"""Print the sampled-conditions table for the preview (PV-2 option, task B0-5).

    backend/.venv/Scripts/python.exe scripts/sampler_condition_table.py [spec.json] [--conditions N] [--seed S]
                                                                        [--alternatives K] [--out table.md]

With no spec file it uses a small demo specification. Output is Markdown: the specification fingerprint,
the counts of conditions, replications and total runs *kept separate* (strategy section 5.2), and one row
per condition. Same specification and seed always print the same table.

This is a DESIGN PROTOTYPE: it shows what the Robustness Lab would sample. It runs no simulation and
reports no results.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from src.uncertainty import UncertaintySpec, fingerprint, sample_conditions

DEMO_FACTORS = [
    {"id": "demand", "kind": "demand_scale", "distribution": {"kind": "uniform"}, "bounds": [0.7, 1.3],
     "rationale": "Assumed planning range around the base demand"},
    {"id": "headway", "kind": "headway_scale", "distribution": {"kind": "triangular", "mode": 1.0},
     "bounds": [0.8, 1.2], "rationale": "Assumed driver-following variation (a proxy; the engine has no reaction delay)"},
    {"id": "speed", "kind": "desired_speed_scale",
     "distribution": {"kind": "truncated_normal", "mean": 1.0, "sd": 0.1}, "bounds": [0.8, 1.2],
     "rationale": "Assumed spread of desired speeds"},
    {"id": "accel", "kind": "max_acceleration_scale",
     "distribution": {"kind": "lognormal", "mu": 0.0, "sigma": 0.2}, "bounds": [0.7, 1.4],
     "rationale": "Assumed spread of maximum acceleration"},
]


def build_spec(args) -> UncertaintySpec:
    if args.spec:
        data = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    else:
        data = {"name": "Demo uncertainty specification", "factors": DEMO_FACTORS,
                "conditions": 12, "replications": 2, "seed": 2026}
    if args.conditions is not None:
        data["conditions"] = args.conditions
    if args.seed is not None:
        data["seed"] = args.seed
    return UncertaintySpec.model_validate(data)


def render(spec: UncertaintySpec, alternatives: int) -> str:
    conditions = sample_conditions(spec)
    total_runs = spec.conditions * alternatives * spec.replications
    ids = [f.id for f in spec.factors]
    lines = [
        (
            "> **DESIGN PROTOTYPE — no simulation results.** This table shows what the Robustness Lab would "
            "sample; every distribution below is an assumption of the analyst, not an estimate from data."
        ),
        "",
        f"**Specification:** {spec.name} · fingerprint `{fingerprint(spec)}` · seed {spec.seed}",
        "",
        (
            f"**{spec.conditions} conditions** × {alternatives} alternatives × {spec.replications} replications "
            f"= **{total_runs} total runs**, but the unit of inference is the **{spec.conditions} conditions**."
        ),
        "",
        "| Factor | Kind | Distribution | Bounds | Basis | Rationale |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for f in spec.factors:
        lines.append(f"| {f.id} | {f.kind} | {f.distribution.kind} | {f.bounds[0]} – {f.bounds[1]} | {f.basis} | {f.rationale} |")
    lines += ["", "| # | " + " | ".join(ids) + " | engine seeds |", "| --: | " + " | ".join("--:" for _ in ids) + " | --- |"]
    for c in conditions:
        vals = " | ".join(f"{c.values[i]:.3f}" for i in ids)
        lines.append(f"| {c.index + 1} | {vals} | {', '.join(str(s) for s in c.seeds)} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="?", help="uncertainty specification JSON (default: demo)")
    ap.add_argument("--conditions", type=int)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--alternatives", type=int, default=3, help="alternatives for the total-runs line (default 3)")
    ap.add_argument("--out", help="write the table to this file instead of stdout")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # the table uses × and — (Windows consoles default to cp1252)
    text = render(build_spec(args), args.alternatives)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
