"""planning/ may import only the allow-listed V1.5 public surface, and the
checked-in JSON Schemas match the Pydantic models."""

import ast
import json
from pathlib import Path

from src.planning.models import PlanningStudy
from src.planning.report import Report

ROOT = Path(__file__).resolve().parents[3]
PKG = ROOT / "backend" / "src" / "planning"
ALLOWED = {
    "src.core.scenario",
    "src.core.provenance",
    "src.core.limits",
    "src.study.runner",
    "src.study.control_comparison",
    "src.study.validation",
    "src.study.tolerances",
    "src.study.calibration",
    "src.study.jobs",
    "src.database.db",
    "src.auth",
    # V2.0 integration: the attached V1.8 run and the V1.9 network model.
    "src.calibration",
    "src.calibration.models",  # schema export only
    "src.calibration.store",
    "src.calibration.runner",
    "src.networks.compile",
    "src.networks.from_scenario",
    "src.networks.models",
    "src.networks.validate",
}


def test_planning_imports_only_the_allowed_surface() -> None:
    bad = []
    for path in PKG.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            mods = []
            if isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module]
            elif isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            for m in mods:
                if (
                    m.startswith("src.")
                    and not m.startswith("src.planning")
                    and m not in ALLOWED
                ):
                    bad.append(f"{path.name}: {m}")
    assert not bad, bad


def test_checked_in_schemas_match_models() -> None:
    for name, model in (("planning-study", PlanningStudy), ("planning-report", Report)):
        path = ROOT / "shared" / "schemas" / "v2" / f"{name}.schema.json"
        assert (
            json.loads(path.read_text(encoding="utf-8")) == model.model_json_schema()
        ), f"{path.name} is stale; run python -m src.planning.export_schemas"
