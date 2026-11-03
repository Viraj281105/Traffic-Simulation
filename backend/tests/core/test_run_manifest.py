"""The run manifest: hash semantics, provenance v2, privacy and verification."""

from __future__ import annotations

import json
from typing import Any, Dict

from src.core.provenance import (
    GIT_COMMIT_HASH,
    PYTHON_VERSION,
    build_run_provenance,
)
from src.core.run_manifest import (
    ENGINE_VERSION,
    MANIFEST_FORMAT,
    build_run_manifest,
    config_hash,
    verify_manifest,
)

CONFIG: Dict[str, Any] = {
    "simulation": {"randomSeed": 7, "duration": 60.0, "timeStep": 0.1},
    "traffic": {"arrivalRate": 0.4},
}


def _manifest(**over: Any) -> Dict[str, Any]:
    args: Dict[str, Any] = dict(
        config=CONFIG,
        seed=7,
        run_mode="single",
        git_commit="a" * 40,
        python_version="3.11.1",
        timing={"timeStep": 0.1, "duration": 60.0, "warmupTime": 0.0},
    )
    args.update(over)
    return build_run_manifest(**args)


def test_config_hash_is_full_sha256_and_stable() -> None:
    h = config_hash(CONFIG)
    assert len(h) == 64 and int(h, 16) >= 0
    assert h == config_hash(json.loads(json.dumps(CONFIG)))


def test_config_hash_ignores_key_order_and_the_seed_only() -> None:
    reordered = {
        "traffic": {"arrivalRate": 0.4},
        "simulation": dict(CONFIG["simulation"]),
    }
    assert config_hash(reordered) == config_hash(CONFIG)
    other_seed = json.loads(json.dumps(CONFIG))
    other_seed["simulation"]["randomSeed"] = 99
    assert config_hash(other_seed) == config_hash(CONFIG)
    changed = json.loads(json.dumps(CONFIG))
    changed["traffic"]["arrivalRate"] = 0.5
    assert config_hash(changed) != config_hash(CONFIG)


def test_config_hash_does_not_mutate_its_input() -> None:
    before = json.dumps(CONFIG, sort_keys=True)
    config_hash(CONFIG)
    assert json.dumps(CONFIG, sort_keys=True) == before


def test_manifest_fields_and_honest_dirty_flag() -> None:
    m = _manifest()
    assert m["format"] == MANIFEST_FORMAT and m["version"] == 1
    assert m["seed"] == 7 and m["configHash"] == config_hash(CONFIG)
    assert m["gitCommit"] == "a" * 40
    assert m["gitDirty"] == "unknown"
    assert m["engineVersion"] == ENGINE_VERSION
    assert "baseSeed" not in m and "scenarioFingerprint" not in m


def test_manifest_records_multi_seed_and_scenario_fields() -> None:
    m = _manifest(base_seed=42, seed_scheme="sha256-v1", scenario_fingerprint="ab12")
    assert (m["baseSeed"], m["seedScheme"], m["scenarioFingerprint"]) == (
        42,
        "sha256-v1",
        "ab12",
    )


def test_manifest_holds_no_secret_or_identifier_keys() -> None:
    text = json.dumps(_manifest()).lower()
    for word in ("user", "email", "token", "password", "secret", "api_key", "cookie"):
        assert word not in text


def test_provenance_without_config_keeps_the_v1_shape() -> None:
    p = build_run_provenance(
        config_source="engine",
        run_mode="single",
        time_step=0.1,
        duration=60.0,
        warmup_time=0.0,
    )
    assert p["schemaVersion"] == 1 and "manifest" not in p


def test_provenance_with_config_is_v2_and_embeds_the_manifest() -> None:
    p = build_run_provenance(
        config_source="engine",
        run_mode="single",
        time_step=0.1,
        duration=60.0,
        warmup_time=0.0,
        config=CONFIG,
        seed=7,
    )
    assert p["schemaVersion"] == 2
    assert p["manifest"]["gitCommit"] == GIT_COMMIT_HASH
    assert p["manifest"]["pythonVersion"] == PYTHON_VERSION
    assert p["manifest"]["timing"] == p["timing"]
    assert p["gitCommitHash"] == GIT_COMMIT_HASH  # v1 fields stay


def test_verify_without_a_manifest_claims_nothing() -> None:
    v = verify_manifest(None, CONFIG, current_commit="x", current_python="y")
    assert v == {"recorded": False, "reasons": [], "configHashMatches": None}


def test_verify_matching_run_has_no_reasons() -> None:
    v = verify_manifest(
        _manifest(), CONFIG, current_commit="a" * 40, current_python="3.11.1"
    )
    assert v["reasons"] == []
    assert (v["configHashMatches"], v["gitCommitMatches"]) == (True, True)
    assert v["pythonVersionMatches"] is True


def test_verify_names_each_cause() -> None:
    changed = json.loads(json.dumps(CONFIG))
    changed["traffic"]["arrivalRate"] = 0.9
    v = verify_manifest(
        _manifest(), changed, current_commit="b" * 40, current_python="3.14.0"
    )
    assert len(v["reasons"]) == 3
    assert not any(
        v[k] for k in ("configHashMatches", "gitCommitMatches", "pythonVersionMatches")
    )


def test_verify_unknown_versions_are_not_a_match_or_a_mismatch() -> None:
    v = verify_manifest(
        _manifest(git_commit="unknown"),
        CONFIG,
        current_commit="a" * 40,
        current_python="3.11.1",
    )
    assert v["gitCommitMatches"] is None and v["reasons"] == []


def test_schema_file_accepts_a_manifest_and_a_study_manifest() -> None:
    import re
    from pathlib import Path

    schema = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "shared"
            / "schemas"
            / "run-manifest.schema.json"
        ).read_text(encoding="utf-8")
    )
    required = schema["required"]
    for m in (_manifest(), _manifest(base_seed=1, seed_scheme="sha256-v1")):
        assert all(k in m for k in required)
        assert set(m) <= set(schema["properties"])
        assert re.fullmatch(
            schema["properties"]["configHash"]["pattern"], m["configHash"]
        )


def test_study_results_carry_a_manifest_that_reproduces() -> None:
    from src.study.multiseed import run_multi_seed

    a = run_multi_seed(geometry="signal", num_seeds=2, duration=10.0, base_seed=5)
    b = run_multi_seed(geometry="signal", num_seeds=2, duration=10.0, base_seed=5)
    m = a["manifest"]
    assert m["runMode"] == "multi-seed" and m["baseSeed"] == 5 and m["seed"] is None
    assert m["configHash"] == b["manifest"]["configHash"]
    assert m["seedScheme"] == a["seedScheme"]
