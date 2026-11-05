"""Calibration against link counts on the network graph model (package 1B)."""

import json
import math
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import get_current_user_id
from src.api.request_limits import compute_slot
from src.api.security import require_api_key
from src.calibration.network_calibration_router import router
from src.calibration.network_counts import load_counts_csv
from src.calibration.network_fit import (
    FitOptions,
    NetworkCalibrationError,
    calibrate_network,
    demand_name,
)
from src.calibration.network_metrics import (
    GCalCriteria,
    g_cal_check,
    geh,
    network_metrics,
)
from src.calibration.network_recalibration import recalibrate
from src.calibration.network_synthetic import demo_flows, demo_grid, generate_counts
from src.networks.graph import parse_graph, serialize_graph
from src.networks.network_sim import Flow

FIXTURES = Path(__file__).parent / "fixtures"
GRAPH = demo_grid()
FLOWS = demo_flows()
TRUTH = json.loads((FIXTURES / "demo_truth.json").read_text(encoding="utf-8"))


def _counts_text() -> str:
    return (FIXTURES / "demo_counts.csv").read_text(encoding="utf-8")


# ---------------------------------------------------------------- loader


def test_loader_reads_rows_and_aggregates_to_vph():
    text = "link_id,interval_start,count,sensor_id\nA,0,50,s1\nA,900,70,s1\nB,0,10,s2\nB,900,20,s2\n"
    cs = load_counts_csv(text)
    assert cs.valid and cs.interval_seconds == 900 and cs.interval_inferred
    flows = cs.link_flows_vph()
    assert flows["A"] == pytest.approx(120 / 0.5)
    assert flows["B"] == pytest.approx(30 / 0.5)
    assert cs.sensors() == ["s1", "s2"]
    assert cs.provenance()["rows"] == 4 and len(cs.sha256) == 64


def test_loader_two_sensors_on_one_link_are_averaged_and_iso_times_work():
    text = (
        "link_id,interval_start,count,sensor_id\n"
        "A,2026-01-05T08:00:00Z,100,s1\nA,2026-01-05T08:15:00Z,100,s1\n"
        "A,2026-01-05T08:00:00Z,60,s2\nA,2026-01-05T08:15:00Z,60,s2\n"
    )
    cs = load_counts_csv(text)
    assert cs.valid and cs.interval_seconds == 900
    assert cs.link_flows_vph()["A"] == pytest.approx((400 + 240) / 2)


@pytest.mark.parametrize(
    "text, fragment",
    [
        ("", "empty"),
        ("link_id,count\nA,3\n", "missing column(s) interval_start"),
        ("link_id,interval_start,count\nA,0,-4\n", "Line 2: count -4 is negative"),
        ("link_id,interval_start,count\nA,0,abc\n", "not a number"),
        ("link_id,interval_start,count\nA,noon,5\n", "not an ISO-8601"),
        ("link_id,interval_start,count\nA,0,5\nA,0,6\n", "duplicate reading"),
        ("link_id,interval_start,count\nA,0\n", "expected 3 fields"),
    ],
)
def test_loader_validation_messages(text, fragment):
    cs = load_counts_csv(text)
    assert not cs.valid
    assert any(fragment in e for e in cs.errors), cs.errors


def test_loader_unknown_links_warn_and_all_unknown_is_an_error():
    text = "link_id,interval_start,count\nA,0,5\nZ,0,9\nA,900,6\n"
    cs = load_counts_csv(text, known_links={"A"})
    assert cs.valid and any("not in the network" in w for w in cs.warnings)
    assert cs.link_ids() == ["A"]
    none = load_counts_csv(text, known_links={"Q"})
    assert not none.valid and any("matches the network" in e for e in none.errors)


def test_loader_single_interval_warns_and_window_keeps_latest():
    one = load_counts_csv("link_id,interval_start,count\nA,0,9\n")
    assert one.valid and any("Only one interval" in w for w in one.warnings)
    many = load_counts_csv(
        "".join(
            ["link_id,interval_start,count\n"]
            + [f"A,{i * 900},{i}\n" for i in range(6)]
        )
    )
    assert len(many.window(2).interval_starts()) == 2
    assert many.window(2).interval_starts() == [4 * 900, 5 * 900]


# ---------------------------------------------------------------- metrics


def test_geh_known_values():
    assert geh(100, 50) == pytest.approx(math.sqrt(2 * 50**2 / 150))
    assert geh(0, 0) == 0.0
    assert geh(300, 300) == 0.0


def test_network_metrics_known_values():
    observed = {"a": 100.0, "b": 200.0, "c": 300.0}
    simulated = {"a": 110.0, "b": 190.0, "c": 300.0}
    m = network_metrics(simulated, observed)
    assert m["rmseVph"] == pytest.approx(math.sqrt((100 + 100 + 0) / 3), abs=1e-4)
    assert m["mapePercent"] == pytest.approx((10 + 5 + 0) / 3, abs=1e-3)
    assert m["r2"] == pytest.approx(1 - 200 / 20000, abs=1e-6)
    perfect = network_metrics(observed, observed)
    assert perfect["rmseVph"] == 0 and perfect["r2"] == 1.0


