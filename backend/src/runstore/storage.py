"""Storage backends for the run store: a small key/bytes interface.

A key is a forward-slash relative path such as ``runs/<run id>/metrics.parquet``. The same key
names the object on every backend: a file under the root directory locally, an object under the
optional prefix in an S3 bucket. Keys are checked with ``sidecar_path_error`` (the package-path rule
in ``src/experiments/manifest.py``), so a key can never climb out of the root or alias a Windows
device name.

``S3Backend`` imports ``boto3`` only when it needs a client, so the rest of the application (and
every test that injects a client) runs without it installed or configured. No credential is ever
passed or stored here: boto3 resolves them from the environment or the instance role.
"""

from __future__ import annotations

import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List, Optional

from src.experiments.manifest import sidecar_path_error


class StorageError(RuntimeError):
    """A backend could not complete an operation (not a missing key; see ``KeyNotFoundError``)."""


class KeyNotFoundError(KeyError):
    """The key does not exist in the store."""


def validate_key(key: str) -> str:
    error = sidecar_path_error(key)
    if error:
        raise ValueError(f"storage key {error}")
    return key


def validate_prefix(prefix: str) -> str:
    """A listing prefix: empty, or a safe key path optionally ending in ``/``."""
    if prefix == "":
        return ""
    validate_key(prefix[:-1] if prefix.endswith("/") else prefix)
    return prefix


class StorageBackend(ABC):
    """What the run store needs from storage. Implementations must be safe to call repeatedly."""

    @abstractmethod
    def put(self, key: str, data: bytes) -> None:
        """Store ``data`` under ``key``, replacing any existing object."""

    @abstractmethod
    def get(self, key: str) -> bytes:
        """The bytes under ``key``; raises ``KeyNotFoundError`` when absent."""

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def list(self, prefix: str = "") -> List[str]:
        """Every key starting with ``prefix``, sorted ascending."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove ``key``; removing an absent key is not an error."""


class LocalFileBackend(StorageBackend):
    """Objects as files under ``root``. Writes go to a temp file and are renamed into place, so
    a reader never sees half a file."""

    def __init__(self, root: "str | os.PathLike[str]") -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        return self.root.joinpath(*validate_key(key).split("/"))

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError:
            raise KeyNotFoundError(key) from None

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def list(self, prefix: str = "") -> List[str]:
        validate_prefix(prefix)
        if not self.root.is_dir():
            return []
        keys = [
            path.relative_to(self.root).as_posix()
            for path in self.root.rglob("*")
            if path.is_file() and not path.name.endswith(".tmp")
        ]
        return sorted(k for k in keys if k.startswith(prefix))

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink()
        except FileNotFoundError:
            pass


class S3Backend(StorageBackend):
    """Objects in an S3 bucket under an optional key prefix.

    ``client`` is any object with the boto3 S3 client methods used below; when omitted a client is
    created on first use from ``boto3`` (imported lazily) with its default credential chain.
    """

    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        *,
        client: Optional[Any] = None,
        region_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ) -> None:
        if not bucket or "/" in bucket:
            raise ValueError("bucket must be a bucket name, not a path")
        self.bucket = bucket
        self.prefix = validate_prefix(prefix).strip("/")
        self._client = client
        self._region_name = region_name
        self._endpoint_url = endpoint_url

    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                import boto3
            except ImportError as exc:  # pragma: no cover - depends on the environment
                raise StorageError("S3 storage needs boto3: pip install boto3") from exc
            self._client = boto3.client(
                "s3", region_name=self._region_name, endpoint_url=self._endpoint_url
            )
        return self._client

    def _full(self, key: str) -> str:
        validate_key(key)
        return f"{self.prefix}/{key}" if self.prefix else key

    def _strip(self, full_key: str) -> str:
        return full_key[len(self.prefix) + 1 :] if self.prefix else full_key

    @staticmethod
    def _is_missing(exc: Exception) -> bool:
        response = getattr(exc, "response", None)
        code = ""
        if isinstance(response, dict):
            code = str(response.get("Error", {}).get("Code", ""))
        return code in ("404", "NoSuchKey", "NotFound")

    def put(self, key: str, data: bytes) -> None:
        full = self._full(key)
        try:
            self.client.put_object(Bucket=self.bucket, Key=full, Body=data)
        except Exception as exc:
            raise StorageError(f"S3 put failed for {key!r}: {exc}") from exc

    def get(self, key: str) -> bytes:
        full = self._full(key)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=full)
            body: bytes = response["Body"].read()
            return body
        except Exception as exc:
            if self._is_missing(exc):
                raise KeyNotFoundError(key) from None
            raise StorageError(f"S3 get failed for {key!r}: {exc}") from exc

    def exists(self, key: str) -> bool:
        full = self._full(key)
        try:
            self.client.head_object(Bucket=self.bucket, Key=full)
            return True
        except Exception as exc:
            if self._is_missing(exc):
                return False
            raise StorageError(f"S3 head failed for {key!r}: {exc}") from exc

    def list(self, prefix: str = "") -> List[str]:
        validate_prefix(prefix)
        full_prefix = f"{self.prefix}/{prefix}" if self.prefix else prefix
        keys: List[str] = []
        token: Optional[str] = None
        try:
            while True:
                kwargs: dict[str, Any] = {
                    "Bucket": self.bucket,
                    "Prefix": full_prefix,
                }
                if token:
                    kwargs["ContinuationToken"] = token
                page = self.client.list_objects_v2(**kwargs)
                keys.extend(self._strip(obj["Key"]) for obj in page.get("Contents", []))
                if not page.get("IsTruncated"):
                    break
                token = page.get("NextContinuationToken")
        except Exception as exc:
            raise StorageError(f"S3 list failed for {prefix!r}: {exc}") from exc
        return sorted(keys)

    def delete(self, key: str) -> None:
        full = self._full(key)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=full)
        except Exception as exc:
            raise StorageError(f"S3 delete failed for {key!r}: {exc}") from exc
