"""The Research lab's teaching examples classify under the real comparison rule.

The frontend teaches the paired-difference reading with made-up numbers
(frontend/src/components/research/evidence.ts: EXAMPLE_TWO and EXAMPLE_THREE)
and reimplements the rule to draw them. These tests run the same numbers
through the backend's `_paired_delay`, so the pictures on the page can never
show a reading, mean gap or interval the implementation would not produce.
Keep the arrays here identical to evidence.ts.
"""

from typing import List

import pytest

from src.study.control_comparison import _paired_delay
from src.study.validation import DEFAULT_CONFIDENCE_LEVEL

EXAMPLE_TWO_A: List[float] = [34, 41, 29, 38, 36, 44, 31, 39, 35, 40]
EXAMPLE_TWO_B: List[float] = [30, 33, 31, 31, 32, 35, 28, 34, 33, 34]

FIXED_TIME: List[float] = [38, 45, 33, 41, 40]
ADAPTIVE: List[float] = [31, 37, 30, 34, 33]
ROUNDABOUT: List[float] = [32, 30, 36, 33, 35]


def test_page_uses_the_implemented_confidence_level() -> None:
    assert DEFAULT_CONFIDENCE_LEVEL == 0.95


@pytest.mark.parametrize(
    "runs, mean_gap, low, high, reading",
    [
        (3, 3.33, -9.17, 15.84, "inconclusive"),
        (10, 4.6, 2.31, 6.89, "higher"),
    ],
)
def test_two_control_example(
    runs: int, mean_gap: float, low: float, high: float, reading: str
) -> None:
    result = _paired_delay(
        EXAMPLE_TWO_A[:runs], EXAMPLE_TWO_B[:runs], DEFAULT_CONFIDENCE_LEVEL
    )
    assert result == {
        "meanDifference": mean_gap,
        "ciLow": low,
        "ciHigh": high,
        "reading": reading,
    }


@pytest.mark.parametrize(
    "first, second, mean_gap, low, high, reading",
    [
        (ADAPTIVE, FIXED_TIME, -6.4, -8.82, -3.98, "lower"),
        (ADAPTIVE, ROUNDABOUT, -0.2, -6.12, 5.72, "tie"),
        (FIXED_TIME, ROUNDABOUT, 6.2, -1.82, 14.22, "inconclusive"),
    ],
)
def test_three_control_example_shows_every_reading(
    first: List[float],
    second: List[float],
    mean_gap: float,
    low: float,
    high: float,
    reading: str,
) -> None:
    result = _paired_delay(first, second, DEFAULT_CONFIDENCE_LEVEL)
    assert result == {
        "meanDifference": mean_gap,
        "ciLow": low,
        "ciHigh": high,
        "reading": reading,
    }
