import json
from pathlib import Path

import pytest

from tests.producers import _helpers as h

import produce_sensitivity as ps  # noqa: E402


def _model(points):
    return [6.0 * p["arrivalRate"] + 1.0 * p["greenTime"] for p in points]


def test_parse_bounds() -> None:
    assert ps.parse_bounds(["arrivalRate=0.1:0.5", "greenTime=15:60"]) == {
        "arrivalRate": (0.1, 0.5),
        "greenTime": (15.0, 60.0),
    }
    for bad in ("arrivalRate", "arrivalRate=1", "bogus=1:2", "greenTime=a:b"):
        with pytest.raises(ValueError):
            ps.parse_bounds([bad])


def test_build_sensitivity_doc_wraps_the_result() -> None:
    from src.study.sensitivity import sobol_lite

    result = sobol_lite(_model, {"arrivalRate": (0.0, 1.0), "greenTime": (0.0, 1.0)}, 32, seed=1)
    doc = ps.build_sensitivity_doc("mean_delay_s", result)
    assert doc["format"] == "urbanflow-sensitivity" and doc["version"] == 1
    assert doc["metric"] == {"id": "mean_delay_s", "label": "Mean delay", "unit": "s"}
    assert doc["inputs"]["arrivalRate"]["unit"] == "veh/s"
    assert doc["result"]["method"] == "sobol-lite"
    with pytest.raises(ValueError):
        ps.build_sensitivity_doc("nope", result)
    with pytest.raises(ValueError):
        ps.build_sensitivity_doc("mean_delay_s", {"method": "one-at-a-time", "ranking": []})


def test_end_to_end_with_a_model_passes_the_sensitivity_endpoint(tmp_path: Path) -> None:
    path = ps.produce(
        h.EXPERIMENT,
        {"arrivalRate": (0.0, 1.0), "greenTime": (0.0, 1.0)},
        samples=64,
        seed=3,
        results_dir=tmp_path,
        evaluate_many=_model,
    )
    assert path == tmp_path / "experiments" / h.EXPERIMENT / "sensitivity.json"
    assert b"\r" not in path.read_bytes()
    body = h.client(tmp_path).get(f"/api/v3/experiments/{h.EXPERIMENT}/sensitivity").json()
    assert {i["id"] for i in body["inputs"]} == {"arrivalRate", "greenTime"}
    assert body["method"]["samples"] == 64 and body["method"]["seed"] == 3
    assert json.loads(path.read_text(encoding="utf-8"))["metric"]["id"] == "mean_delay_s"


def test_end_to_end_with_the_simulation_and_tiny_durations(tmp_path: Path) -> None:
    code = ps.main(
        ["--experiment-id", h.EXPERIMENT, "--input", "arrivalRate=0.1:0.6",
         "--input", "greenTime=10:40", "--samples", "4", "--num-seeds", "1",
         "--duration", "30", "--seed", "5", "--results-dir", str(tmp_path)]
    )
    assert code == 0
    res = h.client(tmp_path).get(f"/api/v3/experiments/{h.EXPERIMENT}/sensitivity")
    # 200 when the delay varied across points; 404 if this tiny run produced a constant output.
    assert res.status_code in (200, 404)
    doc = json.loads(
        (tmp_path / "experiments" / h.EXPERIMENT / "sensitivity.json").read_text(encoding="utf-8")
    )
    assert doc["result"]["evaluations"] == 4 * (2 + 2)


def test_cli_error_exit_code(tmp_path: Path) -> None:
    assert ps.main(["--experiment-id", "x", "--input", "bogus=1:2", "--results-dir", str(tmp_path)]) == 2
