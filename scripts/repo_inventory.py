#!/usr/bin/env python3
"""Generate or check docs/engineering/REPOSITORY_INVENTORY.md.

The inventory lists every tracked file with its format, layer, size, a rough
reference count and two hand-maintained fields kept in
docs/engineering/inventory_review.json:

  - "files":    per-file review records {inspection, disposition, note}.
                inspection is FULL or PARTIAL and is only ever set for a file
                that was actually read; everything else reports NOT_YET.
  - "patterns": glob -> {action, note} recommendations for whole areas. A
                pattern never marks a file as inspected.

Usage:
  python scripts/repo_inventory.py            # rewrite the inventory
  python scripts/repo_inventory.py --check    # exit 1 if tracked files and the
                                              # inventory disagree, or a review
                                              # record names an untracked file
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/engineering/REPOSITORY_INVENTORY.md"
REVIEW = ROOT / "docs/engineering/inventory_review.json"

FORMATS = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TSX",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".css": "CSS",
    ".html": "HTML",
    ".json": "JSON",
    ".md": "Markdown",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".toml": "TOML",
    ".txt": "Text",
    ".sh": "Shell",
    ".ps1": "PowerShell",
    ".svg": "SVG",
    ".png": "PNG",
    ".pdf": "PDF",
    ".docx": "Word",
    ".pptx": "PowerPoint",
    ".mp4": "Video",
    ".csv": "CSV",
    ".template": "nginx template",
}
CODE = {".py", ".ts", ".tsx", ".js", ".mjs", ".css"}
TEXT = CODE | {
    ".html",
    ".json",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
    ".txt",
    ".sh",
    ".ps1",
    ".template",
    "",
}
# Stems too common to count references by name.
GENERIC = {
    "__init__",
    "index",
    "main",
    "app",
    "App",
    "utils",
    "types",
    "config",
    "api",
    "README",
    "conftest",
    "setup",
    "test",
    "models",
    "schemas",
    "base",
    "constants",
}

LAYERS = [
    ("backend/src/", "backend"),
    ("backend/tests/", "backend tests"),
    ("backend/", "backend config"),
    ("frontend/src/test/", "frontend tests"),
    ("frontend/src/landing/", "frontend landing"),
    ("frontend/src/", "frontend app"),
    ("frontend/", "frontend config"),
    ("landingpage/", "legacy prototype"),
    ("shared/", "contracts"),
    ("sdk/", "sdk"),
    ("scripts/", "tooling"),
    (".github/", "ci"),
    ("docs/", "docs"),
    ("fallback-pack/", "demo data"),
    ("recordings/", "media"),
]

CRITICAL_PREFIXES = (
    "backend/src/",
    "backend/Dockerfile",
    "backend/requirements.txt",
    "backend/pyproject.toml",
    "backend/docker-entrypoint.py",
    "frontend/index.html",
    "frontend/app.html",
    "frontend/public/",
    "frontend/templates/",
    "frontend/Dockerfile",
    "frontend/vite.config.ts",
    "frontend/package.json",
    "frontend/package-lock.json",
    "docker-compose.yml",
    "shared/schemas/",
)


def tracked() -> list[str]:
    """Tracked files plus new, not-ignored ones (so uncommitted additions count)."""
    out = subprocess.run(
        [
            "git",
            "-c",
            "core.quotepath=off",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    return sorted({p for p in out.splitlines() if p and (ROOT / p).exists()})


def layer(path: str) -> str:
    for prefix, name in LAYERS:
        if path.startswith(prefix):
            if name == "backend":
                parts = path.split("/")
                return f"backend/{parts[2]}" if len(parts) > 3 else "backend"
            return name
    return "repo root"


def suffix(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    return "." + name.rsplit(".", 1)[-1] if "." in name.lstrip(".") else ""


def read_text(path: str) -> str | None:
    if suffix(path) not in TEXT:
        return None
    try:
        return (ROOT / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


COVERAGE = ROOT / "backend" / "coverage.json"


def purpose(path: str, text: str | None) -> str:
    """The file's own one-line statement of purpose, if it has one: a module
    docstring, a leading comment block, or a first Markdown heading."""
    if not text:
        return ""
    body = text.lstrip("﻿")
    ext = suffix(path)
    found = None
    if ext == ".py":
        found = re.match(r'\s*(?:#![^\n]*\n)?\s*(?:"""|\'\'\')\s*(.+)', body)
    elif ext in {".ts", ".tsx", ".js", ".mjs", ".css"}:
        found = re.match(r"\s*(?:/\*\*?|//)\s*(.+)", body)
    elif ext == ".md":
        found = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    line = found.group(1).strip() if found else ""
    line = line.rstrip("*/").strip().strip('"').strip()
    return line[:90] + ("…" if len(line) > 90 else "")


def coverage_by_file() -> dict[str, str]:
    """Line coverage per backend source file from backend/coverage.json
    (`coverage json` after a pytest --cov run), if present."""
    if not COVERAGE.exists():
        return {}
    data = json.loads(COVERAGE.read_text(encoding="utf-8"))
    out = {}
    for name, info in data.get("files", {}).items():
        rel = "backend/" + name.replace("\\", "/")
        out[rel] = f"{info['summary']['percent_covered']:.0f}%"
    return out


