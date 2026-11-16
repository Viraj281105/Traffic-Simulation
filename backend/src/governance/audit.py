"""Append-only, hash-chained audit log (F10).

Each entry commits to its predecessor: ``hash = SHA-256(canonical JSON of the
entry fields incl. prevHash)``. Editing, deleting or reordering any entry
breaks the chain; dropping the tail is caught by comparing against a head hash
(and length) stored elsewhere.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence

GENESIS_HASH = "0" * 64


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuditEntry:
    seq: int
    timestamp: float
    actor: str
    action: str
    subject: str
    payload_digest: str
    prev_hash: str
    hash: str

    def body(self) -> Dict[str, Any]:
        return {
            "seq": self.seq,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "action": self.action,
            "subject": self.subject,
            "payloadDigest": self.payload_digest,
            "prevHash": self.prev_hash,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {**self.body(), "hash": self.hash}

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AuditEntry":
        return AuditEntry(
            seq=int(data["seq"]),
            timestamp=float(data["timestamp"]),
            actor=str(data["actor"]),
            action=str(data["action"]),
            subject=str(data["subject"]),
            payload_digest=str(data["payloadDigest"]),
            prev_hash=str(data["prevHash"]),
            hash=str(data["hash"]),
        )


def compute_hash(entry: AuditEntry) -> str:
    return sha256_hex(canonical_json(entry.body()))


@dataclass(frozen=True)
class ChainVerification:
    ok: bool
    length: int
    head: str
    error: Optional[str] = None
    bad_seq: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "length": self.length,
            "head": self.head,
            "error": self.error,
            "badSeq": self.bad_seq,
        }


def verify_chain(
    entries: Sequence[AuditEntry],
    expected_head: Optional[str] = None,
    expected_length: Optional[int] = None,
) -> ChainVerification:
    """Check seq continuity, prev-hash links and every entry hash.

    ``expected_head`` / ``expected_length`` (kept outside the log) also detect
    truncation of the tail, which a bare chain cannot reveal.
    """
    prev = GENESIS_HASH
    for index, entry in enumerate(entries):
        head = entries[index - 1].hash if index else GENESIS_HASH

        def fail(msg: str) -> ChainVerification:
            return ChainVerification(False, len(entries), head, msg, entry.seq)

        if entry.seq != index:
            return fail(f"sequence break at position {index}: seq {entry.seq}")
        if entry.prev_hash != prev:
            return fail(f"prevHash mismatch at seq {entry.seq}")
        if compute_hash(entry) != entry.hash:
            return fail(f"hash mismatch at seq {entry.seq} (entry altered)")
        prev = entry.hash
    if expected_length is not None and len(entries) != expected_length:
        return ChainVerification(
            False,
            len(entries),
            prev,
            f"length {len(entries)} != expected {expected_length} (truncated)",
        )
    if expected_head is not None and prev != expected_head:
        return ChainVerification(
            False, len(entries), prev, "head hash differs from the stored head"
        )
    return ChainVerification(True, len(entries), prev)


class AuditStore(Protocol):
    def append(self, entry: AuditEntry) -> None: ...

    def read_all(self) -> List[AuditEntry]: ...


class InMemoryAuditStore:
    def __init__(self) -> None:
        self._entries: List[AuditEntry] = []

    def append(self, entry: AuditEntry) -> None:
        self._entries.append(entry)

    def read_all(self) -> List[AuditEntry]:
        return list(self._entries)


class JsonlAuditStore:
    """One JSON object per line; each append is a single write of a whole line."""

    def __init__(self, path: Path, fsync: bool = False) -> None:
        self._path = Path(path)
        self._fsync = fsync
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, entry: AuditEntry) -> None:
        line = (canonical_json(entry.to_dict()) + "\n").encode("utf-8")
        with open(self._path, "ab") as fh:
            fh.write(line)
            fh.flush()
            if self._fsync:
                os.fsync(fh.fileno())

    def read_all(self) -> List[AuditEntry]:
        if not self._path.exists():
            return []
        out: List[AuditEntry] = []
        with open(self._path, "r", encoding="utf-8") as fh:
            for raw in fh:
                if raw.strip():
                    out.append(AuditEntry.from_dict(json.loads(raw)))
        return out


class AuditLog:
    """Appends entries (no update or delete API) to a store."""

    def __init__(
        self,
        store: Optional[AuditStore] = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._store: AuditStore = store if store is not None else InMemoryAuditStore()
        self._clock = clock
        self._lock = threading.Lock()

    def append(
        self,
        actor: str,
        action: str,
        subject: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        with self._lock:
            existing = self._store.read_all()
            prev = existing[-1].hash if existing else GENESIS_HASH
            draft = AuditEntry(
                seq=len(existing),
                timestamp=float(self._clock()),
                actor=actor,
                action=action,
                subject=subject,
                payload_digest=sha256_hex(canonical_json(payload or {})),
                prev_hash=prev,
                hash="",
            )
            entry = AuditEntry(**{**draft.__dict__, "hash": compute_hash(draft)})
            self._store.append(entry)
            return entry

    def entries(self) -> List[AuditEntry]:
        return self._store.read_all()

    def head(self) -> str:
        entries = self._store.read_all()
        return entries[-1].hash if entries else GENESIS_HASH

    def verify(
        self,
        expected_head: Optional[str] = None,
        expected_length: Optional[int] = None,
    ) -> ChainVerification:
        return verify_chain(self._store.read_all(), expected_head, expected_length)
