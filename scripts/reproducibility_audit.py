"""Reproducibility audit for the G-REL2 release (package R2).

    cd backend
    python ../scripts/reproducibility_audit.py [--quick]

Runs a small, fixed-seed scenario set twice in one process and compares the two
outputs bit for bit after canonical JSON (sorted keys, no whitespace), with
wall-clock fields removed. Prints a table and exits 1 on any difference, 0 when
every scenario repeated exactly.

Scenarios: a multi-seed study of the signal junction, the 12-junction network
metrics, and a calibration of the demo grid against the synthetic fixture
counts. Run-manifest hashes are checked as well: each must be a full SHA-256,
equal across both runs, and (for the study) match a fresh hash of the input
configuration.

This audits repeatability inside one process on one interpreter and one code
version. It does not show equality across machines, Python versions or commits.
"""

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from src.calibration.network_counts import load_counts_csv  # noqa: E402
from src.calibration.network_fit import (  # noqa: E402
    FitOptions,
    SimSettings,
    calibrate_network,
)
from src.calibration.network_synthetic import demo_flows, demo_grid  # noqa: E402
from src.core.run_manifest import config_hash, verify_manifest  # noqa: E402
from src.netmetrics.metrics import network_metrics  # noqa: E402
from src.networks.grid import (  # noqa: E402
    build_twelve_junction_network,
    twelve_junction_flows,
)
from src.study.multiseed import (  # noqa: E402
    default_study_config,
    run_multi_seed,
)

FIXTURES = BACKEND / "tests" / "calibration" / "fixtures"
TIMESTAMP_KEYS = frozenset({"createdAt", "generatedAt", "timestamp", "elapsedSeconds"})


@dataclass
class Sizes:
    study_duration: float = 20.0
    study_seeds: int = 2
    network_duration: float = 120.0
    calib_duration: float = 60.0
    calib_budget: int = 6


QUICK = Sizes(
    study_duration=6.0,
    study_seeds=2,
    network_duration=30.0,
    calib_duration=30.0,
    calib_budget=3,
)


def strip_timestamps(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: strip_timestamps(v) for k, v in value.items() if k not in TIMESTAMP_KEYS
        }
    if isinstance(value, list):
        return [strip_timestamps(v) for v in value]
    return value


def canonical(value: Any) -> str:
    return json.dumps(
        strip_timestamps(value), sort_keys=True, separators=(",", ":"), default=str
    )


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Outcome:
    name: str
    hash_a: str = ""
    hash_b: str = ""
    config_hash: str = ""
    problems: List[str] = field(default_factory=list)

    @property
    def identical(self) -> bool:
        return self.hash_a == self.hash_b and bool(self.hash_a)

    @property
    def ok(self) -> bool:
        return self.identical and not self.problems


Scenario = Callable[[], Tuple[Dict[str, Any], Dict[str, Any]]]


def _study(sizes: Sizes) -> Scenario:
    def run() -> Tuple[Dict[str, Any], Dict[str, Any]]:
        out = run_multi_seed(
            geometry="signal",
            num_seeds=sizes.study_seeds,
            duration=sizes.study_duration,
            base_seed=20260101,
        )
        return out, {"manifest": out["manifest"], "duration": out["duration"]}

    return run


def _network(sizes: Sizes) -> Scenario:
    def run() -> Tuple[Dict[str, Any], Dict[str, Any]]:
        out = network_metrics(
            build_twelve_junction_network(),
            twelve_junction_flows(),
            duration=sizes.network_duration,
            seed=7,
        )
        return out, {}

    return run


def _calibration(sizes: Sizes) -> Scenario:
    def run() -> Tuple[Dict[str, Any], Dict[str, Any]]:
        counts = load_counts_csv(
            (FIXTURES / "demo_counts.csv").read_text(encoding="utf-8")
        )
        report = calibrate_network(
            demo_grid(),
            demo_flows(),
            counts,
            FitOptions(budget=sizes.calib_budget, seed=1),
            SimSettings(duration=sizes.calib_duration, seed=1),
        )
        return report, {"calibrationHash": report["manifest"]["hash"]}

    return run


def _check_study_manifest(extra: Dict[str, Any], out: Outcome) -> None:
    manifest = extra["manifest"]
    out.config_hash = manifest.get("configHash", "")
    if len(out.config_hash) != 64:
        out.problems.append("study configHash is not a full SHA-256")
    config = default_study_config(extra["duration"])
    check = verify_manifest(
        manifest,
        config,
        current_commit=manifest.get("gitCommit", "unknown"),
        current_python=manifest.get("pythonVersion", "unknown"),
    )
    if check.get("configHashMatches") is not True:
        out.problems.append("stored config does not match the manifest configHash")
    if config_hash(config) != out.config_hash:
        out.problems.append("fresh config hash differs from the manifest")


def audit(sizes: Optional[Sizes] = None) -> List[Outcome]:
    """Run every scenario twice; return one Outcome per scenario."""
    sizes = sizes or Sizes()
    scenarios: List[Tuple[str, Scenario]] = [
        ("multi-seed study (signal)", _study(sizes)),
        ("12-junction network metrics", _network(sizes)),
        ("network calibration (synthetic)", _calibration(sizes)),
    ]
    outcomes: List[Outcome] = []
    for name, run in scenarios:
        out = Outcome(name)
        try:
            a, extra_a = run()
            b, extra_b = run()
        except Exception as exc:  # report it, do not hide it
            out.problems.append(f"raised {type(exc).__name__}: {exc}")
            outcomes.append(out)
            continue
        out.hash_a = digest(canonical(a))
        out.hash_b = digest(canonical(b))
        if canonical(extra_a) != canonical(extra_b):
            out.problems.append("manifest side data differs between runs")
        if "manifest" in extra_a:
            _check_study_manifest(extra_a, out)
        if "calibrationHash" in extra_a:
            out.config_hash = extra_a["calibrationHash"]
            if len(out.config_hash) != 64:
                out.problems.append("calibration manifest hash is not a full SHA-256")
        outcomes.append(out)
    return outcomes


def render(outcomes: List[Outcome]) -> str:
    rows = [("Scenario", "Run A", "Run B", "Identical", "Manifest hash", "Notes")]
    for o in outcomes:
        rows.append(
            (
                o.name,
                o.hash_a[:12] or "-",
                o.hash_b[:12] or "-",
                "yes" if o.identical else "NO",
                o.config_hash[:12] or "-",
                "; ".join(o.problems) or "ok",
            )
        )
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    lines = ["  ".join(c.ljust(w) for c, w in zip(r, widths)) for r in rows]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fixed-seed reproducibility audit")
    parser.add_argument("--quick", action="store_true", help="tiny durations")
    args = parser.parse_args(argv)
    outcomes = audit(QUICK if args.quick else Sizes())
    print(render(outcomes))
    failed = [o for o in outcomes if not o.ok]
    verdict = "all scenarios reproduced exactly" if not failed else "FAILED"
    print(f"\nRESULT: {verdict} ({len(outcomes) - len(failed)}/{len(outcomes)})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
