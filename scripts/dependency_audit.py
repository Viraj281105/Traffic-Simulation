#!/usr/bin/env python3
"""Offline audit of the backend requirement files (package 2F). Standard library only, no network.

Checks, per file:

* every requirement is pinned with ``==`` (error);
* no package appears twice, names compared after normalisation (error);
* the pinned version is not below the fixed version in ``RISKY`` below (error), and packages that
  are abandoned or known to be a poor fit are flagged (warning).

``--installed`` also compares the pins with ``pip list`` of the current interpreter (error for a
different version, warning for a missing package).

``RISKY`` is a small CURATED table, written by hand with the date each entry was added. It is not
a vulnerability database: an empty report means "none of these known patterns", not "no known
CVEs". Run a real scanner (pip-audit, OSV, Dependabot) for that; see docs/security/review-v5.3.md.

Usage:
    python scripts/dependency_audit.py [--installed] [--strict] [--all] [FILE ...]

Exit status: 0 clean, 1 errors (or warnings with --strict), 2 unreadable input.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
DEFAULT_FILES = ("requirements.txt",)
ALL_FILES = ("requirements.txt", "requirements-dev.txt", "requirements-rl.txt")


@dataclass(frozen=True)
class Risk:
    """``fixed_in`` None means no release is fixed: any version is flagged."""

    package: str
    fixed_in: Optional[str]
    severity: str  # "error" or "warning"
    note: str
    added: str  # ISO date the entry was written


RISKY: Tuple[Risk, ...] = (
    Risk("python-jose", None, "error", "GHSA-3qf3-8w2g-rqmx algorithm confusion, no fix; "
         "the repo moved to PyJWT (F-33)", "2026-11-05"),
    Risk("ecdsa", None, "error", "GHSA-wj6h-64fc-37mp, no fixed release", "2026-11-05"),
    Risk("pycrypto", None, "error", "unmaintained since 2013; use cryptography", "2026-11-05"),
    Risk("requests", "2.32.0", "error", "CVE-2024-35195 session verify=False persists", "2026-11-05"),
    Risk("urllib3", "2.2.2", "error", "CVE-2024-37891 Proxy-Authorization header leak", "2026-11-05"),
    Risk("cryptography", "42.0.4", "error", "CVE-2024-26130 NULL deref in PKCS12", "2026-11-05"),
    Risk("starlette", "0.40.0", "error", "CVE-2024-47874 multipart form DoS", "2026-11-05"),
    Risk("python-multipart", "0.0.18", "error", "CVE-2024-53981 boundary parsing DoS", "2026-11-05"),
    Risk("pyyaml", "5.4", "error", "CVE-2020-14343 arbitrary code via full_load", "2026-11-05"),
    Risk("jinja2", "3.1.4", "error", "CVE-2024-34064 xmlattr key injection", "2026-11-05"),
    Risk("certifi", "2023.7.22", "error", "removed e-Tugra root certificates (CVE-2023-37920)", "2026-11-05"),
    Risk("boto3", "1.35.0", "warning", "older than two years; refresh with botocore and "
         "s3transfer (not a CVE claim)", "2026-11-05"),
    Risk("botocore", "1.35.0", "warning", "pinned with boto3; same remark", "2026-11-05"),
    Risk("nose", None, "warning", "unmaintained; use pytest", "2026-11-05"),
)

_LINE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*(?P<spec>[^;#]*)"
)
_PIN = re.compile(r"^==\s*([A-Za-z0-9.!+_-]+)\s*$")


@dataclass(frozen=True)
class Requirement:
    name: str
    version: Optional[str]
    spec: str
    line: int
    file: str


@dataclass(frozen=True)
class Finding:
    level: str  # "error" or "warning"
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper():7} {self.where}: {self.message}"


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def version_key(version: str) -> Tuple[int, ...]:
    """Numeric release segments only; a suffix such as rc1 or post1 is ignored."""
    parts: List[int] = []
    for piece in version.split("+")[0].split("."):
        match = re.match(r"\d+", piece)
        if not match:
            break
        parts.append(int(match.group()))
    return tuple(parts)


def parse_requirements(text: str, file: str = "requirements.txt") -> List[Requirement]:
    found: List[Requirement] = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split(" #", 1)[0].strip()
        if not line or line.startswith(("#", "-")):
            continue
        match = _LINE.match(line)
        if not match:
            found.append(Requirement(line, None, "", number, file))
            continue
        spec = match.group("spec").strip()
        pin = _PIN.match(spec)
        found.append(
            Requirement(
                match.group("name"), pin.group(1) if pin else None, spec, number, file
            )
        )
    return found


def check_requirements(reqs: Sequence[Requirement]) -> List[Finding]:
    findings: List[Finding] = []
    seen: Dict[str, Requirement] = {}
    for req in reqs:
        where = f"{req.file}:{req.line}"
        key = normalise(req.name)
        if req.version is None:
            shown = req.spec or "no version"
            findings.append(
                Finding("error", where, f"{req.name} is not pinned with == ({shown})")
            )
        if key in seen:
            findings.append(
                Finding(
                    "error",
                    where,
                    f"{req.name} listed twice (first at line {seen[key].line})",
                )
            )
        else:
            seen[key] = req
    for req in seen.values():
        findings.extend(_risk_findings(req))
    return findings


def _risk_findings(req: Requirement) -> List[Finding]:
    out: List[Finding] = []
    for risk in RISKY:
        if normalise(risk.package) != normalise(req.name):
            continue
        where = f"{req.file}:{req.line}"
        if risk.fixed_in is None:
            out.append(Finding(risk.severity, where, f"{req.name}: {risk.note} (curated {risk.added})"))
        elif req.version is not None and version_key(req.version) < version_key(
            risk.fixed_in
        ):
            out.append(
                Finding(
                    risk.severity,
                    where,
                    f"{req.name}=={req.version} is below {risk.fixed_in}: {risk.note} "
                    f"(curated {risk.added})",
                )
            )
    return out


def installed_versions() -> Dict[str, str]:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "list", "--format=json", "--disable-pip-version-check"],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return {normalise(p["name"]): p["version"] for p in json.loads(result.stdout)}


def compare_installed(
    reqs: Sequence[Requirement], installed: Dict[str, str]
) -> List[Finding]:
    findings: List[Finding] = []
    for req in reqs:
        if req.version is None:
            continue
        have = installed.get(normalise(req.name))
        where = f"{req.file}:{req.line}"
        if have is None:
            findings.append(Finding("warning", where, f"{req.name} is pinned but not installed"))
        elif have != req.version:
            findings.append(
                Finding("error", where, f"{req.name} pinned {req.version}, installed {have}")
            )
    return findings


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("files", nargs="*", help="requirement files (default: backend/requirements.txt)")
    parser.add_argument("--installed", action="store_true", help="compare with pip list")
    parser.add_argument("--strict", action="store_true", help="warnings fail the run")
    parser.add_argument("--all", action="store_true", help="also check the dev and rl files")
    args = parser.parse_args(argv)

    names = args.files or list(ALL_FILES if args.all else DEFAULT_FILES)
    paths = [Path(n) if Path(n).is_absolute() or Path(n).exists() else BACKEND / n for n in names]
    findings: List[Finding] = []
    all_reqs: List[Requirement] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"cannot read {path}: {exc}", file=sys.stderr)
            return 2
        reqs = parse_requirements(text, path.name)
        all_reqs.extend(reqs)
        findings.extend(check_requirements(reqs))
        print(f"{path.name}: {len(reqs)} requirements")
    if args.installed:
        try:
            findings.extend(compare_installed(all_reqs, installed_versions()))
        except (subprocess.SubprocessError, OSError, ValueError) as exc:
            print(f"cannot run pip list: {exc}", file=sys.stderr)
            return 2
    for finding in findings:
        print(finding)
    errors = sum(f.level == "error" for f in findings)
    warnings = len(findings) - errors
    print(f"{errors} error(s), {warnings} warning(s)")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
