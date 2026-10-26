"""Token and Audit Persistence Layer (ADR-013 / ADR-018 / V3 Product Strategy §7).

Implements dedicated store/DAO operations for Personal Access Tokens (uf_pats)
and the append-only audit log (uf_audit_log).
No SQL belongs in the delivery/router layer.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import secrets
import sqlite3
from datetime import timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.api.audit import (
    AUDIT_EVENT_TYPES,
    AuditEvent,
    AuditEventType,
    sanitize_audit_details,
)
from src.database.db import get_db_connection

logger = logging.getLogger(__name__)

# ── SQLite DDL ───────────────────────────────────────────────────────────────

# uf_audit_log (ADR-013 / ADR-018: SQL lives in this persistence module)
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

PAT_TABLE_NAME = "uf_pats"
PAT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS uf_pats (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    sha256_hash TEXT NOT NULL,
    scopes_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    last_used_at TEXT
);
"""
PAT_INDEX_HASH_SQL = """
CREATE INDEX IF NOT EXISTS idx_uf_pats_hash
ON uf_pats (sha256_hash);
"""
PAT_INDEX_USER_SQL = """
CREATE INDEX IF NOT EXISTS idx_uf_pats_user_revoked
ON uf_pats (user_id, revoked_at);
"""

MAX_ACTIVE_TOKENS_PER_USER = 10


def ensure_tables(conn: sqlite3.Connection) -> None:
    """Idempotently create tables and indexes for PATs and audit logs."""
    cursor = conn.cursor()
    cursor.execute(PAT_TABLE_SQL)
    cursor.execute(PAT_INDEX_HASH_SQL)
    cursor.execute(PAT_INDEX_USER_SQL)
    cursor.execute(AUDIT_TABLE_SQL)
    cursor.execute(AUDIT_INDEX_SQL)
    for trigger_sql in AUDIT_APPEND_ONLY_SQL:
        cursor.execute(trigger_sql)
    conn.commit()


