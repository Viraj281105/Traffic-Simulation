"""End-to-end V2.0 demo against a running backend (tiny simulations, ~1 min).

    cd backend && DEV_AUTH_BYPASS=1 python -m uvicorn src.main:app --port 8000
    python scripts/v2_demo.py [http://localhost:8000]

Prints each step and the evidence it produced. Exit code 1 on any failure.
"""

import json
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
HEADERS = {
    "Authorization": "Bearer urbanflow-local-dev",  # needs DEV_AUTH_BYPASS=1
    "Content-Type": "application/json",
}

SCENARIO = {
    "format": "urbanflow-scenario",
    "version": 1,
    "name": "Demo junction",
    "junction": {"type": "fixed_time_signal"},
    "approaches": {
        d: {"lanes": 1, "vehiclesPerHour": 300}
        for d in ("north", "south", "east", "west")
    },
    "simulation": {"duration": 60, "warmup": 10, "seed": 5},
}
OBSERVATIONS = {
    "format": "urbanflow-observations",
    "version": 1,
    "name": "Demo count",
    "period": {"label": "08:00-09:00", "durationSeconds": 3600},
    "approachFlows": [
        {"approach": "north", "vehiclesPerHour": 360},
        {"approach": "east", "vehiclesPerHour": 280},
    ],
}


def call(method, path, body=None, raw=False):
    req = urllib.request.Request(
        BASE + path,
        method=method,
        headers=HEADERS,
        data=None if body is None else json.dumps(body).encode(),
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            text = resp.read().decode()
    except urllib.error.HTTPError as err:
        sys.exit(f"FAIL {method} {path}: {err.code} {err.read().decode()[:400]}")
    return text if raw else json.loads(text)


def step(n, title):
    print(f"\n[{n}] {title}")


step(1, "Define a scenario and see it in the network model")
net = call("POST", "/api/v2/networks/from-scenario", {"scenario": SCENARIO})
print(f"    network valid={net['valid']} fingerprint={net['fingerprint']} "
      f"nodes={len(net['network']['nodes'])} routes={len(net['network']['routes'])}")

step(2, "Calibrate against observed counts (V1.8), fit observed demand")
cal = call("POST", "/api/v2/calibration/runs", {
    "scenario": SCENARIO, "observations": OBSERVATIONS,
    "options": {"seeds": 2, "baseSeed": 1, "fit": ["demand"]}})
run_id = cal["id"]
print(f"    run {run_id} fieldCalibration={cal['result']['fieldCalibration']['status']}")
for c in cal["result"]["caveats"][:2]:
    print("    caveat:", c)

step(3, "Planning study (V2.0): 3 alternatives on the fitted scenario")
study = {
    "name": "Demo study", "objective": "compare control options",
    "subject": {}, "calibration": {"runId": run_id, "useFittedScenario": True},
    "alternatives": [
        {"id": "base", "label": "Fixed-time", "strategy": "fixed_time"},
        {"id": "adaptive", "label": "Adaptive", "strategy": "adaptive"},
        {"id": "rbt", "label": "Roundabout", "strategy": "roundabout"},
    ],
    "demand": {"scales": [1.0]},
    "repetitions": {"seeds": 3, "baseSeed": 1},
}
check = call("POST", "/api/v2/planning/validate", study)
print(f"    valid={check['valid']} simulations={check.get('simulations')}")
done = call("POST", "/api/v2/planning/run", study)
sid, res = done["id"], done["result"]
for row in res["results"]:
    v = row["performance"]["values"]
    print(f"    {row['alternativeId']:9s} delay={v['averageDelay']['mean']:.1f}s "
          f"throughput={v['throughput']['mean']:.0f} "
          f"safety={row['safety']['status']} env={row['environmental']['status']}")

step(4, "Evidence-based findings")
for f in res["findings"][:5]:
    print(f"    [{f['confidence']}] {f['statement']}")

step(5, "Reproducibility")
m = res["meta"]
print(f"    commit={m['gitCommit']} scenario={m['scenarioFingerprint']} "
      f"calibration={m['calibrationRunId']} network={m['networkFingerprint']}")
rep = call("POST", f"/api/v2/planning/{sid}/reproduce")
print(f"    reproduced={rep['reproduced']}")

step(6, "Machine-readable export")
for fmt in ("json", "md", "csv"):
    text = call("GET", f"/api/v2/planning/{sid}/report?format={fmt}", raw=True)
    print(f"    {fmt}: {len(text)} bytes")
print("\nOK")
