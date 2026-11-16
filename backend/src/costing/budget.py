"""Budget check helpers. Pure functions; wiring into the queue is a later step."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BudgetStatus:
    budget: float
    spent: float
    remaining: float
    daily_burn: float
    days_to_exhaustion: Optional[float]  # None when nothing is being spent


@dataclass(frozen=True)
class AdmitDecision:
    allow: bool
    reason: str
    remaining_after: float


def _check(**values: float) -> None:
    for name, value in values.items():
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be a non-negative number")


def budget_status(budget: float, spent: float, elapsed_days: float) -> BudgetStatus:
    """Remaining budget and, from the average daily spend so far, the days until it runs out."""
    _check(budget=budget, spent=spent, elapsed_days=elapsed_days)
    remaining = round(budget - spent, 6)
    burn = spent / elapsed_days if elapsed_days > 0 else 0.0
    days: Optional[float]
    if remaining <= 0:
        days = 0.0
    elif burn > 0:
        days = remaining / burn
    else:
        days = None
    return BudgetStatus(budget, spent, remaining, burn, days)


def should_admit(job_estimate: float, budget: float, spent: float) -> AdmitDecision:
    """Allow a job whose estimated cost fits in what is left (equal to what is left is allowed)."""
    _check(job_estimate=job_estimate, budget=budget, spent=spent)
    remaining = round(budget - spent, 6)
    after = round(remaining - job_estimate, 6)
    if remaining <= 0:
        return AdmitDecision(False, "budget exhausted", after)
    if after < 0:
        return AdmitDecision(
            False,
            f"estimate {job_estimate} exceeds remaining budget {remaining}",
            after,
        )
    return AdmitDecision(True, "within budget", after)
