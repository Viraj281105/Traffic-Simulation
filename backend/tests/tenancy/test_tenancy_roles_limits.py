"""Roles, permission matrix, token buckets, rate limits and quotas."""

import pytest

from src.tenancy.limits import (
    LimitExceededError,
    QuotaManager,
    QuotaPolicy,
    RateLimiter,
    RateLimits,
    TokenBucket,
)
from src.tenancy.roles import (
    ALL_PERMISSIONS,
    PERMISSION_MATRIX,
    RESOURCES_DELETE,
    RUNS_CREATE,
    TENANT_ADMIN,
    Role,
    permissions_for,
    primary_role,
    roles_from_claims,
)


class Clock:
    def __init__(self, now: float = 86400.0 * 100) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


# -- roles ---------------------------------------------------------------


def test_matrix_covers_every_role_and_only_known_permissions() -> None:
    assert set(PERMISSION_MATRIX) == set(Role)
    for perms in PERMISSION_MATRIX.values():
        assert perms <= ALL_PERMISSIONS
    assert PERMISSION_MATRIX[Role.ADMIN] == ALL_PERMISSIONS
    assert TENANT_ADMIN not in PERMISSION_MATRIX[Role.ANALYST]
    assert RESOURCES_DELETE not in PERMISSION_MATRIX[Role.VIEWER]
    assert RUNS_CREATE not in PERMISSION_MATRIX[Role.VIEWER]
    assert RUNS_CREATE in PERMISSION_MATRIX[Role.SERVICE]
    assert RESOURCES_DELETE not in PERMISSION_MATRIX[Role.SERVICE]


@pytest.mark.parametrize(
    "claims, expected",
    [
        ({"cognito:groups": ["Analyst"]}, {Role.ANALYST}),
        ({"cognito:groups": ["admin", "viewer", "unknown"]}, {Role.ADMIN, Role.VIEWER}),
        ({"cognito:groups": "viewer, service"}, {Role.VIEWER, Role.SERVICE}),
        ({"cognito:groups": 7}, set()),
        ({}, set()),
    ],
)
def test_roles_from_default_claim(claims: dict, expected: set) -> None:  # type: ignore[type-arg]
    assert roles_from_claims(claims) == expected


def test_custom_claim_and_exhaustive_group_map() -> None:
    claims = {"roles": ["team-a-owners", "admin"]}
    got = roles_from_claims(
        claims, claim="roles", group_map={"team-a-owners": Role.ANALYST}
    )
    assert got == {Role.ANALYST}  # the unmapped 'admin' grants nothing


def test_primary_role_precedence_and_union() -> None:
    assert primary_role({Role.VIEWER, Role.ANALYST}) is Role.ANALYST
    assert primary_role(set()) is None
    assert permissions_for(set()) == frozenset()
    assert permissions_for({Role.VIEWER, Role.SERVICE}) == (
        PERMISSION_MATRIX[Role.VIEWER] | PERMISSION_MATRIX[Role.SERVICE]
    )


# -- token bucket and rate limiter -----------------------------------------


def test_token_bucket_refills_with_the_clock() -> None:
    clock = Clock(0.0)
    bucket = TokenBucket(2, 1.0, clock)
    bucket.take()
    bucket.take()
    assert bucket.wait_for() == pytest.approx(1.0)
    clock.now = 1.5
    assert bucket.wait_for() == 0.0
    clock.now = 100
    assert bucket.available() == 2  # capped at capacity


def test_rate_limiter_per_user_and_per_tenant() -> None:
    clock = Clock()
    limiter = RateLimiter(
        RateLimits(
            user_burst=2, user_per_minute=60, tenant_burst=3, tenant_per_minute=60
        ),
        clock,
    )
    limiter.check("t1", "u1")
    limiter.check("t1", "u1")
    with pytest.raises(LimitExceededError) as user_hit:
        limiter.check("t1", "u1")
    assert user_hit.value.code == "rate_limited"
    assert user_hit.value.retry_after_seconds == 1
    limiter.check("t1", "u2")  # another user of the same tenant still has burst
    with pytest.raises(LimitExceededError) as tenant_hit:
        limiter.check("t1", "u3")  # but the tenant bucket (3) is now empty
    assert tenant_hit.value.code == "tenant_rate_limited"
    limiter.check("t2", "u1")  # another tenant is unaffected
    clock.now += 5
    limiter.check("t1", "u1")  # refilled


