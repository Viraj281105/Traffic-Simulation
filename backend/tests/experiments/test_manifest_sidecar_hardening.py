"""Sidecar path and digest hardening for the experiment manifest (W7 Stage 0)."""

from __future__ import annotations

from typing import Any, Dict

import pytest
from pydantic import ValidationError

from src.experiments.manifest import (
    MANIFEST_FORMAT,
    MANIFEST_VERSION,
    ExperimentManifest,
    SidecarMetadata,
    build_experiment_manifest,
    sidecar_path_error,
    validate_manifest_semantic,
    validate_manifest_structure,
)
from src.scenario.documents import create_scenario

DIGEST = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _sidecar(**over: Any) -> Dict[str, Any]:
    return {
        "name": "metrics",
        "kind": "tabular_metrics",
        "path": "sidecars/metrics.csv",
        "sha256": DIGEST,
        **over,
    }


def _manifest(sidecars: Any) -> Dict[str, Any]:
    doc = build_experiment_manifest(
        scenario=create_scenario(name="s", driver_aggression="standard"),
        spec_fingerprint="a" * 8,
        result_fingerprint="b" * 8,
    )
    doc["sidecars"] = sidecars
    return doc


UNSAFE_PATHS = [
    "/etc/passwd",
    "\windows\system32",
    "C:/Windows/win.ini",
    "c:relative",
    "//server/share/file",
    "../secret.txt",
    "a/../../secret.txt",
    "a/..",
    "..",
    ".",
    "./a.csv",
    "a/./b.csv",
    "a//b.csv",
    "a/b/",
    "a\b.csv",
    "%2e%2e/secret",
    "a/%2E%2E/b",
    " a.csv",
    "a.csv ",
    "a\x00.csv",
    "a\nb.csv",
    "",
    ".. /x",
    "... /x",
    "a/b.",
    "a/b ./c",
    "CON",
    "nul.txt",
    "dir/COM1.csv",
    "lpt9",
    "a:b.csv",
    "a<b>.csv",
    'a"b.csv',
    "a|b.csv",
    "a?.csv",
    "a*.csv",
]
SAFE_PATHS = [
    "sidecars/metrics.csv",
    "a.csv",
    "console.txt",
    "com10.csv",
    "a.b.c.json",
    "dir/sub dir/file-1.v2.json",
    "ü/ä.txt",
]


@pytest.mark.parametrize("path", UNSAFE_PATHS)
def test_unsafe_paths_are_rejected_everywhere(path: str) -> None:
    assert sidecar_path_error(path) is not None
    with pytest.raises(ValidationError):
        SidecarMetadata.model_validate(_sidecar(path=path))
    ok, err = validate_manifest_structure(_manifest([_sidecar(path=path)]))
    assert ok is False and err and "path" in err
    with pytest.raises(ValueError):
        validate_manifest_semantic(_manifest([_sidecar(path=path)]))


@pytest.mark.parametrize("path", SAFE_PATHS)
def test_safe_relative_paths_are_accepted(path: str) -> None:
    assert sidecar_path_error(path) is None
    assert SidecarMetadata.model_validate(_sidecar(path=path)).path == path
    assert validate_manifest_structure(_manifest([_sidecar(path=path)])) == (True, None)
    validate_manifest_semantic(_manifest([_sidecar(path=path)]))


@pytest.mark.parametrize(
    "digest",
    [
        "",
        "a" * 63,
        "a" * 65,
        "g" * 64,
        "a" * 63 + "\n",
        " " + "a" * 63,
        "0x" + "a" * 62,
    ],
)
def test_sha256_must_be_exactly_64_hex_characters(digest: str) -> None:
    with pytest.raises(ValidationError):
        SidecarMetadata.model_validate(_sidecar(sha256=digest))
    ok, err = validate_manifest_structure(_manifest([_sidecar(sha256=digest)]))
    assert ok is False and err and "sha256" in err


def test_sha256_accepts_upper_and_lower_case_hex() -> None:
    for digest in (DIGEST, DIGEST.upper(), "A" * 64):
        assert SidecarMetadata.model_validate(_sidecar(sha256=digest)).sha256 == digest


@pytest.mark.parametrize("field", ["name", "kind", "path", "sha256"])
def test_missing_sidecar_field_is_rejected(field: str) -> None:
    sc = _sidecar()
    del sc[field]
    ok, err = validate_manifest_structure(_manifest([sc]))
    assert ok is False and err and field in err
    with pytest.raises(ValidationError):
        SidecarMetadata.model_validate(sc)


@pytest.mark.parametrize("field", ["name", "kind", "path", "sha256"])
@pytest.mark.parametrize("bad", [None, 7, ["x"], {"a": 1}, True])
def test_non_string_sidecar_fields_are_rejected(field: str, bad: Any) -> None:
    ok, err = validate_manifest_structure(_manifest([_sidecar(**{field: bad})]))
    assert ok is False and err and "must be a string" in err
    with pytest.raises(ValidationError):
        SidecarMetadata.model_validate(_sidecar(**{field: bad}))


def test_structural_tier_rejects_bad_shapes_and_lengths() -> None:
    assert validate_manifest_structure(_manifest("nope"))[0] is False
    assert validate_manifest_structure(_manifest(["not-an-object"]))[0] is False
    assert validate_manifest_structure(_manifest([_sidecar(extra=1)]))[0] is False
    assert validate_manifest_structure(_manifest([_sidecar(name="")]))[0] is False
    assert (
        validate_manifest_structure(_manifest([_sidecar(name="n" * 121)]))[0] is False
    )
    assert validate_manifest_structure(_manifest([_sidecar(kind="k" * 65)]))[0] is False
    assert (
        validate_manifest_structure(_manifest([_sidecar(path="p" * 257)]))[0] is False
    )


def test_duplicate_paths_are_rejected_case_insensitively() -> None:
    ok, err = validate_manifest_structure(
        _manifest([_sidecar(), _sidecar(name="other", path="SIDECARS/Metrics.csv")])
    )
    assert ok is False and err and "duplicates" in err


def test_unknown_kind_still_gets_the_structural_sidecar_checks() -> None:
    doc = _manifest([_sidecar(path="../x")])
    doc["kind"] = "ai_copilot_proposal_v1"
    assert validate_manifest_structure(doc)[0] is False


def test_valid_existing_manifests_are_preserved() -> None:
    plain = _manifest([])
    assert validate_manifest_structure(plain) == (True, None)
    assert validate_manifest_semantic(plain).sidecars == []
    pre_w7 = {k: v for k, v in plain.items() if k not in ("kind", "sidecars")}
    assert validate_manifest_semantic(pre_w7).sidecars == []
    plain["sidecars"] = None
    assert validate_manifest_semantic(plain).sidecars == []
    assert plain["format"] == MANIFEST_FORMAT and plain["version"] == MANIFEST_VERSION


def test_package_checksums_keys_and_values_are_validated() -> None:
    base = _manifest([])
    good = {**base, "packageChecksums": {"sidecars/metrics.csv": DIGEST}}
    assert ExperimentManifest.model_validate(good).packageChecksums
    for bad in (
        {"../x": DIGEST},
        {"/abs": DIGEST},
        {"ok.csv": "short"},
        {"ok.csv": "z" * 64},
    ):
        with pytest.raises(ValidationError):
            ExperimentManifest.model_validate({**base, "packageChecksums": bad})
