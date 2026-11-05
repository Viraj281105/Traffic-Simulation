"""Secrets scan over tracked files (package 2F).

Conservative on purpose: it looks for patterns that are secrets almost by definition (private key
blocks, AWS access key ids, JWT-shaped tokens, long literal bearer tokens, quoted passwords).
Every allow-list entry names the file and the reason. Skips when git is unavailable. Stdlib only.
The patterns are assembled from pieces so this file does not match itself.
"""

from __future__ import annotations

import fnmatch
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest

REPO = Path(__file__).resolve().parents[3]
MAX_BYTES = 1_000_000
_DASH = "-" * 5

RULES: Dict[str, "re.Pattern[str]"] = {
    "private-key": re.compile(_DASH + r"BEGIN (?:[A-Z]+ )?PRIVATE" + r" KEY" + _DASH),
    "aws-access-key-id": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "jwt": re.compile(
        r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
    ),
    "bearer-token": re.compile(r"[Bb]earer\s+[A-Za-z0-9._~+/-]{32,}={0,2}"),
    "quoted-password": re.compile(
        r"""(?i)(?<![a-z])(?:password|passwd|secret|api[_-]?key|token)\b["']?\s*[:=]\s*["']"""
        r"""(?!<)(?!\$)(?!\{)[^"'\s]{12,}["']"""
    ),
}

# Values that are obviously placeholders, whatever the rule.
PLACEHOLDER = re.compile(
    r"(?i)(example|placeholder|changeme|change-me|your[_-]|dummy|fake|test|sample|"
    r"xxxx|\*{4}|redacted|<|todo|not-a-real|local-dev|insecure)"
)

# (path glob, rule) -> reason. Keep this short; each entry is a reviewed false positive.
ALLOW: Dict[Tuple[str, str], str] = {
    ("backend/tests/**", "jwt"): "forged or fixture tokens used by auth tests",
    ("backend/tests/**", "bearer-token"): "fixture tokens used by auth tests",
    ("backend/tests/**", "quoted-password"): "fixture credentials used by tests",
    (
        "backend/tests/**",
        "aws-access-key-id",
    ): "AWS documentation example key in redaction tests",
    ("frontend/src/**/*.test.*", "jwt"): "fixture tokens in frontend tests",
    ("frontend/src/**/*.test.*", "bearer-token"): "fixture tokens in frontend tests",
    (
        "frontend/src/**/*.test.*",
        "quoted-password",
    ): "fixture credentials in frontend tests",
    ("docs/**", "private-key"): "setup guide quotes the PEM header line, not a key",
    (
        "sdk/**/tests/**",
        "quoted-password",
    ): "fixture personal access token in SDK tests",
    (
        "frontend/src/components/Login.tsx",
        "quoted-password",
    ): "HTML autoComplete attribute value",
    ("docs/**", "jwt"): "truncated example tokens in documentation",
    ("docs/**", "bearer-token"): "example tokens in documentation",
    ("docs/**", "quoted-password"): "example credentials in documentation",
}


def _git_files() -> Optional[List[str]]:
    if shutil.which("git") is None:
        return None
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=REPO,
            capture_output=True,
            check=True,
            timeout=60,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return None
    return [p for p in out.decode("utf-8", "replace").split("\0") if p]


def _allowed(path: str, rule: str) -> bool:
    return any(
        r == rule and fnmatch.fnmatch(path, glob) for (glob, r), _ in ALLOW.items()
    )


# Cheap substring gates, checked once per file, so the regexes only run where they could match.
GATES: Dict[str, Tuple[str, ...]] = {
    "private-key": ("PRIVATE",),
    "aws-access-key-id": ("AKIA", "ASIA"),
    "jwt": ("eyJ",),
    "bearer-token": ("earer",),
    "quoted-password": (
        "password",
        "passwd",
        "secret",
        "api_key",
        "api-key",
        "apikey",
        "token",
    ),
}


def scan_text(path: str, text: str) -> List[str]:
    lowered = text.lower()
    active = [
        rule
        for rule, gate in GATES.items()
        if not _allowed(path, rule)
        and any(
            (g.lower() if rule == "quoted-password" else g)
            in (lowered if rule == "quoted-password" else text)
            for g in gate
        )
    ]
    if not active:
        return []
    hits: List[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for rule in active:
            match = RULES[rule].search(line)
            if not match:
                continue
            if rule != "private-key" and PLACEHOLDER.search(match.group(0)):
                continue
            hits.append(f"{path}:{lineno} [{rule}]")
    return hits


def test_scanner_detects_what_it_claims_to() -> None:
    key = _DASH + "BEGIN RSA PRIVATE" + " KEY" + _DASH
    aws = "AKIA" + "ABCDEFGHIJKLMNOP"
    jwt = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhYmNkZWZnaCJ9.c2lnbmF0dXJlc2lnbmF0dXJl"
    bearer = "Authorization: Bearer " + "A1b2C3d4" * 5
    password = 'db_password = "' + "Zq8vLm2Xr9Tp" + '"'
    for sample in (key, aws, jwt, bearer, password):
        assert scan_text("src/app.py", sample), sample
    assert not scan_text("src/app.py", 'password = "changeme-example-value"')
    assert not scan_text("src/app.py", "token = os.environ['TOKEN_VALUE_FROM_ENV']")


def test_allow_list_entries_have_reasons() -> None:
    assert ALLOW and all(len(reason) >= 10 for reason in ALLOW.values())


def test_no_secrets_in_tracked_files() -> None:
    files = _git_files()
    if files is None:
        pytest.skip("git is not available or this is not a git checkout")
    findings: List[str] = []
    scanned = 0
    for rel in files:
        path = REPO / rel
        if rel.startswith("backend/tests/security/") or not path.is_file():
            continue
        try:
            if path.stat().st_size > MAX_BYTES:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        if b"\0" in data[:4096]:
            continue
        scanned += 1
        findings.extend(scan_text(rel, data.decode("utf-8", "replace")))
    assert scanned > 100, f"only {scanned} files scanned"
    assert not findings, (
        "possible secrets in tracked files (remove them, or add a reviewed ALLOW entry):\n"
        + "\n".join(findings[:50])
    )
