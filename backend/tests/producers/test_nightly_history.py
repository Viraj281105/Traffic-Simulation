import json
from pathlib import Path

import nightly_history as nh  # noqa: E402
import pytest

from tests.producers import _helpers as h


def _run(day: int, status_check: str = "pass"):
    checks = [nh.make_check("suite", "Suite", status_check)]
    return nh.build_run(
        f"2026-11-0{day}", f"2026-11-0{day}T02:17:00Z", "abc", checks, 12.5
    )


def test_run_status_precedence() -> None:
    c = nh.make_check
    assert nh.run_status([c("a", "A", "pass"), c("b", "B", "skipped")]) == "pass"
    assert nh.run_status([c("a", "A", "pass"), c("b", "B", "fail")]) == "fail"
    assert nh.run_status([c("a", "A", "fail"), c("b", "B", "error")]) == "error"
    with pytest.raises(ValueError):
        c("a", "A", "weird")


def test_append_replaces_same_id_sorts_and_trims(tmp_path: Path) -> None:
    path = tmp_path / "nightly" / "history.json"
    for day in (1, 3, 2):
        nh.append_run(path, _run(day))
    nh.append_run(path, _run(2, "fail"))
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["format"] == "urbanflow-nightly-history"
    assert [r["id"] for r in doc["runs"]] == ["2026-11-03", "2026-11-02", "2026-11-01"]
    assert doc["runs"][1]["status"] == "fail"
    nh.append_run(path, _run(4), keep=2)
    assert [r["id"] for r in json.loads(path.read_text(encoding="utf-8"))["runs"]] == [
        "2026-11-04",
        "2026-11-03",
    ]
    assert b"\r" not in path.read_bytes()


def test_a_damaged_history_is_set_aside_not_lost(tmp_path: Path) -> None:
    path = tmp_path / "nightly" / "history.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    nh.append_run(path, _run(1))
    assert (path.parent / "history.json.bad").read_text(encoding="utf-8") == "{not json"
    assert len(json.loads(path.read_text(encoding="utf-8"))["runs"]) == 1


def test_checked_records_pass_fail_error_and_reraises(tmp_path: Path) -> None:
    nh.checked(
        tmp_path, "d", "ok", "Ok", lambda: {"metric": "m", "actual": 2.0, "unit": "s"}
    )

    def failing():
        raise RuntimeError("command failed with exit status 1")

    def broken():
        raise KeyError("boom")

    with pytest.raises(RuntimeError):
        nh.checked(tmp_path, "d", "bad", "Bad", failing)
    with pytest.raises(KeyError):
        nh.checked(tmp_path, "d", "err", "Err", broken)
    checks, started, total = nh.collect_checks(
        tmp_path, "d", [("ok", "Ok"), ("bad", "Bad"), ("err", "Err"), ("gone", "Gone")]
    )
    assert [c["status"] for c in checks] == ["pass", "fail", "error", "skipped"]
    assert checks[0]["actual"] == 2.0 and "_startedAt" not in checks[0]
    assert "exit status" in checks[1]["message"] and "KeyError" in checks[2]["message"]
    assert started.endswith("Z") and total >= 0.0


def test_record_night_file_passes_the_nightly_endpoint(tmp_path: Path) -> None:
    nh.checked(tmp_path, "2026-11-04", "suite", "Suite", lambda: None)
    nh.checked(
        tmp_path,
        "2026-11-04",
        "study",
        "Study",
        lambda: {"metric": "mean_delay_s", "actual": 9.5, "unit": "s"},
    )
    run = nh.record_night(
        tmp_path, "2026-11-04", [("suite", "Suite"), ("study", "Study")], h.REPO
    )
    assert run["status"] == "pass" and run["gitCommit"]
    body = h.client(tmp_path).get("/api/v3/regression/nightly").json()
    assert [r["id"] for r in body["runs"]] == ["2026-11-04"]
    assert body["runs"][0]["checks"][1]["actual"] == 9.5
    # A second night adds to it; a rerun of the same night replaces.
    nh.record_night(tmp_path, "2026-11-05", [("suite", "Suite")], h.REPO)
    nh.record_night(tmp_path, "2026-11-04", [("suite", "Suite")], h.REPO)
    body = h.client(tmp_path).get("/api/v3/regression/nightly").json()
    assert [r["id"] for r in body["runs"]] == ["2026-11-05", "2026-11-04"]


def test_dag_tasks_record_a_failure_and_still_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import nightly_regression as dag
    import urbanflow_common as common

    def boom(cmd, cwd=None):
        raise RuntimeError("exit 1")

    monkeypatch.setattr(common, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(common, "run", boom)
    with pytest.raises(RuntimeError):
        dag.run_backend_suite("d1")
    dag.record_history("d1")
    body = h.client(tmp_path).get("/api/v3/regression/nightly").json()
    statuses = {c["id"]: c["status"] for c in body["runs"][0]["checks"]}
    assert statuses == {"backend_suite": "fail", "multiseed_smoke": "skipped"}
    assert body["runs"][0]["status"] == "fail"
