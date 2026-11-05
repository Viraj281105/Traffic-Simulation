"""Queue semantics of the in-memory implementation: visibility, redelivery, DLQ, de-duplication."""

import pytest

from src.jobs import InMemoryJobQueue, StaleReceiptError

from .conftest import Clock, make_message


def test_received_message_is_hidden_until_the_visibility_timeout(
    queue: InMemoryJobQueue, clock: Clock
) -> None:
    queue.send(make_message())
    (first,) = queue.receive()
    assert queue.receive() == []
    assert queue.stats().in_flight == 1
    clock.advance(29)
    assert queue.receive() == []
    clock.advance(2)
    (again,) = queue.receive()
    assert again.message_id == first.message_id
    assert again.receive_count == 2
    assert again.receipt != first.receipt


def test_ack_deletes_and_stale_receipt_is_refused(
    queue: InMemoryJobQueue, clock: Clock
) -> None:
    queue.send(make_message())
    (first,) = queue.receive()
    clock.advance(31)
    (second,) = queue.receive()
    with pytest.raises(StaleReceiptError):
        queue.ack(first)
    queue.ack(second)
    assert queue.stats().visible == 0 and queue.stats().in_flight == 0
    with pytest.raises(StaleReceiptError):
        queue.ack(second)


def test_nack_with_delay_redelivers_later(
    queue: InMemoryJobQueue, clock: Clock
) -> None:
    queue.send(make_message())
    (d,) = queue.receive()
    queue.nack(d, delay_seconds=10)
    assert queue.receive() == []
    clock.advance(10)
    assert len(queue.receive()) == 1


def test_extend_pushes_the_timeout_out(queue: InMemoryJobQueue, clock: Clock) -> None:
    queue.send(make_message())
    (d,) = queue.receive()
    queue.extend(d, 100)
    clock.advance(60)
    assert queue.receive() == []
    clock.advance(41)
    assert len(queue.receive()) == 1


def test_message_goes_to_the_dlq_after_max_receives(
    queue: InMemoryJobQueue, clock: Clock
) -> None:
    queue.send(make_message())
    for expected in (1, 2, 3):
        (d,) = queue.receive()
        assert d.receive_count == expected
        clock.advance(31)
    assert queue.receive() == []
    stats = queue.stats()
    assert (stats.visible, stats.in_flight, stats.dead_letter) == (0, 0, 1)
    assert queue.dead_letters()[0][1] == "max receives exceeded"


def test_reject_dead_letters_immediately(queue: InMemoryJobQueue) -> None:
    queue.send(make_message())
    (d,) = queue.receive()
    queue.reject(d, "poison")
    assert queue.stats().dead_letter == 1
    assert queue.dead_letters() == [(d.body, "poison")]


def test_same_idempotency_key_is_sent_once(queue: InMemoryJobQueue) -> None:
    a = queue.send(make_message())
    b = queue.send(make_message())
    c = queue.send(make_message(idempotencyKey="other-key"))
    assert a == b != c
    assert queue.stats().visible == 2


def test_batch_size_is_respected(queue: InMemoryJobQueue) -> None:
    for i in range(3):
        queue.send(make_message(idempotencyKey=f"k{i}"))
    assert len(queue.receive(2)) == 2
    assert len(queue.receive(2)) == 1