def hash_token_secret(secret: str) -> str:
    """Return the SHA-256 hexadecimal digest of a PAT secret string."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


class TokenStore:
    """Persistence and lifecycle operations for Personal Access Tokens."""

    @classmethod
    def create_token(
        cls,
        user_id: str,
        name: str,
        scopes: Sequence[str],
        expires_in_days: int = 30,
    ) -> Tuple[Dict[str, Any], str]:
        """Create and persist a new PAT.

        Returns:
            Tuple of (token_metadata_dict, raw_secret_token_string).
            The raw secret is 256 bits of cryptographically secure random bytes
            prefixed with 'uf_pat_' and is returned only once. Only the SHA-256
            hash is stored in the database.

        Raises:
            ValueError: if expires_in_days is outside [1, 90] or scopes invalid.
            RuntimeError: if active token limit (10) is exceeded.
        """
        if not (1 <= expires_in_days <= 90):
            raise ValueError(
                f"expires_in_days must be between 1 and 90, got {expires_in_days}"
            )

        with get_db_connection() as conn:
            ensure_tables(conn)
            # BEGIN IMMEDIATE takes SQLite's write lock before the count, so the
            # count and the insert are one atomic step: concurrent creators for
            # the same user are serialized and cannot all pass the quota check.
            conn.execute("BEGIN IMMEDIATE;")
            try:
                if cls._count_active_with_conn(conn, user_id) >= (
                    MAX_ACTIVE_TOKENS_PER_USER
                ):
                    raise RuntimeError(
                        f"Active PAT limit exceeded (maximum {MAX_ACTIVE_TOKENS_PER_USER} active tokens)"
                    )

                # 256-bit secret: secrets.token_urlsafe(32) -> 43 URL-safe characters
                raw_secret = f"uf_pat_{secrets.token_urlsafe(32)}"
                token_hash = hash_token_secret(raw_secret)
                token_id = f"pat_{secrets.token_hex(6)}"

                now = datetime.datetime.now(timezone.utc)
                created_at = now.isoformat()
                expires_at = (now + timedelta(days=expires_in_days)).isoformat()
                scopes_json = json.dumps(list(scopes))

                conn.execute(
                    """
                    INSERT INTO uf_pats (
                        id, user_id, name, sha256_hash, scopes_json,
                        created_at, expires_at, revoked_at, last_used_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL);
                    """,
                    (
                        token_id,
                        user_id,
                        name,
                        token_hash,
                        scopes_json,
                        created_at,
                        expires_at,
                    ),
                )
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

            metadata = {
                "id": token_id,
                "name": name,
                "scopes": list(scopes),
                "createdAt": created_at,
                "expiresAt": expires_at,
                "lastUsedAt": None,
            }
            return metadata, raw_secret

    @classmethod
    def get_by_hash(cls, sha256_hash: str) -> Optional[Dict[str, Any]]:
        """Lookup a token row by its SHA-256 hash."""
        with get_db_connection() as conn:
            ensure_tables(conn)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, user_id, name, sha256_hash, scopes_json,
                       created_at, expires_at, revoked_at, last_used_at
                FROM uf_pats
                WHERE sha256_hash = ?;
                """,
                (sha256_hash,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return cls._row_to_dict(row)

    @classmethod
    def get_by_id(
        cls, token_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Lookup a token by ID, optionally verifying ownership."""
        with get_db_connection() as conn:
            ensure_tables(conn)
            cursor = conn.cursor()
            if user_id:
                cursor.execute(
                    """
                    SELECT id, user_id, name, sha256_hash, scopes_json,
                           created_at, expires_at, revoked_at, last_used_at
                    FROM uf_pats
                    WHERE id = ? AND user_id = ?;
                    """,
                    (token_id, user_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, user_id, name, sha256_hash, scopes_json,
                           created_at, expires_at, revoked_at, last_used_at
                    FROM uf_pats
                    WHERE id = ?;
                    """,
                    (token_id,),
                )
            row = cursor.fetchone()
            if not row:
                return None
            return cls._row_to_dict(row)

    @classmethod
    def list_active(cls, user_id: str) -> List[Dict[str, Any]]:
        """List active, non-revoked, unexpired tokens owned by user_id."""
        with get_db_connection() as conn:
            ensure_tables(conn)
            now = datetime.datetime.now(timezone.utc).isoformat()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, user_id, name, sha256_hash, scopes_json,
                       created_at, expires_at, revoked_at, last_used_at
                FROM uf_pats
                WHERE user_id = ?
                  AND revoked_at IS NULL
                  AND expires_at > ?
                ORDER BY created_at DESC;
                """,
                (user_id, now),
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "scopes": json.loads(r["scopes_json"]),
                    "createdAt": r["created_at"],
                    "expiresAt": r["expires_at"],
                    "lastUsedAt": r["last_used_at"],
                }
                for r in rows
            ]

    @classmethod
    def count_active(cls, user_id: str) -> int:
        """Count active, non-revoked, unexpired tokens owned by user_id."""
        with get_db_connection() as conn:
            ensure_tables(conn)
            return cls._count_active_with_conn(conn, user_id)

    @staticmethod
    def _count_active_with_conn(conn: sqlite3.Connection, user_id: str) -> int:
        now = datetime.datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM uf_pats
            WHERE user_id = ?
              AND revoked_at IS NULL
              AND expires_at > ?;
            """,
            (user_id, now),
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0

    @classmethod
    def revoke(cls, token_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Revoke a token owned by user_id.

        Returns:
            The token dict if revoked or already revoked.
            None if token not found or owned by a different user.
        """
        with get_db_connection() as conn:
            ensure_tables(conn)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, user_id, name, sha256_hash, scopes_json,
                       created_at, expires_at, revoked_at, last_used_at
                FROM uf_pats
                WHERE id = ? AND user_id = ?;
                """,
                (token_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                return None

            token_data = cls._row_to_dict(row)
            if token_data["revoked_at"] is None:
                now_str = datetime.datetime.now(timezone.utc).isoformat()
                cursor.execute(
                    "UPDATE uf_pats SET revoked_at = ? WHERE id = ?;",
                    (now_str, token_id),
                )
                conn.commit()
                token_data["revoked_at"] = now_str

            return token_data

    @classmethod
    def touch_last_used(cls, token_id: str) -> None:
        """Record the current timestamp as last_used_at."""
        try:
            with get_db_connection() as conn:
                ensure_tables(conn)
                now_str = datetime.datetime.now(timezone.utc).isoformat()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE uf_pats SET last_used_at = ? WHERE id = ?;",
                    (now_str, token_id),
                )
                conn.commit()
        except Exception:
            logger.warning(
                f"Failed to touch last_used_at for token {token_id}", exc_info=True
            )

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "name": row["name"],
            "sha256_hash": row["sha256_hash"],
            "scopes_json": row["scopes_json"],
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
            "revoked_at": row["revoked_at"],
            "last_used_at": row["last_used_at"],
        }


class AuditStore:
    """Append-only persistence for audit events (V3 Product Strategy §7)."""

    @classmethod
    def record_event(
        cls,
        user_id: str,
        event_type: AuditEventType,
        token_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Record an append-only audit event with strictly sanitized details."""
        if event_type not in AUDIT_EVENT_TYPES:
            raise ValueError(
                f"Invalid audit event type: {event_type}. Allowed: {sorted(AUDIT_EVENT_TYPES)}"
            )

        sanitized = sanitize_audit_details(details or {})
        event_id = f"aud_{secrets.token_hex(8)}"
        timestamp = datetime.datetime.now(timezone.utc).isoformat()
        details_json = json.dumps(sanitized)

        with get_db_connection() as conn:
            ensure_tables(conn)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO uf_audit_log (
                    id, timestamp, user_id, token_id, event_type, details_json
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (event_id, timestamp, user_id, token_id, event_type, details_json),
            )
            conn.commit()

        return AuditEvent(
            id=event_id,
            timestamp=timestamp,
            userId=user_id,
            eventType=event_type,
            tokenId=token_id,
            details=sanitized,
        )

    @classmethod
    def list_events(
        cls,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """List audit events in descending chronological order."""
        with get_db_connection() as conn:
            ensure_tables(conn)
            cursor = conn.cursor()
            if user_id:
                cursor.execute(
                    """
                    SELECT id, timestamp, user_id, token_id, event_type, details_json
                    FROM uf_audit_log
                    WHERE user_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?;
                    """,
                    (user_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, timestamp, user_id, token_id, event_type, details_json
                    FROM uf_audit_log
                    ORDER BY timestamp DESC
                    LIMIT ?;
                    """,
                    (limit,),
                )
            rows = cursor.fetchall()
            return [
                AuditEvent(
                    id=r["id"],
                    timestamp=r["timestamp"],
                    userId=r["user_id"],
                    eventType=r["event_type"],
                    tokenId=r["token_id"],
                    details=json.loads(r["details_json"]),
                )
                for r in rows
            ]
