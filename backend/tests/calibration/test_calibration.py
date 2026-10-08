"""V1.8 calibration: observed-data models, rating rules, comparison rows,
request validation, one tiny deterministic run, and the API."""

import copy
from functools import lru_cache
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.calibration.compare import build_rows
from src.calibration.models import ObservationSet, observations_fingerprint
from src.calibration.rating import (
    GOOD,
    INSUFFICIENT_DATA,
    MODERATE,
    POOR,
    classify,
    geh,
    percent_error,
    rate,
)
from src.calibration.runner import (
    CalibrationError,
    run_calibration,
    validate_calibration_request,
)
from src.core.scenario import parse_scenario, scenario_fingerprint
from src.main import app

SCENARIO: Dict[str, Any] = {
    "format": "urbanflow-scenario",
    "version": 1,
    "name": "calibration test",
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
        {"approach": "north", "vehiclesPerHour": 320},
        {"approach": "east", "count": 280},
    ],
    "turningMovements": [
        {"approach": "north", "movement": "left", "count": 20},
        {"approach": "north", "movement": "straight", "count": 60},
        {"approach": "north", "movement": "right", "count": 20},
    ],
    "vehicleMix": {"car": 0.8, "truck": 0.2},
    "queues": [{"approach": "north", "meanVehicles": 2.0, "maxVehicles": 6}],
    "travelTimes": [{"approach": "north", "meanSeconds": 30}],
    "signal": {"averageGreenSeconds": 30},
}


def request(**changes: Any) -> Dict[str, Any]:
    body = {
        "scenario": copy.deepcopy(SCENARIO),
        "observations": copy.deepcopy(OBSERVATIONS),
        "options": {"seeds": 1},
    }
    body.update(changes)
    return body


# ── observed-data documents ────────────────────────────────────────────────
def test_valid_observations_parse_and_convert_units() -> None:
    obs = ObservationSet.model_validate(OBSERVATIONS)
    assert obs.flow_vph() == {"north": 320.0, "east": 280.0}  # count over 1 h
    shares = obs.turning_shares()["north"]
    assert shares == {"left": 0.2, "straight": 0.6, "right": 0.2}
    assert obs.mix_shares() == {"car": 0.8, "truck": 0.2}


def test_count_uses_its_own_duration() -> None:
    obs = ObservationSet.model_validate(
        {"approachFlows": [{"approach": "south", "count": 50, "durationSeconds": 900}]}
    )
    assert obs.flow_vph() == {"south": 200.0}


@pytest.mark.parametrize(
    "bad, fragment",
    [
        ({}, "no observations"),
        ({"approachFlows": [{"approach": "north"}]}, "exactly one"),
        (
            {
                "approachFlows": [
                    {"approach": "north", "vehiclesPerHour": 1, "count": 1}
                ]
            },
            "exactly one",
        ),
        ({"approachFlows": [{"approach": "up", "vehiclesPerHour": 1}]}, "approach"),
        (
            {"approachFlows": [{"approach": "north", "vehiclesPerHour": -5}]},
            "vehiclesPerHour",
        ),
        (
            {
                "approachFlows": [
                    {"approach": "north", "vehiclesPerHour": 1},
                    {"approach": "north", "vehiclesPerHour": 2},
                ]
            },
            "once",
        ),
        (
            {
                "turningMovements": [
                    {"approach": "north", "movement": "left", "share": 0.5},
                    {"approach": "north", "movement": "right", "share": 0.2},
                ]
            },
            "sum to 0.700",
        ),
        (
            {
                "turningMovements": [
                    {"approach": "north", "movement": "left", "share": 0.5},
                    {"approach": "north", "movement": "right", "count": 5},
                ]
            },
            "not both",
        ),
        ({"vehicleMix": {"car": 0.5}}, "sum to 0.500"),
        ({"queues": [{"approach": "north"}]}, "meanVehicles"),
        (
            {
                "approachFlows": [{"approach": "north", "vehiclesPerHour": 1}],
                "extra": 1,
            },
            "extra",
        ),
    ],
)
def test_invalid_observations_are_rejected_with_a_reason(
    bad: Dict[str, Any], fragment: str
) -> None:
    with pytest.raises(ValidationError) as err:
        ObservationSet.model_validate(bad)
    assert fragment in str(err.value)


