"""Tenant scoping: the one way storage keys and DB queries are tied to a tenant.

Storage keys are built only through ``TenantScope.key`` / ``key_for``, which
reject anything that could leave the tenant's prefix (``..``, separators,
percent-encoding in any form, control characters). DB queries take their
tenant condition from ``TenantScope.sql_filter``. A resource of another tenant
is reported exactly like a missing one.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

TENANT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")
_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,199}$")
_IDENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
KEY_ROOT = "tenants"


class InvalidKeyError(ValueError):
    """A key or tenant id that is not allowed."""


def validate_tenant_id(tenant_id: str) -> str:
    if not TENANT_ID_PATTERN.fullmatch(tenant_id):
        raise InvalidKeyError("invalid tenant id")
    return tenant_id


def _check_segment(segment: str) -> str:
    # Strict allow-list: no '%' (so encoded and double-encoded dots and
    # slashes cannot decode later), no separators, no leading dot.
    if not _SEGMENT_PATTERN.fullmatch(segment) or ".." in segment:
        raise InvalidKeyError("invalid key segment")
    return segment


@dataclass(frozen=True)
class TenantScope:
    tenant_id: str

    def __post_init__(self) -> None:
        validate_tenant_id(self.tenant_id)

    @property
    def prefix(self) -> str:
        """Every key of this tenant starts with this (note the trailing '/',
        so tenant ``a`` never matches tenant ``ab``)."""
        return f"{KEY_ROOT}/{self.tenant_id}/"

    def key(self, *segments: str) -> str:
        """Join validated single segments under the tenant prefix."""
        if not segments:
            raise InvalidKeyError("empty key")
        return self.prefix + "/".join(_check_segment(s) for s in segments)

    def key_for(self, relative_path: str) -> str:
        """Like ``key`` for a client-supplied relative path ('a/b/c')."""
        return self.key(*relative_path.split("/"))

    def owns(self, key: str) -> bool:
        """Whether ``key`` is a well-formed key inside this tenant."""
        if not key.startswith(self.prefix):
            return False
        try:
            self.key_for(key[len(self.prefix) :])
        except InvalidKeyError:
            return False
        return True

    def relative(self, key: str) -> str:
        if not self.owns(key):
            raise InvalidKeyError("key outside tenant")
        return key[len(self.prefix) :]

    def sql_filter(self, column: str = "tenant_id") -> Tuple[str, Tuple[str, ...]]:
        """The condition (without WHERE) and parameters selecting this
        tenant's rows. ``column`` is a trusted identifier, never user input."""
        if not _IDENT_PATTERN.fullmatch(column):
            raise InvalidKeyError("invalid column name")
        return f"{column} = ?", (self.tenant_id,)


class InMemoryScopedStore:
    """Reference tenant-scoped key/value store. A real store (S3 prefix, a
    ``tenant_id`` column) follows the same shape: every operation takes the
    scope and derives the key from it."""

    def __init__(self) -> None:
        self._items: Dict[str, bytes] = {}
        self._lock = threading.Lock()

    def put(self, scope: TenantScope, path: str, value: bytes) -> str:
        key = scope.key_for(path)
        with self._lock:
            self._items[key] = value
        return key

    def get(self, scope: TenantScope, path: str) -> Optional[bytes]:
        key = scope.key_for(path)
        with self._lock:
            return self._items.get(key)

    def delete(self, scope: TenantScope, path: str) -> bool:
        key = scope.key_for(path)
        with self._lock:
            return self._items.pop(key, None) is not None

    def list(self, scope: TenantScope) -> List[str]:
        with self._lock:
            keys = [k for k in self._items if scope.owns(k)]
        return sorted(scope.relative(k) for k in keys)
