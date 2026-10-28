"""Record real engine trajectories for the landing page's simulation scene.

    cd backend && .venv/Scripts/python.exe ../scripts/record_landing_scene.py

Runs the same scenario (same seed, same demand) once per control strategy on
the real engine, headlessly, and writes frontend/src/landing/data/scene.json:
vehicle positions and signal state for a window of the run, a once-a-second
queue and throughput series for the whole run, and the headline metrics the
engine reports at the end of each run. Nothing here is estimated: the page
replays these frames. Provenance (git commit, seed, scenario) is stored in the
file so the claim "recorded from the engine" can be checked.

One seed and a short duration: the numbers describe this single run, not a
statistical result.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from src.engine.readout import engine_metrics  # noqa: E402
from src.scenario.documents import compile_scenario, parse_scenario  # noqa: E402
from src.simulations.registry import register_simulation  # noqa: E402
from src.snapshot.builder import SnapshotBuilder  # noqa: E402

OUT = ROOT / "frontend" / "src" / "landing" / "data" / "scene.json"
SEED = 5
DURATION = 150
WARMUP = 30
VPH_PER_ARM = 520
SAMPLE = 0.5  # seconds of simulated time between recorded frames
WINDOW = (40.0, 100.0)  # the stretch of each run the page replays

STRATEGIES = [
    ("fixed_time", "Fixed-time signal"),
    ("adaptive", "Adaptive signal"),
    ("roundabout", "Conventional roundabout"),
    ("metered_entry_roundabout", "Metered-entry roundabout"),
]

# A roundabout whose entries are signal-metered (as in
# scripts/benchmark_signalised_roundabout.py): two alternating phases.
METERED = {
    "entryControl": "metered_entry",
    "entryMetering": {
        "phases": [
            {"entries": ["north", "south"], "green": 20.0},
            {"entries": ["east", "west"], "green": 20.0},
        ],
        "yellow": 3.0,
        "allRed": 2.0,
    },
}

SCENARIO = {
    "format": "urbanflow-scenario",
    "version": 1,
    "name": "Landing scene junction",
    "junction": {"type": "fixed_time_signal"},
    "approaches": {
        d: {"lanes": 1, "vehiclesPerHour": VPH_PER_ARM}
        for d in ("north", "south", "east", "west")
    },
    "simulation": {"duration": DURATION, "warmup": WARMUP, "seed": SEED},
}

METRIC_KEYS = [
    "averageDelay",
    "p95Delay",
    "throughput",
    "maxQueueLength",
    "averageQueueLength",
    "averageStopsPerVehicle",
    "directionalFairnessIndex",
    "averageTravelSpeed",
    "collisionCount",
    "nearMissCount",
    "totalVehiclesSpawned",
]


def vehicle_number(vehicle_id: str) -> int:
    return int(str(vehicle_id).split("_")[-1])


def control_state(controller: dict) -> dict:
    """What the page needs to draw the control: signal colours or metering."""
    out: dict = {}
    if "signals" in controller:
        out["signals"] = controller["signals"]
        out["phase"] = controller.get("currentPhase")
    if "metering" in controller:
        out["metering"] = controller["metering"]
    return out


def record(strategy: str) -> dict:
    scenario = json.loads(json.dumps(SCENARIO))
    compile_as = strategy
    if strategy == "metered_entry_roundabout":
        scenario["roundabout"] = METERED
        compile_as = "roundabout"
    parsed, errors = parse_scenario(scenario)
    assert not errors, errors
    entry = register_simulation(compile_scenario(parsed, compile_as))
    engine, collector = entry["engine"], entry["collector"]
    builder = SnapshotBuilder(
        "landing", "landing", engine, collector, entry["controller"]
    )
    step = engine.clock.time_step
    frame_every = max(1, round(SAMPLE / step))
    series_every = max(1, round(1.0 / step))
    frames: list = []
    series: list = []
    geometry: dict = {}
    while engine.clock.get_elapsed_time() < DURATION:
        engine.step()
        tick = engine.clock.get_tick_count()
        want_frame = tick % frame_every == 0
        want_series = tick % series_every == 0
        if not (want_frame or want_series):
            continue
        snap = builder.build()
        t = snap["timestamp"]
        if want_series:
            queues = snap["metrics"].get("currentQueueLengths", {})
            series.append(
                [round(t), sum(queues.values()), snap["vehicleCounts"]["exited"]]
            )
        if want_frame and WINDOW[0] <= t <= WINDOW[1]:
            if not geometry:
                c = snap["controller"]
                geometry = {
                    k: c[k]
                    for k in ("innerRadius", "outerRadius", "circulatingLanes")
                    if k in c
                }
            frames.append(
                {
                    "t": t,
                    # id, x, y, heading, speed, type
                    "v": [
                        [
                            vehicle_number(v["id"]),
                            round(v["x"], 1),
                            round(v["y"], 1),
                            round(v["heading"]),
                            round(v["speed"], 1),
                            v["vehicleType"],
                        ]
                        for v in snap["vehicles"]
                        if v["state"] != "exited"
                    ],
                    "c": control_state(snap["controller"]),
                }
            )
    metrics = engine_metrics(engine, collector)
    return {
        "geometry": geometry,
        "frames": frames,
        "series": series,
        "metrics": {k: metrics.get(k) for k in METRIC_KEYS},
    }


def write_evidence() -> None:
    """The precomputed 3-seed planning study (fallback-pack) as a slim file."""
    src = ROOT / "fallback-pack" / "medium-precomputed" / "report.json"
    report = json.loads(src.read_text(encoding="utf-8"))
    labels = {a["id"]: a["label"] for a in report["alternatives"]}
    rows = []
    for r in report["results"]:
        d = r["performance"]["values"]["averageDelay"]
        rows.append(
            {
                "alt": r["alternativeId"],
                "scale": r["demandScale"],
                "vph": r["demandVph"],
                "mean": d["mean"],
                "ciLow": d["ciLow"],
                "ciHigh": d["ciHigh"],
                "n": d["n"],
            }
        )
    deltas = [
        {
            "alt": c["alternativeId"],
            "scale": c["demandScale"],
            "delta": c["delta"],
            "ciLow": c["ciLow"],
            "ciHigh": c["ciHigh"],
            "verdict": c["verdict"],
            "n": c["n"],
        }
        for c in report["comparison"]["vsBaseline"]
        if c["metric"] == "averageDelay"
    ]
    out = ROOT / "frontend" / "src" / "landing" / "data" / "evidence.json"
    out.write_text(
        json.dumps(
            {
                "source": "fallback-pack/medium-precomputed/report.json",
                "study": report["name"],
                "gitCommit": report["meta"]["gitCommit"],
                "seeds": report["reliability"]["repetitions"],
                "durationSeconds": report["meta"]["duration"],
                "baseline": report["comparison"]["baselineId"],
                "labels": labels,
                "rows": rows,
                "deltas": deltas,
                "findings": len(report["findings"]),
                "flags": [f["message"] for f in report["reliability"]["flags"]],
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    print("wrote", out)


def main() -> None:
    write_evidence()
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    runs = {}
    for strategy, label in STRATEGIES:
        print("recording", strategy, flush=True)
        runs[strategy] = {"label": label, **record(strategy)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "provenance": {
                    "recordedWith": "backend engine, headless, single seed",
                    "gitCommit": commit,
                    "seed": SEED,
                    "durationSeconds": DURATION,
                    "warmupSeconds": WARMUP,
                    "vehiclesPerHourPerArm": VPH_PER_ARM,
                    "frameSeconds": SAMPLE,
                    "window": list(WINDOW),
                    "scenario": SCENARIO,
                },
                "runs": runs,
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    print("wrote", OUT, OUT.stat().st_size // 1024, "KiB")


if __name__ == "__main__":
    main()
