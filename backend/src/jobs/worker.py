"""Job worker (F17, package 2E): pull a job, run the multi-seed study, store the run, ack.

Delivery is at-least-once, so the handler is built to be repeated:

* A run already in the run store is acked without running again (idempotency).
* A malformed message, an invalid spec or a message past its own retry budget is rejected to the
  dead-letter queue at once (poison handling): retrying cannot fix it.
* A transient failure (the study crashed, storage was unreachable) is nacked with exponential
  backoff; the queue's redrive policy dead-letters it after ``maxReceiveCount`` deliveries.
* A stale receipt (the visibility timeout expired mid-job) is logged and dropped: the run is stored,
  so the redelivery is skipped by the first rule.

Shutdown is graceful: ``request_stop`` (also wired to SIGTERM/SIGINT by
``install_signal_handlers``) lets the job in hand finish, hands back any unstarted messages of the
batch, and ends the loop. Kubernetes must allow the job time to finish: see the worker chart's
``terminationGracePeriodSeconds``.
"""

from __future__ import annotations

import json
import logging
import signal
import threading
from dataclasses import dataclass
from enum import Enum
from types import FrameType
from typing import Any, Callable, Dict, List, Optional

from src.runstore import RunExistsError, RunStore, StorageError

from .cost_tags import ComputeTimeRecorder
from .queue import Delivery, JobQueue, QueueError, StaleReceiptError
from .spec import JobMessage

log = logging.getLogger("urbanflow.jobs.worker")

JOB_RECORD_NAME = "job.json"
BACKOFF_BASE_SECONDS = 5.0
BACKOFF_MAX_SECONDS = 300.0

Runner = Callable[[JobMessage], Dict[str, Any]]


class Outcome(str, Enum):
    COMPLETED = "completed"
    DUPLICATE = "duplicate"
    RETRY = "retry"
    REJECTED = "rejected"
    STALE = "stale"


@dataclass(frozen=True)
class JobResult:
    message_id: str
    outcome: Outcome
    run_id: Optional[str] = None
    detail: str = ""


def run_multi_seed_job(message: JobMessage) -> Dict[str, Any]:
    """The default runner: one multi-seed study (src/study/multiseed.py)."""
    from src.study.multiseed import run_multi_seed

    spec = message.run
    return run_multi_seed(
        config=spec.config,
        geometry=spec.geometry,
        num_seeds=spec.num_seeds,
        duration=spec.duration,
        base_seed=spec.base_seed,
    )


def retry_delay(receive_count: int) -> float:
    """Backoff before a failed job is visible again: 5 s, 10 s, 20 s ... capped at 5 min."""
    return float(
        min(BACKOFF_MAX_SECONDS, BACKOFF_BASE_SECONDS * 2 ** max(0, receive_count - 1))
    )


