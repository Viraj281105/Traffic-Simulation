"""In-memory strategy registry (``urbanflow-strategy`` v1) -- V3.0 W3 (ADR-014).

Provides authoritative registration, lookup, alias resolution, and self-checking
for strategy descriptors.

Security constraint (ADR-014 §3):
- Only pre-defined, typed `StrategyDescriptor` instances can be registered.
- Dynamic client payloads (dicts, JSON text, unvalidated code) are rejected.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from src.strategies.builtins import BUILTIN_STRATEGIES
from src.strategies.models import StrategyDescriptor

logger = logging.getLogger(__name__)

LEGACY_STRATEGY_ALIASES: Dict[str, str] = {
    "fixed_time": "fixed_time_signal",
    "adaptive": "adaptive_signal",
    "roundabout": "conventional_roundabout",
    "signalised_roundabout": "metered_entry_roundabout",
}


class StrategyRegistry:
    """Registry managing available traffic control strategy descriptors."""

    def __init__(self, load_builtins: bool = True) -> None:
        self._strategies: Dict[str, StrategyDescriptor] = {}
        self._aliases: Dict[str, str] = dict(LEGACY_STRATEGY_ALIASES)
        if load_builtins:
            self._register_builtins()

    def _register_builtins(self) -> None:
        """Register the standard built-in strategy descriptors."""
        for builtin in BUILTIN_STRATEGIES:
            self.register(builtin)
        self.self_check()

    def register(self, descriptor: StrategyDescriptor) -> None:
        """Register a valid strategy descriptor.

        Security: Only concrete StrategyDescriptor instances are accepted.
        Arbitrary dicts, client request bodies, or unvalidated objects are rejected.
        """
        if not isinstance(descriptor, StrategyDescriptor):
            raise TypeError(
                f"Registration rejected: expected StrategyDescriptor instance, got {type(descriptor).__name__}."
            )

        if descriptor.id in self._strategies:
            raise ValueError(
                f"Strategy '{descriptor.id}' is already registered. Re-registration is forbidden."
            )

        # Ensure descriptor is internally consistent
        descriptor.validate_self()

        # Ensure fingerprint is populated and matches
        if descriptor.fingerprint is None:
            descriptor = descriptor.with_computed_fingerprint()
        else:
            expected_fp = descriptor.compute_fingerprint()
            if descriptor.fingerprint != expected_fp:
                raise ValueError(
                    f"Strategy '{descriptor.id}' fingerprint mismatch: "
                    f"'{descriptor.fingerprint}' != expected '{expected_fp}'."
                )

        self._strategies[descriptor.id] = descriptor
        logger.debug(
            "Registered strategy descriptor: %s (%s)", descriptor.id, descriptor.name
        )

    def register_alias(self, alias: str, canonical_id: str) -> None:
        """Map a legacy or shorthand alias to a canonical strategy id."""
        if not alias or not isinstance(alias, str):
            raise ValueError("Alias must be a non-empty string.")
        if canonical_id not in self._strategies and canonical_id not in self._aliases:
            raise KeyError(
                f"Cannot alias '{alias}' to unknown strategy '{canonical_id}'."
            )

        # Detect cyclic alias chains immediately
        current = canonical_id
        visited = {alias}
        while current in self._aliases:
            if current in visited:
                raise ValueError(
                    f"Cyclic alias detected for strategy '{alias}' -> '{canonical_id}'."
                )
            visited.add(current)
            current = self._aliases[current]

        self._aliases[alias] = canonical_id

    def resolve_id(self, alias_or_id: str) -> str:
        """Resolve a strategy identifier or alias to its canonical strategy ID."""
        if not isinstance(alias_or_id, str):
            raise TypeError(
                f"Strategy ID must be a string, got {type(alias_or_id).__name__}."
            )

        current = alias_or_id
        visited = set()
        while current in self._aliases:
            if current in visited:
                raise ValueError(f"Cyclic alias detected for strategy '{alias_or_id}'.")
            visited.add(current)
            current = self._aliases[current]

        if current not in self._strategies:
            available = sorted(
                list(self._strategies.keys()) + list(self._aliases.keys())
            )
            raise KeyError(
                f"Unknown strategy '{alias_or_id}'. Registered options: {available}."
            )

        return current

    def get(self, alias_or_id: str) -> StrategyDescriptor:
        """Retrieve a strategy descriptor by canonical ID or alias."""
        canonical_id = self.resolve_id(alias_or_id)
        return self._strategies[canonical_id]

    def has(self, alias_or_id: str) -> bool:
        """Check if a strategy canonical ID or alias exists in the registry."""
        try:
            self.resolve_id(alias_or_id)
            return True
        except (KeyError, TypeError, ValueError):
            return False

    def list_all(self) -> List[StrategyDescriptor]:
        """Return all registered strategy descriptors sorted by ID."""
        return [self._strategies[k] for k in sorted(self._strategies.keys())]

    def list_ids(self) -> List[str]:
        """Return all canonical registered strategy IDs sorted alphabetically."""
        return sorted(self._strategies.keys())

    def list_aliases(self) -> Dict[str, str]:
        """Return a copy of all active strategy aliases."""
        return dict(self._aliases)

    def self_check(self) -> None:
        """Validate integrity and internal consistency of every registered descriptor."""
        for strategy_id, desc in self._strategies.items():
            try:
                desc.validate_self()
            except Exception as exc:
                raise RuntimeError(
                    f"Registry self-check failed for strategy '{strategy_id}': {exc}"
                ) from exc


_GLOBAL_REGISTRY: Optional[StrategyRegistry] = None


def get_strategy_registry() -> StrategyRegistry:
    """Return the global singleton strategy registry instance."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = StrategyRegistry(load_builtins=True)
    return _GLOBAL_REGISTRY


def reset_strategy_registry() -> StrategyRegistry:
    """Reset and reinitialize the global singleton registry (primarily for tests)."""
    global _GLOBAL_REGISTRY
    _GLOBAL_REGISTRY = StrategyRegistry(load_builtins=True)
    return _GLOBAL_REGISTRY
