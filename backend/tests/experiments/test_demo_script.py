"""scripts/v3_demo.py: the demo experiment is valid for the real server model, its report prints what the
server computed, and the offline fallback refuses a file that was changed after it was saved."""

import importlib.util
import json
from pathlib import Path

import pytest

from src.experiments.preparation import prepare

from .conftest import as_user, build_client, wait_for

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "v3_demo.py"


@pytest.fixture(scope="module")
def demo():
    spec = importlib.util.spec_from_file_location("v3_demo", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _result(make_service, demo):
    client = build_client(make_service())
    accepted = client.post(
        "/api/v3/experiments", json=demo.EXPERIMENT, headers=as_user("alice")
    ).json()
    wait_for(client, accepted["id"])
    return client.get(
        f"/api/v3/experiments/{accepted['id']}/result", headers=as_user("alice")
    ).json()


def test_the_demo_experiment_is_valid_and_has_the_advertised_size(demo):
    prepared = prepare(demo.EXPERIMENT)
    assert prepared.errors == []
    # the engine's own notes (mixed vehicle classes are model inputs) are expected; a too-short
    # measured window is not
    assert not any("measured after warm-up" in w for w in prepared.warnings)
    assert prepared.counts == {
        "conditions": 24,
        "alternatives": 3,
        "replications": 2,
        "totalRuns": 144,
    }
    kinds = {f["kind"] for f in demo.EXPERIMENT["uncertainty"]["factors"]}
    assert kinds == {"demand_scale", "turning_shift", "mix_shift", "headway_scale"}
    # every assumption is stated as an assumption, with a reason
    for factor in demo.EXPERIMENT["uncertainty"]["factors"]:
        assert factor["basis"] == "assumed" and factor["rationale"]


def test_the_report_prints_the_servers_numbers_and_the_limits(
    demo, make_service, capsys
):
    result = _result(make_service, demo)
    demo.print_report(result)
    out = capsys.readouterr().out
    assert "Real-world validity: None — assumptions only" in out
    assert "24 conditions x 3 alternatives x 2 replications = 144 runs" in out
    assert "Eligibility: EXPLORATORY" in out  # 24 < 30 valid conditions
    assert "stability" in out and "not assessed" in out
    assert "Fixed-time signal" in out and "Conventional roundabout" in out
    assert "not a ranking" in out
    assert "winner" not in out.lower().replace("names a winner", "")


def test_save_then_offline_round_trips_and_checks_the_checksums(
    demo, make_service, tmp_path, capsys
):
    result = _result(make_service, demo)
    demo.save(tmp_path, demo.EXPERIMENT, result, True, "http://test")
    names = {p.name for p in tmp_path.iterdir()}
    assert names == {"experiment.json", "result.json", "MANIFEST.json", "SHA256SUMS"}
    capsys.readouterr()
    demo.offline(tmp_path)
    out = capsys.readouterr().out
    assert "OFFLINE: showing a precomputed result, not a live run." in out
    assert "checksums verified" in out and "OK (offline)" in out
    assert json.loads((tmp_path / "experiment.json").read_text()) == demo.EXPERIMENT


def test_offline_refuses_a_file_that_was_changed(demo, make_service, tmp_path):
    result = _result(make_service, demo)
    demo.save(tmp_path, demo.EXPERIMENT, result, None, "http://test")
    path = tmp_path / "result.json"
    path.write_text(path.read_text().replace("assumptions only", "validated"))
    with pytest.raises(SystemExit) as stop:
        demo.offline(tmp_path)
    assert stop.value.code == 1


def test_offline_without_a_pack_fails_clearly(demo, tmp_path):
    with pytest.raises(SystemExit) as stop:
        demo.offline(tmp_path / "nothing-here")
    assert stop.value.code == 1


def test_offline_accepts_a_copy_whose_line_endings_were_rewritten(
    demo, make_service, tmp_path, capsys
):
    result = _result(make_service, demo)
    demo.save(tmp_path, demo.EXPERIMENT, result, True, "http://test")
    for name in ("experiment.json", "result.json", "MANIFEST.json"):
        path = tmp_path / name
        # as a Windows editor or a zip tool might
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    capsys.readouterr()
    demo.offline(tmp_path)
    assert "checksums verified" in capsys.readouterr().out


def test_the_committed_example_pack_verifies(demo, capsys):
    pack = SCRIPT.parents[1] / "docs" / "research" / "examples" / "robustness-demo"
    demo.offline(pack)
    out = capsys.readouterr().out
    assert "checksums verified" in out and "OK (offline)" in out
    assert "reproduced the fingerprint: True" in out
