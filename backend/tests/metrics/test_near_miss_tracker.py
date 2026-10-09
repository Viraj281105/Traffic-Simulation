"""Tests for NearMissTracker (near-miss deduplication) in
src/metrics/definitions/safety_conflicts.py.

These tests verify the core deduplication property: a sustained conflict
between the same pair of vehicles must produce exactly one near-miss event
per cooldown window, not one per tick.
"""

from src.metrics.definitions.safety_conflicts import NearMissTracker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _event(va: str = "va", vb: str = "vb", ttc: float = 1.0):
    return (va, vb, ttc)


# ---------------------------------------------------------------------------
# Basic deduplication
# ---------------------------------------------------------------------------


def test_first_event_for_pair_is_always_emitted() -> None:
    """The very first sub-threshold TTC event for a pair must be counted."""
    tracker = NearMissTracker(cooldown_window=5.0)
    count = tracker.update(30.0, [_event()])
    assert count == 1


def test_second_event_within_cooldown_is_suppressed() -> None:
    """A second event 0.5 s after the first (< 5 s cooldown) is suppressed."""
    tracker = NearMissTracker(cooldown_window=5.0)
    tracker.update(30.0, [_event()])
    count = tracker.update(30.5, [_event()])
    assert count == 0


def test_sustained_tailgating_30_ticks_yields_one_event() -> None:
    """Tailgating for 30 consecutive ticks (0.1 s each) = 1 near-miss event."""
    tracker = NearMissTracker(cooldown_window=5.0)
    total = 0
    for i in range(30):
        total += tracker.update(30.0 + i * 0.1, [_event()])
    assert total == 1


def test_event_after_cooldown_window_is_emitted() -> None:
    """A second event that occurs >= cooldown_window seconds later IS counted."""
    tracker = NearMissTracker(cooldown_window=5.0)
    tracker.update(30.0, [_event()])
    count = tracker.update(35.0, [_event()])
    assert count == 1


def test_event_just_before_cooldown_is_suppressed() -> None:
    """An event at t = last + cooldown - epsilon is still suppressed."""
    tracker = NearMissTracker(cooldown_window=5.0)
    tracker.update(30.0, [_event()])
    count = tracker.update(34.99, [_event()])
    assert count == 0


def test_two_distinct_events_10s_apart_yield_two_events() -> None:
    """Two events for the same pair, separated by > cooldown, count as 2."""
    tracker = NearMissTracker(cooldown_window=5.0)
    c1 = tracker.update(30.0, [_event()])
    c2 = tracker.update(40.5, [_event()])
    assert c1 == 1
    assert c2 == 1


def test_pair_order_does_not_matter() -> None:
    """(va, vb) and (vb, va) are the same pair -- second is suppressed."""
    tracker = NearMissTracker(cooldown_window=5.0)
    tracker.update(30.0, [("va", "vb", 1.0)])
    count = tracker.update(30.5, [("vb", "va", 1.2)])
    assert count == 0


def test_different_pairs_are_independent() -> None:
    """Pair (va,vb) cooldown does not affect pair (va,vc)."""
    tracker = NearMissTracker(cooldown_window=5.0)
    c1 = tracker.update(30.0, [("va", "vb", 1.0)])
    c2 = tracker.update(30.1, [("va", "vc", 0.8)])
    assert c1 == 1
    assert c2 == 1


def test_multiple_new_pairs_in_one_tick() -> None:
    """Three new pairs with no history each emit one event = 3 total."""
    tracker = NearMissTracker(cooldown_window=5.0)
    events = [("v1", "v2", 1.0), ("v3", "v4", 0.5), ("v5", "v6", 1.3)]
    count = tracker.update(30.0, events)
    assert count == 3


def test_reset_clears_pair_history() -> None:
    """After reset(), the same pair can fire again immediately."""
    tracker = NearMissTracker(cooldown_window=5.0)
    tracker.update(30.0, [_event()])
    assert tracker.update(30.5, [_event()]) == 0
    tracker.reset()
    assert tracker.update(30.5, [_event()]) == 1


def test_empty_events_list_yields_zero() -> None:
    """No events passed -> no events emitted."""
    tracker = NearMissTracker(cooldown_window=5.0)
    assert tracker.update(30.0, []) == 0


def test_custom_short_cooldown() -> None:
    """A 1.0 s cooldown allows a second event at t = last + 1.0."""
    tracker = NearMissTracker(cooldown_window=1.0)
    tracker.update(30.0, [_event()])
    assert tracker.update(30.9, [_event()]) == 0
    assert tracker.update(31.0, [_event()]) == 1
