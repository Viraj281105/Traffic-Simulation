"""``/api/v2/jobs``: queue depth and a dry run of an enqueue (F17, package 2E).

Neither route ever sends a message. ``enqueue-dry-run`` validates a job exactly as a real enqueue
would and returns the message that would be sent. Mounted from ``main.py`` with the API key and
signed-in-user dependencies (see the register lines in the 2E hand-off).
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from .cost_tags import CostTagError, build_job_tags
from .queue import InMemoryJobQueue, JobQueue, QueueError
from .spec import JobRequest, build_message
from .sqs import SqsJobQueue

router = APIRouter(prefix="/api/v2/jobs", tags=["jobs"])


@lru_cache(maxsize=1)
def _memory_queue() -> InMemoryJobQueue:
    return InMemoryJobQueue()


def get_queue() -> JobQueue:
    """SQS when JOBS_QUEUE_URL is set, otherwise an empty in-process queue. Tests override this."""
    url = os.environ.get("JOBS_QUEUE_URL", "")
    if url:
        return SqsJobQueue(
            url,
            dlq_url=os.environ.get("JOBS_DLQ_URL") or None,
            region_name=os.environ.get("AWS_REGION") or None,
        )
    return _memory_queue()


@router.get("/queue-stats")
def queue_stats(queue: JobQueue = Depends(get_queue)) -> Dict[str, Any]:
    try:
        stats = queue.stats()
    except QueueError as exc:
        raise HTTPException(
            status_code=503, detail=f"queue unavailable: {exc}"
        ) from exc
    backend = "sqs" if isinstance(queue, SqsJobQueue) else "memory"
    return {"backend": backend, "enqueueEnabled": False, **stats.as_dict()}


@router.post("/enqueue-dry-run")
def enqueue_dry_run(request: JobRequest) -> Dict[str, Any]:
    try:
        tags = build_job_tags(
            request.run_id or "pending", tenant=request.tenant, tags=request.cost_tags
        )
        message = build_message(request, tags)
    except CostTagError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "enqueued": False,
        "dryRun": True,
        "message": message.model_dump(mode="json", by_alias=True),
        "messageBytes": len(message.to_json().encode()),
    }
