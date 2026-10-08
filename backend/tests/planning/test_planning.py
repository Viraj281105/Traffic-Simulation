"""V2.0 planning: orchestration, comparison, evidence, report, API."""

import csv
import io
import json
import time
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.scenario import parse_scenario, scenario_fingerprint
from src.planning.findings import resolve_path
from src.planning.models import PlanningStudy
from src.planning.report import SECTION_IDS, export
from src.planning.router import create_router
from src.planning.runner import PlanningError, run_study
from src.planning.service import PlanningService, PlanningStore

from .conftest import DEFAULT_PROFILE, SCENARIO, make_fake, study


def run(payload: Dict[str, Any], fake=None) -> Dict[str, Any]:
    return run_study(
        PlanningStudy.model_validate(payload), comparison_fn=fake or make_fake()
    )


def verdict(result, alt, metric, scale=1.0):
    return next(
        c
        for c in result["comparison"]["vsBaseline"]
        if c["alternativeId"] == alt
        and c["metric"] == metric
        and c["demandScale"] == scale
    )


# ---- orchestration --------------------------------------------------------
def test_orchestration_is_deterministic() -> None:
    a, b = run(study()), run(study())
    assert a["meta"]["resultFingerprint"] == b["meta"]["resultFingerprint"]
    assert a["results"] == b["results"]
    assert a["findings"] == b["findings"]


def test_multiple_alternatives_and_scales() -> None:
    r = run(study(demand={"scales": [0.8, 1.2]}))
    assert len(r["alternatives"]) == 3 and r["alternatives"][0]["isBaseline"]
    assert len(r["results"]) == 3 * 2
    # 2 non-baseline alternatives x 2 scales x 4 compared metrics
    assert len(r["comparison"]["vsBaseline"]) == 2 * 2 * 4


def test_default_alternatives_are_the_builtin_strategies() -> None:
    payload = study()
    del payload["alternatives"]
    r = run(payload)
    assert [a["strategy"] for a in r["alternatives"]] == [
        "fixed_time",
        "adaptive",
        "roundabout",
    ]


def test_repetitions_and_seeds() -> None:
    r = run(study(repetitions={"seeds": 4, "baseSeed": 10}))
    assert r["meta"]["seeds"] == [10, 11, 12, 13] == r["reliability"]["seeds"]
    assert r["results"][0]["performance"]["values"]["averageDelay"]["n"] == 4
    assert r["reliability"]["sampleAdequacy"] == "small"


def test_identical_alternatives_run_once() -> None:
    calls: list = []
    payload = study(
        alternatives=[
            {"id": "a", "strategy": "fixed_time"},
            {"id": "b", "label": "Same again", "strategy": "fixed_time"},
        ]
    )
    r = run(payload, make_fake(calls=calls))
    assert len(calls) == 1
    assert verdict(r, "b", "averageDelay")["verdict"] == "tie"


# ---- evidence classification ---------------------------------------------
def test_clear_difference_is_classified_and_cited() -> None:
    r = run(study())
    delay = verdict(r, "adapt", "averageDelay")
    assert delay["verdict"] == "better" and delay["delta"] == -10.0
    texts = [f["statement"] for f in r["findings"]]
    assert any("Adaptive had lower mean delay than Fixed" in t for t in texts)
    assert any("Roundabout served more vehicles than Fixed" in t for t in texts)
    for f in r["findings"]:
        for ev in f["evidence"]:
            assert resolve_path(r, ev["path"]) is not None, ev["path"]


def test_similar_results_are_a_tie_not_a_win() -> None:
    r = run(study())
    assert verdict(r, "rbt", "averageDelay")["verdict"] == "tie"
    assert any("similar mean delay" in f["statement"] for f in r["findings"])


def test_noisy_difference_is_inconclusive() -> None:
    profile = {**DEFAULT_PROFILE, "roundabout": (36.0, 8.0, 100.0)}
    r = run(study(), make_fake(profile))
    c = verdict(r, "rbt", "averageDelay")
    assert c["verdict"] == "inconclusive" and c["ciLow"] < 0 < c["ciHigh"]
    f = next(
        f
        for f in r["findings"]
        if "inconclusive difference in mean delay" in f["statement"]
    )
    assert f["confidence"] == "low"


def test_single_seed_is_inconclusive_and_warned() -> None:
    r = run(study(repetitions={"seeds": 1}))
    assert verdict(r, "adapt", "averageDelay")["verdict"] == "inconclusive"
    assert r["reliability"]["sampleAdequacy"] == "single_run"
    assert any(f["code"] == "small_sample" for f in r["reliability"]["flags"])
    assert any(f["kind"] == "reliability" for f in r["findings"])


def test_demand_sensitivity_is_reported() -> None:
    # adaptive is far better at x1.0 and no different at x1.5
    def effect(strategy: str, scale: float) -> float:
        base = DEFAULT_PROFILE[strategy][0]
        return base + (10.0 if strategy == "adaptive" and scale > 1.2 else 0.0)

    r = run(study(demand={"scales": [1.0, 1.5]}), make_fake(scale_effect=effect))
    sens = [f for f in r["findings"] if f["kind"] == "demand_sensitivity"]
    assert sens and "depends on demand" in sens[0]["statement"]


