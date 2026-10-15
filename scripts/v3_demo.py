"""V3.0 Robustness Lab demo: 24 sampled conditions x 3 alternatives, submitted through /api/v3.

Live (needs a running backend; a few minutes, depending on the machine):

    cd backend && DEV_AUTH_BYPASS=1 python -m uvicorn src.main:app --port 8000
    python scripts/v3_demo.py [http://localhost:8000] [--verify] [--save DIR]

Fallback (no backend, no simulation): print a result saved earlier, after checking its checksums:

    python scripts/v3_demo.py --offline docs/research/examples/robustness-demo

The study compares a fixed-time signal, an adaptive signal and a conventional roundabout on one
junction while demand, turning shares, vehicle mix and driver headway vary over assumed ranges.
`--verify` submits the same experiment a second time and checks that the result fingerprint is
identical. `--save DIR` writes experiment.json, result.json, MANIFEST.json and SHA256SUMS.

Standard library only. Exit code 1 on any failure. Every number printed comes from the server's
result document; this script computes nothing but column widths.
"""

import argparse
import hashlib
import json
import platform
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEV_TOKEN = "urbanflow-local-dev"  # needs DEV_AUTH_BYPASS=1 on the backend
FILES = ("experiment.json", "result.json")

SCENARIO = {
    "format": "urbanflow-scenario",
    "version": 1,
    "name": "Demo junction (600 veh/h per arm)",
    "junction": {"type": "fixed_time_signal"},
    "approaches": {
        d: {
            "lanes": 1,
            "vehiclesPerHour": 600,
            "turning": {"left": 0.2, "straight": 0.6, "right": 0.2},
        }
        for d in ("north", "south", "east", "west")
    },
    "vehicles": {
        "mix": {"car": 0.7, "suv": 0.1, "bus": 0.05, "truck": 0.1, "motorcycle": 0.05}
    },
    # 105 s are measured after warm-up: enough for vehicles to finish trips at this demand.
    "simulation": {"duration": 120, "warmup": 15, "seed": 5},
}

EXPERIMENT = {
    "format": "urbanflow-experiment",
    "version": 1,
    "name": "Demo: does the preferred control survive uncertainty?",
    "scenario": SCENARIO,
    "alternatives": [
        {"id": "fixed", "label": "Fixed-time signal", "strategy": "fixed_time"},
        {"id": "adaptive", "label": "Adaptive signal", "strategy": "adaptive"},
        {"id": "roundabout", "label": "Conventional roundabout", "strategy": "roundabout"},
    ],
    "baseline": "fixed",
    "uncertainty": {
        "name": "Peak-hour uncertainty (assumed ranges)",
        "conditions": 24,
        "replications": 2,
        "seed": 2026,
        "primaryIndicator": "averageDelay",
        "factors": [
            {
                "id": "demand",
                "kind": "demand_scale",
                "distribution": {"kind": "uniform"},
                "bounds": [0.7, 1.3],
                "basis": "assumed",
                "rationale": "Peak-hour flow varies by about 30 % either way between days.",
            },
            {
                "id": "turning",
                "kind": "turning_shift",
                "distribution": {"kind": "triangular", "mode": 0.0},
                "bounds": [-0.3, 0.3],
                "basis": "assumed",
                "rationale": "Turning shares drift with local events; most days stay near the counted split.",
            },
            {
                "id": "heavy",
                "kind": "mix_shift",
                "distribution": {"kind": "uniform"},
                "bounds": [-0.4, 0.4],
                "basis": "assumed",
                "rationale": "The share of buses and trucks changes between weekdays.",
            },
            {
                "id": "headway",
                "kind": "headway_scale",
                "distribution": {"kind": "triangular", "mode": 1.0},
                "bounds": [0.8, 1.3],
                "basis": "assumed",
                "rationale": "Driver behaviour is uncertain; headway scale is a proxy, not a measured reaction time.",
            },
        ],
    },
}