def test_observation_fingerprint_ignores_name_only() -> None:
    a = ObservationSet.model_validate(OBSERVATIONS)
    renamed = ObservationSet.model_validate({**OBSERVATIONS, "name": "other"})
    changed = copy.deepcopy(OBSERVATIONS)
    changed["approachFlows"][0]["vehiclesPerHour"] = 321
    assert observations_fingerprint(a) == observations_fingerprint(renamed)
    assert observations_fingerprint(a) != observations_fingerprint(
        ObservationSet.model_validate(changed)
    )


# ── rating rules ───────────────────────────────────────────────────────────
def test_percent_error_is_withheld_for_near_zero_denominators() -> None:
    assert percent_error("flow", 0.0, 5.0) is None
    assert percent_error("flow", 19.9, 5.0) is None
    assert percent_error("flow", 100.0, 10.0) == pytest.approx(10.0)


def test_rating_uses_absolute_error_when_the_observed_value_is_tiny() -> None:
    assert rate("flow", 0.0, 10.0) == GOOD  # 10 veh/h off a zero count
    assert rate("flow", 0.0, 40.0) == MODERATE
    assert rate("flow", 0.0, 200.0) == POOR


@pytest.mark.parametrize(
    "observed, simulated, expected",
    [(1000, 1090, GOOD), (1000, 1200, MODERATE), (1000, 1400, POOR), (1000, 700, POOR)],
)
def test_flow_rating_bands(observed: float, simulated: float, expected: str) -> None:
    assert rate("flow", observed, simulated - observed) == expected


def test_geh() -> None:
    assert geh(0, 0) == 0.0
    assert geh(100, 100) == 0.0
    assert geh(1100, 1000) == pytest.approx(3.086, abs=1e-3)


def test_overall_classification_rule() -> None:
    assert classify([])["overall"] == INSUFFICIENT_DATA
    assert classify([GOOD] * 4 + [MODERATE])["overall"] == GOOD  # 80 % good
    assert classify([GOOD] * 3 + [MODERATE] * 2)["overall"] == MODERATE
    assert classify([GOOD] * 9 + [POOR])["overall"] == MODERATE  # any POOR blocks GOOD
    assert classify([GOOD, POOR])["overall"] == POOR


def test_poor_threshold_is_strictly_above_a_quarter() -> None:
    assert classify([GOOD, GOOD, GOOD, POOR])["overall"] == MODERATE
    assert classify([GOOD, GOOD, POOR, POOR])["overall"] == POOR


# ── comparison rows (no simulation) ────────────────────────────────────────
def fake_tally(north: int, left: int, straight: int, right: int) -> Dict[str, Any]:
    return {
        "measuredSeconds": 50.0,
        "flowCount": {"north": north},
        "movementCount": {
            "north": {"left": left, "straight": straight, "right": right}
        },
        "travelTimes": {"north": [30.0, 40.0]},
        "movementTravelTimes": {"north": {"left": [50.0]}},
        "classCount": {"car": 8, "truck": 2},
        "exited": 10,
        "metrics": {
            "approachBreakdown": {
                "north": {"averageQueueLength": 2.5, "maxQueueLength": 6}
            },
            "signalTiming": {"averageGreenDuration": 31.0},
        },
    }


def test_rows_carry_observed_simulated_and_errors() -> None:
    obs = ObservationSet.model_validate(OBSERVATIONS)
    rows = build_rows(obs, [fake_tally(10, 2, 6, 2)], "fixed_time", [])
    by = {
        (r["metric"], r["location"]["approach"], r["location"]["movement"]): r
        for r in rows
    }
    flow = by[("approachFlow", "north", None)]
    assert flow["observed"] == 320.0
    assert flow["simulated"] == pytest.approx(720.0)  # 10 veh over 50 s
    assert flow["absoluteError"] == pytest.approx(400.0)
    assert flow["percentError"] == pytest.approx(125.0)
    assert flow["rating"] == POOR
    assert flow["geh"] > 10
    turning = by[("turningShare", "north", "straight")]
    assert turning["simulated"] == pytest.approx(0.6)
    assert turning["rating"] == GOOD
    assert by[("meanQueueLength", "north", None)]["absoluteError"] == pytest.approx(0.5)
    assert by[("averageGreenDuration", None, None)]["simulated"] == 31.0
    # East was observed but the tally has no east vehicles: reported, not rated.
    east = by[("approachFlow", "east", None)]
    assert east["simulated"] == pytest.approx(0.0) and east["rating"] is not None


