"""Cancel and resume of ``/api/v3`` experiments (W7 Stage 3) and the daily simulated-seconds quota (Stage 2)."""

from __future__ import annotations

import threading
import time
from typing import Any, List, Optional

import pytest

from src.experiments import limits
from src.experiments.service import ExperimentService
from src.experiments.store import ExperimentStore, UsageStore
from src.study.runner import CancelledRun

from .conftest import (
    FakeExecutor,
    as_user,
    build_client,
    experiment,
    submit,
    wait_for,
)

ALICE, BOB = "alice", "bob"
TOTAL_RUNS = 40  # experiment(): 10 conditions x 2 alternatives x 2 replications


class GatedExecutor:
    """Runs canned tasks in order; after ``after`` tasks it waits for the test, then honours a cancel."""

    def __init__(self, after: Optional[int] = None) -> None:
        self.after = after
        self.reached = threading.Event()
        self.release = threading.Event()
        self.batches: List[int] = []
        self._canned = FakeExecutor()

    def __call__(self, tasks: List[Any], progress: Any = None) -> List[Any]:
        self.batches.append(len(tasks))
        out: List[Any] = []
        for i, task in enumerate(tasks):
            if self.after is not None and i == self.after:
                self.reached.set()
                assert self.release.wait(30), "test never released the executor"
            if progress is not None and progress.cancelled:
                out.append(CancelledRun())
                continue
            out.append(self._canned([task])[0])
        return out


def wait_settled(
    service: ExperimentService, experiment_id: str, user: str = ALICE
) -> dict:
    for _ in range(300):
        record = service.store.get(user, experiment_id)
        if record is not None and not record.get("settling"):
            return record
        time.sleep(0.02)
    raise AssertionError("experiment never settled")


def start_and_cancel(make_service, after: int = 12, persist: bool = False):
    executor = GatedExecutor(after=after)
    service = make_service(executor, persist=persist)
    client = build_client(service)
    accepted = submit(client, ALICE)
    assert executor.reached.wait(30)
    cancelled = client.post(
        f"/api/v3/experiments/{accepted['id']}/cancel", headers=as_user(ALICE)
    )
    executor.release.set()
    return service, client, executor, accepted["id"], cancelled


def test_cancel_a_running_experiment_keeps_what_finished(make_service):
    service, client, _executor, eid, cancelled = start_and_cancel(
        make_service, after=12
    )
    assert cancelled.status_code == 202
    assert cancelled.json()["status"] == "cancelled"
    record = wait_settled(service, eid)
    assert record["status"] == "cancelled"
    assert len(record["checkpoint"]) == 12

    body = client.get(f"/api/v3/experiments/{eid}/result", headers=as_user(ALICE))
    assert body.status_code == 200
    partial = body.json()
    assert partial["format"] == "urbanflow-experiment-partial-result"
    assert partial["complete"] is False
    assert partial["runs"] == {
        "planned": TOTAL_RUNS,
        "completed": 12,
        "resumable": True,
    }
    assert "resultFingerprint" not in partial and "manifest" not in partial


def test_unfinished_conditions_are_excluded_as_incomplete_cancelled(make_service):
    service, _client, _executor, eid, _ = start_and_cancel(make_service, after=12)
    partial = wait_settled(service, eid)["result"]
    reasons = partial["analysis"]["exclusions"]["byReason"]
    assert reasons.get("incomplete_cancelled", 0) > 0


def test_resume_runs_only_the_missing_runs_and_reproduces_the_fingerprint(make_service):
    service, client, executor, eid, _ = start_and_cancel(make_service, after=12)
    wait_settled(service, eid)

    resumed = client.post(f"/api/v3/experiments/{eid}/resume", headers=as_user(ALICE))
    assert resumed.status_code == 202
    done = wait_for(client, eid)
    assert done["status"] == "completed"
    assert (
        executor.batches[-1] == TOTAL_RUNS - 12
    )  # nothing already finished was run again
    result = client.get(
        f"/api/v3/experiments/{eid}/result", headers=as_user(ALICE)
    ).json()
    assert result["format"] == "urbanflow-experiment-result"
    assert result["execution"]["runsFromCheckpoint"] == 12

    # An uninterrupted run of the same request gives the same fingerprint.
    clean_client = build_client(make_service(FakeExecutor()))
    clean_id = submit(clean_client, BOB)["id"]
    wait_for(clean_client, clean_id, user=BOB)
    clean = clean_client.get(
        f"/api/v3/experiments/{clean_id}/result", headers=as_user(BOB)
    ).json()
    assert result["resultFingerprint"] == clean["resultFingerprint"]
    assert result["analysis"] == clean["analysis"]


