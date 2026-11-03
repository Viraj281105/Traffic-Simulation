"""The run manifest: what a saved run records so it can be re-run and checked.

A manifest is stored inside the run's ``provenance`` (schemaVersion 2, see
``src/core/provenance.py``); it adds no table and no migration, and older rows
(provenance v1 or none) read as before. It never holds a secret or a user
identifier: it names the seed, a hash of the configuration, the code version
and the interpreter, and nothing else about who ran it.

``config_hash`` is the full 64-hex SHA-256 of the configuration's canonical
JSON (sorted keys, compact separators). The only key left out is
``simulation.randomSeed``: the seed is recorded in its own field, so two runs
of one configuration under different seeds share a ``configHash`` and differ
in ``seed``. Everything else, including timing and demand, is part of the hash.

``gitDirty`` is ``"unknown"`` on purpose. Git state is read from ``.git``
without a subprocess (``provenance.py``), and whether the working tree has
uncommitted edits cannot be told reliably that way. A false ``False`` would
let a manifest claim a commit that did not produce the result, so it is not
claimed.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

MANIFEST_FORMAT = "urbanflow-run-manifest"
MANIFEST_VERSION = 1

# The one place the project version is read from (src/main.py uses it too).
ENGINE_VERSION = "1.0.0"

UNKNOWN = "unknown"

# Dotted paths removed before hashing. Keep this list short and explained:
# anything not listed here changes the hash.
NON_SEMANTIC_KEYS = ("simulation.randomSeed",)


def _without(config: Dict[str, Any], dotted: str) -> None:
    *parents, leaf = dotted.split(".")
    node: Any = config
    for part in parents:
        node = node.get(part) if isinstance(node, dict) else None
    if isinstance(node, dict):
        node.pop(leaf, None)


def config_hash(config: Dict[str, Any]) -> str:
    """Full SHA-256 (64 hex) of the configuration, minus ``NON_SEMANTIC_KEYS``."""
    body = copy.deepcopy(config)
    for dotted in NON_SEMANTIC_KEYS:
        _without(body, dotted)
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode()).hexdigest()


def build_run_manifest(
    *,
    config: Dict[str, Any],
    seed: Optional[int],
    run_mode: str,
    git_commit: str,
    python_version: str,
    timing: Dict[str, Any],
    scenario_fingerprint: Optional[str] = None,
    base_seed: Optional[int] = None,
    seed_scheme: Optional[str] = None,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    manifest: Dict[str, Any] = {
        "format": MANIFEST_FORMAT,
        "version": MANIFEST_VERSION,
        "seed": seed,
        "configHash": config_hash(config),
        "gitCommit": git_commit,
        "gitDirty": UNKNOWN,
        "pythonVersion": python_version,
        "engineVersion": ENGINE_VERSION,
        "runMode": run_mode,
        "timing": dict(timing),
        "createdAt": created_at
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if scenario_fingerprint is not None:
        manifest["scenarioFingerprint"] = scenario_fingerprint
    if base_seed is not None:
        manifest["baseSeed"] = base_seed
        manifest["seedScheme"] = seed_scheme
    return manifest


def verify_manifest(
    manifest: Optional[Dict[str, Any]],
    config: Optional[Dict[str, Any]],
    *,
    current_commit: str,
    current_python: str,
) -> Dict[str, Any]:
    """Compare a stored manifest with the stored config and this process.

    Answers *why* a re-run could differ, by cause: the configuration no longer
    matches its recorded hash, the code is at another commit, or the
    interpreter differs. A comparison that cannot be made is ``None``, never
    ``True``.
    """
    if not manifest:
        return {"recorded": False, "reasons": [], "configHashMatches": None}

    recorded_hash = manifest.get("configHash")
    config_matches: Optional[bool] = (
        config_hash(config) == recorded_hash if config and recorded_hash else None
    )
    recorded_commit = manifest.get("gitCommit")
    commit_matches: Optional[bool] = (
        None
        if UNKNOWN in (recorded_commit, current_commit) or not recorded_commit
        else recorded_commit == current_commit
    )
    recorded_python = manifest.get("pythonVersion")
    python_matches: Optional[bool] = (
        None
        if UNKNOWN in (recorded_python, current_python) or not recorded_python
        else recorded_python == current_python
    )

    reasons: List[str] = []
    if config_matches is False:
        reasons.append("configuration differs from the one recorded")
    if commit_matches is False:
        reasons.append("code is at a different commit than the recorded run")
    if python_matches is False:
        reasons.append("Python version differs from the recorded run")
    return {
        "recorded": True,
        "configHashMatches": config_matches,
        "gitCommitMatches": commit_matches,
        "pythonVersionMatches": python_matches,
        "reasons": reasons,
    }


def build_study_manifest(
    *,
    config: Dict[str, Any],
    run_mode: str,
    base_seed: int,
    seed_scheme: str,
    duration: float,
    time_step: Optional[float] = None,
) -> Dict[str, Any]:
    """The manifest of a multi-seed study (``run_mode`` ``"multi-seed"`` or
    ``"monte-carlo"``). ``seed`` is None: each repetition's seed is derived
    from ``baseSeed`` under ``seedScheme``, and listed in the study result."""
    from src.core.provenance import GIT_COMMIT_HASH, PYTHON_VERSION

    manifest = build_run_manifest(
        config=config,
        seed=None,
        run_mode=run_mode,
        git_commit=GIT_COMMIT_HASH,
        python_version=PYTHON_VERSION,
        timing={"timeStep": time_step, "duration": duration, "warmupTime": None},
        base_seed=base_seed,
        seed_scheme=seed_scheme,
    )
    # A study result must repeat exactly from its baseSeed, so it carries no
    # wall-clock time (a saved run's own row has its createdAt).
    del manifest["createdAt"]
    return manifest
