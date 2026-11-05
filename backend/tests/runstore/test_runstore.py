"""Run store: Parquet round trip on the local backend, and the S3 backend against a fake client."""

from typing import Any, Dict, List

# ruff: noqa: N803  (boto3 client methods take capitalised keyword arguments)
import pytest

from src.core.run_manifest import build_run_manifest
from src.runstore import (
    KeyNotFoundError,
    LocalFileBackend,
    RunExistsError,
    RunNotFoundError,
    RunStore,
    S3Backend,
    StorageError,
    run_id_for,
)
from src.runstore.storage import validate_key
from src.runstore.store import RUNS_PREFIX


def _manifest(seed: int = 1, **overrides: Any) -> Dict[str, Any]:
    return build_run_manifest(
        config={"simulation": {"randomSeed": seed, "duration": 30}, "x": 1},
        seed=seed,
        run_mode="multi-seed",
        git_commit="abc123",
        python_version="3.14.0",
        timing={"timeStep": 0.1, "duration": 30.0, "warmupTime": 5.0},
        created_at=overrides.pop("created_at", "2026-11-09T00:00:00+00:00"),
        **overrides,
    )


RECORDS: List[Dict[str, Any]] = [
    {"seed": 1, "delay": 4.5, "throughput": 12, "label": "a"},
    {"seed": 2, "delay": 5.25, "throughput": 11, "label": "a"},
]


class FakeClientError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeS3Client:
    """The few boto3 S3 client methods the backend uses, over a dict. Pages of 2 keys."""

    def __init__(self) -> None:
        self.objects: Dict[str, bytes] = {}
        self.fail_with: Exception | None = None

    def _maybe_fail(self) -> None:
        if self.fail_with:
            raise self.fail_with

    def put_object(self, Bucket: str, Key: str, Body: bytes) -> None:
        self._maybe_fail()
        self.objects[Key] = Body

    def get_object(self, Bucket: str, Key: str) -> Dict[str, Any]:
        self._maybe_fail()
        if Key not in self.objects:
            raise FakeClientError("NoSuchKey")
        data = self.objects[Key]

        class Body:
            def read(self) -> bytes:
                return data

        return {"Body": Body()}

    def head_object(self, Bucket: str, Key: str) -> Dict[str, Any]:
        self._maybe_fail()
        if Key not in self.objects:
            raise FakeClientError("404")
        return {}

    def delete_object(self, Bucket: str, Key: str) -> None:
        self._maybe_fail()
        self.objects.pop(Key, None)

    def list_objects_v2(self, **kwargs: Any) -> Dict[str, Any]:
        self._maybe_fail()
        keys = sorted(k for k in self.objects if k.startswith(kwargs["Prefix"]))
        start = int(kwargs.get("ContinuationToken", 0))
        page = keys[start : start + 2]
        out: Dict[str, Any] = {"Contents": [{"Key": k} for k in page]}
        if start + 2 < len(keys):
            out["IsTruncated"] = True
            out["NextContinuationToken"] = str(start + 2)
        return out


@pytest.fixture(params=["local", "s3"])
def store(request: pytest.FixtureRequest, tmp_path: Any) -> RunStore:
    if request.param == "local":
        return RunStore(LocalFileBackend(tmp_path / "store"))
    return RunStore(S3Backend("bucket", "team/a", client=FakeS3Client()))


def test_round_trip(store: RunStore) -> None:
    manifest = _manifest()
    rid = store.save_run(manifest, RECORDS)
    assert rid == run_id_for(manifest)
    run = store.load_run(rid)
    assert run.records == RECORDS
    assert run.manifest == manifest
    assert store.list_runs() == [rid] and store.has_run(rid)


def test_same_run_saved_twice_is_refused_unless_overwrite(store: RunStore) -> None:
    manifest = _manifest()
    rid = store.save_run(manifest, RECORDS)
    with pytest.raises(RunExistsError):
        store.save_run(manifest, RECORDS)
    store.save_run(manifest, RECORDS[:1], overwrite=True)
    assert store.load_run(rid).records == RECORDS[:1]


def test_created_at_does_not_change_the_run_id() -> None:
    assert run_id_for(_manifest(created_at="2026-01-01T00:00:00+00:00")) == run_id_for(
        _manifest(created_at="2027-01-01T00:00:00+00:00")
    )
    assert run_id_for(_manifest(seed=1)) != run_id_for(_manifest(seed=2))


def test_explicit_run_id_and_listing(store: RunStore) -> None:
    store.save_run(_manifest(1), RECORDS, run_id="beta")
    store.save_run(_manifest(2), RECORDS, run_id="alpha")
    assert store.list_runs() == ["alpha", "beta"]
    store.delete_run("alpha")
    store.delete_run("alpha")  # absent is not an error
    assert store.list_runs() == ["beta"]
    with pytest.raises(RunNotFoundError):
        store.load_run("alpha")


def test_incomplete_run_without_manifest_is_not_listed(store: RunStore) -> None:
    store.save_run(_manifest(), RECORDS, run_id="whole")
    store.backend.put(f"{RUNS_PREFIX}partial/metrics.parquet", b"x")
    assert store.list_runs() == ["whole"]


def test_missing_table_is_a_not_found(store: RunStore) -> None:
    store.save_run(_manifest(), RECORDS, run_id="r1")
    store.backend.delete(f"{RUNS_PREFIX}r1/metrics.parquet")
    with pytest.raises(RunNotFoundError):
        store.load_run("r1")


