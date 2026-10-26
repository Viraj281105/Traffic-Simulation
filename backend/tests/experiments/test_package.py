"""``.ufpkg`` export, verification and safe extraction (W7 Stage 4)."""

from __future__ import annotations

import hashlib
import io
import json
import stat
import zipfile
from typing import Any, Dict

import pytest

from src.experiments import limits
from src.experiments import package as pkg
from src.experiments.package import (
    PackageError,
    build_package,
    extract_package,
    inspect_package,
    render_checksums,
)

from .conftest import FakeExecutor, as_user, build_client, submit, wait_for

ALICE, BOB = "alice", "bob"


@pytest.fixture
def exported(make_service):
    """(client, service, experiment id, package bytes) of one completed experiment."""
    service = make_service(FakeExecutor())
    client = build_client(service)
    eid = submit(client, ALICE)["id"]
    assert wait_for(client, eid)["status"] == "completed"
    res = client.get(f"/api/v3/experiments/{eid}/package", headers=as_user(ALICE))
    assert res.status_code == 200
    return client, service, eid, res.content


def unpack(data: bytes) -> Dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return {i.filename: zf.read(i) for i in zf.infolist()}


def pack(
    members: Dict[str, bytes],
    *,
    fix_sums: bool = True,
    compress: int = zipfile.ZIP_DEFLATED,
) -> bytes:
    """A zip of ``members``; SHA256SUMS is recomputed unless ``fix_sums`` is False."""
    members = dict(members)
    if fix_sums:
        body = {n: c for n, c in members.items() if n != pkg.CHECKSUMS_NAME}
        members[pkg.CHECKSUMS_NAME] = render_checksums(body)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compress) as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return buffer.getvalue()


def errors_of(data: bytes) -> str:
    report = inspect_package(data)
    assert report.internallyConsistent is False, report
    return " | ".join(report.errors)


def with_manifest(members: Dict[str, bytes], **changes: Any) -> Dict[str, bytes]:
    manifest = json.loads(members[pkg.MANIFEST_NAME])
    manifest.update(changes)
    out = dict(members)
    out[pkg.MANIFEST_NAME] = json.dumps(manifest).encode()
    return out


# ---- round trip --------------------------------------------------------------------------------------


def test_round_trip_verifies_and_reports_an_exact_replay(exported):
    client, _service, _eid, data = exported
    verified = client.post(
        "/api/v3/packages/verify",
        content=data,
        headers={**as_user(ALICE), "Content-Type": "application/octet-stream"},
    )
    assert verified.status_code == 200
    report = verified.json()
    assert report["internallyConsistent"] is True and report["errors"] == []
    assert report["replayClass"] == "exact"
    assert report["kind"] == "robustness_experiment"
    assert report["format"] == "urbanflow-package-verification"
    assert report["integrityNote"].startswith("Integrity is not authenticity")
    names = {m["name"] for m in report["manifestSummary"]["members"]}
    assert names == {"manifest.json", "experiment.json", "result.json", "SHA256SUMS"}


def test_export_is_deterministic_and_well_formed(exported):
    client, _service, eid, data = exported
    again = client.get(f"/api/v3/experiments/{eid}/package", headers=as_user(ALICE))
    assert again.content == data
    assert again.headers["content-type"] == "application/zip"
    assert again.headers["content-disposition"].startswith("attachment; filename=")
    assert again.headers["cache-control"] == "no-store"
    members = unpack(data)
    assert list(members) == [
        "experiment.json",
        "result.json",
        "manifest.json",
        "SHA256SUMS",
    ] or set(members) == {
        "manifest.json",
        "experiment.json",
        "result.json",
        "SHA256SUMS",
    }
    sums = members["SHA256SUMS"].decode()
    assert "\r" not in sums and sums.endswith("\n")
    for line in sums.splitlines():
        digest, name = line.split("  ", 1)
        assert hashlib.sha256(members[name]).hexdigest() == digest
    manifest = json.loads(members["manifest.json"])
    assert (
        manifest["packageChecksums"]["result.json"]
        == hashlib.sha256(members["result.json"]).hexdigest()
    )


def test_export_is_owner_only_and_completed_only(make_service):
    import threading

    release = threading.Event()
    service = make_service(FakeExecutor(block=release))
    client = build_client(service)
    eid = submit(client, ALICE)["id"]
    try:
        running = client.get(
            f"/api/v3/experiments/{eid}/package", headers=as_user(ALICE)
        )
        assert running.status_code == 409
    finally:
        release.set()
        wait_for(client, eid)
    assert (
        client.get(
            f"/api/v3/experiments/{eid}/package", headers=as_user(BOB)
        ).status_code
        == 404
    )
    assert (
        client.get(
            "/api/v3/experiments/nope/package", headers=as_user(ALICE)
        ).status_code
        == 404
    )


