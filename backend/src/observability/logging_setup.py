"""Structured logging: one JSON object per line, or plain text for local use.

``LOG_FORMAT=json`` (the containers set it) gives machine-readable lines with
``ts``, ``level``, ``logger``, ``message``, the ``request_id`` of the request
being handled (if any), any structured ``extra`` fields, and the exception
with its traceback. Anything else gives the familiar plain format with the
request id appended. ``LOG_LEVEL`` sets the root level (default INFO).

Every record passes ``RedactingFilter`` first: bearer tokens, personal access
tokens (``uf_pat_…``) and JWT-shaped strings are replaced, whatever logger
wrote them, so a token pasted into an error message never reaches a log.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# The request being handled on this task or thread (set by the middleware).
request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id", default=None
)

_REDACTIONS = (
    # "Bearer <anything>" in headers or messages.
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer [REDACTED]"),
    # Personal access tokens (src/api/store.py issues uf_pat_<secret>).
    (re.compile(r"\buf_pat_[A-Za-z0-9_-]+"), "uf_pat_[REDACTED]"),
    # Three base64url segments: a JWT.
    (
        re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}"),
        "[REDACTED_JWT]",
    ),
)

# LogRecord's own attributes; anything else on a record came from ``extra``.
_STANDARD = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "request_id",
}


def redact(text: str) -> str:
    """``text`` with every token-like substring replaced."""
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def _redact_arg(value: Any) -> Any:
    return redact(value) if isinstance(value, str) else value


class RedactingFilter(logging.Filter):
    """Scrubs tokens from a record and attaches the request id.

    The message template and each string argument are redacted in place,
    keeping ``args`` as they were in shape: some formatters read the args
    themselves (uvicorn's access formatter unpacks the tuple). Only when a
    token still shows in the formatted message (split between template and
    argument) is the record collapsed to its redacted text.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_redact_arg(a) for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: _redact_arg(v) for k, v in record.args.items()}
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - a bad format string must not lose the record
            return True
        cleaned = redact(message)
        if cleaned != message:
            record.msg = cleaned
            record.args = None
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per record."""

    def format(self, record: logging.LogRecord) -> str:
        body: Dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            body["request_id"] = request_id
        for key, value in record.__dict__.items():
            if key not in _STANDARD and not key.startswith("_"):
                body[key] = value if _jsonable(value) else repr(value)
        if record.exc_info:
            body["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(body, default=str)


class PlainFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s: %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        request_id = getattr(record, "request_id", None)
        if record.exc_info:
            text = redact(text)
        return f"{text} [request_id={request_id}]" if request_id else text


def _jsonable(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool, type(None), list, dict))


def configure_logging() -> None:
    """Install the formatter and the redacting filter on the root logger.

    Idempotent: replaces the handlers it installed before, keeps any other
    handler (pytest's capture, for example) and adds the filter to it.
    """
    root = logging.getLogger()
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    root.setLevel(getattr(logging, level, logging.INFO))
    for handler in list(root.handlers):
        if getattr(handler, "_urbanflow", False):
            root.removeHandler(handler)
    handler = logging.StreamHandler()
    handler._urbanflow = True  # type: ignore[attr-defined]
    json_logs = os.getenv("LOG_FORMAT", "").strip().lower() == "json"
    handler.setFormatter(JsonFormatter() if json_logs else PlainFormatter())
    root.addHandler(handler)
    for h in root.handlers:
        if not any(isinstance(f, RedactingFilter) for f in h.filters):
            h.addFilter(RedactingFilter())
    # uvicorn's loggers have their own handlers and do not propagate to the
    # root; a logger-level filter covers every record they create.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        server_logger = logging.getLogger(name)
        if not any(isinstance(f, RedactingFilter) for f in server_logger.filters):
            server_logger.addFilter(RedactingFilter())