def test_cancel_is_idempotent_and_state_transitions_are_guarded(make_service):
    service, client, _executor, eid, _ = start_and_cancel(make_service, after=5)
    wait_settled(service, eid)
    again = client.post(f"/api/v3/experiments/{eid}/cancel", headers=as_user(ALICE))
    assert again.status_code == 202 and again.json()["status"] == "cancelled"

    # Not the owner's: indistinguishable from a missing one.
    assert (
        client.post(
            f"/api/v3/experiments/{eid}/cancel", headers=as_user(BOB)
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v3/experiments/{eid}/resume", headers=as_user(BOB)
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v3/experiments/nope/cancel", headers=as_user(ALICE)
        ).status_code
        == 404
    )

    assert (
        client.post(
            f"/api/v3/experiments/{eid}/resume", headers=as_user(ALICE)
        ).status_code
        == 202
    )
    wait_for(client, eid)
    # A completed experiment can be neither cancelled nor resumed; a second resume is refused.
    assert (
        client.post(
            f"/api/v3/experiments/{eid}/cancel", headers=as_user(ALICE)
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v3/experiments/{eid}/resume", headers=as_user(ALICE)
        ).status_code
        == 409
    )


def test_resume_is_refused_unless_cancelled(make_service):
    release = threading.Event()
    client = build_client(make_service(FakeExecutor(block=release)))
    try:
        accepted = submit(client, ALICE)
        refused = client.post(
            f"/api/v3/experiments/{accepted['id']}/resume", headers=as_user(ALICE)
        )
        assert refused.status_code == 409 and "cancelled" in refused.json()["detail"]
    finally:
        release.set()
        wait_for(client, accepted["id"])


def test_delete_after_cancel_is_allowed_but_not_while_stopping(make_service):
    executor = GatedExecutor(after=3)
    service = make_service(executor)
    client = build_client(service)
    eid = submit(client, ALICE)["id"]
    assert executor.reached.wait(30)
    client.post(f"/api/v3/experiments/{eid}/cancel", headers=as_user(ALICE))
    # Cancelled, but a simulation is still finishing: it still counts and cannot be deleted or resumed.
    assert (
        client.delete(f"/api/v3/experiments/{eid}", headers=as_user(ALICE)).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v3/experiments/{eid}/resume", headers=as_user(ALICE)
        ).status_code
        == 409
    )
    assert service.store.active(ALICE) == 1
    executor.release.set()
    wait_settled(service, eid)
    assert service.store.active(ALICE) == 0
    assert (
        client.delete(f"/api/v3/experiments/{eid}", headers=as_user(ALICE)).status_code
        == 200
    )


def test_cancel_while_queued_never_starts_the_run(make_service, monkeypatch):
    executor = GatedExecutor()
    service = make_service(executor)
    held: List[Any] = []
    monkeypatch.setattr(service.jobs, "submit", lambda kind, work: held.append(work))
    client = build_client(service)
    eid = submit(client, ALICE)["id"]
    assert (
        client.post(
            f"/api/v3/experiments/{eid}/cancel", headers=as_user(ALICE)
        ).status_code
        == 202
    )
    from src.study.runner import Progress

    held[0](Progress())  # the job now reaches the front of the queue
    record = wait_settled(service, eid)
    assert record["status"] == "cancelled" and executor.batches == []
    # Resuming a never-started experiment simply runs all of it.
    monkeypatch.undo()
    assert (
        client.post(
            f"/api/v3/experiments/{eid}/resume", headers=as_user(ALICE)
        ).status_code
        == 202
    )
    assert wait_for(client, eid)["status"] == "completed"
    assert executor.batches == [TOTAL_RUNS]