def _keys(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from _keys(v)
    elif isinstance(node, list):
        for v in node:
            yield from _keys(v)


def test_no_universal_winner_anywhere() -> None:
    r = run(study())
    forbidden = {
        "winner",
        "best",
        "rank",
        "ranking",
        "score",
        "recommended",
        "recommendation",
    }
    assert not forbidden & {k.lower() for k in _keys(r)}
    assert r["summary"]["recommendationBasis"].startswith("None")
    assert all(f["kind"] != "winner" for f in r["findings"])


def test_unavailable_indicators_make_no_claims() -> None:
    r = run(study())
    env = r["results"][0]["environmental"]
    assert {u["key"] for u in env["unavailable"]} >= {"fuelConsumption", "co2Emissions"}
    assert env["status"] == "proxy"
    assert "minTTC" in {u["key"] for u in r["results"][0]["safety"]["unavailable"]}
    assert not any(
        "emission" in f["statement"].lower() and f["kind"] != "note"
        for f in r["findings"]
    )


def test_breakdowns_and_signal_timing_present() -> None:
    r = run(study())
    row = r["results"][0]
    assert "north" in row["perApproach"] and "car" in row["perVehicleType"]
    assert row["signalTiming"] is not None
    assert r["results"][2]["signalTiming"] is None  # roundabout


# ---- scenario, patches, fingerprints -------------------------------------
def test_scenario_fingerprint_propagates() -> None:
    doc, _ = parse_scenario(SCENARIO)
    fp = scenario_fingerprint(doc)
    r = run(study())
    assert r["scenario"]["fingerprint"] == fp == r["meta"]["scenarioFingerprint"]
    assert r["scenario"]["id"] == f"scn_{fp}"
    assert {a["fingerprint"] for a in r["alternatives"]} == {
        fp
    }  # same scenario, control differs
    assert r["meta"]["scenarioFingerprints"] == {"base": fp, "adapt": fp, "rbt": fp}
    assert r["report"]["scenarioFingerprint"] == fp


def test_patched_alternative_gets_its_own_fingerprint_and_change_list() -> None:
    payload = study(
        alternatives=[
            {"id": "base", "strategy": "fixed_time"},
            {
                "id": "long",
                "strategy": "fixed_time",
                "patch": {"signal": {"greenTime": 45}},
            },
        ]
    )
    r = run(payload)
    base, long_ = r["alternatives"]
    assert base["fingerprint"] != long_["fingerprint"]
    assert long_["changesFromBase"] == ["signal.greenTime"]
    assert r["scenario"]["fingerprint"] == base["fingerprint"]


def test_invalid_patches_are_rejected() -> None:
    for patch in (
        {"nonsense": 1},
        {"simulation": {"seed": 9}},
        {"signal": {"greenTime": 1}},
    ):
        payload = study(
            alternatives=[
                {"id": "base", "strategy": "fixed_time"},
                {"id": "bad", "strategy": "fixed_time", "patch": patch},
            ]
        )
        with pytest.raises(PlanningError):
            run(payload)


def test_demand_changing_patch_is_flagged() -> None:
    payload = study(
        alternatives=[
            {"id": "base", "strategy": "fixed_time"},
            {
                "id": "more",
                "strategy": "fixed_time",
                "patch": {"approaches": {"north": {"vehiclesPerHour": 500}}},
            },
        ]
    )
    r = run(payload)
    assert any(
        "not compared under the same traffic" in w
        for w in r["alternatives"][1]["warnings"]
    )


def test_fingerprint_mismatch_from_comparison_is_an_error() -> None:
    good = make_fake()

    def bad(document, *a, **k):
        out = good(document, *a, **k)
        out["fingerprint"] = "0" * 16
        return out

    with pytest.raises(PlanningError, match="does not match"):
        run(study(), bad)


def test_study_model_rejects_bad_requests() -> None:
    for over in (
        {"alternatives": [{"id": "a", "strategy": "x"}, {"id": "a", "strategy": "x"}]},
        {"repetitions": {"seeds": 31}},
        {"unknown": 1},
        {"subject": {}},  # a subject is required (scenario or network)
    ):
        with pytest.raises(Exception):
            PlanningStudy.model_validate(study(**over))
    with pytest.raises(Exception):
        PlanningStudy.model_validate(
            study(
                demand={"scales": [1, 1.1, 1.2, 1.3, 1.4, 1.5]},
                repetitions={"seeds": 30},
            )
        )


# ---- report ---------------------------------------------------------------
def test_report_structure_and_exports() -> None:
    r = run(study())
    ids = [s["id"] for s in r["report"]["sections"]]
    assert ids == list(SECTION_IDS)
    assert (
        json.loads(export(r, "json")["content"])["format"]
        == "urbanflow-planning-result"
    )
    md = export(r, "md")["content"]
    assert "Fixed" in md and "## Findings" in md and "## Limitations" in md
    rows = list(csv.DictReader(io.StringIO(export(r, "csv")["content"])))
    assert rows and {x["scenarioFingerprint"] for x in rows} == {
        r["scenario"]["fingerprint"]
    }
    fuel = [x for x in rows if x["indicator"] == "fuelConsumption"]
    assert fuel and all(x["status"] == "unavailable" and x["mean"] == "" for x in fuel)
    delay = next(
        x
        for x in rows
        if x["alternativeId"] == "adapt"
        and x["group"] == "performance"
        and x["indicator"] == "averageDelay"
    )
    assert float(delay["mean"]) == pytest.approx(19.9)
    with pytest.raises(ValueError):
        export(r, "pdf")


def test_result_is_json_serialisable_and_round_trips() -> None:
    r = run(study())
    assert json.loads(json.dumps(r)) == r


# ---- reproducibility ------------------------------------------------------
def test_meta_is_reproducible() -> None:
    r = run(study())
    m = r["meta"]
    assert m["gitCommit"] and m["pythonVersion"] and m["inputFingerprint"]
    assert set(m["compiledConfigs"]) == {"base", "adapt", "rbt"}
    assert m["timeStep"] == 0.1 and m["request"]["name"] == "Test study"
    again = run(m["request"])
    assert again["meta"]["inputFingerprint"] == m["inputFingerprint"]
    assert again["meta"]["resultFingerprint"] == m["resultFingerprint"]


# ---- API ------------------------------------------------------------------
@pytest.fixture
def client() -> TestClient:
    svc = PlanningService(store=PlanningStore(persist=False), comparison_fn=make_fake())
    app = FastAPI()
    current = {"user": "alice"}
    app.include_router(
        create_router(user_dependency=lambda: current["user"], service=svc)
    )
    c = TestClient(app)
    c.current = current  # type: ignore[attr-defined]
    return c


def test_api_validate(client: TestClient) -> None:
    ok = client.post("/api/v2/planning/validate", json=study()).json()
    assert ok["valid"] and ok["simulations"] == 15 and len(ok["alternatives"]) == 3
    bad = client.post("/api/v2/planning/validate", json=study(unknown=1)).json()
    assert not bad["valid"] and bad["errors"]


def test_api_run_retrieve_export_reproduce(client: TestClient) -> None:
    done = client.post("/api/v2/planning/run", json=study()).json()
    assert done["status"] == "completed"
    sid = done["id"]
    got = client.get(f"/api/v2/planning/{sid}").json()
    assert (
        got["result"]["meta"]["resultFingerprint"]
        == done["result"]["meta"]["resultFingerprint"]
    )
    csv_resp = client.get(f"/api/v2/planning/{sid}/report?format=csv")
    assert csv_resp.status_code == 200 and csv_resp.text.startswith(
        "scenarioFingerprint"
    )
    assert client.get(f"/api/v2/planning/{sid}/report?format=md").status_code == 200
    assert client.get(f"/api/v2/planning/{sid}/report?format=pdf").status_code == 422
    assert client.post(f"/api/v2/planning/{sid}/reproduce").json()["reproduced"] is True


def test_api_job_flow_and_ownership(client: TestClient) -> None:
    r = client.post("/api/v2/planning/jobs", json=study())
    assert r.status_code == 202
    sid = r.json()["id"]
    body: Dict[str, Any] = {}
    for _ in range(100):
        body = client.get(f"/api/v2/planning/{sid}").json()
        if body["status"] in ("completed", "failed"):
            break
        time.sleep(0.05)
    assert body["status"] == "completed" and body["result"]["findings"]
    client.current["user"] = "mallory"  # type: ignore[attr-defined]
    assert client.get(f"/api/v2/planning/{sid}").status_code == 404
    assert client.get(f"/api/v2/planning/{sid}/report").status_code == 404


def test_api_rejects_invalid_study(client: TestClient) -> None:
    assert client.post("/api/v2/planning/run", json=study(unknown=1)).status_code == 422
    assert (
        client.post("/api/v2/planning/jobs", json=study(unknown=1)).status_code == 422
    )
    assert client.get("/api/v2/planning/nope").status_code == 404


# ---- one tiny real simulation --------------------------------------------
def test_real_comparison_end_to_end_is_deterministic() -> None:
    payload = study(
        alternatives=[
            {"id": "fixed", "strategy": "fixed_time"},
            {"id": "rbt", "strategy": "roundabout"},
        ],
        repetitions={"seeds": 2, "baseSeed": 1},
    )
    a = run_study(PlanningStudy.model_validate(payload))
    b = run_study(PlanningStudy.model_validate(payload))
    assert a["meta"]["resultFingerprint"] == b["meta"]["resultFingerprint"]
    assert a["meta"]["seeds"] == [1, 2]
    assert {r["alternativeId"] for r in a["results"]} == {"fixed", "rbt"}
    assert a["results"][0]["performance"]["values"]["throughput"]["n"] == 2
    assert a["reliability"]["sampleAdequacy"] == "small"
