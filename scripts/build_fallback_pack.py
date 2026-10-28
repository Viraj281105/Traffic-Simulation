"""Build the preview fallback pack: precomputed planning studies with exports and checksums (task B0-3).

    cd backend && DEV_AUTH_BYPASS=1 python -m uvicorn src.main:app --port 8765
    python scripts/build_fallback_pack.py [http://localhost:8765] [output-dir]

For each study in STUDIES it runs the planning study, checks that `reproduce` returns the same result,
saves the JSON / Markdown / CSV exports, then writes MANIFEST.json (commit, Python version, timings)
and SHA256SUMS. Generate the final pack on the frozen preview commit; a pack from any other commit is
a rehearsal pack. Exit code 1 on any failure.
"""

import hashlib
import json
import platform
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765").rstrip("/")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "fallback-pack")
HEADERS = {"Authorization": "Bearer urbanflow-local-dev", "Content-Type": "application/json"}

ALTERNATIVES = [
    {"id": "base", "label": "Fixed-time", "strategy": "fixed_time"},
    {"id": "adaptive", "label": "Adaptive", "strategy": "adaptive"},
    {"id": "rbt", "label": "Roundabout", "strategy": "roundabout"},
]


def scenario(name, duration, warmup, vph):
    return {
        "format": "urbanflow-scenario", "version": 1, "name": name,
        "junction": {"type": "fixed_time_signal"},
        "approaches": {d: {"lanes": 1, "vehiclesPerHour": vph} for d in ("north", "south", "east", "west")},
        "simulation": {"duration": duration, "warmup": warmup, "seed": 5},
    }


def study(slug, name, objective, scen, scales, seeds):
    return slug, {
        "name": name, "objective": objective, "subject": {"scenario": scen},
        "alternatives": ALTERNATIVES, "demand": {"scales": scales},
        "repetitions": {"seeds": seeds, "baseSeed": 1},
    }


STUDIES = [
    study("small-live", "Preview study (small, live-capable)", "compare control options at one demand level",
          scenario("Demo junction", 60, 10, 300), [1.0], 3),
    study("medium-precomputed", "Preview study (medium, precomputed)", "compare control options across three demand levels",
          scenario("Demo junction", 300, 30, 300), [0.8, 1.0, 1.2], 3),
]


def call(method, path, body=None, raw=False):
    req = urllib.request.Request(BASE + path, method=method, headers=HEADERS,
                                 data=None if body is None else json.dumps(body).encode())
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            text = resp.read().decode()
    except urllib.error.HTTPError as err:
        sys.exit(f"FAIL {method} {path}: {err.code} {err.read().decode()[:400]}")
    return text if raw else json.loads(text)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    version = call("GET", "/api/version")
    manifest = {
        "purpose": "Preview fallback pack (B0-3)",
        "generatedAtUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "backend": version,
        "host": {"platform": platform.platform(), "python": platform.python_version()},
        "studies": [],
    }
    for slug, payload in STUDIES:
        t0 = time.perf_counter()
        done = call("POST", "/api/v2/planning/run", payload)
        seconds = round(time.perf_counter() - t0, 2)
        sid, res = done["id"], done["result"]
        rep = call("POST", f"/api/v2/planning/{sid}/reproduce")
        if not rep.get("reproduced"):
            sys.exit(f"FAIL study {slug}: reproduce returned {rep}")
        d = OUT / slug
        d.mkdir(exist_ok=True)
        (d / "study.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        for fmt, ext in (("json", "json"), ("md", "md"), ("csv", "csv")):
            text = call("GET", f"/api/v2/planning/{sid}/report?format={fmt}", raw=True)
            (d / f"report.{ext}").write_text(text, encoding="utf-8")
        meta = res["meta"]
        manifest["studies"].append({
            "slug": slug, "studyId": sid, "runSeconds": seconds, "reproduced": True,
            "gitCommit": meta.get("gitCommit"), "scenarioFingerprint": meta.get("scenarioFingerprint"),
        })
        print(f"{slug}: id={sid} {seconds}s reproduced=True")
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    lines = []
    for p in sorted(OUT.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS":
            lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(OUT).as_posix()}")
    (OUT / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nOK: {len(lines)} files in {OUT} (commit {version.get('gitCommit')})")


if __name__ == "__main__":
    main()
