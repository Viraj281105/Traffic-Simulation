"""Tenant-isolation sweep: two tenants cannot list, read, overwrite or delete
each other's resources through the tenancy dependencies and scoping helpers,
including key-prefix traversal attempts. Also the HTTP surface of the layer
(auth failures, roles, 429s, the /api/v2/tenancy router)."""

from typing import Dict, Iterator, List, Tuple

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from tenancy_mock_issuer import AUDIENCE, ISSUER, MockIssuer

from src.tenancy.deps import (
    TenancyRuntime,
    TenantContext,
    acquire_run_slot,
    get_runtime,
    require_permission,
    require_role,
)
from src.tenancy.limits import (
    QuotaManager,
    QuotaPolicy,
    RateLimiter,
    RateLimits,
    RunLease,
)
from src.tenancy.oidc import OidcConfig, OidcVerifier
from src.tenancy.roles import RESOURCES_DELETE, RESOURCES_READ, RESOURCES_WRITE, Role
from src.tenancy.router import router as tenancy_router
from src.tenancy.scoping import InMemoryScopedStore, InvalidKeyError, TenantScope


class Clock:
    def __init__(self) -> None:
        self.now = 86400.0 * 200

    def __call__(self) -> float:
        return self.now


def build_app(
    issuer: MockIssuer,
    clock: Clock,
    limits: RateLimits = RateLimits(),
    policy: QuotaPolicy = QuotaPolicy(),
) -> Tuple[FastAPI, InMemoryScopedStore, TenancyRuntime]:
    runtime = TenancyRuntime(
        verifier=OidcVerifier(
            OidcConfig(issuer=ISSUER, audience=AUDIENCE), fetcher=issuer.fetcher
        ),
        limiter=RateLimiter(limits, clock),
        quotas=QuotaManager(policy, clock),
    )
    store = InMemoryScopedStore()
    app = FastAPI()
    app.dependency_overrides[get_runtime] = lambda: runtime

    @app.get("/res")
    def list_res(
        ctx: TenantContext = Depends(require_permission(RESOURCES_READ)),
    ) -> List[str]:
        return store.list(ctx.scope)

    @app.put("/res/{name:path}")
    def put_res(
        name: str,
        ctx: TenantContext = Depends(require_permission(RESOURCES_WRITE)),
    ) -> Dict[str, str]:
        try:
            return {"key": store.put(ctx.scope, name, ctx.tenant_id.encode())}
        except InvalidKeyError:
            raise HTTPException(status_code=400, detail="invalid key")

    @app.get("/res/{name:path}")
    def get_res(
        name: str,
        ctx: TenantContext = Depends(require_permission(RESOURCES_READ)),
    ) -> Dict[str, str]:
        try:
            value = store.get(ctx.scope, name)
        except InvalidKeyError:
            raise HTTPException(status_code=400, detail="invalid key")
        if value is None:
            raise HTTPException(status_code=404, detail="not found")
        return {"owner": value.decode()}

    @app.delete("/res/{name:path}")
    def delete_res(
        name: str,
        ctx: TenantContext = Depends(require_permission(RESOURCES_DELETE)),
    ) -> Dict[str, bool]:
        try:
            if not store.delete(ctx.scope, name):
                raise HTTPException(status_code=404, detail="not found")
        except InvalidKeyError:
            raise HTTPException(status_code=400, detail="invalid key")
        return {"deleted": True}

    @app.get("/admin-only")
    def admin_only(ctx: TenantContext = Depends(require_role(Role.ADMIN))) -> str:
        return ctx.tenant_id

    @app.post("/runs")
    def start_run(lease: RunLease = Depends(acquire_run_slot)) -> Dict[str, str]:
        return {"tenant": lease.tenant}

    app.include_router(tenancy_router)
    return app, store, runtime


@pytest.fixture(scope="module")
def issuer() -> MockIssuer:
    return MockIssuer()


@pytest.fixture()
def world(
    issuer: MockIssuer,
) -> Iterator[Tuple[TestClient, MockIssuer, Clock, InMemoryScopedStore]]:
    clock = Clock()
    app, store, _ = build_app(issuer, clock)
    yield TestClient(app), issuer, clock, store


def auth(issuer: MockIssuer, **kw: object) -> Dict[str, str]:
    return {"Authorization": f"Bearer {issuer.token(**kw)}"}  # type: ignore[arg-type]


# -- isolation sweep -------------------------------------------------------

TRAVERSAL = [
    "../tenants/globex/secret.json",
    "..%2ftenants%2fglobex%2fsecret.json",
    "%2e%2e/tenants/globex/secret.json",
    "%2e%2e%2ftenants%2fglobex%2fsecret.json",
    "%252e%252e%252ftenants%252fglobex%252fsecret.json",
    "..\\tenants\\globex\\secret.json",
    "a/../../globex/secret.json",
    "./secret.json",
    "docs//secret.json",
    "/tenants/globex/secret.json",
    "secret.json%00",
    "secret.json\n",
    "..;/globex/secret.json",
    "%c0%ae%c0%ae/globex/secret.json",
    "....//globex/secret.json",
]


