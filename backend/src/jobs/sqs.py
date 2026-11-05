"""SQS implementation of ``JobQueue`` (F17, package 2E).

``boto3`` is imported only when a client has to be created, so the module imports, and every test
that injects a client, run without it. No credential is passed or stored: boto3 resolves them from
the environment or the pod's IAM role (IRSA).

The queue is a standard queue with a redrive policy to a dead-letter queue (infra/terraform/modules/sqs).
Standard queues deliver at least once and do not de-duplicate sends, so the worker, not the queue,
guarantees a job's effect happens once (it checks the run store first).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .queue import Delivery, QueueError, QueueStats, StaleReceiptError
from .spec import JobMessage

# SQS caps: 10 messages per receive, 20 s long poll, 12 h visibility.
MAX_BATCH = 10
MAX_WAIT_SECONDS = 20
MAX_VISIBILITY = 12 * 3600

_STALE_CODES = {"ReceiptHandleIsInvalid", "InvalidParameterValue", "MessageNotInflight"}


def _code(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        return str(response.get("Error", {}).get("Code", ""))
    return ""


class SqsJobQueue:
    """``client`` is any object with the boto3 SQS client methods used below."""

    def __init__(
        self,
        queue_url: str,
        *,
        dlq_url: Optional[str] = None,
        client: Optional[Any] = None,
        region_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        default_visibility: int = 900,
    ) -> None:
        if not queue_url:
            raise ValueError("queue_url is required")
        self.queue_url = queue_url
        self.dlq_url = dlq_url
        self.default_visibility = default_visibility
        self._client = client
        self._region_name = region_name
        self._endpoint_url = endpoint_url

    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                import boto3
            except ImportError as exc:  # pragma: no cover - depends on the environment
                raise QueueError("SQS needs boto3: pip install boto3") from exc
            self._client = boto3.client(
                "sqs", region_name=self._region_name, endpoint_url=self._endpoint_url
            )
        return self._client

    def _call(self, name: str, **kwargs: Any) -> Any:
        try:
            return getattr(self.client, name)(**kwargs)
        except QueueError:
            raise
        except Exception as exc:
            if _code(exc) in _STALE_CODES:
                raise StaleReceiptError(str(exc)) from exc
            raise QueueError(f"SQS {name} failed: {exc}") from exc

    def send(self, message: JobMessage) -> str:
        response = self._call(
            "send_message",
            QueueUrl=self.queue_url,
            MessageBody=message.to_json(),
            MessageAttributes={
                "tenant": {"DataType": "String", "StringValue": message.tenant},
                "idempotencyKey": {
                    "DataType": "String",
                    "StringValue": message.idempotency_key,
                },
            },
        )
        return str(response["MessageId"])

    def receive(
        self,
        max_messages: int = 1,
        *,
        wait_seconds: float = 0,
        visibility_timeout: Optional[float] = None,
    ) -> List[Delivery]:
        timeout = (
            self.default_visibility
            if visibility_timeout is None
            else visibility_timeout
        )
        response = self._call(
            "receive_message",
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=max(1, min(int(max_messages), MAX_BATCH)),
            WaitTimeSeconds=max(0, min(int(wait_seconds), MAX_WAIT_SECONDS)),
            VisibilityTimeout=max(0, min(int(timeout), MAX_VISIBILITY)),
            AttributeNames=["ApproximateReceiveCount"],
        )
        out: List[Delivery] = []
        for raw in response.get("Messages", []):
            count = int(raw.get("Attributes", {}).get("ApproximateReceiveCount", "1"))
            out.append(
                Delivery(
                    raw["MessageId"], raw["ReceiptHandle"], raw.get("Body", ""), count
                )
            )
        return out

    def ack(self, delivery: Delivery) -> None:
        self._call(
            "delete_message", QueueUrl=self.queue_url, ReceiptHandle=delivery.receipt
        )

    def _set_visibility(self, delivery: Delivery, seconds: float) -> None:
        self._call(
            "change_message_visibility",
            QueueUrl=self.queue_url,
            ReceiptHandle=delivery.receipt,
            VisibilityTimeout=max(0, min(int(seconds), MAX_VISIBILITY)),
        )

    def nack(self, delivery: Delivery, delay_seconds: float = 0) -> None:
        self._set_visibility(delivery, delay_seconds)

    def extend(self, delivery: Delivery, seconds: float) -> None:
        self._set_visibility(delivery, seconds)

    def reject(self, delivery: Delivery, reason: str) -> None:
        """Dead-letter now. With a DLQ url the body is copied there and the original deleted;
        without one the message is made visible at once and the redrive policy retires it."""
        if self.dlq_url is None:
            self._set_visibility(delivery, 0)
            return
        self._call(
            "send_message",
            QueueUrl=self.dlq_url,
            MessageBody=delivery.body,
            MessageAttributes={
                "rejectReason": {"DataType": "String", "StringValue": reason[:256]}
            },
        )
        self.ack(delivery)

    def _depth(self, url: str) -> Dict[str, int]:
        response = self._call(
            "get_queue_attributes",
            QueueUrl=url,
            AttributeNames=[
                "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible",
            ],
        )
        attrs = response.get("Attributes", {})
        return {
            "visible": int(attrs.get("ApproximateNumberOfMessages", 0)),
            "in_flight": int(attrs.get("ApproximateNumberOfMessagesNotVisible", 0)),
        }

    def stats(self) -> QueueStats:
        main = self._depth(self.queue_url)
        dead = self._depth(self.dlq_url)["visible"] if self.dlq_url else 0
        return QueueStats(main["visible"], main["in_flight"], dead)