def test_a_refused_request_spends_nothing() -> None:
    limiter = RateLimiter(
        RateLimits(
            user_burst=1, user_per_minute=60, tenant_burst=5, tenant_per_minute=60
        ),
        Clock(),
    )
    limiter.check("t", "u")
    for _ in range(3):
        with pytest.raises(LimitExceededError):
            limiter.check("t", "u")
    assert limiter.remaining("t", "u") == (0, 4)


# -- quotas ----------------------------------------------------------------


def test_daily_run_quota_resets_at_utc_midnight() -> None:
    clock = Clock(86400.0 * 100 + 86400 - 100)  # 100 s before midnight
    quotas = QuotaManager(
        QuotaPolicy(daily_runs_per_user=2, concurrent_runs_per_user=9), clock
    )
    quotas.acquire_run("t", "u").release()
    quotas.acquire_run("t", "u").release()
    with pytest.raises(LimitExceededError) as hit:
        quotas.acquire_run("t", "u")
    assert hit.value.code == "daily_quota_exceeded"
    assert hit.value.retry_after_seconds == 100
    clock.now += 101
    quotas.acquire_run("t", "u").release()
    assert quotas.usage("t", "u")["user"]["runsToday"] == 1
    assert quotas.usage("t", "u")["user"]["runsTotal"] == 3


def test_concurrent_quota_frees_on_release_and_release_is_idempotent() -> None:
    quotas = QuotaManager(QuotaPolicy(concurrent_runs_per_user=1), Clock())
    lease = quotas.acquire_run("t", "u")
    with pytest.raises(LimitExceededError) as hit:
        quotas.acquire_run("t", "u")
    assert hit.value.code == "concurrent_quota_exceeded"
    assert hit.value.retry_after_seconds >= 1
    lease.release()
    lease.release()
    quotas.acquire_run("t", "u")
    assert quotas.usage("t", "u")["user"]["activeRuns"] == 1


def test_tenant_quotas_bind_all_users_but_not_other_tenants() -> None:
    quotas = QuotaManager(
        QuotaPolicy(
            daily_runs_per_user=5,
            daily_runs_per_tenant=2,
            concurrent_runs_per_user=5,
            concurrent_runs_per_tenant=5,
        ),
        Clock(),
    )
    quotas.acquire_run("t1", "a")
    quotas.acquire_run("t1", "b")
    with pytest.raises(LimitExceededError) as hit:
        quotas.acquire_run("t1", "c")
    assert hit.value.code == "tenant_daily_quota_exceeded"
    quotas.acquire_run("t2", "a")


def test_tenant_policy_override_and_remaining() -> None:
    quotas = QuotaManager(
        QuotaPolicy(daily_runs_per_user=1),
        Clock(),
        tenant_overrides={"big": QuotaPolicy(daily_runs_per_user=10)},
    )
    quotas.acquire_run("small", "u")
    assert quotas.remaining("small", "u")["dailyRuns"]["remaining"] == 0
    quotas.acquire_run("big", "u")
    assert quotas.remaining("big", "u")["dailyRuns"]["remaining"] == 9


def test_usage_counters_and_user_breakdown() -> None:
    quotas = QuotaManager(clock=Clock())
    quotas.record_request("t", "u1")
    quotas.record_request("t", "u2", limited=True)
    usage = quotas.usage("t", "u1")
    assert usage["tenant"]["requestsTotal"] == 2
    assert usage["tenant"]["rateLimitedTotal"] == 1
    assert usage["user"]["requestsTotal"] == 1
    assert set(quotas.usage_by_user("t")) == {"u1", "u2"}
    assert quotas.usage_by_user("other") == {}