def test_mape_skips_small_denominators_and_r2_none_without_variance():
    m = network_metrics(
        {"a": 5.0, "b": 100.0}, {"a": 1.0, "b": 100.0}, min_observed_vph=10
    )
    assert m["mapeLinks"] == 1 and m["mapeSkippedLinks"] == 1 and m["mapePercent"] == 0
    flat = network_metrics({"a": 1.0, "b": 2.0}, {"a": 50.0, "b": 50.0})
    assert flat["r2"] is None


def test_g_cal_default_and_agreed_thresholds():
    observed = {f"l{i}": 400.0 for i in range(20)}
    good = dict(observed)
    assert g_cal_check(good, observed)["passed"]
    # 17 of 20 links within GEH 5 is exactly 85 %: passes; 16 of 20 fails.
    sim17 = {k: (400.0 if i < 17 else 600.0) for i, k in enumerate(observed)}
    sim16 = {k: (400.0 if i < 16 else 600.0) for i, k in enumerate(observed)}
    assert g_cal_check(sim17, observed)["passed"]
    failed = g_cal_check(sim16, observed)
    assert not failed["passed"] and "85%" in failed["reasons"][0]
    strict = g_cal_check(sim17, observed, GCalCriteria(max_mape=1.0))
    assert not strict["passed"] and any("MAPE" in r for r in strict["reasons"])
    assert not g_cal_check({}, {})["passed"]


# ---------------------------------------------------------------- fixture


def test_fixture_matches_generator():
    """The checked-in counts regenerate exactly from the checked-in truth."""
    assert generate_counts(GRAPH, FLOWS, TRUTH) == _counts_text()
    parsed, errors = parse_graph(
        json.loads((FIXTURES / "demo_graph.json").read_text(encoding="utf-8"))
    )
    assert errors == [] and serialize_graph(parsed) == serialize_graph(GRAPH)


# ---------------------------------------------------------------- recovery


@pytest.fixture(scope="module")
def recovered():
    counts = load_counts_csv(
        _counts_text(), known_links=GRAPH.link_map(), source="demo_counts.csv"
    )
    return calibrate_network(GRAPH, FLOWS, counts, FitOptions(budget=400))


def test_recovers_known_parameters_from_synthetic_counts(recovered):
    fitted = recovered["parameters"]["fitted"]
    assert set(fitted) == set(TRUTH)
    for name, true in TRUTH.items():
        assert abs(fitted[name] - true) / true <= 0.15, (name, fitted[name], true)
    assert abs(fitted["speed:all"] - TRUTH["speed:all"]) <= 0.05


def test_fit_improves_error_and_meets_g_cal(recovered):
    b, a = recovered["before"]["metrics"], recovered["after"]["metrics"]
    assert a["rmseVph"] < b["rmseVph"] / 5
    assert a["mapePercent"] < 5 and a["r2"] > 0.99
    assert not recovered["before"]["gCal"]["passed"] or b["meanGeh"] > a["meanGeh"]
    assert (
        recovered["status"] == "PASS"
        and recovered["after"]["gCal"]["gehFraction"] >= 0.85
    )
    assert recovered["optimiser"]["evaluations"] <= 400


def test_report_shape_and_provenance(recovered):
    assert (
        recovered["format"] == "urbanflow-network-calibration"
        and recovered["gate"] == "G-CAL"
    )
    row = recovered["perLink"][0]
    assert set(row) == {"linkId", "observedVph", "before", "after"}
    assert set(row["after"]) == {"simulatedVph", "residualVph", "geh", "percentError"}
    prov = recovered["provenance"]["counts"]
    assert (
        prov["source"] == "demo_counts.csv"
        and prov["sha256"]
        and prov["intervals"] == 4
    )
    assert len(recovered["manifest"]["hash"]) == 64
    assert recovered["thresholds"]["gCal"]["geh_limit"] == 5.0
    json.dumps(recovered)  # JSON-serialisable end to end


def test_calibration_is_deterministic_and_manifest_tracks_inputs():
    counts = load_counts_csv(_counts_text(), known_links=GRAPH.link_map())
    opts = FitOptions(budget=40)
    one = calibrate_network(GRAPH, FLOWS, counts, opts)
    two = calibrate_network(GRAPH, FLOWS, counts, opts)
    assert one == two
    assert one["optimiser"]["evaluations"] <= 40
    other = calibrate_network(GRAPH, FLOWS, counts, FitOptions(budget=40, seed=2))
    assert other["manifest"]["hash"] != one["manifest"]["hash"]


def test_recovery_with_five_percent_count_noise():
    text = generate_counts(GRAPH, FLOWS, TRUTH, noise=0.05, intervals=6)
    counts = load_counts_csv(text, known_links=GRAPH.link_map())
    report = calibrate_network(GRAPH, FLOWS, counts, FitOptions(budget=400))
    assert report["status"] == "PASS"
    for name, true in TRUTH.items():
        assert abs(report["parameters"]["fitted"][name] - true) / true <= 0.25, name


