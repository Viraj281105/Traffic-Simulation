"""Audit vocabulary and contract for W7 platform activity (V3 Product Strategy §7).

Records token lifecycle and quota rejections into an append-only audit log
without payloads or secrets.
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field

AUDIT_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "token_created",
        "token_revoked",
        "experiment_submitted",
        "experiment_cancelled",
        "quota_rejected",
        "auth_failed",
        "package_exported",
        "package_verified",
    }
)
AuditEventType = Literal[
    "token_created",
    "token_revoked",
    "experiment_submitted",
    "experiment_cancelled",
    "quota_rejected",
    "auth_failed",
    "package_exported",
    "package_verified",
]

# Keys strictly forbidden from audit details to guarantee no secrets/payloads are logged.
_REDACTED_KEY_SUBSTRINGS = (
    "token",
    "secret",
    "key",
    "password",
    "authorization",
    "api_key",
    "x_api_key",
    "payload",
    "scenario",
    "config",
    "patch",
    "raw",
)


def sanitize_audit_details(details: Mapping[str, Any]) -> Dict[str, Any]:
    """Strip payloads, credentials, and secrets from audit metadata.

    Ensures compliance with Product Strategy §7:
    'with user id, token id, kind, counts and reason — no payloads, no secrets'.
    """
    sanitized: Dict[str, Any] = {}
    for k, v in details.items():
        lower_k = k.lower()
        if any(substr in lower_k for substr in _REDACTED_KEY_SUBSTRINGS):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, (str, int, float, bool)) or v is None:
            sanitized[k] = v
        elif isinstance(v, (list, tuple)):
            sanitized[k] = [
                item if isinstance(item, (str, int, float, bool)) else "[COMPLEX]"
                for item in v
            ]
        elif isinstance(v, dict):
            # Recurse into nested dictionary
            sanitized[k] = sanitize_audit_details(v)
        else:
            sanitized[k] = "[COMPLEX]"
    return sanitized


class AuditEvent(BaseModel):
    """Contract for an entry in the append-only audit log."""

    model_config = ConfigDict(extra="forbid")

    id: Optional[str] = None
    timestamp: str
    userId: str
    eventType: AuditEventType
    tokenId: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