# ── transport ──────────────────────────────────────────────────────────────


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    def call(self, method: str, path: str, body=None):
        request = urllib.request.Request(
            self.base + path,
            method=method,
            headers={
                "Authorization": f"Bearer {DEV_TOKEN}",
                "Content-Type": "application/json",
            },
            data=None if body is None else json.dumps(body).encode(),
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as err:
            fail(f"{method} {path}: HTTP {err.code} {err.read().decode()[:600]}")
        except urllib.error.URLError as err:
            fail(f"cannot reach {self.base} ({err.reason}); start the backend, or use --offline")


def fail(message: str) -> None:
    print(f"FAIL {message}", file=sys.stderr)
    sys.exit(1)


def step(n: int, title: str) -> None:
    print(f"\n[{n}] {title}")


# ── report (all numbers are the server's) ──────────────────────────────────


def pct(p: float) -> str:
    return f"{p * 100:.0f}%"


def secs(value) -> str:
    if value is None:
        return "n/a"
    text = f"{abs(value):.2f}"
    return ("-" if value < 0 and float(text) != 0 else "") + text


def print_report(result: dict) -> None:
    a = result["analysis"]
    labels = {x["id"]: x["label"] or x["id"] for x in result["alternatives"]}
    counts = a["counts"]
    print(f"\n  Real-world validity: {a['realWorldValidity']}")
    print("  Every input range is an assumption; the simulation is not calibrated to observed traffic.")
    print(
        f"\n  {counts['conditions']} conditions x {counts['alternatives']} alternatives x "
        f"{counts['replications']} replications = {counts['totalRuns']} runs; "
        f"{counts['validConditions']} valid conditions (the unit of inference)."
    )
    excluded = a["exclusions"]
    if excluded["excluded"]:
        print(f"  Excluded: {excluded['excluded']} ({excluded['byReason']})")
    verdict = a["eligibility"]
    print(f"\n  Eligibility: {verdict['class'].upper()}")
    for c in verdict["criteria"]:
        mark = {True: "met", False: "NOT MET", None: "not assessed"}[c["passed"]]
        print(f"    - {c['id']:15s} {mark:13s} {c['detail']}")
    base = labels[a["baseline"]]
    print(f"\n  Against the baseline ({base}); lower {a['primaryIndicator']} is better.")
    print(f"  {'alternative':26s} {'better':>8s} {'tie':>8s} {'worse':>8s}   mean difference (95% interval)")
    for alt_id, alt in a["alternatives"].items():
        comparison = alt.get("comparison")
        if alt["isBaseline"] or not comparison:
            continue
        mean = comparison["difference"]["mean"]
        low, high = mean["ci"]
        print(
            f"  {labels[alt_id]:26s} {pct(comparison['win']['p']):>8s} "
            f"{pct(comparison['tie']['p']):>8s} {pct(comparison['loss']['p']):>8s}   "
            f"{secs(mean['value'])} s ({secs(low)} to {secs(high)})"
        )
        for key in ("win", "tie", "loss"):
            lo, hi = comparison[key]["ci"]
            print(f"      {key:5s} {comparison[key]['count']:3d} of {counts['validConditions']}  95% interval {pct(lo)} to {pct(hi)}")
    print(f"\n  {'alternative':26s} {'mean regret':>12s} {'p95 regret':>11s} {'pref. share':>12s}")
    for alt_id, alt in a["alternatives"].items():
        regret = alt.get("regret") or {}
        print(
            f"  {labels[alt_id]:26s} {secs(regret.get('mean')):>10s} s {secs(regret.get('p95')):>9s} s "
            f"{pct(alt['preferenceShare']) if 'preferenceShare' in alt else 'n/a':>12s}"
        )
    print("\n  Assumptions:")
    for s in result["assumptions"]:
        print(f"    - {s['kind']:20s} {s['bounds']}  [{s['basis']}] {s['rationale']}")
    prov = result["provenance"]
    print(
        f"\n  Provenance: commit {prov['gitCommit'][:12]}, Python {prov['pythonVersion']}, "
        f"spec {result['specFingerprint']}, result {result['resultFingerprint']}"
    )
    print("  Win/tie/loss are descriptive comparisons, not a ranking; nothing here names a winner.")


# ── saving and the offline fallback ─────────────────────────────────────────


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(folder: Path, experiment: dict, result: dict, verified, base: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "experiment.json").write_bytes(
        (json.dumps(experiment, indent=2, sort_keys=True) + "\n").encode()
    )
    (folder / "result.json").write_bytes(
        (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    )
    manifest = {
        "what": "Precomputed V3.0 Robustness Lab demo result (fallback; not a live run)",
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "gitCommit": result["provenance"]["gitCommit"],
        "pythonVersion": result["provenance"]["pythonVersion"],
        "platform": platform.platform(),
        "backend": base,
        "specFingerprint": result["specFingerprint"],
        "resultFingerprint": result["resultFingerprint"],
        "wallSeconds": result["execution"]["wallSeconds"],
        "workers": result["execution"]["workers"],
        "rerunReproducedFingerprint": verified,
        "note": "Exact replay needs the same commit, Python minor version, dependency pins and CPU class.",
    }
    (folder / "MANIFEST.json").write_bytes((json.dumps(manifest, indent=2) + "\n").encode())
    lines = [f"{sha256(folder / n)}  {n}" for n in (*FILES, "MANIFEST.json")]
    (folder / "SHA256SUMS").write_bytes(("\n".join(lines) + "\n").encode())
    print(f"    saved to {folder}")


def offline(folder: Path) -> None:
    sums = folder / "SHA256SUMS"
    if not sums.is_file():
        fail(f"{sums} not found")
    for line in sums.read_text().splitlines():
        digest, name = line.split(None, 1)
        if sha256(folder / name.strip()) != digest:
            fail(f"checksum mismatch for {name.strip()}: the saved file was changed")
    manifest = json.loads((folder / "MANIFEST.json").read_text())
    result = json.loads((folder / "result.json").read_text())
    print("OFFLINE: showing a precomputed result, not a live run.")
    print(f"  generated {manifest['generatedAt']} at commit {manifest['gitCommit'][:12]} "
          f"on {manifest['platform']}; checksums verified")
    print(f"  the live run took {manifest['wallSeconds']} s on {manifest['workers']} workers; "
          f"re-run reproduced the fingerprint: {manifest['rerunReproducedFingerprint']}")
    print_report(result)
    print("\nOK (offline)")


# ── live run ───────────────────────────────────────────────────────────────


def run_experiment(api: Api) -> dict:
    accepted = api.call("POST", "/api/v3/experiments", EXPERIMENT)
    experiment_id = accepted["id"]
    print(f"    experiment {experiment_id}  (page: /app/experiments/{experiment_id})")
    last = ""
    while True:
        status = api.call("GET", f"/api/v3/experiments/{experiment_id}")
        progress = status.get("progress")
        line = status["status"]
        if progress and progress.get("total"):
            line += f": {progress['completed']} of {progress['total']} simulations"
        if line != last:
            print(f"    {line}")
            last = line
        if status["status"] == "failed":
            fail(f"experiment failed: {status.get('error')}")
        if status["status"] == "completed":
            return api.call("GET", f"/api/v3/experiments/{experiment_id}/result")
        time.sleep(3)


def live(base: str, verify: bool, save_to: Path | None) -> None:
    api = Api(base)
    step(1, "What this server offers")
    capabilities = api.call("GET", "/api/v3/capabilities")
    on = [k for k, v in capabilities["features"].items() if v]
    print(f"    API v{capabilities['apiVersion']}, available: {', '.join(on)}")
    quotas = capabilities["quotas"]
    print(f"    quotas: {quotas['maxRunsPerExperiment']} runs, "
          f"{quotas['maxSimulationStepsPerExperiment']:,} engine steps per experiment")

    step(2, "Check the experiment without running it")
    check = api.call("POST", "/api/v3/experiments/validate", EXPERIMENT)
    if not check["valid"]:
        fail("; ".join(check["errors"]))
    c = check["counts"]
    print(f"    valid: {c['conditions']} conditions x {c['alternatives']} alternatives x "
          f"{c['replications']} replications = {c['totalRuns']} runs")
    for warning in check["warnings"]:
        print(f"    warning: {warning}")

    step(3, "Submit and follow it")
    started = time.monotonic()
    result = run_experiment(api)
    print(f"    finished in {time.monotonic() - started:.0f} s")

    step(4, "The result")
    print_report(result)

    verified = None
    if verify:
        step(5, "Run it again: the same inputs and seed must give the same fingerprint")
        again = run_experiment(api)
        verified = again["resultFingerprint"] == result["resultFingerprint"]
        print(f"    reproduced: {verified} ({result['resultFingerprint']} vs {again['resultFingerprint']})")
        if not verified:
            fail("the second run did not reproduce the result fingerprint")

    if save_to is not None:
        step(6 if verify else 5, "Save the fallback")
        save(save_to, EXPERIMENT, result, verified, base)
    print("\nOK")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("base", nargs="?", default="http://localhost:8000")
    parser.add_argument("--verify", action="store_true", help="submit twice and compare fingerprints")
    parser.add_argument("--save", type=Path, metavar="DIR", help="write the fallback files to DIR")
    parser.add_argument("--offline", type=Path, metavar="DIR", help="print a saved result; no backend")
    args = parser.parse_args()
    if args.offline:
        offline(args.offline)
    else:
        live(args.base, args.verify, args.save)


if __name__ == "__main__":
    main()