@pytest.mark.parametrize("bad", ["", "../x", "a/b", "a b", "-lead", "x" * 200])
def test_bad_run_ids_rejected(store: RunStore, bad: str) -> None:
    with pytest.raises(ValueError):
        store.save_run(_manifest(), RECORDS, run_id=bad)
    with pytest.raises(ValueError):
        store.load_run(bad)


def test_manifest_must_be_a_run_manifest(store: RunStore) -> None:
    with pytest.raises(ValueError, match="format"):
        store.save_run({"format": "other", "configHash": "0" * 64}, RECORDS)
    bad = dict(_manifest())
    bad["configHash"] = "short"
    with pytest.raises(ValueError, match="configHash"):
        store.save_run(bad, RECORDS)


def test_bad_record_writes_nothing(store: RunStore) -> None:
    with pytest.raises(Exception):
        store.save_run(_manifest(), [{"a": 1}, {"a": "text"}])
    assert store.backend.list("") == []


def test_parquet_object_is_real_parquet(tmp_path: Any) -> None:
    backend = LocalFileBackend(tmp_path)
    store = RunStore(backend)
    rid = store.save_run(_manifest(), RECORDS)
    assert backend.get(f"runs/{rid}/metrics.parquet")[:4] == b"PAR1"


# -- Local backend --


def test_local_backend_keys_cannot_escape(tmp_path: Any) -> None:
    backend = LocalFileBackend(tmp_path)
    for bad in ("../evil", "/abs", "a/../../b", "a\\b", "C:/x", ""):
        with pytest.raises(ValueError):
            backend.put(bad, b"x")
    with pytest.raises(ValueError):
        validate_key("a//b")


def test_local_backend_basics(tmp_path: Any) -> None:
    backend = LocalFileBackend(tmp_path / "root")
    assert backend.list() == []
    backend.put("a/b/c.bin", b"one")
    backend.put("a/b/c.bin", b"two")
    backend.put("a/z.bin", b"z")
    assert backend.get("a/b/c.bin") == b"two"
    assert backend.exists("a/b/c.bin") and not backend.exists("a/b")
    assert backend.list("a/b/") == ["a/b/c.bin"]
    assert backend.list() == ["a/b/c.bin", "a/z.bin"]
    with pytest.raises(KeyNotFoundError):
        backend.get("nope")
    backend.delete("a/z.bin")
    assert backend.list() == ["a/b/c.bin"]
    assert not list((tmp_path / "root").rglob("*.tmp"))


# -- S3 backend (client injected; boto3 is never touched) --


def test_s3_prefix_and_pagination() -> None:
    client = FakeS3Client()
    backend = S3Backend("bucket", "team/a/", client=client)
    for i in range(5):
        backend.put(f"runs/r{i}/manifest.json", b"{}")
    assert "team/a/runs/r0/manifest.json" in client.objects
    assert backend.list("runs/") == [f"runs/r{i}/manifest.json" for i in range(5)]
    assert backend.get("runs/r0/manifest.json") == b"{}"
    assert backend.exists("runs/r4/manifest.json")
    assert not backend.exists("runs/r9/manifest.json")
    backend.delete("runs/r0/manifest.json")
    assert not backend.exists("runs/r0/manifest.json")


def test_s3_no_prefix_keys_are_unchanged() -> None:
    client = FakeS3Client()
    backend = S3Backend("bucket", client=client)
    backend.put("k/v", b"1")
    assert list(client.objects) == ["k/v"] and backend.list() == ["k/v"]


def test_s3_missing_key_vs_other_errors() -> None:
    client = FakeS3Client()
    backend = S3Backend("bucket", client=client)
    with pytest.raises(KeyNotFoundError):
        backend.get("absent")
    client.fail_with = FakeClientError("AccessDenied")
    with pytest.raises(StorageError, match="get failed"):
        backend.get("x")
    with pytest.raises(StorageError, match="head failed"):
        backend.exists("x")
    with pytest.raises(StorageError, match="put failed"):
        backend.put("x", b"1")
    with pytest.raises(StorageError, match="list failed"):
        backend.list()
    with pytest.raises(StorageError, match="delete failed"):
        backend.delete("x")


def test_s3_rejects_bad_bucket_and_keys() -> None:
    with pytest.raises(ValueError):
        S3Backend("a/b", client=FakeS3Client())
    with pytest.raises(ValueError):
        S3Backend("", client=FakeS3Client())
    with pytest.raises(ValueError):
        S3Backend("b", "../up", client=FakeS3Client())
    with pytest.raises(ValueError):
        S3Backend("b", client=FakeS3Client()).put("../x", b"1")


def test_s3_client_is_created_lazily_from_boto3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys
    import types

    calls: List[Any] = []
    fake_boto3 = types.ModuleType("boto3")

    def client(service: str, **kwargs: Any) -> str:
        calls.append((service, kwargs))
        return "client-object"

    fake_boto3.client = client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    backend = S3Backend("bucket", region_name="eu-west-1", endpoint_url="http://x")
    assert calls == []  # construction does not touch boto3
    assert backend.client == "client-object"
    assert backend.client == "client-object"  # cached
    assert calls == [("s3", {"region_name": "eu-west-1", "endpoint_url": "http://x"})]


def test_s3_missing_boto3_is_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setitem(
        sys.modules, "boto3", None
    )  # makes `import boto3` raise ImportError
    with pytest.raises(StorageError, match="boto3"):
        S3Backend("bucket").client
