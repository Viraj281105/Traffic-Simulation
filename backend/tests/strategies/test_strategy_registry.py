"""Unit tests for StrategyRegistry (ADR-014 §2, §3)."""

import pytest

from src.strategies.builtins import (
    ADAPTIVE_SIGNAL,
    CONVENTIONAL_ROUNDABOUT,
    FIXED_TIME_SIGNAL,
    METERED_ENTRY_ROUNDABOUT,
)
from src.strategies.registry import (
    StrategyRegistry,
    get_strategy_registry,
    reset_strategy_registry,
)


class TestStrategyRegistry:
    def setup_method(self) -> None:
        reset_strategy_registry()

    def test_default_registry_contains_all_builtins(self) -> None:
        """Default registry must contain all 4 built-in strategy descriptors."""
        registry = get_strategy_registry()
        expected_ids = [
            "adaptive_signal",
            "conventional_roundabout",
            "fixed_time_signal",
            "metered_entry_roundabout",
        ]
        assert registry.list_ids() == sorted(expected_ids)
        assert len(registry.list_all()) == 4
        # self_check passes without exception
        registry.self_check()

    def test_lookup_canonical_strategies(self) -> None:
        """Retrieval by canonical ID returns the correct StrategyDescriptor."""
        registry = get_strategy_registry()
        assert registry.get("fixed_time_signal") == FIXED_TIME_SIGNAL
        assert registry.get("adaptive_signal") == ADAPTIVE_SIGNAL
        assert registry.get("conventional_roundabout") == CONVENTIONAL_ROUNDABOUT
        assert registry.get("metered_entry_roundabout") == METERED_ENTRY_ROUNDABOUT

    def test_legacy_alias_resolution(self) -> None:
        """Legacy strategy names must resolve transparently to canonical descriptors."""
        registry = get_strategy_registry()
        assert registry.resolve_id("fixed_time") == "fixed_time_signal"
        assert registry.resolve_id("adaptive") == "adaptive_signal"
        assert registry.resolve_id("roundabout") == "conventional_roundabout"
        assert registry.resolve_id("signalised_roundabout") == "metered_entry_roundabout"

        assert registry.get("fixed_time") == FIXED_TIME_SIGNAL
        assert registry.get("adaptive") == ADAPTIVE_SIGNAL
        assert registry.get("roundabout") == CONVENTIONAL_ROUNDABOUT
        assert registry.get("signalised_roundabout") == METERED_ENTRY_ROUNDABOUT

    def test_has_strategy(self) -> None:
        """has() correctly checks presence of canonical IDs and aliases."""
        registry = get_strategy_registry()
        assert registry.has("fixed_time_signal") is True
        assert registry.has("fixed_time") is True
        assert registry.has("non_existent_strategy") is False
        assert registry.has("") is False

    def test_get_unknown_strategy_raises_key_error(self) -> None:
        """Retrieving an unknown strategy must raise KeyError with available options."""
        registry = get_strategy_registry()
        with pytest.raises(KeyError, match="Unknown strategy 'flying_cars'"):
            registry.get("flying_cars")

    def test_reject_duplicate_registration(self) -> None:
        """Registering an already-registered strategy ID must be rejected."""
        registry = get_strategy_registry()
        with pytest.raises(ValueError, match="already registered"):
            registry.register(FIXED_TIME_SIGNAL)

    def test_security_rejects_untrusted_client_payloads(self) -> None:
        """ADR-014 §3 security constraint: arbitrary dicts or text cannot be registered."""
        registry = get_strategy_registry()

        # Reject dict payload
        raw_dict = {
            "id": "malicious_strategy",
            "name": "Malicious Strategy",
            "geometry": {"intersection_type": "fixed_time_signal"},
        }
        with pytest.raises(TypeError, match="expected StrategyDescriptor instance"):
            registry.register(raw_dict)  # type: ignore[arg-type]

        # Reject arbitrary string
        with pytest.raises(TypeError, match="expected StrategyDescriptor instance"):
            registry.register('{"id": "exploit"}')  # type: ignore[arg-type]

        # Reject None or arbitrary class
        with pytest.raises(TypeError, match="expected StrategyDescriptor instance"):
            registry.register(None)  # type: ignore[arg-type]

    def test_reject_corrupt_fingerprint_registration(self) -> None:
        """Registering a descriptor with a mismatched fingerprint must fail."""
        empty_registry = StrategyRegistry(load_builtins=False)
        corrupted = FIXED_TIME_SIGNAL.model_copy(update={"fingerprint": "badc0ffeedeadbeef"})
        with pytest.raises(ValueError, match="fingerprint mismatch"):
            empty_registry.register(corrupted)

    def test_manual_valid_registration(self) -> None:
        """A valid custom StrategyDescriptor can be registered on a custom registry instance."""
        custom_registry = StrategyRegistry(load_builtins=False)
        assert len(custom_registry.list_all()) == 0

        custom_registry.register(FIXED_TIME_SIGNAL)
        assert custom_registry.has("fixed_time_signal")
        assert len(custom_registry.list_all()) == 1
