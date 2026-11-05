"""Rate limits and quotas per tenant and per user (in memory).

* ``TokenBucket`` / ``RateLimiter``: request rate, one bucket per user and one
  per tenant; a request needs a token from both.
* ``QuotaManager``: runs per UTC day and runs in flight, per user and per
  tenant, plus usage counters.

State is per process and lost on restart (see docs/security/tenancy.md). The
clock is injectable (seconds, like ``time.time``) so tests never sleep.
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

Clock = Callable[[], float]


class LimitExceededError(Exception):
    """A rate limit or quota refused the request (HTTP 429)."""

    def __init__(
        self, code: str, message: str, limit: int, retry_after_seconds: int
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.limit = limit
        self.retry_after_seconds = max(1, retry_after_seconds)

    def detail(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "limit": self.limit,
            "retryAfterSeconds": self.retry_after_seconds,
        }


class TokenBucket:
    def __init__(self, capacity: float, refill_per_second: float, clock: Clock) -> None:
        self.capacity = capacity
        self.refill = refill_per_second
        self._clock = clock
        self._tokens = capacity
        self._at = clock()

    def _top_up(self) -> None:
        now = self._clock()
        self._tokens = min(
            self.capacity, self._tokens + max(0.0, now - self._at) * self.refill
        )
        self._at = now

    def available(self) -> float:
        self._top_up()
        return self._tokens

    def wait_for(self, cost: float = 1.0) -> float:
        """Seconds until ``cost`` tokens exist (0 when they do now)."""
        missing = cost - self.available()
        if missing <= 0:
            return 0.0
        return missing / self.refill if self.refill > 0 else math.inf

    def take(self, cost: float = 1.0) -> None:
        self._top_up()
        self._tokens -= cost


@dataclass(frozen=True)
class RateLimits:
    user_burst: int = 30
    user_per_minute: int = 120
    tenant_burst: int = 300
    tenant_per_minute: int = 1200


class RateLimiter:
    def __init__(self, limits: RateLimits = RateLimits(), clock: Clock = time.time):
        self.limits = limits
        self._clock = clock
        self._buckets: Dict[Tuple[str, ...], TokenBucket] = {}
        self._lock = threading.Lock()

    def _bucket(self, key: Tuple[str, ...], burst: int, per_minute: int) -> TokenBucket:
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = TokenBucket(burst, per_minute / 60.0, self._clock)
            self._buckets[key] = bucket
        return bucket

    def _pair(self, tenant: str, user: str) -> Tuple[TokenBucket, TokenBucket]:
        lim = self.limits
        return (
            self._bucket(("u", tenant, user), lim.user_burst, lim.user_per_minute),
            self._bucket(("t", tenant), lim.tenant_burst, lim.tenant_per_minute),
        )

    def check(self, tenant: str, user: str) -> None:
        """Spend one token from the user's and the tenant's bucket, or raise
        ``LimitExceededError`` (spending nothing)."""
        with self._lock:
            ub, tb = self._pair(tenant, user)
            wait_user, wait_tenant = ub.wait_for(), tb.wait_for()
            if wait_user > 0:
                raise LimitExceededError(
                    "rate_limited",
                    "Per-user request rate limit exceeded",
                    self.limits.user_per_minute,
                    math.ceil(wait_user),
                )
            if wait_tenant > 0:
                raise LimitExceededError(
                    "tenant_rate_limited",
                    "Per-tenant request rate limit exceeded",
                    self.limits.tenant_per_minute,
                    math.ceil(wait_tenant),
                )
            ub.take()
            tb.take()

    def remaining(self, tenant: str, user: str) -> Tuple[int, int]:
        with self._lock:
            ub, tb = self._pair(tenant, user)
            return int(ub.available()), int(tb.available())


@dataclass(frozen=True)
class QuotaPolicy:
    daily_runs_per_user: int = 50
    daily_runs_per_tenant: int = 500
    concurrent_runs_per_user: int = 2
    concurrent_runs_per_tenant: int = 10


@dataclass
class _Counters:
    day: str = ""
    requests_total: int = 0
    rate_limited_total: int = 0
    runs_today: int = 0
    runs_total: int = 0
    active_runs: int = 0

    def roll(self, day: str) -> None:
        if self.day != day:
            self.day = day
            self.runs_today = 0


@dataclass
class RunLease:
    """One run slot. ``release`` is idempotent."""

    tenant: str
    user: str
    _manager: "QuotaManager"
    released: bool = field(default=False)
    keep: bool = field(default=False)

    def release(self) -> None:
        self._manager._release(self)


def _day_of(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def seconds_to_utc_midnight(ts: float) -> int:
    return 86400 - int(ts % 86400)


class QuotaManager:
    CONCURRENT_RETRY_HINT_SECONDS = 10

    def __init__(
        self,
        policy: QuotaPolicy = QuotaPolicy(),
        clock: Clock = time.time,
        tenant_overrides: Optional[Dict[str, QuotaPolicy]] = None,
    ) -> None:
        self.default_policy = policy
        self._overrides = dict(tenant_overrides or {})
        self._clock = clock
        self._users: Dict[Tuple[str, str], _Counters] = {}
        self._tenants: Dict[str, _Counters] = {}
        self._lock = threading.Lock()

    def policy_for(self, tenant: str) -> QuotaPolicy:
        return self._overrides.get(tenant, self.default_policy)

    def _counters(self, tenant: str, user: Optional[str]) -> _Counters:
        day = _day_of(self._clock())
        if user is None:
            c = self._tenants.setdefault(tenant, _Counters())
        else:
            c = self._users.setdefault((tenant, user), _Counters())
        c.roll(day)
        return c

    def record_request(self, tenant: str, user: str, *, limited: bool = False) -> None:
        with self._lock:
            for c in (self._counters(tenant, user), self._counters(tenant, None)):
                c.requests_total += 1
                if limited:
                    c.rate_limited_total += 1

    def acquire_run(self, tenant: str, user: str) -> RunLease:
        """Take a run slot or raise ``LimitExceededError`` (HTTP 429)."""
        with self._lock:
            pol = self.policy_for(tenant)
            uc, tc = self._counters(tenant, user), self._counters(tenant, None)
            reset = seconds_to_utc_midnight(self._clock())
            if uc.runs_today >= pol.daily_runs_per_user:
                raise LimitExceededError(
                    "daily_quota_exceeded",
                    "Daily run quota for this user is used up",
                    pol.daily_runs_per_user,
                    reset,
                )
            if tc.runs_today >= pol.daily_runs_per_tenant:
                raise LimitExceededError(
                    "tenant_daily_quota_exceeded",
                    "Daily run quota for this tenant is used up",
                    pol.daily_runs_per_tenant,
                    reset,
                )
            hint = self.CONCURRENT_RETRY_HINT_SECONDS
            if uc.active_runs >= pol.concurrent_runs_per_user:
                raise LimitExceededError(
                    "concurrent_quota_exceeded",
                    "Too many runs in progress for this user",
                    pol.concurrent_runs_per_user,
                    hint,
                )
            if tc.active_runs >= pol.concurrent_runs_per_tenant:
                raise LimitExceededError(
                    "tenant_concurrent_quota_exceeded",
                    "Too many runs in progress for this tenant",
                    pol.concurrent_runs_per_tenant,
                    hint,
                )
            for c in (uc, tc):
                c.runs_today += 1
                c.runs_total += 1
                c.active_runs += 1
            return RunLease(tenant, user, self)

    def _release(self, lease: RunLease) -> None:
        with self._lock:
            if lease.released:
                return
            lease.released = True
            for c in (
                self._users.get((lease.tenant, lease.user)),
                self._tenants.get(lease.tenant),
            ):
                if c is not None and c.active_runs > 0:
                    c.active_runs -= 1

    def remaining(self, tenant: str, user: str) -> Dict[str, Any]:
        with self._lock:
            pol = self.policy_for(tenant)
            uc, tc = self._counters(tenant, user), self._counters(tenant, None)
            now = self._clock()
            return {
                "dailyRuns": {
                    "limit": pol.daily_runs_per_user,
                    "used": uc.runs_today,
                    "remaining": max(
                        0,
                        min(
                            pol.daily_runs_per_user - uc.runs_today,
                            pol.daily_runs_per_tenant - tc.runs_today,
                        ),
                    ),
                    "resetsInSeconds": seconds_to_utc_midnight(now),
                },
                "concurrentRuns": {
                    "limit": pol.concurrent_runs_per_user,
                    "active": uc.active_runs,
                    "remaining": max(
                        0,
                        min(
                            pol.concurrent_runs_per_user - uc.active_runs,
                            pol.concurrent_runs_per_tenant - tc.active_runs,
                        ),
                    ),
                },
            }

    def usage(self, tenant: str, user: str) -> Dict[str, Any]:
        with self._lock:
            return {
                "day": _day_of(self._clock()),
                "user": _as_dict(self._counters(tenant, user)),
                "tenant": _as_dict(self._counters(tenant, None)),
            }

    def usage_by_user(self, tenant: str) -> Dict[str, Dict[str, int]]:
        with self._lock:
            return {
                u: _as_dict(self._counters(t, u))
                for (t, u) in sorted(self._users)
                if t == tenant
            }


def _as_dict(c: _Counters) -> Dict[str, int]:
    return {
        "requestsTotal": c.requests_total,
        "rateLimitedTotal": c.rate_limited_total,
        "runsToday": c.runs_today,
        "runsTotal": c.runs_total,
        "activeRuns": c.active_runs,
    }