def build(files: list[str]) -> list[dict]:
    texts = {p: read_text(p) for p in files}
    covered = coverage_by_file()
    # Word index: which files mention each identifier-like token.
    mentions: dict[str, set[str]] = {}
    for p, t in texts.items():
        if t is None or p.endswith("scene.json"):
            continue
        for tok in set(re.findall(r"[A-Za-z_][A-Za-z0-9_-]*", t)):
            mentions.setdefault(tok, set()).add(p)
    review = json.loads(REVIEW.read_text(encoding="utf-8")) if REVIEW.exists() else {}
    per_file = review.get("files", {})
    patterns = review.get("patterns", {})
    rows = []
    for p in files:
        ext = suffix(p)
        stem = (
            p.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            if "." in p.rsplit("/", 1)[-1]
            else p.rsplit("/", 1)[-1]
        )
        if ext in CODE and stem not in GENERIC:
            refs = str(len(mentions.get(stem, set()) - {p}))
        else:
            refs = "–"
        text = texts[p]
        size = (
            f"{text.count(chr(10)) + 1} lines"
            if text is not None
            else f"{(ROOT / p).stat().st_size // 1024} KiB"
        )
        rec = per_file.get(p, {})
        action = next(
            (v.get("action", "") for g, v in patterns.items() if fnmatch.fnmatch(p, g)),
            "",
        )
        rows.append(
            {
                "path": p,
                "format": FORMATS.get(ext, ext or "none"),
                "layer": layer(p),
                "critical": "yes" if p.startswith(CRITICAL_PREFIXES) else "",
                "size": size,
                "refs": refs,
                "inspection": rec.get("inspection", "NOT_YET"),
                "disposition": rec.get("disposition", "PENDING"),
                "action": rec.get("action", action),
                "note": rec.get("note", ""),
                "purpose": purpose(p, text),
                "coverage": covered.get(p, ""),
            }
        )
    return rows


def render(rows: list[dict], deleted: dict[str, str]) -> str:
    insp = Counter(r["inspection"] for r in rows)
    disp = Counter(r["disposition"] for r in rows)
    by_layer = Counter(r["layer"] for r in rows)
    lines = [
        "# Repository inventory",
        "",
        "Generated by `python scripts/repo_inventory.py` from `git ls-files`; do not edit by hand.",
        "Review records live in [inventory_review.json](inventory_review.json).",
        "",
        "Column meanings:",
        "",
        "- **refs**: other tracked text files that mention the file's name (a dead-code *hint*, not proof;",
        "  `–` = not a code file or a name too generic to count).",
        "- **inspection**: `FULL` / `PARTIAL` only for files actually read during the refactor; `NOT_YET` otherwise.",
        "  Listing a file here is not a review of it.",
        "- **disposition**: outcome after review (`MODIFIED`, `VERIFIED_UNCHANGED`, `ADDED`, ...); `PENDING` = not reviewed.",
        "- **action**: recommended next step, from a per-file record or an area pattern.",
        "- **profile**: generated facts, not a review: the file's own one-line purpose (docstring, leading",
        "  comment or first heading) and, for backend source, line coverage from `backend/coverage.json`.",
        "",
        f"## Totals ({len(rows)} tracked files)",
        "",
        "| Inspection | Files |",
        "| --- | ---: |",
        *[f"| {k} | {v} |" for k, v in sorted(insp.items())],
        "",
        "| Disposition | Files |",
        "| --- | ---: |",
        *[f"| {k} | {v} |" for k, v in sorted(disp.items())],
        "",
        "| Layer | Files |",
        "| --- | ---: |",
        *[f"| {k} | {v} |" for k, v in sorted(by_layer.items())],
        "",
        "## Files",
        "",
        "| Path | Format | Layer | Critical | Size | Refs | Inspection | Disposition | Action / note | Profile |",
        "| --- | --- | --- | :-: | ---: | ---: | --- | --- | --- | --- |",
    ]
    for r in rows:
        extra = "; ".join(x for x in (r["action"], r["note"]) if x)
        cells = [
            f"`{r['path']}`",
            r["format"],
            r["layer"],
            r["critical"],
            r["size"],
            r["refs"],
            r["inspection"],
            r["disposition"],
            extra.replace("|", "\\|"),
            "; ".join(
                x
                for x in (r["purpose"], r["coverage"] and f"coverage {r['coverage']}")
                if x
            ).replace("|", "\\|"),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    if deleted:
        lines += [
            "",
            f"## Deleted during the refactor ({len(deleted)})",
            "",
            "| Path | Reason |",
            "| --- | --- |",
            *[f"| `{p}` | {why} |" for p, why in sorted(deleted.items())],
        ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    files = tracked()
    if args.check:
        files_section = OUT.read_text(encoding="utf-8").split("\n## Deleted")[0]
        listed = set(re.findall(r"^\| `([^`]+)` \|", files_section, re.MULTILINE))
        review = json.loads(REVIEW.read_text(encoding="utf-8"))
        current = set(files)
        problems = [f"missing from inventory: {p}" for p in sorted(current - listed)]
        problems += [
            f"inventory lists untracked file: {p}" for p in sorted(listed - current)
        ]
        problems += [
            f"review record for untracked file: {p}"
            for p in sorted(set(review.get("files", {})) - current)
        ]
        problems += [
            f"recorded as deleted but still present: {p}"
            for p in sorted(set(review.get("deleted", {})) & current)
        ]
        for line in problems:
            print(line)
        print(
            f"{len(current)} tracked, {len(listed)} listed, {len(problems)} problem(s)"
        )
        return 1 if problems else 0
    review = json.loads(REVIEW.read_text(encoding="utf-8")) if REVIEW.exists() else {}
    OUT.write_text(
        render(build(files), review.get("deleted", {})), encoding="utf-8", newline="\n"
    )
    print(f"wrote {OUT.relative_to(ROOT)} ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
