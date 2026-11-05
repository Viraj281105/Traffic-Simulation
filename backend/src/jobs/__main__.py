"""Run a worker: ``python -m src.jobs``.

Reads JOBS_QUEUE_URL, JOBS_DLQ_URL, RUNSTORE_BUCKET (and optional RUNSTORE_PREFIX, AWS_REGION).
Credentials come from the pod role; nothing secret is read here.
"""

from __future__ import annotations

import logging
import os
import socket

from src.runstore import RunStore, S3Backend

from .sqs import SqsJobQueue
from .worker import Worker


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    queue_url = os.environ.get("JOBS_QUEUE_URL", "")
    bucket = os.environ.get("RUNSTORE_BUCKET", "")
    if not queue_url or not bucket:
        logging.error("JOBS_QUEUE_URL and RUNSTORE_BUCKET must be set")
        return 2
    region = os.environ.get("AWS_REGION") or None
    queue = SqsJobQueue(
        queue_url, dlq_url=os.environ.get("JOBS_DLQ_URL") or None, region_name=region
    )
    store = RunStore(
        S3Backend(bucket, os.environ.get("RUNSTORE_PREFIX", ""), region_name=region)
    )
    worker = Worker(queue, store, worker_id=socket.gethostname())
    worker.install_signal_handlers()
    worker.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
