"""V1.8 + V1.9 + V2.0 wired together, through the real app.

Tiny simulations only (60 s, 2 seeds). The flow is the reviewer's demo:
scenario -> calibration -> fitted scenario -> planning study (alternatives,
metrics, safety/environmental status, findings) -> network view -> exports
-> reproduce.
"""

import copy
import csv
import io
import json
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from src.auth import DEV_AUTH_TOKEN
from src.core.scenario import parse_scenario, scenario_fingerprint
from src.main import app
from src.networks.from_scenario import scenario_to_network
from src.networks.validate import parse_network, validate_network

SCENARIO: Dict[str, Any] = {
    "format": "urbanflow-scenario",
    "version": 1,
    "name": "Integration junction",
    "junction": {"type": "fixed_time_signal"},
    "approaches": {
        d: {"lanes": 1, "vehiclesPerHour": 300}
        for d in ("north", "south", "east", "west")
    },
    "simulation": {"duration": 60, "warmup": 10, "seed": 5},
}

OBSERVATIONS: Dict[str, Any] = {
    "format": "urbanflow-observations",
    "version": 1,
    "name": "AM peak count",
    "period": {"label": "08:00-09:00", "durationSeconds": 3600},
    "approachFlows": [
        {"approach": "north", "vehiclesPerHour": 360},
        {"approach": "east", "vehiclesPerHour": 280},
    ],
}


def _study(**over: Any) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "name": "Integration study",
        "subject": {"scenario": SCENARIO},
        "alternatives": [
            {"id": "base", "strategy": "fixed_time"},
            {"id": "rbt", "strategy": "roundabout"},
        ],
        "repetitions": {"seeds": 2, "baseSeed": 1},
    }
    body.update(over)
    return body


def _calibration_request(**options: Any) -> Dict[str, Any]:
    return {
        "scenario": SCENARIO,
        "observations": OBSERVATIONS,
        "options": {"seeds": 1, **options},
    }


