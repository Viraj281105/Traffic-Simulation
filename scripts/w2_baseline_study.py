"""V3.0 W2 baseline-comparison study: metered roundabout vs the three existing strategies.

SR-23 / SR-21 (sprint plan section 3.3 "baseline-comparison study with intervals"): one
junction, one set of seeded arrivals, four alternatives run through the existing planning
machinery (``planning.runner.run_study`` -> ``study.control_comparison``), so every
alternative faces the same vehicles and the comparison is paired per seed:

    conventional   roundabout, no entry control               (the baseline)
    metered        roundabout + ``metered_entry`` fixed plan  (the W2 feature)
    fixed_time     fixed-time signalised intersection
    adaptive       adaptive signalised intersection

    python scripts/w2_baseline_study.py [--seeds 6] [--duration 180] [--out DIR]

Writes ``study.json`` (the request), ``result.json`` (the planner's result document),
``report.md`` (the planner's Markdown export) and ``SHA256SUMS`` into DIR (default
``docs/research/examples/signalised-roundabout-baseline``).  Prints a table whose
every number is read from the result document; this script computes only the layout.

The result is exploratory: demand, timings and geometry are assumptions, nothing is
calibrated against a real site, and no claim is made about real-world safety.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from src.planning.models import PlanningStudy  # noqa: E402
from src.planning.report import export  # noqa: E402
from src.planning.runner import run_study  # noqa: E402

# Uneven peak demand (veh/h per arm at scale 1.0): a heavy north-south corridor and a
# light east-west side street.  Scales 0.25 / 0.5 / 1.0 give a low, a medium and a peak
# tier; the 0.25 tier is the "about 25 % of capacity" point of D-W2-9c.
PEAK_VPH = {"north": 800, "south": 800, "east": 400, "west": 400}
SCALES = [0.25, 0.5, 1.0]

METERED_PATCH: Dict[str, Any] = {
    "roundabout": {
        "entryControl": "metered_entry",
        "entryMetering": {
            # Green shares follow the demand split (2:1) rather than an equal split.
            "phases": [
                {"entries": ["north", "south"], "green": 28, "minGreen": 8},
                {"entries": ["east", "west"], "green": 14, "minGreen": 8},
            ],
            "yellow": 3,
            "allRed": 2,
        },
    }
}


def build_study(seeds: int, duration: float) -> Dict[str, Any]:
    return {
        "format": "urbanflow-planning-study",
        "version": 1,
        "name": "W2 baseline: metered roundabout vs conventional, fixed-time and adaptive",
        "objective": (
            "Report how a fixed-plan metered roundabout compares with the three existing "
            "strategies on one assumed junction. Evidence only; not a recommendation."
        ),
        "subject": {
            "scenario": {
                "format": "urbanflow-scenario",
                "version": 1,
                "name": "W2 baseline junction (uneven peak demand)",
                "junction": {"type": "roundabout"},
                "approaches": {
                    d: {
                        "lanes": 1,
                        "length": 150.0,
                        "vehiclesPerHour": vph,
                        "turning": {"left": 0.2, "straight": 0.6, "right": 0.2},
                    }
                    for d, vph in PEAK_VPH.items()
                },
                "vehicles": {
                    "mix": {
                        "car": 0.8,
                        "suv": 0.08,
                        "bus": 0.04,
                        "truck": 0.05,
                        "motorcycle": 0.03,
                    }
                },
                "simulation": {"duration": duration, "warmup": 30.0, "seed": 101},
            }
        },
        "alternatives": [
            {
                "id": "conventional",
                "label": "Conventional roundabout",
                "strategy": "roundabout",
            },
            {
                "id": "metered",
                "label": "Metered-entry roundabout (28/14 s)",
                "strategy": "roundabout",
                "patch": METERED_PATCH,
            },
            {
                "id": "fixed_time",
                "label": "Fixed-time signal",
                "strategy": "fixed_time",
            },
            {"id": "adaptive", "label": "Adaptive signal", "strategy": "adaptive"},
        ],
        "demand": {"scales": SCALES},
        "repetitions": {"seeds": seeds, "baseSeed": 101, "confidenceLevel": 0.95},
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--duration", type=float, default=180.0)
    ap.add_argument(
        "--out",
        default=str(
            ROOT / "docs" / "research" / "examples" / "signalised-roundabout-baseline"
        ),
    )
    args = ap.parse_args()

    payload = build_study(args.seeds, args.duration)
    study = PlanningStudy.model_validate(payload)
    runs = 4 * len(SCALES) * args.seeds
    print(
        f"{runs} simulations ({args.seeds} seeds x {len(SCALES)} demand tiers x 4 alternatives)"
    )
    t0 = time.perf_counter()
    result = run_study(study)
    elapsed = time.perf_counter() - t0
    print(f"done in {elapsed / 60:.1f} min")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "study.json").write_text(json.dumps(payload, indent=2) + "\n")
    (out / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    (out / "report.md").write_text(export(result, "markdown")["content"])
    lines = [
        f"{_sha256(out / n)}  {n}" for n in ("study.json", "result.json", "report.md")
    ]
    (out / "SHA256SUMS").write_text("\n".join(lines) + "\n")

    print(f"result fingerprint {result['meta']['resultFingerprint']}")
    print(f"written to {out}")
    rows: List[Dict[str, Any]] = result["results"]
    print(
        f"\n{'alternative':<14}{'scale':>6}{'vph':>7}{'delay s':>9}{'+-95%':>7}"
        f"{'served':>8}{'queue':>7}{'coll':>6}"
    )
    for r in rows:
        perf = (r.get("performance") or {}).get("values") or {}
        saf = (r.get("safety") or {}).get("values") or {}
        delay = perf.get("averageDelay") or {}
        print(
            f"{r['alternativeId']:<14}{r['demandScale']:>6}{r['demandVph']:>7.0f}"
            f"{_num(delay.get('mean')):>9}{_num(delay.get('ciHalfWidth')):>7}"
            f"{_num(perf.get('throughput', {}).get('mean')):>8}"
            f"{_num(perf.get('averageQueueLength', {}).get('mean')):>7}"
            f"{_num(saf.get('collisionCount', {}).get('mean')):>6}"
        )
    print(
        "\nMean delay vs the conventional roundabout (paired per seed, 95 % interval):"
    )
    for c in result["comparison"]["vsBaseline"]:
        if c["metric"] != "averageDelay":
            continue
        print(
            f"  {c['alternativeId']:<12} scale {c['demandScale']:<5} "
            f"{c['delta']:+7.2f} s ({c['deltaPct']:+6.1f} %)  "
            f"[{c['ciLow']:+.2f}, {c['ciHigh']:+.2f}]  {c['verdict']}"
        )
    return 0


def _num(x: Any) -> str:
    return f"{x:.1f}" if isinstance(x, (int, float)) else "-"


if __name__ == "__main__":
    sys.exit(main())
