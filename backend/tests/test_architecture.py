"""The backend's dependency rules (docs/architecture/02-backend-architecture.md §2),
checked from the import statements of every module under src/.

* The simulation domain is a strict stack: a package imports only packages
  below it, so there are no cycles inside the model.
* The domain imports no web framework, no database and nothing from the
  application or delivery layers.
* Nothing imports the composition root (main.py), except the developer tool
  that snapshots its OpenAPI document.
* Routers hold no SQL.
"""

import ast
from pathlib import Path
from typing import Dict, Iterator, Set, Tuple

SRC = Path(__file__).resolve().parents[1] / "src"

# Lower number = lower layer. A domain package may import only packages with
# a strictly lower rank (and itself). scenario/ and engine/ share a rank: they
# are siblings that must not import each other.
DOMAIN_RANK: Dict[str, int] = {
    "core": 0,
    "roads": 1,
    "vehicles": 2,
    "intersection": 3,
    "controllers": 4,
    "metrics": 5,
    "scenario": 6,
    "engine": 6,
    "snapshot": 7,
}

FORBIDDEN_IN_DOMAIN_EXTERNAL = ("fastapi", "starlette", "sqlite3", "uvicorn")

# The one module allowed to import the app: it snapshots the OpenAPI document
# for shared/schemas and runs only as a developer tool, never in the server.
MAIN_IMPORT_ALLOWED = {"experiments/export_schemas.py"}


def _modules() -> Iterator[Tuple[str, Set[str]]]:
    """(path relative to src/, imported module names) for every module."""
    for path in sorted(SRC.rglob("*.py")):
        imported: Set[str] = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        yield path.relative_to(SRC).as_posix(), imported


def _package(rel: str) -> str:
    return rel.split("/", 1)[0].removesuffix(".py")


def test_the_simulation_domain_is_a_strict_stack() -> None:
    violations = []
    for rel, imported in _modules():
        pkg = _package(rel)
        if pkg not in DOMAIN_RANK:
            continue
        for mod in imported:
            if not mod.startswith("src."):
                continue
            target = mod.split(".")[1]
            if target == pkg:
                continue
            if target not in DOMAIN_RANK:
                violations.append(f"{rel} imports {mod} (outside the domain)")
            elif DOMAIN_RANK[target] >= DOMAIN_RANK[pkg]:
                violations.append(f"{rel} imports {mod} (same or higher layer)")
    assert violations == []


def test_the_domain_uses_no_web_or_database_library() -> None:
    violations = [
        f"{rel} imports {mod}"
        for rel, imported in _modules()
        if _package(rel) in DOMAIN_RANK
        for mod in imported
        if mod.split(".")[0] in FORBIDDEN_IN_DOMAIN_EXTERNAL
    ]
    assert violations == []


def test_nothing_imports_the_composition_root() -> None:
    violations = [
        rel
        for rel, imported in _modules()
        if "src.main" in imported and rel not in MAIN_IMPORT_ALLOWED
    ]
    assert violations == []


def test_routers_hold_no_sql() -> None:
    violations = []
    for path in SRC.rglob("*.py"):
        if path.name not in ("router.py", "api.py", "meta.py"):
            continue
        source = path.read_text(encoding="utf-8")
        for needle in ("conn.execute(", ".cursor()", "SELECT ", "INSERT ", "UPDATE "):
            if needle in source:
                violations.append(f"{path.relative_to(SRC).as_posix()}: {needle}")
    assert violations == []


def test_sql_lives_only_in_the_persistence_modules() -> None:
    """database/ owns the shared tables; a feature that keeps its own table
    does so in its store.py (calibration, planning, experiments)."""
    violations = []
    for path in SRC.rglob("*.py"):
        rel = path.relative_to(SRC).as_posix()
        if rel.startswith("database/") or path.name == "store.py":
            continue
        source = path.read_text(encoding="utf-8")
        for needle in ("CREATE TABLE", "conn.execute(", ".cursor()"):
            if needle in source:
                violations.append(f"{rel}: {needle}")
    assert violations == []