@pytest.fixture
def client(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("src.database.db.DB_PATH", str(tmp_path / "v2.db"))
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    return TestClient(app, headers={"Authorization": f"Bearer {DEV_AUTH_TOKEN}"})


def test_all_v2_routes_are_registered() -> None:
    paths = set(app.openapi()["paths"])
    for p in (
        "/api/v2/calibration/validate",
        "/api/v2/calibration/runs",
        "/api/v2/calibration/runs/{run_id}/scenario",
        "/api/v2/networks/validate",
        "/api/v2/networks/from-scenario",
        "/api/v2/planning/validate",
        "/api/v2/planning/run",
        "/api/v2/planning/jobs",
        "/api/v2/planning/{study_id}/report",
        "/api/v2/planning/{study_id}/reproduce",
        "/api/v1/scenarios/validate",  # V1.x untouched
    ):
        assert p in paths, p


def test_scenario_round_trips_through_the_network_model() -> None:
    doc, errors = parse_scenario(SCENARIO)
    assert doc is not None, errors
    network = scenario_to_network(doc)
    check = validate_network(network)
    assert check["valid"], check["errors"]
    # 4 arms x (left, straight, right) = 12 routes; demand is conserved.
    assert len(network["routes"]) == 12
    assert sum(d["vehiclesPerHour"] for d in network["demand"]) == pytest.approx(1200)
    parsed, _ = parse_network(network)
    assert parsed is not None
    assert scenario_fingerprint(parsed.nodes[0].scenario) == scenario_fingerprint(doc)


def test_full_pipeline(client: TestClient) -> None:
    # 1. V1.8: calibrate (fit observed demand), then fetch the fitted scenario.
    request = _calibration_request(seeds=2, baseSeed=1, fit=["demand"])
    assert client.post("/api/v2/calibration/validate", json=request).json()["valid"]
    cal = client.post("/api/v2/calibration/runs", json=request)
    assert cal.status_code == 201, cal.text
    cal_id = cal.json()["id"]
    cal_result = cal.json()["result"]
    fitted = client.get(f"/api/v2/calibration/runs/{cal_id}/scenario").json()
    assert fitted["fingerprint"] == cal_result["scenario"]["fittedFingerprint"]
    assert fitted["fingerprint"] != cal_result["scenario"]["fingerprint"]
    fitted_doc, _ = parse_scenario(fitted["scenario"])
    assert fitted_doc is not None
    assert scenario_fingerprint(fitted_doc) == fitted["fingerprint"]

    # 2. V2.0 validates with the calibration attached (fitted scenario as subject).
    attach = _study(
        subject={}, calibration={"runId": cal_id, "useFittedScenario": True}
    )
    v = client.post("/api/v2/planning/validate", json=attach).json()
    assert v["valid"], v["errors"]
    assert v["scenarioFingerprint"] == fitted["fingerprint"]

    # 3. Run it.
    done = client.post("/api/v2/planning/run", json=attach)
    assert done.status_code == 200, done.text
    study_id = done.json()["id"]
    result = done.json()["result"]

    # Calibration reaches validity, meta and the report.
    status = cal_result["fieldCalibration"]["status"]
    assert result["validity"]["fieldCalibration"] == status
    detail = result["validity"]["fieldCalibrationDetail"]
    assert detail["runId"] == cal_id and detail["relation"] == "fitted_scenario"
    meta = result["meta"]
    assert meta["calibrationRunId"] == cal_id
    obs_fp = cal_result["meta"]["observationsFingerprint"]
    assert meta["calibrationFingerprint"] == obs_fp
    # Scenario fingerprints agree end to end.
    assert meta["scenarioFingerprint"] == fitted["fingerprint"]
    assert set(meta["scenarioFingerprints"].values()) == {fitted["fingerprint"]}
    # The network model carries the same scenario.
    net = result["network"]
    assert net["status"] == "representation_only"
    assert net["fingerprint"] == meta["networkFingerprint"]
    parsed, _ = parse_network(net["document"])
    assert parsed is not None
    junction = next(n for n in parsed.nodes if n.kind == "junction")
    assert scenario_fingerprint(junction.scenario) == fitted["fingerprint"]
    assert any("multi-junction" in m.lower() for m in result["limitations"])
    # Metrics, safety and environmental status, findings.
    row = result["results"][0]
    assert row["performance"]["values"]["averageDelay"]["n"] == 2
    assert "safety" in row and "environmental" in row
    assert all(f["evidence"] for f in result["findings"])

    # 4. Machine-readable exports.
    base = f"/api/v2/planning/{study_id}/report"
    assert (
        json.loads(client.get(f"{base}?format=json").text)["meta"]["calibrationRunId"]
        == cal_id
    )
    assert cal_id in client.get(f"{base}?format=md").text
    rows = list(csv.reader(io.StringIO(client.get(f"{base}?format=csv").text)))
    assert len(rows) > 1

    # 5. Reproduce.
    assert client.post(f"/api/v2/planning/{study_id}/reproduce").json()["reproduced"]


def test_calibration_of_another_scenario_is_refused(client: TestClient) -> None:
    cal_id = client.post(
        "/api/v2/calibration/runs", json=_calibration_request()
    ).json()["id"]
    other = copy.deepcopy(SCENARIO)
    other["approaches"]["north"]["vehiclesPerHour"] = 900
    resp = client.post(
        "/api/v2/planning/validate",
        json=_study(subject={"scenario": other}, calibration={"runId": cal_id}),
    ).json()
    assert resp["valid"] is False
    assert "only applies to the scenario it was run on" in " ".join(resp["errors"])
    unknown = client.post(
        "/api/v2/planning/validate", json=_study(calibration={"runId": "nope"})
    ).json()
    assert unknown["valid"] is False and "not found" in " ".join(unknown["errors"])


def test_unfitted_scenario_with_calibration_warns(client: TestClient) -> None:
    cal_id = client.post(
        "/api/v2/calibration/runs", json=_calibration_request(fit=["demand"])
    ).json()["id"]
    # The scenario as given is the calibration's ORIGINAL, not the fitted copy.
    resp = client.post(
        "/api/v2/planning/validate", json=_study(calibration={"runId": cal_id})
    ).json()
    assert resp["valid"], resp["errors"]
    assert any("useFittedScenario" in w for w in resp["warnings"])


def test_network_subject_single_junction_matches_scenario_subject(
    client: TestClient,
) -> None:
    doc, _ = parse_scenario(SCENARIO)
    assert doc is not None
    network = client.post(
        "/api/v2/networks/from-scenario", json={"scenario": SCENARIO}
    ).json()
    assert network["valid"], network["errors"]
    via_network = client.post(
        "/api/v2/planning/validate",
        json=_study(subject={"network": network["network"]}),
    ).json()
    assert via_network["valid"], via_network["errors"]
    assert via_network["scenarioFingerprint"] == scenario_fingerprint(doc)


def test_multi_junction_network_is_refused_honestly(client: TestClient) -> None:
    doc, _ = parse_scenario(SCENARIO)
    assert doc is not None
    network = scenario_to_network(doc)
    # Chain J1's east exit into a second junction J2 (drop what ended at D_east).
    network["nodes"] = [n for n in network["nodes"] if n["id"] != "D_east"]
    network["nodes"].append({"id": "J2", "kind": "junction", "scenario": SCENARIO})
    dropped = {r["id"] for r in network["routes"] if "OUT_east" in r["path"]}
    network["routes"] = [r for r in network["routes"] if r["id"] not in dropped]
    network["demand"] = [d for d in network["demand"] if d["routeId"] not in dropped]
    for edge in network["edges"]:
        if edge["id"] == "OUT_east":
            edge["to"] = {"node": "J2", "arm": "west"}
    assert validate_network(network)["valid"], validate_network(network)["errors"]
    resp = client.post(
        "/api/v2/planning/validate", json=_study(subject={"network": network})
    ).json()
    assert resp["valid"] is False
    assert "one junction per study" in " ".join(resp["errors"])


def test_subject_must_be_given_exactly_once(client: TestClient) -> None:
    for subject in ({}, {"scenario": SCENARIO, "network": {"x": 1}}):
        resp = client.post("/api/v2/planning/validate", json=_study(subject=subject))
        assert resp.json()["valid"] is False
