"""Golden fingerprints of the conventional roundabout (V3.0 W2, ADR-014 §7).

ADR-014 requires that the conventional roundabout stays **bit-identical** —
same metric and snapshot fingerprints — once the ``EntryGate`` seam exists
and the default gate is ``AlwaysOpen``. The "before" side of that comparison
is the controller as it was before the seam, so its fingerprints are recorded
here once, from the unmodified code, and pinned in
``tests/fixtures/roundabout_golden_fingerprints.json``. Each case stores its
compiled engine configuration, so the pin tests the controller and engine
only: a later change to scenario compilation cannot move it.

Two paths are covered, because both reach ``RoundaboutController``:

* ``direct`` — ``create_controller`` on one engine (single runs, live runs);
* ``study`` — ``DualSimulationOrchestrator``'s roundabout engine, the path
  ``study/runner.py`` uses for every planner and Robustness Lab run (it
  rebuilds the roundabout's controller section itself).

Each case is pinned twice.

**Exact** (``exact[<environment>]``) — raw bits, for one interpreter on one
platform (``environment_key()``): ``trajectory`` (every tick, every active
vehicle's id, lane, and ``float.hex`` of its position and speed),
``metrics`` (the collector's final metrics, read as ``engine/readout.py``
reads them) and ``snapshots`` (every ``SNAPSHOT_EVERY``-th tick's snapshot
without its wall-clock time), each a SHA-256 of canonical JSON
(``planning.models.canonical_json``). This is ADR-014's bit-identity. It is
checked wherever the running environment has a pin; elsewhere that test is
skipped and says so.

**Portable** (``expected``) — the same three fingerprints, checked in every
environment: vehicle ids and lanes exact, positions and speeds to
``TRAJECTORY_DECIMALS`` decimals (1 µm, 1 µm/s: the precision of the V1.0
pins in ``tests/integration/test_vehicle_types_and_lanes.py``), every float
in metrics and snapshots to ``FLOAT_DIGITS`` significant digits; plus exact
tick, exit and collision counts.

Why both (measured 2026-10-19 on this corpus): Windows / Python 3.14.7 and
Linux / Python 3.11.16 put the same vehicles on the same lanes at every tick,
but ~10 % of positions and speeds differ by ≤ 6e-14 m (platform ``libm`` /
``pow``) and two aggregate metrics (``minTTC``, ``averageTravelSpeed``) by
≤ 6e-15 relative (Python ≥ 3.12 sums floats with compensation). Raw bits
therefore cannot be compared across environments; the portable pin can.

What the portable pin proves, and what it does not. Equal portable
fingerprints mean that at every tick the same vehicles exist on the same
lanes with positions and speeds that agree to the micrometre, and every
reported metric and snapshot value agrees to 12 significant digits (about
1,000× the measured cross-environment noise). A changed decision — a gap
accepted one tick earlier, a different yield, a vehicle on another lane —
appears as a structural difference or a divergence far above a micrometre,
so it fails. It does **not** prove bit-identity: a change that only perturbs
floating-point rounding (for example re-associating a sum) and stays below
1 µm and 12 significant digits for the whole run passes the portable pin.
That class is what the exact pin is for. A value lying on a rounding
boundary could round differently in an environment with other last bits;
that is fixed per environment (never intermittent), and does not occur in
the two environments measured.

Recording is deliberate and never automatic::

    python -m tests.controllers.roundabout_golden --record [--force]
    python -m tests.controllers.roundabout_golden --add-environment

``--record`` writes a new fixture (portable pins and this environment's exact
pins) and refuses to overwrite one without ``--force``: overwriting discards
the "before" side of the bit-identity test, so it needs a recorded reason
(ADR-014 §7). ``--add-environment`` only adds this environment's exact pins,
and only when the simulation source is the one the fixture was recorded from
(``sourceDigest``) and this environment reproduces the portable pins. Once
the seam has landed, run it from a checkout of ``recordedFrom``.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import src
from src.controllers.factory import create_controller
from src.core.clock import Clock
from src.engine.readout import engine_metrics
from src.engine.simulation_engine import SimulationEngine
from src.engine.tick_callback import build_tick_callback
from src.metrics.collector import MetricCollector
from src.planning.models import canonical_json
from src.scenario.documents import compile_scenario, parse_scenario, validate_scenario
from src.snapshot.builder import SnapshotBuilder
from src.snapshot.dual_orchestrator import DualSimulationOrchestrator

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "roundabout_golden_fingerprints.json"
)
FIXTURE_FORMAT = "urbanflow-roundabout-golden"
FIXTURE_VERSION = 1
SNAPSHOT_EVERY = 10  # ticks (1 s at the default 0.1 s step)
FLOAT_DIGITS = 12  # significant digits kept in the portable metrics/snapshots
TRAJECTORY_DECIMALS = 6  # 1 µm and 1 µm/s in the portable trajectory


def _rounded(value: Any) -> Any:
    if isinstance(value, float):
        return float(f"{value:.{FLOAT_DIGITS}g}")
    if isinstance(value, dict):
        return {k: _rounded(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_rounded(v) for v in value]
    return value


def _portable_json(value: Any) -> str:
    """Canonical JSON with floats at FLOAT_DIGITS significant digits."""
    return canonical_json(_rounded(value))


def environment_key() -> str:
    """What an exact pin is valid for: implementation and full Python
    version, OS, machine, and the C library (glibc version on Linux; the OS
    build on Windows, which fixes its UCRT)."""
    libc = "".join(platform.libc_ver()) or platform.version()
    return "-".join(
        (
            platform.python_implementation(),
            platform.python_version(),
            platform.system(),
            platform.machine(),
            libc,
        )
    )


def source_digest() -> str:
    """SHA-256 of every ``src/**/*.py`` (path and content, line endings
    normalised): the simulation code a fixture was recorded from."""
    root = Path(src.__file__).resolve().parent
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


URBAN_MIX = {"car": 0.7, "suv": 0.15, "bus": 0.05, "truck": 0.05, "motorcycle": 0.05}
HEAVY_MIX = {"car": 0.6, "suv": 0.1, "bus": 0.15, "truck": 0.15}


def _arm(
    lanes: int,
    vph: float,
    length: float = 200.0,
    turning: Optional[Dict[str, float]] = None,
    **extra: Any,
) -> Dict[str, Any]:
    arm: Dict[str, Any] = {
        "lanes": lanes,
        "length": length,
        "vehiclesPerHour": vph,
        "turning": turning or {"left": 0.25, "straight": 0.5, "right": 0.25},
    }
    arm.update(extra)
    return arm


def _turning(left: float, straight: float, right: float) -> Dict[str, float]:
    """Turning shares; a three-arm case gives 0 to the missing arm."""
    return {"left": left, "straight": straight, "right": right}


def _document(
    name: str,
    approaches: Dict[str, Optional[Dict[str, Any]]],
    *,
    seed: int,
    duration: float,
    rings: Optional[int] = None,
    mix: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    doc: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": name,
        "junction": {"type": "roundabout"},
        "approaches": approaches,
        "simulation": {"duration": duration, "warmup": 20.0, "seed": seed},
    }
    if rings is not None:
        doc["roundabout"] = {"circulatingLanes": rings}
    if mix is not None:
        doc["vehicles"] = {"mix": dict(mix)}
    return doc


# The corpus. "fast" cases run in the ordinary CI job; the rest are slow.
# Demand: low ≈ 25 %, medium ≈ 60 %, saturated ≥ 100 % of what the layout
# discharges (judged from the existing lock-up and capacity tests).
CORPUS: List[Dict[str, Any]] = [
    {
        "id": "one-ring-4arm-cars-medium",
        "fast": True,
        "path": "direct",
        "document": _document(
            "one-ring 4-arm cars medium",
            {d: _arm(1, 300) for d in ("north", "south", "east", "west")},
            seed=1,
            duration=120,
        ),
    },
    {
        "id": "two-ring-4arm-urban-mix-medium",
        "fast": True,
        "path": "direct",
        "document": _document(
            "two-ring 4-arm urban mix medium",
            {d: _arm(2, 550) for d in ("north", "south", "east", "west")},
            seed=2,
            duration=120,
            rings=2,
            mix=URBAN_MIX,
        ),
    },
    {
        "id": "one-ring-3arm-low",
        "fast": True,
        "path": "direct",
        "document": _document(
            "one-ring 3-arm low",
            {
                "north": _arm(1, 150, turning=_turning(0.5, 0.5, 0.0)),
                "south": _arm(1, 150, turning=_turning(0.0, 0.5, 0.5)),
                "east": _arm(1, 150, turning=_turning(0.5, 0.0, 0.5)),
                "west": None,
            },
            seed=3,
            duration=120,
        ),
    },
    {
        "id": "study-path-two-ring-medium",
        "fast": True,
        "path": "study",
        "document": _document(
            "study path two-ring medium",
            {d: _arm(2, 500) for d in ("north", "south", "east", "west")},
            seed=4,
            duration=120,
            rings=2,
        ),
    },
    {
        "id": "merging-entry-one-ring",
        "fast": False,
        "path": "direct",
        "document": _document(
            "two-lane approaches into a one-lane ring",
            {d: _arm(2, 350) for d in ("north", "south", "east", "west")},
            seed=5,
            duration=180,
            rings=1,
        ),
    },
    {
        "id": "two-ring-heavy-mix-saturated",
        "fast": False,
        "path": "direct",
        "document": _document(
            "two-ring heavy mix saturated",
            {d: _arm(2, 1000) for d in ("north", "south", "east", "west")},
            seed=6,
            duration=180,
            rings=2,
            mix=HEAVY_MIX,
        ),
    },
    {
        "id": "three-lane-approaches-uneven",
        "fast": False,
        "path": "direct",
        "document": _document(
            "three-lane approaches, uneven demand",
            {
                "north": _arm(3, 900),
                "south": _arm(3, 300),
                "east": _arm(2, 600),
                "west": _arm(2, 200),
            },
            seed=7,
            duration=180,
            rings=2,
            mix=URBAN_MIX,
        ),
    },
    {
        "id": "main-road-side-street-skewed",
        "fast": False,
        "path": "direct",
        "document": _document(
            "two-lane main road, one-lane side street, skewed arms",
            {
                "north": _arm(2, 700, bearing=10.0),
                "south": _arm(2, 700),
                "east": _arm(1, 250, bearing=100.0),
                "west": _arm(1, 250, length=150.0),
            },
            seed=8,
            duration=180,
            rings=2,
        ),
    },
    {
        "id": "one-ring-3arm-saturated-study",
        "fast": False,
        "path": "study",
        "document": _document(
            "one-ring 3-arm saturated, study path",
            {
                "north": _arm(1, 700, turning=_turning(0.5, 0.0, 0.5)),
                "south": None,
                "east": _arm(1, 700, turning=_turning(0.0, 0.5, 0.5)),
                "west": _arm(1, 700, turning=_turning(0.5, 0.5, 0.0)),
            },
            seed=9,
            duration=180,
            mix=URBAN_MIX,
        ),
    },
]


def compile_case(case: Dict[str, Any]) -> Dict[str, Any]:
    """The engine configuration of a corpus case (validated first)."""
    document, errors = parse_scenario(case["document"])
    assert document is not None and not errors, (case["id"], errors)
    report = validate_scenario(case["document"], ["roundabout"])
    assert report["valid"], (case["id"], report["errors"])
    return compile_scenario(document, "roundabout")


def _build(config: Dict[str, Any], path: str) -> Any:
    """(engine, collector, builder) for one roundabout run on *path*."""
    if path == "direct":
        clock = Clock(time_step=float(config["simulation"]["timeStep"]))
        engine = SimulationEngine(
            clock, duration=config["simulation"]["duration"], config=config
        )
        controller = create_controller(config, engine.network)
        engine.controller = controller
        collector = MetricCollector(config)
        engine.register_tick_callback(
            build_tick_callback(controller, clock, engine, collector)
        )
        builder = SnapshotBuilder("golden", "golden", engine, collector, controller)
        return engine, collector, builder
    if path == "study":
        orch = DualSimulationOrchestrator(config)
        return (
            orch.engine_roundabout,
            orch.collector_roundabout,
            orch.builder_roundabout,
        )
    raise ValueError(f"unknown path {path!r}")


def fingerprint_run(config: Dict[str, Any], path: str) -> Dict[str, Any]:
    """Run *config* on *path* once; return ``{"portable": ..., "exact": ...}``
    (see the module docstring)."""
    config = copy.deepcopy(config)
    # A collision logs a warning per event; a lock-up can log thousands.
    logging.getLogger("src.engine.vehicle_pool").setLevel(logging.ERROR)
    engine, collector, builder = _build(config, path)
    traj_portable, traj_exact = hashlib.sha256(), hashlib.sha256()
    snap_portable, snap_exact = hashlib.sha256(), hashlib.sha256()
    ticks = engine.clock.ticks_for_duration(config["simulation"]["duration"])
    for tick in range(1, ticks + 1):
        engine.step()
        traj_portable.update(f"t{tick}".encode())
        traj_exact.update(f"t{tick}".encode())
        for v in engine.pool.active_vehicles:
            lane_id = v.lane.lane_id if v.lane is not None else ""
            position, speed = float(v.position), float(v.speed)
            traj_portable.update(
                f"|{v.vehicle_id}|{lane_id}|{position:.{TRAJECTORY_DECIMALS}f}"
                f"|{speed:.{TRAJECTORY_DECIMALS}f}".encode()
            )
            traj_exact.update(
                f"|{v.vehicle_id}|{lane_id}|{position.hex()}|{speed.hex()}".encode()
            )
        if tick % SNAPSHOT_EVERY == 0:
            snap = builder.build()
            snap.pop("wallClockTime", None)
            snap_portable.update(_portable_json(snap).encode() + b"\n")
            snap_exact.update(canonical_json(snap).encode() + b"\n")
    metrics = engine_metrics(engine, collector)
    return {
        "portable": {
            "trajectory": traj_portable.hexdigest(),
            "metrics": hashlib.sha256(_portable_json(metrics).encode()).hexdigest(),
            "snapshots": snap_portable.hexdigest(),
            "ticks": ticks,
            "exited": len(engine.pool.exited_vehicles),
            "collisions": int(engine.pool.collision_count),
        },
        "exact": {
            "trajectory": traj_exact.hexdigest(),
            "metrics": hashlib.sha256(canonical_json(metrics).encode()).hexdigest(),
            "snapshots": snap_exact.hexdigest(),
        },
    }


def load_fixture() -> Dict[str, Any]:
    with open(FIXTURE, encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)
    assert data["format"] == FIXTURE_FORMAT and data["version"] == FIXTURE_VERSION
    return data


def _git_head() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).resolve().parent,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return out.stdout.strip()


def _write(data: Dict[str, Any]) -> None:
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    with open(FIXTURE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"wrote {FIXTURE}")


def record(force: bool) -> None:
    if FIXTURE.exists() and not force:
        sys.exit(
            f"{FIXTURE} exists. Re-recording discards the 'before' side of the "
            "ADR-014 bit-identity test; pass --force only with a recorded reason."
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
                "Conventional-roundabout fingerprints recorded from the "
                "controller before the ADR-014 EntryGate seam. See "
                "tests/controllers/roundabout_golden.py."
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