def test_a_cancelled_experiment_cannot_be_exported(make_service):
    from .test_cancel_resume import start_and_cancel, wait_settled

    service, client, _executor, eid, _ = start_and_cancel(make_service, after=4)
    wait_settled(service, eid)
    assert (
        client.get(
            f"/api/v3/experiments/{eid}/package", headers=as_user(ALICE)
        ).status_code
        == 409
    )


def test_oversized_export_is_413(exported, monkeypatch):
    client, _service, eid, _data = exported
    monkeypatch.setattr(limits, "MAX_PACKAGE_BYTES", 100)
    res = client.get(f"/api/v3/experiments/{eid}/package", headers=as_user(ALICE))
    assert res.status_code == 413


# ---- tampering --------------------------------------------------------------------------------------


def test_altered_member_bytes_are_rejected(exported):
    members = unpack(exported[3])
    members["result.json"] = members["result.json"].replace(b"a", b"b", 1)
    assert "does not match its SHA-256" in errors_of(pack(members, fix_sums=False))


def test_altered_result_with_recomputed_checksums_fails_the_fingerprint_check(exported):
    members = unpack(exported[3])
    result = json.loads(members["result.json"])
    result["analysis"]["settings"] = {"tampered": True}
    members["result.json"] = json.dumps(result).encode()
    text = errors_of(pack(members))
    assert "result fingerprint does not match" in text or "packageChecksums" in text


def test_missing_and_unlisted_members_are_rejected(exported):
    members = unpack(exported[3])
    without = {n: c for n, c in members.items() if n != "result.json"}
    assert "result.json is missing" in errors_of(pack(without, fix_sums=False))

    extra = dict(members)
    extra["notes.txt"] = b"hi"
    assert "not a recognised package member" in errors_of(pack(extra))

    undeclared = dict(members)
    undeclared["sidecars/extra.txt"] = b"hi"
    assert "not declared in the manifest" in errors_of(pack(undeclared))

    unlisted = dict(members)
    sums = unlisted["SHA256SUMS"].decode().splitlines()
    unlisted["SHA256SUMS"] = ("\n".join(sums[:-1]) + "\n").encode()
    assert "is not listed in SHA256SUMS" in errors_of(pack(unlisted, fix_sums=False))

    ghost = dict(members)
    ghost["SHA256SUMS"] = (
        members["SHA256SUMS"] + (b"0" * 64) + b"  sidecars/ghost.txt\n"
    )
    assert "which is not in the package" in errors_of(pack(ghost, fix_sums=False))


def test_malformed_checksum_files_are_rejected(exported):
    members = unpack(exported[3])
    good = members["SHA256SUMS"]
    for bad in (
        good.replace(b"\n", b"\r\n"),
        good.rstrip(b"\n"),
        good.upper(),
        b"not a checksum line\n",
        b"\n".join(reversed(good.splitlines())) + b"\n",
        good + good.splitlines()[0] + b"\n",
        b"\xff\xfe",
    ):
        assert errors_of(pack({**members, "SHA256SUMS": bad}, fix_sums=False))


def test_digest_in_manifest_for_a_sidecar_must_match(exported):
    members = unpack(exported[3])
    manifest = json.loads(members["manifest.json"])
    content = b"a,b\n1,2\n"
    manifest["sidecars"] = [
        {
            "name": "data.csv",
            "kind": "csv",
            "path": "sidecars/data.csv",
            "sha256": "f" * 64,
        }
    ]
    members["manifest.json"] = json.dumps(manifest).encode()
    members["sidecars/data.csv"] = content
    assert "does not match the digest in the manifest" in errors_of(pack(members))


def test_a_declared_sidecar_round_trips(exported):
    client, service, eid, _data = exported
    record = service.store.get(ALICE, eid)
    data = build_package(
        record["request"],
        record["result"],
        record["createdAt"],
        {"table.csv": b"a,b\n1,2\n"},
    )
    report = inspect_package(data)
    assert report.internallyConsistent, report.errors
    assert "sidecars/table.csv" in {
        m["name"] for m in report.manifestSummary["members"]
    }


