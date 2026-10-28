"""AI Copilot cost controls and output validation (budget caps, kill switch, patch stripping)."""

from __future__ import annotations

from typing import Any, Dict, Iterator, List

import pytest
from fastapi.testclient import TestClient

from src.ai import budget
from src.ai import groq_client as gc
from src.main import app

client = TestClient(app)
REPLY: Dict[str, Any] = {}  # what the fake model returns from complete_json


@pytest.fixture(autouse=True)
def model(monkeypatch: pytest.MonkeyPatch) -> Iterator[List[str]]:
    """Pretend a provider is configured; record every model call instead of making it."""
    calls: List[str] = []
    budget.reset()
    monkeypatch.setattr(gc, "is_configured", lambda: True)

    def complete_json(
        system: str, user: str, schema: Any, max_tokens: int = 0
    ) -> Dict[str, Any]:
        calls.append("json")
        return dict(REPLY)

    def complete(
        system: str, user: str, history: Any = None, max_tokens: int = 0
    ) -> str:
        calls.append("text")
        return "A model answer."

    REPLY.clear()
    REPLY.update(summary="ok", bullets=["a"], warnings=[])
    monkeypatch.setattr(gc, "complete_json", complete_json)
    monkeypatch.setattr(gc, "complete", complete)
    yield calls
    budget.reset()


SUMMARY = {
    "metrics": {"averageDelay": 10.0},
    "config": {},
    "geometry": "fixed_time_signal",
}


def test_per_client_daily_cap_falls_back_instead_of_calling_the_model(
    model, monkeypatch
):
    monkeypatch.setenv("AI_CALLS_PER_CLIENT_PER_DAY", "3")
    answers = [client.post("/api/ai/summary", json=SUMMARY).json() for _ in range(5)]
    assert [a["fallback"] for a in answers] == [False, False, False, True, True]
    assert len(model) == 3


def test_global_daily_cap(model, monkeypatch):
    monkeypatch.setenv("AI_CALLS_PER_DAY", "2")
    for _ in range(4):
        client.post("/api/ai/chat", json={"question": "why?"})
    assert len(model) == 2


def test_kill_switch(model, monkeypatch):
    monkeypatch.setenv("AI_COPILOT_ENABLED", "0")
    res = client.post("/api/ai/summary", json=SUMMARY).json()
    assert res["fallback"] is True and model == []


def test_unconfigured_provider_never_spends_budget(model, monkeypatch):
    monkeypatch.setattr(gc, "is_configured", lambda: False)
    client.post("/api/ai/summary", json=SUMMARY)
    assert model == [] and budget._total == 0


def test_invalid_and_unknown_patch_fields_are_stripped(model):
    model_reply = {
        "patch": {
            "lanes": "three",  # wrong type
            "arrivalRate": 5.0,  # out of range
            "duration": 120,  # valid
            "__proto__": {"x": 1},  # not a field
            "laneChanging": "yes",  # not a boolean
            "vehicleMix": {"car": "lots"},
        },
        "assumptions": "not a list",
        "warnings": None,
        "clarification": None,
    }
    REPLY.clear()
    REPLY.update(model_reply)
    res = client.post(
        "/api/ai/patch",
        json={"instruction": "make it busy", "current_config": {"arrivalRate": 0.3}},
    ).json()
    assert res["patch"] == {"duration": 120}
    assert res["merged"] == {"arrivalRate": 0.3, "duration": 120}
    assert res["assumptions"] == []
    joined = " ".join(res["warnings"])
    for field in ("lanes", "arrivalRate", "__proto__", "laneChanging", "vehicleMix"):
        assert field in joined


def test_model_output_of_the_wrong_shape_is_coerced(model):
    REPLY.clear()
    REPLY.update(summary=42, bullets="x", warnings=[1, 2])
    res = client.post("/api/ai/summary", json=SUMMARY).json()
    assert (
        res["summary"] == "42"
        and res["bullets"] == []
        and res["warnings"] == ["1", "2"]
    )
