"""Alternatives: what is being compared, and how each is derived.

An alternative is a control strategy plus a merge-patch over the study's
scenario. Where alternatives come from is behind ``AlternativeSource`` so a
later adapter (V1.7 scenario sets) can supply them without changing the
runner. Nothing here imports V1.6/V1.7.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Sequence

from src.core.scenario import (
    STRATEGIES,
    STRATEGY_TITLES,
    ScenarioDocument,
    parse_scenario,
    scenario_fingerprint,
    validate_scenario,
)
from src.planning.models import AlternativeSpec

# Seeds, duration and warm-up must be common to all alternatives, otherwise
# the per-seed pairing the comparison relies on is meaningless.
FORBIDDEN_PATCH_ROOTS = ("simulation", "format", "version")
# Changing these makes alternatives face different traffic: allowed, but flagged.
DEMAND_PATHS = ("vehiclesPerHour", "turning", "vehicleMix")


class AlternativeSource(Protocol):
    def list_alternatives(self) -> List[AlternativeSpec]: ...


class InlineAlternatives:
    """Alternatives given in the request."""

    def __init__(self, specs: Sequence[AlternativeSpec]):
        self._specs = list(specs)

    def list_alternatives(self) -> List[AlternativeSpec]:
        return list(self._specs)


class DefaultStrategyAlternatives:
    """No patch, one alternative per built-in strategy; first is the baseline."""

    def list_alternatives(self) -> List[AlternativeSpec]:
        return [
            AlternativeSpec(id=s, label=STRATEGY_TITLES[s], strategy=s)
            for s in STRATEGIES
        ]


def merge_patch(target: Any, patch: Any) -> Any:
    """RFC 7386 JSON merge-patch (``null`` deletes a key). Pure."""
    if not isinstance(patch, dict):
        return copy.deepcopy(patch)
    result: Dict[str, Any] = dict(target) if isinstance(target, dict) else {}
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = merge_patch(result.get(key), value)
    return result


def changed_paths(a: Any, b: Any, prefix: str = "") -> List[str]:
    """Dotted paths whose value differs between two JSON documents."""
    if isinstance(a, dict) and isinstance(b, dict):
        out: List[str] = []
        for key in sorted(set(a) | set(b)):
            out.extend(
                changed_paths(
                    a.get(key), b.get(key), f"{prefix}.{key}" if prefix else key
                )
            )
        return out
    return [] if a == b else [prefix]


@dataclass
class ResolvedAlternative:
    spec: AlternativeSpec
    document: Optional[ScenarioDocument]
    fingerprint: Optional[str]
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    changes: List[str] = field(default_factory=list)  # paths differing from base

    @property
    def id(self) -> str:
        return self.spec.id

    @property
    def label(self) -> str:
        return self.spec.label or STRATEGY_TITLES.get(self.spec.strategy, self.spec.id)


def resolve_alternative(
    base: ScenarioDocument, spec: AlternativeSpec
) -> ResolvedAlternative:
    """Apply the patch to a copy of ``base`` and validate the result."""
    errors: List[str] = []
    warnings: List[str] = []
    if spec.strategy not in STRATEGIES:
        errors.append(
            f"{spec.id}: unknown strategy {spec.strategy!r}; expected one of "
            f"{list(STRATEGIES)}"
        )
    bad = [k for k in spec.patch if k in FORBIDDEN_PATCH_ROOTS]
    if bad:
        errors.append(
            f"{spec.id}: patch may not change {bad}; seeds, duration and warm-up "
            "are shared by every alternative"
        )
    if errors:
        return ResolvedAlternative(spec, None, None, errors)

    base_body = base.model_dump()
    patched = merge_patch(base_body, spec.patch)
    # junction.type is left alone: the strategy is passed explicitly when
    # compiling, and an unpatched alternative then shares the base fingerprint.
    document, parse_errors = parse_scenario(patched)
    if document is None:
        return ResolvedAlternative(
            spec, None, None, [f"{spec.id}: {e}" for e in parse_errors]
        )
    check = validate_scenario(document.model_dump(), [spec.strategy])
    if not check["valid"]:
        errors.extend(f"{spec.id}: {e}" for e in check["errors"])
    warnings.extend(f"{spec.id}: {w}" for w in check.get("warnings", []))

    changes = changed_paths(
        {
            k: v
            for k, v in base_body.items()
            if k not in ("junction", "name", "description", "preset")
        },
        {
            k: v
            for k, v in document.model_dump().items()
            if k not in ("junction", "name", "description", "preset")
        },
    )
    if any(
        any(seg in c.split(".") or c.endswith(seg) for seg in DEMAND_PATHS)
        for c in changes
    ):
        warnings.append(
            f"{spec.id}: this alternative changes demand ({', '.join(c for c in changes if any(d in c for d in DEMAND_PATHS))}); "
            "it is not compared under the same traffic as the baseline"
        )
    return ResolvedAlternative(
        spec, document, scenario_fingerprint(document), errors, warnings, changes
    )


def resolve_all(
    base: ScenarioDocument, source: AlternativeSource
) -> List[ResolvedAlternative]:
    return [resolve_alternative(base, spec) for spec in source.list_alternatives()]