# ---- archive structure ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "../evil.txt",
        "sidecars/../../evil.txt",
        "/etc/passwd",
        "C:/evil.txt",
        "sidecars\\evil.txt",
        "sidecars/.hidden.txt",
        "sidecars/con.txt",
        "sidecars/a b.txt",
        "sidecars/sub/dir.txt",
        "sidecars/evil.py",
        "sidecars/evil.exe",
        "sidecars/",
        "x" * 200,
    ],
)
def test_unsafe_member_names_are_rejected(exported, name):
    members = unpack(exported[3])
    members[name] = b"data"
    text = errors_of(pack(members))
    assert "member" in text or "directory" in text


def test_duplicate_and_case_colliding_names_are_rejected(exported):
    members = unpack(exported[3])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
        with pytest.warns(UserWarning):
            zf.writestr("manifest.json", b"{}")
        zf.writestr("MANIFEST.JSON", b"{}")
    assert "appears more than once" in errors_of(buffer.getvalue())


def test_symlinks_encrypted_and_unsupported_compression_are_rejected(exported):
    members = unpack(exported[3])

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
        link = zipfile.ZipInfo("sidecars/link.txt")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(link, "/etc/passwd")
    assert "link or special file" in errors_of(buffer.getvalue())

    raw = bytearray(pack(members))
    at = raw.find(b"PK")
    while at != -1:  # set the "encrypted" flag in every central-directory entry
        raw[at + 8] |= 0x1
        at = raw.find(b"PK", at + 4)
    assert "encrypted" in errors_of(bytes(raw))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_BZIP2) as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    assert "unsupported compression" in errors_of(buffer.getvalue())


def test_entry_count_size_and_ratio_limits(exported, monkeypatch):
    members = unpack(exported[3])
    many = dict(members)
    for i in range(limits.MAX_PACKAGE_ENTRIES + 1):
        many[f"sidecars/f{i}.txt"] = b"x"
    assert "more than" in errors_of(pack(many))

    # A bomb: a few KB on the wire, far more once unpacked.
    bomb = dict(members)
    bomb["sidecars/zeros.txt"] = b"0" * (limits.MAX_PACKAGE_UNCOMPRESSED_BYTES + 1024)
    data = pack(bomb)
    assert len(data) < limits.MAX_PACKAGE_BYTES
    assert "larger than the unpacked size limit" in errors_of(data)

    # Well-compressed but within the byte limit: the ratio check still refuses it.
    squeezed = dict(members)
    squeezed["sidecars/zeros.txt"] = b"0" * (5 * 1024 * 1024)
    assert "compressed suspiciously well" in errors_of(pack(squeezed))

    # The total of all members is bounded too.
    monkeypatch.setattr(limits, "MAX_PACKAGE_UNCOMPRESSED_BYTES", 1000)
    assert "unpacks to more than" in errors_of(exported[3])


