"""Tests for CSV formula injection mitigation and simulation CSV reports."""

from __future__ import annotations

import csv
import io
from typing import Any, Dict

from fastapi.testclient import TestClient

from src.csv_safety import spreadsheet_safe
from src.main import app


def test_spreadsheet_safe_unit() -> None:
    # Safe text remains untouched
    assert spreadsheet_safe("hello world") == "hello world"
    assert spreadsheet_safe("flowRate") == "flowRate"
    assert spreadsheet_safe("") == ""

    # Numeric strings with +/- signs are preserved as data
    assert spreadsheet_safe("-3.5") == "-3.5"
    assert spreadsheet_safe("+42") == "+42"
    assert spreadsheet_safe("0") == "0"
    assert spreadsheet_safe("-100.25") == "-100.25"

    # Formula injection triggers get prefixed with '
    assert spreadsheet_safe("=1+1") == "'=1+1"
    assert spreadsheet_safe("=SUM(A1:B10)") == "'=SUM(A1:B10)"
    assert spreadsheet_safe("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert spreadsheet_safe("-cmd|' /C calc'!A0") == "'-cmd|' /C calc'!A0"
    assert spreadsheet_safe("@something") == "'@something"
    assert spreadsheet_safe("\tcmd") == "'\tcmd"
    assert spreadsheet_safe("\rcmd") == "'\rcmd"


def test_simulation_report_csv_formula_escaped() -> None:
    client = TestClient(app)

    # Create and register a simulation
    from src.snapshot.buffer import SnapshotBuffer

    # Create dummy engine with custom metrics containing formula injection
    class DummyClock:
        def get_tick_count(self) -> int:
            return 100

    class DummyEngine:
        def __init__(self) -> None:
            self.clock = DummyClock()
            self.lock = None

    class DummyCollector:
        pass

    # Patch engine_metrics for this test or inject a registered simulation
    from unittest.mock import patch

    injected_metrics: Dict[str, Any] = {
        "normalMetric": 42.5,
        "=maliciousKey": "=2+2",
        "nested": {"@danger": "-cmd|' /C calc'!A0"},
    }

    with patch("src.simulations.router.engine_metrics", return_value=injected_metrics):
        # Register a mock sim
        sim_id = "test_csv_safety_sim"
        from src.simulations.registry import simulations_db

        simulations_db[sim_id] = {
            "engine": DummyEngine(),
            "collector": DummyCollector(),
            "buffer": SnapshotBuffer(),
            "task": None,
            "created_at": 1000.0,
            "status": "STOPPED",
            "error": None,
        }

        try:
            res = client.get(f"/api/v1/simulations/{sim_id}/report?format=csv")
            assert res.status_code == 200
            assert "text/csv" in res.headers["content-type"]

            # Parse CSV content
            reader = csv.reader(io.StringIO(res.text))
            rows = list(reader)

            header = rows[0]
            assert header == ["Metric Name", "Value"]

            rows_dict = dict(rows[1:])
            # Check keys and values are escaped
            assert "'=maliciousKey" in rows_dict
            assert rows_dict["'=maliciousKey"] == "'=2+2"
            assert rows_dict["normalMetric"] == "42.5"
        finally:
            simulations_db.pop(sim_id, None)
