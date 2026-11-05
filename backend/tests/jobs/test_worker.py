"""Worker: idempotency, retries, poison handling, graceful shutdown and the default runner."""

from typing import Any, Dict, List

from src.jobs import (
    ComputeTimeRecorder,
    InMemoryJobQueue,
    JobMessage,
    Outcome,
    Worker,
)
from src.runstore import RunStore

from .conftest import Clock, fake_runner, make_message


def _worker(
    queue: InMemoryJobQueue, store: RunStore, runner: Any = fake_runner
) -> Worker:
    return Worker(queue, store, runner=runner, wait_seconds=0, idle_sleep=0.01)


def test_job_runs_stores_and_acks(queue: InMemoryJobQueue, store: RunStore) -> None:
    message = make_message()
    queue.send(message)
    recorder = ComputeTimeRecorder()
    worker = Worker(queue, store, runner=fake_runner, recorder=recorder, wait_seconds=0)
    (result,) = worker.run_once()
    assert result.outcome is Outcome.COMPLETED
    assert store.list_runs() == [message.run_id]
    stored = store.load_run(message.run_id)
    assert [r["seed"] for r in stored.records] == [0, 1]
    assert stored.records[0]["geometry"] == "signal"
    assert queue.stats().visible == 0 and queue.stats().in_flight == 0
    (usage,) = recorder.records()
    assert usage.succeeded and usage.tenant == "acme"
    assert usage.tags["run-id"] == message.run_id
    job_record = store.backend.get(f"runs/{message.run_id}/job.json")
    assert b'"tenant": "acme"' in job_record


def test_redelivered_job_is_not_run_twice(
    queue: InMemoryJobQueue, store: RunStore, clock: Clock
) -> None:
    runs: List[str] = []

    def counting(message: JobMessage) -> Dict[str, Any]:
        runs.append(message.run_id)
        return fake_runner(message)

    message = make_message()
    queue.send(message)
    worker = _worker(queue, store, counting)
    worker.run_once()
    # The same job arrives again under another idempotency key (a duplicate submit or SQS redelivery).
    queue.send(make_message(idempotencyKey="again", runId=message.run_id))
    (second,) = worker.run_once()
    assert second.outcome is Outcome.DUPLICATE
    assert runs == [message.run_id]
    assert queue.stats().visible == 0


def test_failed_job_is_retried_with_backoff_then_dead_lettered(
    queue: InMemoryJobQueue, store: RunStore, clock: Clock
) -> None:
    def boom(message: JobMessage) -> Dict[str, Any]:
        raise RuntimeError("engine crashed")

    queue.send(make_message())
    worker = _worker(queue, store, boom)
    (first,) = worker.run_once()
    assert first.outcome is Outcome.RETRY and "engine crashed" in first.detail
    assert worker.run_once() == []  # backing off for 5 s
    clock.advance(5)
    assert worker.run_once()[0].outcome is Outcome.RETRY
    clock.advance(10)
    assert worker.run_once()[0].outcome is Outcome.RETRY
    clock.advance(1000)
    assert (
        worker.run_once() == []
    )  # fourth receive: over the queue limit, dead-lettered
    assert queue.stats().dead_letter == 1
    assert store.list_runs() == []


def test_invalid_spec_from_the_runner_is_rejected_without_retry(
    queue: InMemoryJobQueue, store: RunStore
) -> None:
    def refuses(message: JobMessage) -> Dict[str, Any]:
        raise ValueError("bad config")

    queue.send(make_message())
    (result,) = _worker(queue, store, refuses).run_once()
    assert result.outcome is Outcome.REJECTED
    assert queue.stats().dead_letter == 1


def test_poison_messages_are_dead_lettered_at_once(
    queue: InMemoryJobQueue, store: RunStore
) -> None:
    queue.send_raw("this is not json")
    queue.send_raw('{"schemaVersion": 1, "tenant": "x"}')
    worker = _worker(queue, store)
    worker.batch_size = 2
    results = worker.run_once()
    assert [r.outcome for r in results] == [Outcome.REJECTED, Outcome.REJECTED]
    assert queue.stats().dead_letter == 2
    assert "malformed" in queue.dead_letters()[0][1]


def test_message_past_its_own_retry_budget_is_rejected(
    queue: InMemoryJobQueue, store: RunStore, clock: Clock
) -> None:
    queue = InMemoryJobQueue(max_receives=10, visibility_timeout=30, clock=clock)
    queue.send(make_message(maxReceives=1))
    first = queue.receive()
    assert len(first) == 1
    clock.advance(31)
    (result,) = _worker(queue, store).run_once()
    assert result.outcome is Outcome.REJECTED
    assert result.detail == "retry budget exhausted"


def test_ack_after_the_visibility_timeout_is_reported_stale(
    queue: InMemoryJobQueue, store: RunStore, clock: Clock
) -> None:
    def slow(message: JobMessage) -> Dict[str, Any]:
        clock.advance(31 * 60)  # longer than the message's 15 minute timeout
        queue.receive()  # another consumer picks the message up meanwhile
        return fake_runner(message)

    message = make_message()
    queue.send(message)
    (result,) = _worker(queue, store, slow).run_once()
    assert result.outcome is Outcome.STALE
    assert store.has_run(
        message.run_id
    )  # the work is kept; the redelivery will be skipped
    clock.advance(31)
    (again,) = _worker(queue, store).run_once()
    assert again.outcome is Outcome.DUPLICATE


def test_graceful_stop_hands_back_unstarted_messages(
    queue: InMemoryJobQueue, store: RunStore
) -> None:
    for i in range(3):
        queue.send(make_message(idempotencyKey=f"k{i}", runId=f"run-{i}"))
    worker = _worker(queue, store)
    worker.batch_size = 3

    def stop_after_first(message: JobMessage) -> Dict[str, Any]:
        worker.request_stop()
        return fake_runner(message)

    worker.runner = stop_after_first
    results = worker.run_once()
    assert len(results) == 1 and results[0].outcome is Outcome.COMPLETED
    assert queue.stats().visible == 2  # handed back, visible again at once
    assert worker.run_once() == []  # stopped: takes nothing new
    assert worker.run_forever() == 0


def test_run_forever_drains_then_stops(
    queue: InMemoryJobQueue, store: RunStore
) -> None:
    for i in range(2):
        queue.send(make_message(idempotencyKey=f"k{i}", runId=f"run-{i}"))
    worker = _worker(queue, store)
    original = worker.runner
    seen: List[str] = []

    def runner(message: JobMessage) -> Dict[str, Any]:
        seen.append(message.run_id)
        if len(seen) == 2:
            worker.request_stop()
        return original(message)

    worker.runner = runner
    assert worker.run_forever() == 2
    assert store.list_runs() == ["run-0", "run-1"]


def test_default_runner_runs_a_real_multi_seed_study(
    queue: InMemoryJobQueue, store: RunStore
) -> None:
    message = make_message(run={"numSeeds": 2, "duration": 3, "baseSeed": 7})
    queue.send(message)
    (result,) = Worker(queue, store, wait_seconds=0).run_once()
    assert result.outcome is Outcome.COMPLETED, result.detail
    stored = store.load_run(message.run_id)
    assert len(stored.records) == 2
    assert stored.manifest["baseSeed"] == 7
