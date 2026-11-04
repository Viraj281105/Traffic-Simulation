"""Grounded-summary checker: every number in a generated summary must trace to the real numbers.

Used by the eval harness (W35) and the report generator (W37, F8: "the summary contains no number that
is not in the computed results"). Unlike ``interpretation.grounding_check`` (a boolean guard used at
request time) this returns a structured report saying, for each number in the text, which data path it
traces to or that it traces to nothing, so a failing build explains itself.

A number in the text is *grounded* when some number in the data matches it under one of these rules:

* exact equality;
* display rounding (default): the text rounds the data value to the decimals the text shows
  (``12.3`` traces to ``12.34``; ``12.35`` does not trace to ``12.34``); a whole number is
  rounded only from 10 up, so ``1`` never traces to ``0.75``;
* percentage: the text ``45%`` (or ``45``) traces to a proportion ``0.45``;
* sign: ``3.2`` traces to ``-3.2`` ("lower by 3.2 s").

Numbers glued to letters (``p95``, ``A2``, ``v3``) are identifiers, not measurements, and are ignored.
``allowed_numbers`` lists literals that need no source (for example the ``95`` of "95% interval").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

_TOKEN = re.compile(r"(?<![A-Za-z0-9_.])-?\d[\d,]*(?:\.\d+)?%?(?![A-Za-z0-9_])")


@dataclass(frozen=True)
class NumberFinding:
    token: str
    value: float
    start: int
    source: Optional[str]  # data path it traces to; None when ungrounded


@dataclass
class GroundingReport:
    ok: bool
    ungrounded: List[NumberFinding] = field(default_factory=list)
    grounded: List[NumberFinding] = field(default_factory=list)

    @property
    def ungrounded_tokens(self) -> List[str]:
        return [f.token for f in self.ungrounded]


def _to_decimal(token: str) -> Optional[Decimal]:
    cleaned = token.rstrip("%").replace(",", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def flatten_numbers(data: Any, path: str = "$") -> Iterator[Tuple[str, Decimal]]:
    """Yield ``(path, number)`` for every numeric leaf (booleans excluded) of a nested structure.
    Numbers inside strings of the data (``"n=240"``) count as data too."""
    if isinstance(data, bool) or data is None:
        return
    if isinstance(data, float):
        if data == data and data not in (float("inf"), float("-inf")):
            yield path, Decimal(repr(data))
    elif isinstance(data, int):
        yield path, Decimal(data)
    elif isinstance(data, dict):
        for key, value in data.items():
            yield from flatten_numbers(value, f"{path}.{key}")
    elif isinstance(data, (list, tuple)):
        for i, value in enumerate(data):
            yield from flatten_numbers(value, f"{path}[{i}]")
    elif isinstance(data, str):
        for match in _TOKEN.finditer(data):
            dec = _to_decimal(match.group(0))
            if dec is not None:
                yield path, dec


def _decimals(token: str) -> int:
    body = token.rstrip("%").replace(",", "")
    return len(body.split(".")[1]) if "." in body else 0


def _round(value: Decimal, places: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _matches(text_value: Decimal, token: str, data: Decimal, rounding: bool) -> bool:
    places = _decimals(token)
    candidates = [abs(data)]
    if abs(data) <= 1:
        candidates.append(abs(data) * 100)  # a proportion written as a percentage
    probe = abs(text_value)
    for cand in candidates:
        if cand == probe:
            return True
        # Whole-number rounding is allowed only from 10 up: 0.75 must not 'trace' a stray 1.
        if rounding and (places > 0 or probe >= 10) and _round(cand, places) == probe:
            return True
    return False


def check_grounded_summary(
    text: str,
    numbers: Any,
    *,
    allowed_numbers: Iterable[float] = (),
    rounding: bool = True,
) -> GroundingReport:
    """Flag every number in ``text`` that does not trace to ``numbers`` (any nested dict/list)."""
    source = list(flatten_numbers(numbers))
    allowed = {Decimal(repr(float(a))) for a in allowed_numbers}
    report = GroundingReport(ok=True)
    for match in _TOKEN.finditer(text):
        token = match.group(0)
        value = _to_decimal(token)
        if value is None:
            continue
        origin: Optional[str] = None
        if any(abs(value) == a for a in allowed):
            origin = "allowed"
        else:
            for path, data in source:
                if _matches(value, token, data, rounding):
                    origin = path
                    break
        finding = NumberFinding(token, float(value), match.start(), origin)
        (report.grounded if origin else report.ungrounded).append(finding)
    report.ok = not report.ungrounded
    return report


def assert_grounded(text: str, numbers: Dict[str, Any], **kwargs: Any) -> None:
    """Raise ``AssertionError`` naming the ungrounded numbers; for report generation and tests."""
    report = check_grounded_summary(text, numbers, **kwargs)
    if not report.ok:
        raise AssertionError(
            "summary contains numbers not in the computed results: "
            + ", ".join(report.ungrounded_tokens)
        )
