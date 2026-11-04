"""Helpers shared by the producer tests: import paths and a minimal /api/v3 insights client."""

import sys
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.api.errors import http_exception_handler
from src.insights.locations import ResultsLocations
from src.insights.router import create_router

REPO = Path(__file__).resolve().parents[3]
for sub in ("scripts", "airflow/dags"):
    path = str(REPO / sub)
    if path not in sys.path:
        sys.path.insert(0, path)

USER = "alice"
EXPERIMENT = "exp-1"


class _Store:
    def __init__(self, records: Dict[str, Dict[str, Any]]) -> None:
        self.records = records

    def get(self, user_id: str, experiment_id: str) -> Optional[Dict[str, Any]]:
        rec = self.records.get(experiment_id)
        return rec if rec and rec["userId"] == user_id else None


class _Service:
    def __init__(self, records: Dict[str, Dict[str, Any]]) -> None:
        self.store = _Store(records)


def finished_experiment(experiment_id: str = EXPERIMENT) -> Dict[str, Dict[str, Any]]:
    result = {
        "name": "Junction study",
        "specification": {"seed": 7},
        "manifest": {"scenarioFingerprint": "s" * 16, "specFingerprint": "p" * 16},
        "provenance": {"gitCommit": "abc1234"},
        "assumptions": [],
        "analysis": {
            "eligibility": {"class": "indicative"},
            "limitations": [],
            "realWorldValidity": "None - assumptions only",
        },
    }
    return {experiment_id: {"userId": USER, "name": "Junction study", "result": result}}


def client(
    root: Path, records: Optional[Dict[str, Dict[str, Any]]] = None
) -> TestClient:
    app = FastAPI()
    app.exception_handler(HTTPException)(http_exception_handler)
    app.include_router(
        create_router(
            user_dependency=lambda: USER,
            service=_Service(records if records is not None else finished_experiment()),  # type: ignore[arg-type]
            locations=ResultsLocations(root),
        )
    )
    return TestClient(app)
