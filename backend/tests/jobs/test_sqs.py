"""SqsJobQueue against a fake boto3 client."""

# ruff: noqa: N803  (boto3 client methods take capitalised keyword arguments)
from typing import Any, Dict, List, Tuple

import pytest

from src.jobs import Delivery, QueueError, SqsJobQueue, StaleReceiptError

from .conftest import make_message

URL = "https://sqs.test/123/jobs"
DLQ = "https://sqs.test/123/jobs-dlq"


class FakeClientError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeSqs:
    def __init__(self) -> None:
        self.calls: List[Tuple[str, Dict[str, Any]]] = []
        self.inbox: List[Dict[str, Any]] = []
        self.fail_with = ""

    def _rec(self, name: str, kw: Dict[str, Any]) -> None:
        self.calls.append((name, kw))
        if self.fail_with:
            raise FakeClientError(self.fail_with)

    def send_message(self, **kw: Any) -> Dict[str, Any]:
        self._rec("send_message", kw)
        return {"MessageId": "m-1"}

    def receive_message(self, **kw: Any) -> Dict[str, Any]:
        self._rec("receive_message", kw)
        return {"Messages": self.inbox}

    def delete_message(self, **kw: Any) -> None:
        self._rec("delete_message", kw)

    def change_message_visibility(self, **kw: Any) -> None:
        self._rec("change_message_visibility", kw)

    def get_queue_attributes(self, **kw: Any) -> Dict[str, Any]:
        self._rec("get_queue_attributes", kw)
        n = {URL: ("4", "2"), DLQ: ("7", "0")}[kw["QueueUrl"]]
        return {
            "Attributes": {
                "ApproximateNumberOfMessages": n[0],
                "ApproximateNumberOfMessagesNotVisible": n[1],
            }
        }

    def names(self) -> List[str]:
        return [c[0] for c in self.calls]


def test_send_carries_body_and_attributes() -> None:
    fake = FakeSqs()
    message = make_message()
    assert SqsJobQueue(URL, client=fake).send(message) == "m-1"
    kw = fake.calls[0][1]
    assert kw["QueueUrl"] == URL and kw["MessageBody"] == message.to_json()
    assert kw["MessageAttributes"]["tenant"]["StringValue"] == "acme"


def test_receive_maps_messages_and_clamps_arguments() -> None:
    fake = FakeSqs()
    fake.inbox = [
        {
            "MessageId": "m",
            "ReceiptHandle": "rh",
            "Body": "{}",
            "Attributes": {"ApproximateReceiveCount": "3"},
        }
    ]
    q = SqsJobQueue(URL, client=fake)
    (d,) = q.receive(50, wait_seconds=99, visibility_timeout=10**9)
    assert (d.message_id, d.receipt, d.receive_count) == ("m", "rh", 3)
    kw = fake.calls[0][1]
    assert kw["MaxNumberOfMessages"] == 10
    assert kw["WaitTimeSeconds"] == 20
    assert kw["VisibilityTimeout"] == 12 * 3600


def test_ack_nack_extend_use_the_receipt() -> None:
    fake = FakeSqs()
    fake.inbox = [{"MessageId": "m", "ReceiptHandle": "rh", "Body": "x"}]
    q = SqsJobQueue(URL, client=fake)
    (d,) = q.receive()
    assert d.receive_count == 1
    q.ack(d)
    q.nack(d, 12)
    q.extend(d, 300)
    assert fake.names()[1:] == [
        "delete_message",
        "change_message_visibility",
        "change_message_visibility",
    ]
    assert fake.calls[2][1]["VisibilityTimeout"] == 12
    assert fake.calls[3][1]["VisibilityTimeout"] == 300
    assert all(c[1]["ReceiptHandle"] == "rh" for c in fake.calls[1:])


def test_reject_copies_to_the_dlq_then_deletes() -> None:
    fake = FakeSqs()
    q = SqsJobQueue(URL, dlq_url=DLQ, client=fake)
    q.reject(Delivery("m", "rh", "garbage", 1), "malformed")
    assert fake.names() == ["send_message", "delete_message"]
    sent = fake.calls[0][1]
    assert sent["QueueUrl"] == DLQ and sent["MessageBody"] == "garbage"


def test_reject_without_dlq_url_leaves_it_to_the_redrive_policy() -> None:
    fake = FakeSqs()
    SqsJobQueue(URL, client=fake).reject(Delivery("m", "rh", "x", 1), "bad")
    assert fake.names() == ["change_message_visibility"]
    assert fake.calls[0][1]["VisibilityTimeout"] == 0


def test_stats_include_the_dlq() -> None:
    stats = SqsJobQueue(URL, dlq_url=DLQ, client=FakeSqs()).stats()
    assert (stats.visible, stats.in_flight, stats.dead_letter) == (4, 2, 7)


def test_errors_are_translated() -> None:
    fake = FakeSqs()
    q = SqsJobQueue(URL, client=fake)
    fake.fail_with = "ReceiptHandleIsInvalid"
    with pytest.raises(StaleReceiptError):
        q.ack(Delivery("m", "rh", "x", 1))
    fake.fail_with = "AccessDenied"
    with pytest.raises(QueueError):
        q.send(make_message())


def test_queue_url_is_required() -> None:
    with pytest.raises(ValueError):
        SqsJobQueue("")