def test_missing_simulated_data_is_reported_not_invented() -> None:
    obs = ObservationSet.model_validate(OBSERVATIONS)
    tally = fake_tally(10, 2, 6, 2)
    tally["travelTimes"] = {}
    tally["classCount"] = {}
    tally["exited"] = 0
    rows = build_rows(obs, [tally], "fixed_time", [])
    unrated = {r["metric"] for r in rows if r["rating"] is None}
    assert {"meanTravelTime", "vehicleClassShare"} <= unrated
    assert all(
        r["simulated"] is None and "Not compared" in r["note"]
        for r in rows
        if r["rating"] is None
    )


def test_zero_observed_flow_gives_no_percentage() -> None:
    obs = ObservationSet.model_validate(
        {"approachFlows": [{"approach": "north", "vehiclesPerHour": 0}]}
    )
    row = build_rows(obs, [fake_tally(1, 1, 0, 0)], "fixed_time", [])[0]
    assert row["percentError"] is None and "absolute" in row["note"]


def test_signal_observations_are_skipped_for_a_roundabout() -> None:
    obs = ObservationSet.model_validate({"signal": {"averageGreenSeconds": 30}})
    assert build_rows(obs, [fake_tally(1, 1, 0, 0)], "roundabout", []) == []


def test_rows_are_deterministic() -> None:
    obs = ObservationSet.model_validate(OBSERVATIONS)
    tallies = [fake_tally(10, 2, 6, 2), fake_tally(12, 3, 6, 3)]
    assert build_rows(obs, tallies, "fixed_time", []) == build_rows(
        obs, tallies, "fixed_time", []
    )


# ── request validation (no simulation) ─────────────────────────────────────
def test_validate_ok_reports_fingerprints_and_plan() -> None:
    out = validate_calibration_request(request())
    assert out["valid"], out["errors"]
    doc, _ = parse_scenario(SCENARIO)
    assert out["scenarioFingerprint"] == scenario_fingerprint(doc)
    assert out["plannedComparisons"]["approachFlow"] == 2
    assert out["plannedComparisons"]["queue"] == 2
    assert out["strategy"] == "fixed_time"


def test_scenario_mismatch_on_fingerprint() -> None:
    body = request()
    body["observations"]["scenarioFingerprint"] = "0000000000000000"
    out = validate_calibration_request(body)
    assert not out["valid"]
    assert any("Scenario mismatch" in e for e in out["errors"])


def test_scenario_mismatch_on_absent_approach() -> None:
    body = request()
    body["scenario"]["approaches"]["west"] = None
    body["observations"]["approachFlows"].append(
        {"approach": "west", "vehiclesPerHour": 100}
    )
    out = validate_calibration_request(body)
    assert not out["valid"]
    assert any("west approach" in e for e in out["errors"])


def test_scenario_input_mismatch_is_a_warning_unless_fitted() -> None:
    body = request()
    body["observations"]["approachFlows"][0]["vehiclesPerHour"] = 500
    out = validate_calibration_request(body)
    assert out["valid"]
    assert any("north offers 300" in w for w in out["warnings"])
    body["options"] = {"seeds": 1, "fit": ["demand"]}
    fitted = validate_calibration_request(body)
    assert not any("north offers" in w for w in fitted["warnings"])


def test_missing_and_invalid_inputs_are_all_reported() -> None:
    assert validate_calibration_request("nope")["valid"] is False
    out = validate_calibration_request({"scenario": {}, "observations": {}})
    assert not out["valid"] and len(out["errors"]) >= 2
    out = validate_calibration_request(request(options={"seeds": 0}))
    assert any(e.startswith("options:") for e in out["errors"])


def test_fit_needs_its_observations() -> None:
    body = request(options={"seeds": 1, "fit": ["mix"]})
    del body["observations"]["vehicleMix"]
    out = validate_calibration_request(body)
    assert any("needs observations.vehicleMix" in e for e in out["errors"])


def test_run_budget_and_window_are_enforced() -> None:
    body = request(options={"seeds": 10})
    body["scenario"]["simulation"] = {"duration": 400, "warmup": 10, "seed": 1}
    assert any("limit" in e for e in validate_calibration_request(body)["errors"])
    body = request()
    body["scenario"]["simulation"] = {"duration": 30, "warmup": 30, "seed": 1}
    assert any("warmup" in e for e in validate_calibration_request(body)["errors"])


def test_run_refuses_an_invalid_request() -> None:
    with pytest.raises(CalibrationError) as err:
        run_calibration({"scenario": SCENARIO, "observations": {}})
    assert err.value.errors


