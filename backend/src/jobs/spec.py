"""Job message schema (F17, package 2E): the run spec, tenant, cost tags and idempotency key.

A queue message is the JSON of ``JobMessage``. The run spec is a multi-seed study of one scenario
(``src/study/multiseed.py``); more kinds can be added to ``JobSpec.kind`` later.

Idempotency: the key defaults to a hash of tenant + run id + spec, so submitting the same job twice
gives the same key. The queue drops a second send with the same key; the worker skips a job whose
run is already in the run store. Together a job runs to completion once however often SQS delivers it.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from src.runstore.store import validate_run_id
from src.study.limits import MAX_STUDY_DURATION_SECONDS, MIN_STUDY_DURATION_SECONDS

from .cost_tags import validate_tags

SCHEMA_VERSION = 1
GEOMETRIES = ("signal", "roundabout")
MAX_JOB_SEEDS = 100
MAX_SEED = 2**31 - 1
# SQS rejects a message body over 256 KiB; keep headroom for attributes.
MAX_MESSAGE_BYTES = 200 * 1024
# SQS visibility timeout bounds: 0 seconds to 12 hours; a job below 30 s is not worth a heartbeat.
MIN_VISIBILITY_SECONDS = 30
MAX_VISIBILITY_SECONDS = 12 * 3600
DEFAULT_VISIBILITY_SECONDS = 900
DEFAULT_MAX_RECEIVES = 3
MAX_RECEIVES_LIMIT = 10

_TENANT_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")
_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class _Model(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )


class JobSpec(_Model):
    """What to run. Validated on the way in, so a worker never sees an impossible job."""

    kind: Literal["multi-seed"] = "multi-seed"
    geometry: Literal["signal", "roundabout"] = "signal"
    num_seeds: int = Field(default=5, ge=1, le=MAX_JOB_SEEDS)
    duration: float = Field(
        default=30.0, ge=MIN_STUDY_DURATION_SECONDS, le=MAX_STUDY_DURATION_SECONDS
    )
    base_seed: Optional[int] = Field(default=None, ge=0, le=MAX_SEED)
    config: Optional[Dict[str, Any]] = None


class JobRequest(_Model):
    """A submission: the spec plus who it is for and how it is tagged."""

    run: JobSpec = Field(default_factory=JobSpec)
    tenant: str
    run_id: Optional[str] = None
    cost_tags: Dict[str, str] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None
    visibility_timeout_seconds: int = Field(
        default=DEFAULT_VISIBILITY_SECONDS,
        ge=MIN_VISIBILITY_SECONDS,
        le=MAX_VISIBILITY_SECONDS,
    )
    max_receives: int = Field(default=DEFAULT_MAX_RECEIVES, ge=1, le=MAX_RECEIVES_LIMIT)

    @field_validator("tenant")
    @classmethod
    def _tenant(cls, value: str) -> str:
        if not _TENANT_RE.fullmatch(value):
            raise ValueError(
                "tenant must be 1-63 characters: lowercase letters, digits, '-' and '_'"
            )
        return value

    @field_validator("run_id")
    @classmethod
    def _run_id(cls, value: Optional[str]) -> Optional[str]:
        return None if value is None else validate_run_id(value)

    @field_validator("idempotency_key")
    @classmethod
    def _key(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not _KEY_RE.fullmatch(value):
            raise ValueError(
                "idempotency key must be 1-128 characters: letters, digits and _ . : -"
            )
        return value

    @model_validator(mode="after")
    def _tags_are_plain_strings(self) -> "JobRequest":
        for key, value in self.cost_tags.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("cost tags must map strings to strings")
        return self


def _canonical(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def spec_digest(tenant: str, spec: JobSpec) -> str:
    body = _canonical({"tenant": tenant, "spec": spec.model_dump(mode="json")})
    return hashlib.sha256(body.encode()).hexdigest()


class JobMessage(_Model):
    """The body of one queue message. Always built with ``build_message``."""

    schema_version: int = SCHEMA_VERSION
    job_id: str
    idempotency_key: str
    tenant: str
    run_id: str
    run: JobSpec
    cost_tags: Dict[str, str]
    visibility_timeout_seconds: int
    max_receives: int
    enqueued_at: float

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True)

    @classmethod
    def from_json(cls, text: str) -> "JobMessage":
        """Parse and validate a message body. Raises ``ValueError`` (pydantic's included) for
        anything that is not a current-version message: the worker treats that as poison."""
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("job message must be a JSON object")
        if data.get("schemaVersion") != SCHEMA_VERSION:
            raise ValueError(
                f"unsupported job schemaVersion {data.get('schemaVersion')!r}"
            )
        message = cls.model_validate(data)
        validate_run_id(message.run_id)
        validate_tags(message.cost_tags)
        return message


def build_message(
    request: JobRequest,
    cost_tags: Dict[str, str],
    *,
    now: Optional[float] = None,
    job_id: Optional[str] = None,
) -> JobMessage:
    """Turn a validated request and its (already validated) tags into the message to enqueue.

    The run id defaults to the first 20 hex of the spec digest, so a repeat submission lands on
    the same run; the idempotency key defaults to the whole digest.
    """
    digest = spec_digest(request.tenant, request.run)
    run_id = request.run_id or digest[:20]
    message = JobMessage(
        job_id=job_id or uuid.uuid4().hex,
        idempotency_key=request.idempotency_key or digest,
        tenant=request.tenant,
        run_id=run_id,
        run=request.run,
        # The run-id tag always names the final run id, whatever the caller tagged with.
        cost_tags={**cost_tags, "run-id": run_id},
        visibility_timeout_seconds=request.visibility_timeout_seconds,
        max_receives=request.max_receives,
        enqueued_at=time.time() if now is None else now,
    )
    size = len(message.to_json().encode())
    if size > MAX_MESSAGE_BYTES:
        raise ValueError(
            f"job message is {size} bytes; the limit is {MAX_MESSAGE_BYTES} "
            "(shrink the config override)"
        )
    return message