def test_bad_inputs_raise_plain_messages():
    counts = load_counts_csv(_counts_text(), known_links=GRAPH.link_map())
    with pytest.raises(NetworkCalibrationError) as err:
        calibrate_network(
            GRAPH, [Flow("GW0", "NOPE", 10), Flow("GW0", "NOPE", 20)], counts
        )
    assert any("unknown node" in e for e in err.value.errors)
    assert any("appears twice" in e for e in err.value.errors)
    with pytest.raises(NetworkCalibrationError):
        calibrate_network(GRAPH, FLOWS, load_counts_csv("link_id,count\n"))


# ---------------------------------------------------------- recalibration


def test_recalibration_warm_starts_and_reports_drift(recovered):
    changed = dict(TRUTH)
    changed[demand_name(FLOWS[0])] = (
        TRUTH[demand_name(FLOWS[0])] * 0.6
    )  # demand fell 40 %
    first = generate_counts(GRAPH, FLOWS, TRUTH, intervals=4)
    later = generate_counts(GRAPH, FLOWS, changed, intervals=4, start_time=4 * 900.0)
    merged = first + "".join(later.splitlines(keepends=True)[1:])
    counts = load_counts_csv(merged, known_links=GRAPH.link_map())
    assert len(counts.interval_starts()) == 8

    previous = recovered["parameters"]["fitted"]
    report = recalibrate(
        GRAPH,
        FLOWS,
        counts,
        previous,
        window_intervals=4,
        options=FitOptions(budget=200, initial_step=0.2),
    )
    rec = report["recalibration"]
    assert rec["windowIntervals"] == 4 and rec["windowFirstIntervalStart"] == "3600"
    assert rec["warmStartFrom"] == {k: pytest.approx(v) for k, v in previous.items()}
    drift = rec["drift"]
    assert drift["drifted"] and demand_name(FLOWS[0]) in drift["flagged"]
    assert drift["maxAbsRelativeChange"] > 0.15
    # the old parameters no longer fit the new window; the refit does
    assert (
        report["after"]["metrics"]["rmseVph"] < report["before"]["metrics"]["rmseVph"]
    )
    fitted = report["parameters"]["fitted"][demand_name(FLOWS[0])]
    assert (
        abs(fitted - changed[demand_name(FLOWS[0])]) / changed[demand_name(FLOWS[0])]
        <= 0.2
    )


def test_recalibration_on_unchanged_demand_reports_no_drift(recovered):
    counts = load_counts_csv(_counts_text(), known_links=GRAPH.link_map())
    report = recalibrate(
        GRAPH,
        FLOWS,
        counts,
        recovered["parameters"]["fitted"],
        options=FitOptions(budget=60, initial_step=0.05),
    )
    assert not report["recalibration"]["drift"]["drifted"]
    assert report["recalibration"]["previousParametersGCalPassed"]


# ----------------------------------------------------------------- router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_api_key] = lambda: None
    app.dependency_overrides[get_current_user_id] = lambda: "tester"
    app.dependency_overrides[compute_slot] = lambda: None
    return TestClient(app)


def _body(**extra):
    body = {
        "graph": serialize_graph(GRAPH),
        "flows": [
            {
                "origin": f.origin,
                "destination": f.destination,
                "vehiclesPerHour": f.vehicles_per_hour,
            }
            for f in FLOWS
        ],
        "countsCsv": _counts_text(),
        "options": {"budget": 30},
    }
    body.update(extra)
    return body


def test_router_validate_counts_and_fit_and_recalibrate():
    client = _client()
    bad = client.post(
        "/api/v2/calibration/network-fit/validate-counts",
        json={"graph": serialize_graph(GRAPH), "countsCsv": "link_id,count\n"},
    )
    assert (
        bad.status_code == 200 and bad.json()["valid"] is False and bad.json()["errors"]
    )

    ok = client.post(
        "/api/v2/calibration/network-fit/validate-counts",
        json={"graph": serialize_graph(GRAPH), "countsCsv": _counts_text()},
    )
    assert ok.json()["valid"] and ok.json()["provenance"]["intervals"] == 4

    fit = client.post("/api/v2/calibration/network-fit", json=_body())
    assert fit.status_code == 200
    report = fit.json()
    assert report["format"] == "urbanflow-network-calibration"
    assert report["optimiser"]["evaluations"] <= 30

    again = client.post(
        "/api/v2/calibration/network-fit/recalibrate",
        json=_body(previous=report["parameters"]["fitted"], windowIntervals=2),
    )
    assert (
        again.status_code == 200
        and again.json()["recalibration"]["windowIntervals"] == 2
    )


def test_router_rejects_bad_requests_with_plain_messages():
    client = _client()
    r = client.post("/api/v2/calibration/network-fit", json=_body(graph={"nodes": 3}))
    assert r.status_code == 400 and "Invalid graph" in r.json()["detail"]
    r = client.post(
        "/api/v2/calibration/network-fit", json=_body(countsCsv="link_id,count\n")
    )
    assert r.status_code == 400 and "missing column" in r.json()["detail"]
    r = client.post(
        "/api/v2/calibration/network-fit", json=_body(options={"budget": 100000})
    )
    assert r.status_code == 422
