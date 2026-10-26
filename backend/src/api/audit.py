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
    }
)
AuditEventType = Literal[
    "token_created",
    "token_revoked",
    "experiment_submitted",
    "experiment_cancelled",
    "quota_rejected",
    "auth_failed",
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


# SQLite schema definition for uf_audit_log (ADR-013 / Stage 1 seam)
AUDIT_TABLE_NAME = "uf_audit_log"
AUDIT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS uf_audit_log (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    user_id TEXT NOT NULL,
    token_id TEXT,
    event_type TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}'
);
"""
# Append-only guard. These triggers make the application's own SQL (and any
# other connection that uses this schema) unable to UPDATE or DELETE a row.
# The BEFORE INSERT trigger closes INSERT OR REPLACE: SQLite does not fire
# delete triggers for a REPLACE's implicit delete (recursive_triggers is off),
# so an insert that reuses an existing id is aborted instead.
# They do NOT stop someone with write access to the database file from dropping
# the triggers or the table, or replacing the file: that needs file permissions,
# an external log sink or a hash chain, none of which Stage 1 provides.
AUDIT_APPEND_ONLY_SQL = (
    """
CREATE TRIGGER IF NOT EXISTS trg_uf_audit_no_update
BEFORE UPDATE ON uf_audit_log
BEGIN
    SELECT RAISE(ABORT, 'uf_audit_log is append-only');
END;
""",
    """
CREATE TRIGGER IF NOT EXISTS trg_uf_audit_no_delete
BEFORE DELETE ON uf_audit_log
BEGIN
    SELECT RAISE(ABORT, 'uf_audit_log is append-only');
END;
""",
    """
CREATE TRIGGER IF NOT EXISTS trg_uf_audit_no_replace
BEFORE INSERT ON uf_audit_log
WHEN EXISTS (SELECT 1 FROM uf_audit_log WHERE id = NEW.id)
BEGIN
    SELECT RAISE(ABORT, 'uf_audit_log is append-only');
END;
""",
)
AUDIT_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_uf_audit_user_time
ON uf_audit_log (user_id, timestamp);
"""