def test_concurrent_cancel_and_resume_requests_leave_one_consistent_state(make_service):
    service, client, _executor, eid, _ = start_and_cancel(make_service, after=8)
    wait_settled(service, eid)
    codes: List[int] = []

    def resume() -> None:
        codes.append(
            client.post(
                f"/api/v3/experiments/{eid}/resume", headers=as_user(ALICE)
            ).status_code
        )

    threads = [threading.Thread(target=resume) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(codes).count(202) == 1 and set(codes) <= {202, 409}
    assert wait_for(client, eid)["status"] == "completed"


def test_cancelling_after_every_run_finished_still_resumes_cleanly(make_service):
    service = make_service(FakeExecutor())
    client = build_client(service)
    eid = submit(client, ALICE)["id"]
    wait_for(client, eid)
    assert (
        client.post(
            f"/api/v3/experiments/{eid}/cancel", headers=as_user(ALICE)
        ).status_code
        == 409
    )


def test_cancellation_survives_a_restart(make_service):
    service, _client, _executor, eid, _ = start_and_cancel(
        make_service, after=10, persist=True
    )
    wait_settled(service, eid)
    restarted = ExperimentService(
        executor=GatedExecutor(), store=ExperimentStore(persist=True)
    )
    record = restarted.store.get(ALICE, eid)
    assert record is not None and record["status"] == "cancelled"
    assert len(record["checkpoint"]) == 10
    client = build_client(restarted)
    assert (
        client.post(
            f"/api/v3/experiments/{eid}/resume", headers=as_user(ALICE)
        ).status_code
        == 202
    )
    assert wait_for(client, eid)["status"] == "completed"


# ---- daily simulated seconds (Stage 2) ----------------------------------------------------------------


def test_daily_simulated_seconds_quota_names_itself(make_service, monkeypatch):
    monkeypatch.setattr(limits, "MAX_DAILY_SIMULATED_SECONDS_PER_USER", 3000)
    client = build_client(make_service(FakeExecutor()))
    first = submit(client, ALICE)  # 40 runs x 60 s = 2400 s
    wait_for(client, first["id"])
    second = client.post(
        "/api/v3/experiments", json=experiment(), headers=as_user(ALICE)
    )
    assert second.status_code == 429
    assert "maxDailySimulatedSecondsPerUser" in second.json()["detail"]
    # Another user has their own day.
    submit(client, BOB)


def test_an_experiment_that_can_never_fit_in_a_day_is_422(make_service, monkeypatch):
    monkeypatch.setattr(limits, "MAX_DAILY_SIMULATED_SECONDS_PER_USER", 1000)
    client = build_client(make_service(FakeExecutor()))
    res = client.post("/api/v3/experiments", json=experiment(), headers=as_user(ALICE))
    assert res.status_code == 422
    assert "maxDailySimulatedSecondsPerUser" in str(res.json()["detail"])


def test_cancellation_refunds_the_runs_that_never_ran(make_service):
    service, _client, _executor, eid, _ = start_and_cancel(make_service, after=20)
    wait_settled(service, eid)
    # Half of 40 runs of 60 s were kept.
    assert service.usage.used(ALICE) == pytest.approx(20 * 60)


@pytest.mark.parametrize("persist", [False, True])
def test_usage_reservations_are_atomic_under_concurrency(
    tmp_path, monkeypatch, persist
):
    monkeypatch.setattr("src.database.db.DB_PATH", str(tmp_path / "usage.db"))
    store = UsageStore(persist=persist)
    wins: List[bool] = []
    barrier = threading.Barrier(24)
    lock = threading.Lock()

    def reserve() -> None:
        barrier.wait()
        ok, _used = store.reserve("racer", 100, 1000)
        with lock:
            wins.append(ok)

    threads = [threading.Thread(target=reserve) for _ in range(24)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert wins.count(True) == 10 and store.used("racer") == 1000


def test_usage_persists_across_a_restart(tmp_path, monkeypatch):
    monkeypatch.setattr("src.database.db.DB_PATH", str(tmp_path / "usage.db"))
    assert UsageStore(persist=True).reserve("u", 500, 1000, day="2026-01-01")[0]
    again = UsageStore(persist=True)
    assert again.used("u", day="2026-01-01") == 500
    assert not again.reserve("u", 600, 1000, day="2026-01-01")[0]
    assert again.reserve("u", 600, 1000, day="2026-01-02")[0]  # a new UTC day
    again.release("u", 200, "2026-01-01")
    assert again.used("u", day="2026-01-01") == 300
    again.release("u", 9999, "2026-01-01")
    assert again.used("u", day="2026-01-01") == 0  # floored at zero


def test_real_engine_cancel_then_resume_reproduces_the_uninterrupted_fingerprint(
    monkeypatch,
):
    """On the real process pool: cancel as soon as work has started, resume, compare with a clean run."""
    from src.study import runner

    monkeypatch.setenv("STUDY_WORKERS", "2")
    body = experiment()
    body["scenario"]["simulation"] = {"duration": 40, "warmup": 5, "seed": 3}
    body["uncertainty"].update(conditions=6, replications=1)
    try:
        service = ExperimentService(store=ExperimentStore(persist=False))
        client = build_client(service)
        eid = client.post(
            "/api/v3/experiments", json=body, headers=as_user(ALICE)
        ).json()["id"]
        for _ in range(600):  # until the pool is busy
            progress = client.get(
                f"/api/v3/experiments/{eid}", headers=as_user(ALICE)
            ).json()["progress"]
            if progress and progress.get("running"):
                break
            time.sleep(0.05)
        assert (
            client.post(
                f"/api/v3/experiments/{eid}/cancel", headers=as_user(ALICE)
            ).status_code
            == 202
        )
        record = wait_settled(service, eid)
        assert record["status"] == "cancelled"
        assert len(record["checkpoint"]) < 12  # not everything had finished

        assert (
            client.post(
                f"/api/v3/experiments/{eid}/resume", headers=as_user(ALICE)
            ).status_code
            == 202
        )
        assert wait_for(client, eid, timeout=180)["status"] == "completed"
        resumed = client.get(
            f"/api/v3/experiments/{eid}/result", headers=as_user(ALICE)
        ).json()

        other = ExperimentService(store=ExperimentStore(persist=False))
        other_client = build_client(other)
        clean_id = other_client.post(
            "/api/v3/experiments", json=body, headers=as_user(BOB)
        ).json()["id"]
        assert (
            wait_for(other_client, clean_id, user=BOB, timeout=180)["status"]
            == "completed"
        )
        clean = other_client.get(
            f"/api/v3/experiments/{clean_id}/result", headers=as_user(BOB)
        ).json()
        assert resumed["resultFingerprint"] == clean["resultFingerprint"]
        assert resumed["analysis"] == clean["analysis"]
    finally:
        runner.shutdown_pool()
