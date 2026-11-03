"""Build the preview fallback pack: precomputed planning studies with exports and checksums (task B0-3).

    cd backend && DEV_AUTH_BYPASS=1 python -m uvicorn src.main:app --port 8765
    python scripts/build_fallback_pack.py [http://localhost:8765] [output-dir]
    python scripts/build_fallback_pack.py --verify [pack-dir]

For each study in STUDIES it runs the planning study, checks that `reproduce` returns the same result,
saves the JSON / Markdown / CSV exports, then writes MANIFEST.json (commit, Python version, timings)
and SHA256SUMS. Generate the final pack on the frozen preview commit; a pack from any other commit is
a rehearsal pack. Exit code 1 on any failure.

Files are written with LF line endings and hashed with CRLF normalised to LF (as scripts/v3_demo.py
does), so a pack checked out, zipped or edited on Windows still verifies; any other change does not.
"""

import hashlib
import json
import platform
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

VERIFY = sys.argv[1:2] == ["--verify"]
ARGS = sys.argv[2:] if VERIFY else sys.argv[1:]
if VERIFY:
    BASE, OUT = "", Path(ARGS[0] if ARGS else "fallback-pack")
else:
    BASE = (ARGS[0] if ARGS else "http://localhost:8765").rstrip("/")
    OUT = Path(ARGS[1] if len(ARGS) > 1 else "fallback-pack")
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


def digest(path):
    """SHA-256 with line endings normalised to LF."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def write(path, text):
    path.write_text(text, encoding="utf-8", newline="\n")


def verify(pack):
    """Check every file listed in SHA256SUMS; return the number that differ."""
    bad = 0
    for line in (pack / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        want, name = line.split(None, 1)
        if digest(pack / name) != want:
            print(f"MISMATCH {name}")
            bad += 1
    return bad


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
        write(d / "study.json", json.dumps(payload, indent=2))
        for fmt, ext in (("json", "json"), ("md", "md"), ("csv", "csv")):
            text = call("GET", f"/api/v2/planning/{sid}/report?format={fmt}", raw=True)
            write(d / f"report.{ext}", text)
        meta = res["meta"]
        manifest["studies"].append({
            "slug": slug, "studyId": sid, "runSeconds": seconds, "reproduced": True,
            "gitCommit": meta.get("gitCommit"), "scenarioFingerprint": meta.get("scenarioFingerprint"),
        })
        print(f"{slug}: id={sid} {seconds}s reproduced=True")
    write(OUT / "MANIFEST.json", json.dumps(manifest, indent=2))
    lines = []
    for p in sorted(OUT.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS":
            lines.append(f"{digest(p)}  {p.relative_to(OUT).as_posix()}")
    write(OUT / "SHA256SUMS", "\n".join(lines) + "\n")
    print(f"\nOK: {len(lines)} files in {OUT} (commit {version.get('gitCommit')})")


if __name__ == "__main__":
    if VERIFY:
        failures = verify(OUT)
        print("checksums verified" if not failures else f"{failures} file(s) changed")
        sys.exit(1 if failures else 0)
    main()
