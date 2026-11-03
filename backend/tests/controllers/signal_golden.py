"""Golden fingerprints of the signalised junction (V3.1 W31, F4 "fixed-seed golden tests").

The roundabout has had a pinned corpus since V3.0 W2 (``roundabout_golden.py``);
the fixed-time and adaptive signals had capacity-curve pins but no whole-run
fingerprints, so a change that moved one vehicle at one tick but kept the
capacity curve could pass. This is the signal counterpart. It reuses the
roundabout harness unchanged: the per-tick trajectory, final metrics and
periodic snapshots are hashed twice, **exact** (raw bits, one interpreter on one
platform) and **portable** (positions and speeds to 1 um, floats to 12
significant digits, checked everywhere). See that module's docstring for what
each pin does and does not prove, and for the measured Windows / Python 3.14 vs
Linux / Python 3.11 differences that made the portable pin necessary.

Each case stores its compiled engine configuration, so the pins test the
engine and controllers only: a later change to scenario compilation cannot
move them (``test_pinned_configs_are_what_the_corpus_compiles_to`` is what
notices that it did).

Two paths reach the signal controllers and both are covered: ``direct``
(``create_controller`` on one engine: single and live runs) and
``study-signal`` (``DualSimulationOrchestrator``'s signal engine: every study,
planner and Robustness Lab run).

Recording is deliberate and never automatic::

    python -m tests.controllers.signal_golden --record [--force]
    python -m tests.controllers.signal_golden --add-environment

``--record`` refuses to overwrite a fixture without ``--force``; overwriting
discards the baseline, so it needs a recorded reason (``BASELINE_DIGEST`` in
the test module moves in the same diff). ``--add-environment`` adds only this
environment's exact pins, and only when the simulation source is the one the
fixture was recorded from and this environment reproduces the portable pins.
CI enforces the portable pins everywhere and the exact pins where an
environment is pinned; add the CI environment (Linux, Python 3.11) from a
checkout of ``recordedFrom`` once the first CI run is green.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.planning.models import canonical_json
from src.scenario.documents import compile_scenario, parse_scenario, validate_scenario
from tests.controllers.roundabout_golden import (
    FLOAT_DIGITS,
    HEAVY_MIX,
    SNAPSHOT_EVERY,
    TRAJECTORY_DECIMALS,
    URBAN_MIX,
    _arm,
    _git_head,
    _turning,
    environment_key,
    fingerprint_run,
    source_digest,
)

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "signal_golden_fingerprints.json"
)
FIXTURE_FORMAT = "urbanflow-signal-golden"
FIXTURE_VERSION = 1

ARMS = ("north", "south", "east", "west")
JUNCTION_OF = {"fixed_time": "fixed_time_signal", "adaptive": "adaptive_signal"}


def _document(
    name: str,
    strategy: str,
    approaches: Dict[str, Optional[Dict[str, Any]]],
    *,
    seed: int,
    duration: float,
    mix: Optional[Dict[str, float]] = None,
    signal: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    doc: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": name,
        "junction": {"type": JUNCTION_OF[strategy]},
        "approaches": approaches,
        "simulation": {"duration": duration, "warmup": 20.0, "seed": seed},
    }
    if mix is not None:
        doc["vehicles"] = {"mix": dict(mix)}
    if signal is not None:
        doc["signal"] = dict(signal)
    return doc


def _case(
    case_id: str,
    strategy: str,
    approaches: Dict[str, Optional[Dict[str, Any]]],
    *,
    seed: int,
    duration: float = 90.0,
    fast: bool = True,
    path: str = "direct",
    mix: Optional[Dict[str, float]] = None,
    signal: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "id": case_id,
        "fast": fast,
        "path": path,
        "strategy": strategy,
        "document": _document(
            case_id,
            strategy,
            approaches,
            seed=seed,
            duration=duration,
            mix=mix,
            signal=signal,
        ),
    }


def _all(lanes: int, vph: float) -> Dict[str, Optional[Dict[str, Any]]]:
    return {d: _arm(lanes, vph) for d in ARMS}


def _three_arm(vph: float, lanes: int = 1) -> Dict[str, Optional[Dict[str, Any]]]:
    return {
        "north": _arm(lanes, vph, turning=_turning(0.5, 0.5, 0.0)),
        "south": _arm(lanes, vph, turning=_turning(0.0, 0.5, 0.5)),
        "east": _arm(lanes, vph, turning=_turning(0.5, 0.0, 0.5)),
        "west": None,
    }


# The corpus. "fast" cases run in the ordinary CI job; the rest are slow.
# Demand: low ~ 25 %, medium ~ 60 %, saturated >= 100 % of what the layout
# discharges (judged from the existing capacity and lock-up tests).
CORPUS: List[Dict[str, Any]] = [
    _case("fixed-1lane-4arm-low", "fixed_time", _all(1, 150), seed=11),
    _case("fixed-1lane-4arm-medium", "fixed_time", _all(1, 350), seed=12),
    _case("fixed-2lane-4arm-medium", "fixed_time", _all(2, 500), seed=13),
    _case(
        "fixed-2lane-4arm-urban-mix",
        "fixed_time",
        _all(2, 500),
        seed=14,
        mix=URBAN_MIX,
    ),
    _case("fixed-3arm-low", "fixed_time", _three_arm(150), seed=15),
    _case(
        "fixed-custom-timing-uneven",
        "fixed_time",
        {
            "north": _arm(1, 450),
            "south": _arm(1, 450),
            "east": _arm(1, 200),
            "west": _arm(1, 200),
        },
        seed=16,
        signal={"nsGreenTime": 40.0, "ewGreenTime": 20.0, "yellowTime": 3.0},
    ),
    _case("adaptive-1lane-4arm-medium", "adaptive", _all(1, 350), seed=17),
    _case("adaptive-2lane-4arm-medium", "adaptive", _all(2, 500), seed=18),
    _case(
        "adaptive-2lane-urban-mix",
        "adaptive",
        _all(2, 500),
        seed=19,
        mix=URBAN_MIX,
    ),
    _case(
        "adaptive-skewed-demand",
        "adaptive",
        {
            "north": _arm(1, 600),
            "south": _arm(1, 600),
            "east": _arm(1, 100),
            "west": _arm(1, 100),
        },
        seed=20,
    ),
    _case("adaptive-3arm-low", "adaptive", _three_arm(150), seed=21),
    _case(
        "study-path-fixed-2lane-medium",
        "fixed_time",
        _all(2, 500),
        seed=22,
        path="study-signal",
    ),
    _case(
        "study-path-adaptive-1lane-medium",
        "adaptive",
        _all(1, 350),
        seed=23,
        path="study-signal",
    ),
    # --- slow: longer horizons and saturation ---
    _case(
        "fixed-1lane-saturated",
        "fixed_time",
        _all(1, 700),
        seed=31,
        duration=240,
        fast=False,
    ),
    _case(
        "fixed-2lane-heavy-mix-saturated",
        "fixed_time",
        _all(2, 900),
        seed=32,
        duration=240,
        fast=False,
        mix=HEAVY_MIX,
    ),
    _case(
        "adaptive-1lane-saturated",
        "adaptive",
        _all(1, 700),
        seed=33,
        duration=240,
        fast=False,
    ),
    _case(
        "adaptive-2lane-saturated-urban",
        "adaptive",
        _all(2, 900),
        seed=34,
        duration=240,
        fast=False,
        mix=URBAN_MIX,
    ),
    _case(
        "fixed-3arm-saturated",
        "fixed_time",
        _three_arm(600),
        seed=35,
        duration=240,
        fast=False,
    ),
    _case(
        "study-path-adaptive-saturated",
        "adaptive",
        _all(2, 800),
        seed=36,
        duration=240,
        fast=False,
        path="study-signal",
    ),
]


def compile_case(case: Dict[str, Any]) -> Dict[str, Any]:
    """The engine configuration of a corpus case (validated first)."""
    document, errors = parse_scenario(case["document"])
    assert document is not None and not errors, (case["id"], errors)
    report = validate_scenario(case["document"], [case["strategy"]])
    assert report["valid"], (case["id"], report["errors"])
    return compile_scenario(document, case["strategy"])


def load_fixture() -> Dict[str, Any]:
    with open(FIXTURE, encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)
    assert data["format"] == FIXTURE_FORMAT and data["version"] == FIXTURE_VERSION
    return data


def baseline_digest(fixture: Dict[str, Any]) -> str:
    """SHA-256 of what the baseline *means*: each case's id, strategy, path,
    compiled config and portable pin. Exact pins are left out so adding an
    environment does not move it; re-recording or editing a pin does."""
    keys = ("id", "strategy", "path", "fast", "config", "expected")
    body = [{k: c[k] for k in keys} for c in fixture["cases"]]
    return hashlib.sha256(canonical_json(body).encode()).hexdigest()


def _write(data: Dict[str, Any]) -> None:
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    with open(FIXTURE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"wrote {FIXTURE}")


def record(force: bool) -> None:
    if FIXTURE.exists() and not force:
        sys.exit(
            f"{FIXTURE} exists. Re-recording discards the baseline; pass --force "
            "only with a recorded reason."
        )
    env = environment_key()
    cases = []
    for case in CORPUS:
        config = compile_case(case)
        result = fingerprint_run(config, case["path"])
        cases.append(
            {
                "id": case["id"],
                "fast": case["fast"],
                "path": case["path"],
                "strategy": case["strategy"],
                "config": config,
                "expected": result["portable"],
                "exact": {env: result["exact"]},
            }
        )
        print(
            f"{case['id']}: exited={result['portable']['exited']} "
            f"collisions={result['portable']['collisions']}",
            flush=True,
        )
    _write(
        {
            "format": FIXTURE_FORMAT,
            "version": FIXTURE_VERSION,
            "description": (
                "Fixed-time and adaptive signal fingerprints. See "
                "tests/controllers/signal_golden.py."
            ),
            "recordedFrom": _git_head(),
            "sourceDigest": source_digest(),
            "snapshotEvery": SNAPSHOT_EVERY,
            "floatDigits": FLOAT_DIGITS,
            "trajectoryDecimals": TRAJECTORY_DECIMALS,
            "cases": cases,
        }
    )


def add_environment() -> None:
    data = load_fixture()
    if source_digest() != data["sourceDigest"]:
        sys.exit(
            "The simulation source differs from the one the fixture was "
            f"recorded from; check out {data['recordedFrom']} and run this there."
        )
    env = environment_key()
    for case in data["cases"]:
        result = fingerprint_run(case["config"], case["path"])
        if result["portable"] != case["expected"]:
            sys.exit(
                f"{case['id']}: this environment does not reproduce the portable "
                "pin, so an exact pin would not describe the same behaviour"
            )
        known = case["exact"].get(env)
        if known is not None and known != result["exact"]:
            sys.exit(f"{case['id']}: an exact pin for {env} exists and differs")
        case["exact"][env] = result["exact"]
        print(f"{case['id']}: pinned for {env}", flush=True)
    _write(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--record", action="store_true")
    mode.add_argument("--add-environment", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.record:
        record(args.force)
    else:
        add_environment()
