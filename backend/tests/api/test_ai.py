"""
Unit and integration tests for Phase 1 AI Copilot endpoints and fallback logic.
"""
from fastapi.testclient import TestClient

from src.ai.fallback import chat_fallback, patch_fallback, summary_fallback
from src.main import app

client = TestClient(app)

def test_ai_fallback_functions():
    metrics = {
        "averageDelay": 14.2,
        "throughput": 120,
        "maxQueueLength": 7,
        "directionalFairnessIndex": 0.88,
    }
    config = {
        "arrivalRate": 0.5,
        "duration": 60,
    }

    # Summary fallback
    summary_res = summary_fallback(metrics, config, "fixed_time_signal")
    assert summary_res.fallback is True
    assert len(summary_res.summary) > 0
    assert len(summary_res.bullets) > 0

    # Chat fallback
    chat_res = chat_fallback("What is the average delay?", metrics, config)
    assert chat_res.fallback is True
    assert "14.2" in chat_res.answer or "average delay" in chat_res.answer.lower()

    # Patch fallback
    patch_res = patch_fallback("Heavy Pune peak-hour traffic", config)
    assert patch_res.fallback is True
    assert len(patch_res.assumptions) > 0


def test_ai_summary_endpoint():
    payload = {
        "metrics": {"averageDelay": 15.0, "throughput": 100},
        "config": {"arrivalRate": 0.5},
        "geometry": "fixed_time_signal",
    }
    response = client.post("/api/ai/summary", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "bullets" in data
    assert "warnings" in data
    assert "fallback" in data


def test_ai_chat_endpoint():
    payload = {
        "question": "How can I reduce delay?",
        "metrics": {"averageDelay": 20.0},
        "config": {"arrivalRate": 0.6},
        "history": [],
    }
    response = client.post("/api/ai/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "fallback" in data


def test_ai_patch_endpoint():
    payload = {
        "instruction": "Simulate heavy peak-hour traffic with aggressive drivers",
        "current_config": {"arrivalRate": 0.3},
    }
    response = client.post("/api/ai/patch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "patch" in data
    assert "assumptions" in data
    assert "warnings" in data
