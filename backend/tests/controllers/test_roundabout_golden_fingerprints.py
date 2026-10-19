"""The conventional roundabout reproduces its pre-seam fingerprints.

ADR-014 §7 (sprint plan §1.5, "never cut" in §7): with the default
``AlwaysOpen`` entry gate, the conventional roundabout is bit-identical —
same metric and snapshot fingerprints — to the behaviour recorded before the
seam existed. Pins, harness and the meaning of each pin (exact vs portable)
are in ``roundabout_golden.py``. The fast cases run in the ordinary CI job,
the full corpus in the ``roundabout-golden`` slow shard.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List

import pytest

from src.planning.models import canonical_json
from tests.controllers.roundabout_golden import (
    CORPUS,
    compile_case,
    environment_key,
    fingerprint_run,
    load_fixture,
)

_PINNED: List[Dict[str, Any]] = load_fixture()["cases"]
_RUNS: Dict[str, Dict[str, Any]] = {}

_DO_NOT_RERECORD = (
    "ADR-014 §7: the conventional roundabout must stay bit-identical; do not "
    "re-record the fixture to make this pass."
)


def _run(case: Dict[str, Any]) -> Dict[str, Any]:
    """One simulation per case per session, shared by both pin tests."""
    if case["id"] not in _RUNS:
        _RUNS[case["id"]] = fingerprint_run(case["config"], case["path"])
    return _RUNS[case["id"]]


def _params() -> List[Any]:
    return [
        pytest.param(c, id=c["id"], marks=() if c["fast"] else (pytest.mark.slow,))
        for c in _PINNED
    ]


@pytest.mark.parametrize("case", _params())
def test_conventional_roundabout_matches_its_exact_pin(case: Dict[str, Any]) -> None:
    env = environment_key()
    pinned = case["exact"].get(env)
    if pinned is None:
        pytest.skip(
            f"no exact pin for {env} (pinned: {sorted(case['exact'])}); the "
            "portable pin still runs. Add one with --add-environment from the "
            "recording commit."
        )
    assert _run(case)["exact"] == pinned, (
        f"{case['id']} ({case['path']} path) is not bit-identical to the "
        f"pre-seam roundabout on {env}. {_DO_NOT_RERECORD}"
    )


@pytest.mark.parametrize("case", _params())
def test_conventional_roundabout_matches_its_portable_pin(
    case: Dict[str, Any],
) -> None:
    assert _run(case)["portable"] == case["expected"], (
        f"{case['id']} ({case['path']} path) no longer reproduces the pre-seam "
        f"roundabout to 1 µm / 12 significant digits. {_DO_NOT_RERECORD}"
    )


# The baseline itself, pinned (2026-10-19). Re-recording (--record --force),
# removing a case, hand-editing a pin or adding an environment changes the
# fixture, so it fails here until this block is edited in the same diff —
# which is where a reviewer sees that the baseline moved and asks for the
# ADR-014 §7 reason. The digest is over the parsed fixture (canonical JSON),
# so line endings cannot move it.
BASELINE_COMMIT = "e43bfec"
BASELINE_SOURCE_DIGEST = (
    "693bf5f8f199d0efef1b82257af12775b8fecb446bdb4f412f9d65ac97414ad1"
)
BASELINE_FIXTURE_DIGEST = (
    "274b293d65f9f773495466bacebcce8ddb5c68984cda7760754be3a2135745d8"
)


def test_the_baseline_fixture_is_the_one_recorded_from_e43bfec() -> None:
    fixture = load_fixture()
    assert fixture["recordedFrom"] == BASELINE_COMMIT
    assert fixture["sourceDigest"] == BASELINE_SOURCE_DIGEST
    found = hashlib.sha256(canonical_json(fixture).encode()).hexdigest()
    assert found == BASELINE_FIXTURE_DIGEST, (
        "tests/fixtures/roundabout_golden_fingerprints.json changed. If the "
        "pre-seam baseline was deliberately re-recorded or extended, update "
        "the BASELINE_* constants in this diff and record the reason "
        f"(ADR-014 §7). {_DO_NOT_RERECORD}"
    )


def test_every_corpus_case_is_pinned_and_nothing_else() -> None:
    assert [c["id"] for c in _PINNED] == [c["id"] for c in CORPUS]


def test_every_case_has_at_least_one_exact_pin() -> None:
    assert all(c["exact"] for c in _PINNED)


def test_the_corpus_covers_the_layouts_adr_014_names() -> None:
    """Three- and four-arm, one and two ring lanes, multi-lane and merging
    entries, mixed vehicles, and both controller-building paths."""
    configs = {c["id"]: c["config"] for c in _PINNED}
    arms = {
        len(c["geometry"].get("arms") or ["n", "s", "e", "w"]) for c in configs.values()
    }
    rings = {c["geometry"].get("circulatingLanes", 1) for c in configs.values()}
    widest = {c["roads"]["lanesPerApproach"] for c in configs.values()}
    assert arms == {3, 4}
    assert rings == {1, 2}
    assert widest >= {1, 2, 3}
    assert any("vehicleMix" in c["vehicleGeneration"] for c in configs.values())
    assert {c["path"] for c in _PINNED} == {"direct", "study"}
    assert any(c["fast"] for c in _PINNED) and not all(c["fast"] for c in _PINNED)


@pytest.mark.parametrize(
    "case", [c for c in CORPUS if c["fast"]], ids=lambda c: c["id"]
)
def test_pinned_configs_are_what_the_corpus_compiles_to(case: Dict[str, Any]) -> None:
    """The stored configs are the corpus documents compiled today. The pins
    keep testing their stored config if the compiler changes; this test is
    what notices that it did."""
    pinned = next(c for c in _PINNED if c["id"] == case["id"])
    assert compile_case(case) == pinned["config"]