def test_oversized_package_and_non_zip_input(exported):
    assert "is empty" in errors_of(b"")
    assert "not a valid ZIP" in errors_of(b"definitely not a zip")
    assert "not a valid ZIP" in errors_of(exported[3][: len(exported[3]) // 2])
    big = b"\0" * (limits.MAX_PACKAGE_BYTES + 1)
    assert "larger than" in errors_of(big)


def test_corrupt_member_data_is_reported_not_raised(exported):
    data = bytearray(exported[3])
    middle = len(data) // 3
    for i in range(middle, middle + 8):
        data[i] ^= 0xFF
    report = inspect_package(bytes(data))
    assert report.internallyConsistent is False and report.errors


# ---- executable content ----------------------------------------------------------------------------


def declared_sidecar(
    members: Dict[str, bytes], leaf: str, content: bytes
) -> Dict[str, bytes]:
    out = with_manifest(
        members,
        sidecars=[
            {
                "name": leaf,
                "kind": "data",
                "path": f"sidecars/{leaf}",
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        ],
    )
    out[f"sidecars/{leaf}"] = content
    return out


@pytest.mark.parametrize(
    "content,what",
    [
        (b"MZ\x90\x00 fake exe", "executable"),
        (b"\x7fELF\x02\x01", "executable"),
        (b"#!/bin/sh\nrm -rf /\n", "script"),
        (b"PK\x03\x04nested", "nested archive"),
        (b"\x1f\x8b\x08gz", "archive"),
    ],
)
def test_executable_and_archive_content_is_rejected_whatever_it_is_called(
    exported, content, what
):
    members = declared_sidecar(unpack(exported[3]), "data.txt", content)
    assert what in errors_of(pack(members))


def test_sidecars_must_be_utf8_text(exported):
    members = declared_sidecar(unpack(exported[3]), "data.csv", b"a,b\n\x00\x01\n")
    assert "not text" in errors_of(pack(members))
    members = declared_sidecar(unpack(exported[3]), "data.csv", b"\xff\xfe\xfd")
    assert "not UTF-8 text" in errors_of(pack(members))


def test_build_refuses_disallowed_sidecars(exported):
    _client, service, eid, _ = exported
    record = service.store.get(ALICE, eid)
    for leaf, content in (
        ("run.py", b"print(1)"),
        ("x.txt", b"#!/bin/sh"),
        ("../x.txt", b"a"),
    ):
        with pytest.raises(PackageError):
            build_package(record["request"], record["result"], "t", {leaf: content})
    with pytest.raises(PackageError):
        build_package(record["request"], {"format": "other"}, "t")


# ---- manifest handling ----------------------------------------------------------------------------


def test_pre_w7_manifest_without_kind_or_sidecars_still_verifies(exported):
    members = unpack(exported[3])
    manifest = json.loads(members["manifest.json"])
    for key in ("kind", "sidecars", "packageChecksums", "createdAt"):
        manifest.pop(key, None)
    members["manifest.json"] = json.dumps(manifest).encode()
    report = inspect_package(pack(members))
    assert report.internallyConsistent, report.errors
    assert report.kind == "robustness_experiment"


def test_unknown_kind_is_verified_structurally_only(exported):
    members = unpack(exported[3])
    manifest = json.loads(members["manifest.json"])
    manifest["kind"] = "ai_copilot_proposal_v1"
    manifest["assumptions"] = {"anything": "goes"}
    members = {
        "manifest.json": json.dumps(manifest).encode(),
    }
    report = inspect_package(pack(members))
    assert report.internallyConsistent, report.errors
    assert report.kind == "ai_copilot_proposal_v1"
    assert any("not recognised" in w for w in report.warnings)
    assert report.replayClass == "differs (engine or runtime changed)"


def test_invalid_manifests_are_rejected(exported):
    members = unpack(exported[3])
    for changes in (
        {"format": "other"},
        {"version": 2},
        {"specFingerprint": 5},
        {"sidecars": [{"name": "x"}]},
        {"sidecars": [{"name": "a", "kind": "k", "path": "../x", "sha256": "0" * 64}]},
        {
            "sidecars": [
                {"name": "a", "kind": "k", "path": "sidecars/x.txt", "sha256": "xyz"}
            ]
        },
        {"surprise": True},
    ):
        errors_of(pack(with_manifest(members, **changes)))
    broken = dict(members)
    broken["manifest.json"] = b"[1, 2]"
    assert "JSON object" in errors_of(pack(broken))
    broken["manifest.json"] = b"\xff not json"
    assert "not valid JSON" in errors_of(pack(broken))
    broken["manifest.json"] = b"[" * 3000
    assert errors_of(pack(broken))


def test_manifest_package_checksums_must_agree_with_sha256sums(exported):
    members = unpack(exported[3])
    manifest = json.loads(members["manifest.json"])
    manifest["packageChecksums"]["result.json"] = "0" * 64
    members["manifest.json"] = json.dumps(manifest).encode()
    assert "packageChecksums disagree" in errors_of(pack(members))


def test_experiment_and_result_must_describe_the_same_run(exported):
    members = unpack(exported[3])
    request = json.loads(members["experiment.json"])
    request["uncertainty"]["seed"] = 999
    members["experiment.json"] = json.dumps(request).encode()
    text = errors_of(pack(members))
    assert "different specifications" in text or "packageChecksums" in text
    members = unpack(exported[3])
    members["experiment.json"] = b'{"nonsense": true}'
    assert "not a valid experiment request" in errors_of(pack(members))


# ---- replay class -----------------------------------------------------------------------------------


def test_replay_class_follows_recorded_provenance(exported, monkeypatch):
    data = exported[3]
    assert inspect_package(data).replayClass == "exact"

    monkeypatch.setattr(pkg, "GIT_COMMIT_HASH", "0" * 40)
    other_commit = inspect_package(data)
    assert other_commit.replayClass == "comparable" and other_commit.warnings
    monkeypatch.undo()

    monkeypatch.setattr(pkg, "PYTHON_VERSION", "2.7.18")
    assert inspect_package(data).replayClass == "differs (engine or runtime changed)"
    monkeypatch.undo()

    members = unpack(data)
    manifest = json.loads(members["manifest.json"])
    manifest["assumptions"]["driverAggressionHash"] = "deadbeefdeadbeef"
    members["manifest.json"] = json.dumps(manifest).encode()
    changed = inspect_package(pack(members))
    assert changed.replayClass == "differs (engine or runtime changed)"

    members = unpack(data)
    manifest = json.loads(members["manifest.json"])
    manifest.pop("gitCommit"), manifest.pop("pythonVersion")
    members["manifest.json"] = json.dumps(manifest).encode()
    legacy = inspect_package(pack(members))
    assert legacy.replayClass == "comparable" and any(
        "pre-W7" in w for w in legacy.warnings
    )


# ---- extraction --------------------------------------------------------------------------------------


def test_extract_writes_verified_members_exclusively(exported, tmp_path):
    data = exported[3]
    written = extract_package(data, tmp_path / "out")
    assert {p.name for p in written} == {
        "manifest.json",
        "experiment.json",
        "result.json",
        "SHA256SUMS",
    }
    with pytest.raises(FileExistsError):
        extract_package(data, tmp_path / "out")  # never overwrites


def test_extract_refuses_a_package_that_fails_verification(exported, tmp_path):
    members = unpack(exported[3])
    members["result.json"] = b"{}"
    with pytest.raises(PackageError):
        extract_package(pack(members, fix_sums=False), tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_extract_checks_resolved_paths_against_the_root(exported, tmp_path):
    data = exported[3]
    members = unpack(data)
    record_data = declared_sidecar(members, "data.csv", b"a,b\n")
    package = pack(record_data)
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "sidecars"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        link = None  # no symlink privilege here: the containment rule is still tested below
    if link is not None:
        with pytest.raises(PackageError, match="escapes"):
            extract_package(package, root)
        assert list(outside.iterdir()) == []


def test_resolved_path_containment_rule(tmp_path):
    root = tmp_path.resolve()
    assert pkg._resolve_inside(root, "sidecars/a.txt") == root / "sidecars" / "a.txt"
    for bad in ("../x", "sidecars/../../x", "/abs/x", "", "a/../../b"):
        with pytest.raises(PackageError, match="escapes"):
            pkg._resolve_inside(root, bad)
    (root / "sub").mkdir()
    (root / "sub" / "..").resolve()  # sanity


# ---- HTTP: authentication, scopes, limits ---------------------------------------------------------


def test_verify_requires_packages_write_and_export_packages_read(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    import src.api.security as security
    from src.api.auth import reset_auth_failures
    from src.api.store import TokenStore
    from src.main import app

    monkeypatch.setattr("src.database.db.DB_PATH", str(tmp_path / "pkg.db"))
    monkeypatch.setattr(security, "API_KEY", "k")
    reset_auth_failures()
    client = TestClient(app)

    def pat(scopes):
        _, raw = TokenStore.create_token("carol", "t", scopes)
        return {"X-API-Key": "k", "Authorization": f"Bearer {raw}"}

    read, write, none = (
        pat(["packages:read"]),
        pat(["packages:write"]),
        pat(["experiments:read"]),
    )
    body = {
        "content": b"not a package",
        "headers": {"Content-Type": "application/octet-stream"},
    }

    def verify(headers):
        return client.post(
            "/api/v3/packages/verify",
            content=body["content"],
            headers={**headers, **body["headers"]},
        )

    assert verify(none).status_code == 403
    assert verify(read).status_code == 403
    ok = verify(write)
    assert ok.status_code == 200 and ok.json()["internallyConsistent"] is False
    assert client.post("/api/v3/packages/verify", content=b"x").status_code in (
        401,
        403,
    )

    assert (
        client.get("/api/v3/experiments/abc/package", headers=write).status_code == 403
    )
    assert (
        client.get("/api/v3/experiments/abc/package", headers=read).status_code == 404
    )

    too_big = client.post(
        "/api/v3/packages/verify",
        content=b"\0" * (limits.MAX_PACKAGE_BYTES + 1),
        headers={**write, "Content-Type": "application/octet-stream"},
    )
    assert too_big.status_code == 413


def test_verify_never_leaks_attacker_controlled_names(exported):
    members = unpack(exported[3])
    members["sidecars/\x1b[31mevil\n.txt"] = b"x"
    text = errors_of(pack(members))
    assert "\x1b" not in text and "\n" not in text
    assert "Traceback" not in text and "/home" not in text and "C:\\" not in text


def test_audit_events_for_packages_hold_no_content(exported):
    from src.api.store import AuditStore

    client, _service, eid, data = exported
    client.get(f"/api/v3/experiments/{eid}/package", headers=as_user(ALICE))
    client.post("/api/v3/packages/verify", content=data, headers=as_user(ALICE))
    events = [
        e
        for e in AuditStore.list_events(user_id=ALICE)
        if e.eventType.startswith("package_")
    ]
    kinds = {e.eventType for e in events}
    assert kinds == {"package_exported", "package_verified"}
    for e in events:
        assert "PK" not in json.dumps(e.details) and "result" not in json.dumps(
            e.details
        )