class Worker:
    def __init__(
        self,
        queue: JobQueue,
        run_store: RunStore,
        *,
        runner: Runner = run_multi_seed_job,
        recorder: Optional[ComputeTimeRecorder] = None,
        worker_id: str = "worker-0",
        batch_size: int = 1,
        wait_seconds: float = 20,
        idle_sleep: float = 1.0,
    ) -> None:
        self.queue = queue
        self.run_store = run_store
        self.runner = runner
        self.recorder = recorder or ComputeTimeRecorder()
        self.worker_id = worker_id
        self.batch_size = batch_size
        self.wait_seconds = wait_seconds
        self.idle_sleep = idle_sleep
        self._stop = threading.Event()

    # -- shutdown ---------------------------------------------------------------------------

    def request_stop(self) -> None:
        self._stop.set()

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    def install_signal_handlers(self) -> None:
        """Route SIGTERM and SIGINT to ``request_stop``. Main thread only."""

        def handler(signum: int, _frame: Optional[FrameType]) -> None:
            log.info(
                "signal %s received: finishing the current job, then stopping", signum
            )
            self.request_stop()

        signal.signal(signal.SIGTERM, handler)
        signal.signal(signal.SIGINT, handler)

    # -- loop -------------------------------------------------------------------------------

    def run_once(self) -> List[JobResult]:
        """Receive one batch and handle it. Returns one result per message handled."""
        if self.stopping:
            return []
        try:
            deliveries = self.queue.receive(
                self.batch_size, wait_seconds=self.wait_seconds
            )
        except QueueError:
            log.exception("receive failed")
            return []
        results: List[JobResult] = []
        for i, delivery in enumerate(deliveries):
            if self.stopping:
                self._hand_back(deliveries[i:])
                break
            results.append(self.handle(delivery))
        return results

    def run_forever(self) -> int:
        """Loop until stopped. Returns the number of jobs handled."""
        handled = 0
        while not self.stopping:
            results = self.run_once()
            handled += len(results)
            if not results:
                self._stop.wait(self.idle_sleep)
        log.info("worker %s stopped after %d job(s)", self.worker_id, handled)
        return handled

    def _hand_back(self, deliveries: List[Delivery]) -> None:
        for delivery in deliveries:
            try:
                self.queue.nack(delivery, 0)
            except QueueError:
                log.warning("could not hand back %s", delivery.message_id)

    # -- one message ------------------------------------------------------------------------

    def handle(self, delivery: Delivery) -> JobResult:
        try:
            message = JobMessage.from_json(delivery.body)
        except ValueError as exc:
            return self._reject(delivery, None, f"malformed message: {exc}"[:240])

        run_id = message.run_id
        if delivery.receive_count > message.max_receives:
            return self._reject(delivery, run_id, "retry budget exhausted")

        try:
            if self.run_store.has_run(run_id):
                return self._finish(
                    delivery, run_id, Outcome.DUPLICATE, "run already stored"
                )
        except StorageError as exc:
            return self._retry(delivery, run_id, f"run store unavailable: {exc}")

        try:
            self.queue.extend(delivery, message.visibility_timeout_seconds)
        except StaleReceiptError:
            return JobResult(
                delivery.message_id, Outcome.STALE, run_id, "receipt expired"
            )
        except QueueError as exc:
            log.warning("could not extend visibility for %s: %s", run_id, exc)

        try:
            with self.recorder.measure(
                job_id=message.job_id,
                run_id=run_id,
                tenant=message.tenant,
                worker_id=self.worker_id,
                tags=message.cost_tags,
            ) as timing:
                result = self.runner(message)
                timing.ok = True
        except ValueError as exc:
            # The study refused the spec (for example a bad config override): permanent.
            return self._reject(delivery, run_id, f"invalid job: {exc}"[:240])
        except Exception as exc:
            log.exception("job %s failed", run_id)
            return self._retry(delivery, run_id, f"run failed: {exc}"[:240])

        try:
            self._store(message, result, timing.wall_seconds, delivery.receive_count)
        except RunExistsError:
            pass  # a parallel delivery stored it first: the same run, so the same outcome
        except (StorageError, ValueError, KeyError) as exc:
            return self._retry(
                delivery, run_id, f"could not store the run: {exc}"[:240]
            )

        return self._finish(delivery, run_id, Outcome.COMPLETED, "")

    def _store(
        self, message: JobMessage, result: Dict[str, Any], seconds: float, attempt: int
    ) -> None:
        records = [
            {"geometry": message.run.geometry, **row} for row in result["seedRuns"]
        ]
        record = {
            "jobId": message.job_id,
            "runId": message.run_id,
            "tenant": message.tenant,
            "idempotencyKey": message.idempotency_key,
            "workerId": self.worker_id,
            "attempt": attempt,
            "computeSeconds": round(seconds, 3),
            "costTags": message.cost_tags,
        }
        # The usage record goes first and is simply overwritten by a retry; the manifest, written
        # last by save_run, is what marks the run complete.
        self.run_store.backend.put(
            f"runs/{message.run_id}/{JOB_RECORD_NAME}",
            json.dumps(record, sort_keys=True, indent=2).encode(),
        )
        self.run_store.save_run(result["manifest"], records, run_id=message.run_id)

    # -- settling a message -----------------------------------------------------------------

    def _finish(
        self, delivery: Delivery, run_id: str, outcome: Outcome, detail: str
    ) -> JobResult:
        try:
            self.queue.ack(delivery)
        except StaleReceiptError:
            # The run is stored; the redelivery will be skipped as a duplicate.
            return JobResult(
                delivery.message_id, Outcome.STALE, run_id, "ack after timeout"
            )
        except QueueError as exc:
            log.warning("ack failed for %s: %s", run_id, exc)
            return JobResult(
                delivery.message_id, Outcome.RETRY, run_id, f"ack failed: {exc}"
            )
        return JobResult(delivery.message_id, outcome, run_id, detail)

    def _retry(self, delivery: Delivery, run_id: str, detail: str) -> JobResult:
        try:
            self.queue.nack(delivery, retry_delay(delivery.receive_count))
        except QueueError as exc:
            log.warning("nack failed for %s: %s", run_id, exc)
        return JobResult(delivery.message_id, Outcome.RETRY, run_id, detail)

    def _reject(
        self, delivery: Delivery, run_id: Optional[str], reason: str
    ) -> JobResult:
        log.warning("rejecting %s: %s", delivery.message_id, reason)
        try:
            self.queue.reject(delivery, reason)
        except QueueError as exc:
            log.warning("reject failed for %s: %s", delivery.message_id, exc)
        return JobResult(delivery.message_id, Outcome.REJECTED, run_id, reason)
