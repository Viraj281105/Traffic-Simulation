"""Small numeric helpers shared by the views."""

from __future__ import annotations

import math
from typing import Any, List, Optional, Sequence


def finite(value: Any) -> Optional[float]:
    """The value as a float when it is a finite real number (not a bool), else None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def finite_list(values: Any) -> Optional[List[float]]:
    """Every item as a finite float, or None if ``values`` is not a list of finite numbers."""
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return None
    out: List[float] = []
    for v in values:
        f = finite(v)
        if f is None:
            return None
        out.append(f)
    return out
