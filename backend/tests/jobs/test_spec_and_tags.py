"""Job spec validation, message round trip, tag mandatory-ness and the compute-time recorder."""

from typing import Any

import pytest
from pydantic import ValidationError

from src.jobs import (
    ComputeTimeRecorder,
    CostTagError,
    JobMessage,
    JobRequest,
    build_job_tags,
    build_message,
    validate_tags,
)
from src.jobs.cost_tags import default_tags
from src.jobs.spec import MAX_MESSAGE_BYTES

from .conftest import TAGS, Clock, make_message


@pytest.mark.parametrize(
    "payload",
    [
        {"tenant": "Bad Tenant"},
        {"tenant": ""},
        {"tenant": "acme", "run": {"numSeeds": 0}},
        {"tenant": "acme", "run": {"numSeeds": 101}},
        {"tenant": "acme", "run": {"duration": 0}},
        {"tenant": "acme", "run": {"duration": 99999}},
        {"tenant": "acme", "run": {"geometry": "triangle"}},
        {"tenant": "acme", "run": {"kind": "other"}},
        {"tenant": "acme", "runId": "../etc"},
        {"tenant": "acme", "idempotencyKey": "has space"},
        {"tenant": "acme", "visibilityTimeoutSeconds": 5},
        {"tenant": "acme", "maxReceives": 0},
        {"tenant": "acme", "surprise": 1},
    ],
)
def test_invalid_requests_are_refused(payload: Any) -> None:
    with pytest.raises(ValidationError):
        JobRequest.model_validate(payload)


def test_message_round_trips_and_defaults_are_derived() -> None:
    message = make_message()
    assert JobMessage.from_json(message.to_json()) == message
    assert len(message.run_id) == 20
    assert message.idempotency_key.startswith(message.run_id)
    assert message.cost_tags["tenant"] == "acme"


def test_same_request_gives_same_key_and_run_id() -> None:
    assert make_message().run_id == make_message().run_id
    assert make_message("other").run_id != make_message().run_id


@pytest.mark.parametrize(
    "text",
    ["not json", "[1]", '{"schemaVersion": 2}', '{"schemaVersion": 1}'],
)
def test_malformed_bodies_raise_value_error(text: str) -> None:
    with pytest.raises(ValueError):
        JobMessage.from_json(text)


def test_oversized_message_is_refused() -> None:
    request = JobRequest.model_validate(
        {"tenant": "acme", "run": {"config": {"blob": "x" * MAX_MESSAGE_BYTES}}}
    )
    with pytest.raises(ValueError, match="bytes"):
        build_message(request, dict(TAGS))


@pytest.mark.parametrize("missing", ["project", "env", "owner"])
def test_each_mandatory_tag_is_required(missing: str) -> None:
    tags = {k: v for k, v in TAGS.items() if k != missing}
    with pytest.raises(CostTagError, match=missing):
        validate_tags(tags)


def test_blank_mandatory_tag_counts_as_missing() -> None:
    with pytest.raises(CostTagError):
        validate_tags({**TAGS, "owner": "  "})


def test_tags_are_filled_from_the_environment() -> None:
    env = {"URBANFLOW_ENV": "staging", "URBANFLOW_OWNER": "platform"}
    tags = build_job_tags("run1", tenant="acme", environ=env)
    assert tags == {
        "project": "urbanflow",
        "env": "staging",
        "owner": "platform",
        "run-id": "run1",
        "tenant": "acme",
    }
    assert default_tags({}) == {"project": "urbanflow"}


def test_job_cannot_override_tenant_or_run_id_tags() -> None:
    tags = build_job_tags(
        "real",
        tenant="acme",
        tags={**TAGS, "tenant": "evil", "run-id": "fake"},
        environ={},
    )
    assert tags["tenant"] == "acme" and tags["run-id"] == "real"


@pytest.mark.parametrize("key", ["aws:createdBy", "bad|key", ""])
def test_aws_rejected_tag_keys_are_refused(key: str) -> None:
    with pytest.raises(CostTagError):
        validate_tags({**TAGS, key: "v"})


def test_recorder_totals_by_tenant_and_marks_failures() -> None:
    clock = Clock()
    rec = ComputeTimeRecorder(capacity=2, clock=clock)
    with rec.measure(job_id="1", run_id="r1", tenant="a", worker_id="w") as m:
        clock.advance(4)
        m.ok = True
    with pytest.raises(RuntimeError):
        with rec.measure(job_id="2", run_id="r2", tenant="b", worker_id="w"):
            clock.advance(1.5)
            raise RuntimeError("boom")
    assert [r.succeeded for r in rec.records()] == [True, False]
    assert rec.seconds_by_tenant() == {"a": 4.0, "b": 1.5}
    with rec.measure(job_id="3", run_id="r3", tenant="a", worker_id="w"):
        clock.advance(1)
    assert len(rec.records()) == 2  # capacity bound
    assert rec.total_seconds() == 2.5