# ── one tiny real run ──────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _first_run() -> Dict[str, Any]:
    return run_calibration(request())


def test_run_result_shape_and_reproducibility_metadata() -> None:
    result = _first_run()
    assert result["format"] == "urbanflow-calibration-result"
    doc, _ = parse_scenario(SCENARIO)
    assert result["scenario"]["fingerprint"] == scenario_fingerprint(doc)
    meta = result["meta"]
    assert meta["seeds"] == [5] and meta["repetitions"] == 1 and meta["baseSeed"] == 5
    assert meta["duration"] == 60 and meta["warmupTime"] == 10
    assert meta["measuredSeconds"] == pytest.approx(50.0)
    assert meta["observationsFingerprint"] == observations_fingerprint(
        ObservationSet.model_validate(OBSERVATIONS)
    )
    assert {"gitCommit", "pythonVersion", "timeStep"} <= set(meta)
    fc = result["fieldCalibration"]
    assert fc["status"] in {GOOD, MODERATE, POOR}
    assert fc["thresholds"]["flow"]["pctGood"] == 10.0
    assert "calibrated" in fc["engineCapacityCalibration"]
    for row in result["comparisons"]:
        assert {
            "metric",
            "location",
            "observed",
            "simulated",
            "absoluteError",
            "rating",
        } <= set(row)
    assert any("1 repetition" in c for c in result["caveats"])


def test_run_is_deterministic() -> None:
    assert run_calibration(request()) == _first_run()


def test_a_run_compared_with_its_own_output_is_good() -> None:
    first = _first_run()
    flows = [
        {"approach": r["location"]["approach"], "vehiclesPerHour": r["simulated"]}
        for r in first["comparisons"]
        if r["metric"] == "approachFlow"
    ]
    shares = [
        {
            "approach": "north",
            "movement": r["location"]["movement"],
            "share": r["simulated"],
        }
        for r in first["comparisons"]
        if r["metric"] == "turningShare"
    ]
    assert flows and shares
    body = request()
    body["observations"] = {
        "approachFlows": flows,
        "turningMovements": shares,
    }
    again = run_calibration(body)
    assert again["fieldCalibration"]["status"] == GOOD
    assert all(r["rating"] == GOOD for r in again["comparisons"])


def test_fit_writes_observed_demand_to_a_copy() -> None:
    body = request(options={"seeds": 1, "fit": ["demand"]})
    result = run_calibration(body)
    assert result["appliedFit"] == ["demand"]
    assert result["scenario"]["fittedFingerprint"] != result["scenario"]["fingerprint"]
    assert any("not independent evidence" in c for c in result["caveats"])
    flows = [r for r in result["comparisons"] if r["metric"] == "approachFlow"]
    assert all(r["inputWasFitted"] for r in flows)


# ── API ────────────────────────────────────────────────────────────────────
@pytest.fixture
def client(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("src.database.db.DB_PATH", str(tmp_path / "cal.db"))
    return TestClient(app)


def test_api_thresholds_and_validate(client: TestClient) -> None:
    assert client.get("/api/v2/calibration/thresholds").json()["thresholds"]["flow"]
    ok = client.post("/api/v2/calibration/validate", json=request())
    assert ok.status_code == 200 and ok.json()["valid"]
    bad = client.post(
        "/api/v2/calibration/validate",
        json={"scenario": SCENARIO, "observations": {"approachFlows": []}},
    )
    assert bad.status_code == 200 and bad.json()["valid"] is False


def test_api_run_store_and_retrieve(client: TestClient) -> None:
    created = client.post("/api/v2/calibration/runs", json=request())
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["result"] == _first_run()
    got = client.get(f"/api/v2/calibration/runs/{body['id']}")
    assert got.status_code == 200
    assert got.json()["result"] == body["result"]
    assert got.json()["request"]["observations"]["name"] == "AM peak count"
    listing = client.get("/api/v2/calibration/runs").json()["runs"]
    assert listing[0]["id"] == body["id"] and listing[0]["status"] in {
        GOOD,
        MODERATE,
        POOR,
    }


def test_api_invalid_run_is_400_and_unknown_id_is_404(client: TestClient) -> None:
    bad = request()
    bad["observations"]["scenarioFingerprint"] = "ffffffffffffffff"
    resp = client.post("/api/v2/calibration/runs", json=bad)
    assert resp.status_code == 400
    assert "Scenario mismatch" in resp.text
    assert client.get("/api/v2/calibration/runs/nope").status_code == 404