@pytest.mark.parametrize("attacker, victim", [("acme", "globex"), ("globex", "acme")])
def test_tenants_cannot_list_read_overwrite_or_delete_each_other(
    world: Tuple[TestClient, MockIssuer, Clock, InMemoryScopedStore],
    attacker: str,
    victim: str,
) -> None:
    client, issuer, _, store = world
    victim_h = auth(issuer, sub="v", tenant=victim, groups=["admin"])
    attacker_h = auth(issuer, sub="a", tenant=attacker, groups=["admin"])

    assert client.put("/res/secret.json", headers=victim_h).status_code == 200

    # list shows only own resources
    assert client.get("/res", headers=attacker_h).json() == []
    assert client.get("/res", headers=victim_h).json() == ["secret.json"]

    # the same name is a different, missing resource for the attacker
    assert client.get("/res/secret.json", headers=attacker_h).status_code == 404
    assert client.delete("/res/secret.json", headers=attacker_h).status_code == 404

    # writing the same name does not touch the victim's copy
    assert client.put("/res/secret.json", headers=attacker_h).status_code == 200
    assert client.get("/res/secret.json", headers=victim_h).json() == {"owner": victim}
    assert client.get("/res/secret.json", headers=attacker_h).json() == {
        "owner": attacker
    }
    # an admin of the attacker's tenant is still confined to it
    assert client.delete("/res/secret.json", headers=attacker_h).status_code == 200
    assert client.get("/res/secret.json", headers=victim_h).status_code == 200


@pytest.mark.parametrize("path", TRAVERSAL)
def test_traversal_attempts_never_reach_another_tenant(
    world: Tuple[TestClient, MockIssuer, Clock, InMemoryScopedStore], path: str
) -> None:
    client, issuer, _, store = world
    store.put(TenantScope("globex"), "secret.json", b"globex")
    attacker = auth(issuer, sub="a", tenant="acme", groups=["admin"])
    url = "/res/" + path.replace(chr(10), "%0A")
    for call in (client.get, client.put, client.delete):
        status = call(url, headers=attacker).status_code
        assert status in (400, 404, 200, 307, 405), (path, status)
    # whatever happened, globex's object is intact and nothing new appeared there
    assert store.get(TenantScope("globex"), "secret.json") == b"globex"
    globex_keys = [k for k in store._items if k.startswith("tenants/globex/")]
    assert globex_keys == ["tenants/globex/secret.json"]
    assert all(k.startswith(("tenants/acme/", "tenants/globex/")) for k in store._items)


@pytest.mark.parametrize("path", TRAVERSAL)
def test_scope_helper_rejects_or_confines_traversal(path: str) -> None:
    scope = TenantScope("acme")
    try:
        key = scope.key_for(path)
    except InvalidKeyError:
        return
    assert key.startswith("tenants/acme/")
    assert ".." not in key.split("/")
    assert scope.owns(key)


def test_prefix_of_one_tenant_is_not_a_prefix_of_another() -> None:
    a, ab = TenantScope("a"), TenantScope("ab")
    key = ab.key("x")
    assert not a.owns(key)
    assert a.relative(a.key("x")) == "x"
    with pytest.raises(InvalidKeyError):
        a.relative(key)


def test_sql_filter_binds_the_tenant_as_a_parameter() -> None:
    sql, params = TenantScope("acme").sql_filter()
    assert (sql, params) == ("tenant_id = ?", ("acme",))
    assert TenantScope("acme").sql_filter("owner_tenant")[0] == "owner_tenant = ?"
    with pytest.raises(InvalidKeyError):
        TenantScope("acme").sql_filter("tenant_id; DROP TABLE x")


@pytest.mark.parametrize("bad", ["", "A", "a/b", "../x", "a b", "x" * 80, "a\n"])
def test_invalid_tenant_ids_are_rejected(bad: str) -> None:
    with pytest.raises(InvalidKeyError):
        TenantScope(bad)


# -- the HTTP surface -------------------------------------------------------


def test_missing_and_bad_tokens_are_401(
    world: Tuple[TestClient, MockIssuer, Clock, InMemoryScopedStore],
) -> None:
    client, issuer, _, _ = world
    assert client.get("/res").status_code == 401
    r = client.get("/res", headers={"Authorization": "Bearer junk"})
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"
    assert client.get("/res", headers=auth(issuer, expires_in=-600)).status_code == 401


def test_token_without_tenant_or_role_is_403(
    world: Tuple[TestClient, MockIssuer, Clock, InMemoryScopedStore],
) -> None:
    client, issuer, _, _ = world
    assert client.get("/res", headers=auth(issuer, tenant=None)).status_code == 403
    assert client.get("/res", headers=auth(issuer, tenant="../x")).status_code == 403
    assert client.get("/res", headers=auth(issuer, groups=[])).status_code == 403


