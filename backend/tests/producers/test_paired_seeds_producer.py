import json
from pathlib import Path
from typing import Any, Dict

import produce_paired_seeds as pp  # noqa: E402  (path set up by _helpers)
import pytest

from tests.producers import _helpers as h


def _run(seeds, delay, thr, queue) -> Dict[str, Any]:
    return {
        "seeds": seeds,
        "seedRuns": [
            {"seed": s, "delay": d, "throughput": t, "queue": q}
            for s, d, t, q in zip(seeds, delay, thr, queue)
        ],
    }


def _runs() -> Dict[str, Dict[str, Any]]:
    return {
        "fixed": _run([1, 2, 3], [40.0, 42.0, 39.0], [100, 101, 99], [5.0, 6.0, 5.5]),
        "adaptive": _run(
            [1, 2, 3], [35.0, 36.0, 34.0], [110, 111, 109], [3.0, 3.5, 3.2]
        ),
    }


def test_build_paired_doc_shape_and_values() -> None:
    doc = pp.build_paired_doc(_runs(), baseline="fixed", labels={"fixed": "Fixed time"})
    assert doc["format"] == "urbanflow-paired-seeds" and doc["version"] == 1
    assert doc["primaryMetric"] == "mean_delay_s" and doc["baseline"] == "fixed"
    assert doc["metrics"]["throughput"]["lowerIsBetter"] is False
    fixed = doc["alternatives"]["fixed"]
    assert fixed["label"] == "Fixed time" and fixed["seeds"] == [1, 2, 3]
    assert fixed["values"]["mean_delay_s"] == [40.0, 42.0, 39.0]
    assert doc["alternatives"]["adaptive"]["label"] == "adaptive"
    assert "metricsRunId" not in doc
    json.dumps(doc, allow_nan=False)


def test_build_paired_doc_refuses_bad_input() -> None:
    runs = _runs()
    with pytest.raises(ValueError, match="at least two"):
        pp.build_paired_doc({"fixed": runs["fixed"]}, baseline="fixed")
    with pytest.raises(ValueError, match="baseline"):
        pp.build_paired_doc(runs, baseline="nope")
    runs["adaptive"] = _run([1, 2, 4], [1.0] * 3, [1] * 3, [1.0] * 3)
    with pytest.raises(ValueError, match="same seeds"):
        pp.build_paired_doc(runs, baseline="fixed")
    with pytest.raises(ValueError, match="alternative id"):
        pp.build_paired_doc(
            {"../x": _runs()["fixed"], "b": _runs()["adaptive"]}, baseline="b"
        )


def test_deep_merge_does_not_mutate_inputs() -> None:
    base = {"controller": {"a": 1}, "x": 1}
    merged = pp.deep_merge(base, {"controller": {"signalControl": "adaptive"}})
    assert merged == {"controller": {"a": 1, "signalControl": "adaptive"}, "x": 1}
    assert base == {"controller": {"a": 1}, "x": 1}


def test_parse_alternatives() -> None:
    out = pp.parse_alternatives(
        ["fixed=signal", "ad=signal"],
        ['ad={"controller":{"signalControl":"adaptive"}}'],
    )
    assert out["fixed"] == {"geometry": "signal", "overrides": {}}
    assert out["ad"]["overrides"]["controller"]["signalControl"] == "adaptive"
    with pytest.raises(ValueError):
        pp.parse_alternatives(["a=hexagon"], [])
    with pytest.raises(ValueError):
        pp.parse_alternatives(["a=signal"], ["b={}"])
    with pytest.raises(ValueError):
        pp.parse_alternatives(["a=signal"], ["a=[1]"])
    with pytest.raises(ValueError):
        pp.parse_alternatives(["a=signal"], ["a={bad"])


def test_cli_rejects_bad_arguments(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = pp.main(
        [
            "--experiment-id",
            "../x",
            "--alt",
            "a=signal",
            "--alt",
            "b=signal",
            "--baseline",
            "a",
            "--results-dir",
            str(tmp_path),
        ]
    )
    assert code == 2 and "experiment id" in capsys.readouterr().err
    assert not list(tmp_path.iterdir())


def test_end_to_end_file_passes_the_comparison_and_report_endpoints(
    tmp_path: Path,
) -> None:
    path = pp.produce(
        h.EXPERIMENT,
        {
            "fixed": {"geometry": "signal", "overrides": {}},
            "adaptive": {
                "geometry": "signal",
                "overrides": {"controller": {"signalControl": "adaptive"}},
            },
        },
        baseline="fixed",
        num_seeds=3,
        duration=40.0,
        base_seed=11,
        labels={"fixed": "Fixed time", "adaptive": "Adaptive"},
        results_dir=tmp_path,
        save_runs=True,
    )
    assert path == tmp_path / "experiments" / h.EXPERIMENT / "paired.json"
    assert b"\r" not in path.read_bytes()
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["metricsRunId"] == f"{h.EXPERIMENT}-fixed"
    assert (
        doc["alternatives"]["fixed"]["seeds"]
        == doc["alternatives"]["adaptive"]["seeds"]
    )

    api = h.client(tmp_path)
    res = api.get(f"/api/v3/experiments/{h.EXPERIMENT}/comparison")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["pairs"] == 3 and body["a"]["label"] == "Fixed time"
    assert body["b"]["id"] == "adaptive"
    assert api.get(f"/api/v3/experiments/{h.EXPERIMENT}/report").status_code == 200
    # The saved per-seed rows are a real stored run; they hold no trips, so values are null, not zero.
    runs = api.get(f"/api/v3/runs/{h.EXPERIMENT}-fixed/metrics")
    assert runs.status_code == 200 and runs.json()["vehiclesCompleted"] is None