def test_roles_gate_the_routes(
    world: Tuple[TestClient, MockIssuer, Clock, InMemoryScopedStore],
) -> None:
    client, issuer, _, _ = world
    viewer = auth(issuer, groups=["viewer"])
    assert client.get("/res", headers=viewer).status_code == 200
    assert client.put("/res/x", headers=viewer).status_code == 403
    assert client.post("/runs", headers=viewer).status_code == 403
    assert (
        client.get("/admin-only", headers=auth(issuer, groups=["analyst"])).status_code
        == 403
    )
    admin = client.get("/admin-only", headers=auth(issuer, groups=["admin"]))
    assert admin.json() == "acme"
    service = auth(issuer, groups=["service"])
    assert client.put("/res/x", headers=service).status_code == 200
    assert client.delete("/res/x", headers=service).status_code == 403


def test_rate_limit_returns_429_with_retry_after(issuer: MockIssuer) -> None:
    clock = Clock()
    app, _, _ = build_app(
        issuer, clock, limits=RateLimits(user_burst=2, user_per_minute=60)
    )
    client = TestClient(app)
    h = auth(issuer)
    assert client.get("/res", headers=h).status_code == 200
    assert client.get("/res", headers=h).status_code == 200
    r = client.get("/res", headers=h)
    assert r.status_code == 429
    assert r.headers["retry-after"] == "1"
    assert r.json()["detail"]["code"] == "rate_limited"
    clock.now += 2
    assert client.get("/res", headers=h).status_code == 200


def test_run_quotas_return_429_and_release_after_the_request(
    issuer: MockIssuer,
) -> None:
    clock = Clock()
    app, _, runtime = build_app(
        issuer, clock, policy=QuotaPolicy(daily_runs_per_user=2)
    )
    client = TestClient(app)
    h = auth(issuer)
    assert client.post("/runs", headers=h).status_code == 200
    assert client.post("/runs", headers=h).status_code == 200  # slot was released
    r = client.post("/runs", headers=h)
    assert r.status_code == 429
    assert r.json()["detail"]["code"] == "daily_quota_exceeded"
    assert int(r.headers["retry-after"]) > 0
    assert runtime.quotas.usage("acme", "user-1")["user"]["activeRuns"] == 0
    # another tenant's quota is separate
    assert (
        client.post("/runs", headers=auth(issuer, tenant="globex")).status_code == 200
    )


def test_me_endpoint_shape(
    world: Tuple[TestClient, MockIssuer, Clock, InMemoryScopedStore],
) -> None:
    client, issuer, _, _ = world
    body = client.get(
        "/api/v2/tenancy/me",
        headers=auth(issuer, sub="u7", groups=["analyst", "viewer"]),
    ).json()
    assert body["identity"]["userId"] == "u7"
    assert body["identity"]["email"] == "u7@example.com"
    assert body["tenant"] == {"id": "acme"}
    assert body["role"] == "analyst"
    assert body["roles"] == ["analyst", "viewer"]
    assert "runs:create" in body["permissions"]
    assert "tenant:admin" not in body["permissions"]
    quota = body["quota"]
    assert quota["dailyRuns"]["limit"] == 50
    assert quota["dailyRuns"]["remaining"] == 50
    assert quota["concurrentRuns"]["remaining"] == 2
    assert quota["requests"]["user"]["burst"] == 30


def test_usage_endpoint_counts_and_admin_only_breakdown(
    world: Tuple[TestClient, MockIssuer, Clock, InMemoryScopedStore],
) -> None:
    client, issuer, _, _ = world
    client.post("/runs", headers=auth(issuer, sub="a1", groups=["analyst"]))
    client.get("/res", headers=auth(issuer, sub="a2", groups=["viewer"]))
    analyst = client.get(
        "/api/v2/tenancy/usage", headers=auth(issuer, sub="a1", groups=["analyst"])
    ).json()
    assert analyst["user"]["runsToday"] == 1
    assert analyst["tenant"]["runsToday"] == 1
    assert analyst["users"] is None
    admin = client.get(
        "/api/v2/tenancy/usage", headers=auth(issuer, sub="boss", groups=["admin"])
    ).json()
    assert {"a1", "a2", "boss"} <= set(admin["users"])
    other = client.get(
        "/api/v2/tenancy/usage",
        headers=auth(issuer, sub="x", tenant="globex", groups=["admin"]),
    ).json()
    assert other["tenant"]["runsToday"] == 0
    assert "a1" not in other["users"]


def test_unconfigured_runtime_is_503(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.tenancy import deps

    for name in ("TENANCY_OIDC_ISSUER", "COGNITO_USER_POOL_ID", "COGNITO_CLIENT_ID"):
        monkeypatch.delenv(name, raising=False)
    deps.set_runtime(None)
    app = FastAPI()
    app.include_router(tenancy_router)
    try:
        assert TestClient(app).get("/api/v2/tenancy/me").status_code == 503
    finally:
        deps.set_runtime(None)


def test_runtime_from_env_builds_a_cognito_verifier() -> None:
    from src.tenancy.deps import runtime_from_env

    rt = runtime_from_env(
        {"COGNITO_USER_POOL_ID": "us-east-1_X", "COGNITO_CLIENT_ID": "cid"}
    )
    assert rt is not None
    assert rt.verifier.config.issuer.endswith("/us-east-1_X")
    assert runtime_from_env({}) is None
