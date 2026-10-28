"""The Python client against the real ``/api/v3`` app (contract and integration tests, W7 Stage 5).

The client's own transport is replaced by one that calls the FastAPI app in process, so these tests check
that what the client sends is what the server accepts, and that the server's errors become the client's
exceptions, without opening a socket."""

from __future__ import annotations

import json
import re
import sys
import threading
from pathlib import Path
from typing import Iterator, List, Mapping, Optional

import pytest
from fastapi.testclient import TestClient

SDK_ROOT = Path(__file__).resolve().parents[3] / "sdk" / "python"
sys.path.insert(0, str(SDK_ROOT))

from urbanflow_client import (  # noqa: E402
    AuthenticationError,
    Client,
    Conflict,
    InvalidRequest,
    NotFound,
    PermissionDenied,
    QuotaExceeded,
    Response,
)

import src.api.security as security  # noqa: E402
from src.api.auth import reset_auth_failures  # noqa: E402
from src.api.store import TokenStore  # noqa: E402
from src.experiments.service import ExperimentService, get_service  # noqa: E402
from src.main import app  # noqa: E402
from tests.experiments.conftest import FakeExecutor, experiment  # noqa: E402

BASE = "http://localhost:8000"
API_KEY = "sdk-test-key"
ALL_SCOPES = [
    "experiments:read",
    "experiments:run",
    "packages:read",
    "packages:write",
    "tokens:read",
    "tokens:manage",
]


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[TestClient]:
    monkeypatch.setattr("src.database.db.DB_PATH", str(tmp_path / "sdk.db"))
    monkeypatch.setattr(security, "API_KEY", API_KEY)
    monkeypatch.delenv("DEV_AUTH_BYPASS", raising=False)
    reset_auth_failures()
    service: ExperimentService = get_service()
    previous = service.executor
    service.executor = FakeExecutor()
    service.store._records.clear()
    try:
        yield TestClient(app)
    finally:
        service.executor = previous
        service.store._records.clear()
        reset_auth_failures()


def transport_for(tc: TestClient):
    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Optional[bytes],
        timeout: float,
        max_bytes: int,
    ) -> Response:
        res = tc.request(
            method, url.replace(BASE, ""), headers=dict(headers), content=body
        )
        return Response(res.status_code, dict(res.headers), res.content)

    return transport


def client_for(
    tc: TestClient, user: str = "sdk-user", scopes: Optional[List[str]] = None
) -> Client:
    _, raw = TokenStore.create_token(user, "sdk", scopes or ALL_SCOPES)
    return Client(
        BASE,
        raw,
        api_key=API_KEY,
        transport=transport_for(tc),
        retries=0,
        sleep=lambda _s: None,
    )


def test_full_lifecycle_through_the_client(server: TestClient, tmp_path: Path):
    api = client_for(server)
    caps = api.capabilities()
    assert (
        caps["features"]["pythonClient"] is True
        and caps["features"]["experimentPackages"]
    )

    checked = api.validate(experiment())
    assert checked["valid"] is True

    seen: List[str] = []
    result = api.run(
        experiment(), poll_interval=0.05, on_progress=lambda s: seen.append(s["status"])
    )
    assert result["format"] == "urbanflow-experiment-result"
    assert seen and seen[-1] == "completed"

    listing = api.list_experiments()
    assert len(listing["experiments"]) == 1
    eid = listing["experiments"][0]["id"]

    package = tmp_path / "run.ufpkg"
    data = api.export_package(eid, package)
    assert package.read_bytes() == data
    report = api.verify_package(package)
    assert report["internallyConsistent"] is True and report["replayClass"] == "exact"
    assert report["integrityNote"].startswith("Integrity is not authenticity")

    tokens = api.list_tokens()
    assert (
        tokens
        and "uf_pat_" not in json.dumps(tokens)
        and "sha256" not in json.dumps(tokens)
    )
    api.delete(eid)
    with pytest.raises(NotFound):
        api.status(eid)


def test_cancel_and_resume_through_the_client(server: TestClient):
    from tests.experiments.test_cancel_resume import GatedExecutor, wait_settled

    service = get_service()
    executor = GatedExecutor(after=10)
    service.executor = executor
    api = client_for(server)
    eid = api.submit(experiment())["id"]
    assert executor.reached.wait(30)
    assert api.cancel(eid)["status"] == "cancelled"
    executor.release.set()
    wait_settled(service, eid, user="sdk-user")
    assert api.wait(eid, poll_interval=0.05)["status"] == "cancelled"
    assert api.result(eid)["format"] == "urbanflow-experiment-partial-result"
    with pytest.raises(Conflict):
        api.export_package(eid)
    api.resume(eid)
    assert api.wait(eid, poll_interval=0.05)["status"] == "completed"
    assert api.result(eid)["format"] == "urbanflow-experiment-result"


def test_server_errors_become_typed_exceptions(server: TestClient):
    api = client_for(server)
    with pytest.raises(NotFound):
        api.status("does-not-exist")
    with pytest.raises(InvalidRequest) as invalid:
        api.submit({"format": "urbanflow-experiment"})
    assert invalid.value.errors

    read_only = client_for(server, scopes=["experiments:read"])
    with pytest.raises(PermissionDenied):
        read_only.submit(experiment())
    with pytest.raises(PermissionDenied):
        read_only.list_tokens()
    with pytest.raises(PermissionDenied):
        read_only.verify_package(b"x")

    stranger = client_for(server, user="someone-else")
    eid = api.submit(experiment())["id"]
    api.wait(eid, poll_interval=0.05)
    with pytest.raises(NotFound):
        stranger.status(eid)
    with pytest.raises(NotFound):
        stranger.export_package(eid)

    revoked = client_for(server)
    token_id = revoked.list_tokens()[0]["id"]
    revoked.revoke_token(token_id)
    with pytest.raises(AuthenticationError) as err:
        revoked.capabilities()
    assert "uf_pat_" not in str(err.value)

    bad = Client(
        BASE,
        "uf_pat_" + "x" * 43,
        api_key=API_KEY,
        transport=transport_for(server),
        retries=0,
    )
    with pytest.raises(AuthenticationError):
        bad.capabilities()


def test_the_per_user_quota_comes_back_as_quota_exceeded(server: TestClient):
    service = get_service()
    release = threading.Event()
    service.executor = FakeExecutor(block=release)
    api = client_for(server)
    try:
        api.submit(experiment())
        with pytest.raises(QuotaExceeded) as err:
            api.submit(experiment())
        assert "maxActiveExperimentsPerUser" in str(err.value)
    finally:
        release.set()


def test_the_package_size_limit_is_413(server: TestClient):
    from urbanflow_client import PayloadTooLarge

    api = client_for(server)

    def oversized(method, url, headers, body, timeout, max_bytes):  # noqa: ANN001
        res = server.request(
            method,
            url.replace(BASE, ""),
            headers=dict(headers),
            content=b"\0" * (10 * 1024 * 1024 + 1),
        )
        return Response(res.status_code, dict(res.headers), res.content)

    api._transport = oversized
    with pytest.raises(PayloadTooLarge):
        api.verify_package(b"x")


def test_every_route_the_client_uses_is_in_the_openapi_snapshot():
    snapshot = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "shared"
            / "schemas"
            / "v3"
            / "openapi.v3.snapshot.json"
        ).read_text(encoding="utf-8")
    )
    operations = {
        (method.upper(), path)
        for path, item in snapshot["paths"].items()
        for method in item
    }
    source = (SDK_ROOT / "urbanflow_client" / "client.py").read_text(encoding="utf-8")
    used = set()
    for method, path in re.findall(
        r'"(GET|POST|DELETE)",\s*f?"(/api/v3[^"]*)"', source
    ):
        template = re.sub(r"\{[^{}]*\}", "{ID}", path).split("?")[0]
        used.add((method, template))
    assert used, "no routes found in the client"
    normalised = {(m, re.sub(r"\{[a-z_]+\}", "{ID}", p)) for m, p in operations}
    assert used <= normalised, used - normalised


def test_every_documented_v3_operation_has_a_client_method_or_is_deliberately_omitted():
    """POST /tokens needs a browser session, so the client (which holds a PAT) has no method for it."""
    snapshot = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "shared"
            / "schemas"
            / "v3"
            / "openapi.v3.snapshot.json"
        ).read_text(encoding="utf-8")
    )
    operations = {
        (method.upper(), re.sub(r"\{[a-z_]+\}", "{ID}", path))
        for path, item in snapshot["paths"].items()
        for method in item
    }
    source = (SDK_ROOT / "urbanflow_client" / "client.py").read_text(encoding="utf-8")
    used = {
        (m, re.sub(r"\{[^{}]*\}", "{ID}", p).split("?")[0])
        for m, p in re.findall(r'"(GET|POST|DELETE)",\s*f?"(/api/v3[^"]*)"', source)
    }
    assert operations - used == {("POST", "/api/v3/tokens")}


def test_copilot_proposal_confirm_and_interpretation_through_the_client(
    server: TestClient,
):
    from src.ai import groq_client as gc

    api = client_for(server)
    original = gc.is_configured
    gc.is_configured = lambda: False  # type: ignore[assignment]
    try:
        assert api.copilot_catalogue()["format"] == "urbanflow-copilot-catalogue"
        proposal = api.propose(
            "adaptive signal versus fixed-time signal at peak", deterministic=True
        )
        assert proposal["validated"] is True and proposal["mode"] == "deterministic"
        assert api.proposal(proposal["id"])["contentHash"] == proposal["contentHash"]
        accepted = api.confirm_proposal(proposal)
        assert api.wait(accepted["id"], poll_interval=0.05)["status"] == "completed"
        reading = api.interpret(
            accepted["id"], preferred="fixed_time", template_only=True
        )
        assert (
            reading["interpretation"] is None and "Eligibility:" in reading["template"]
        )
        with pytest.raises(Conflict):
            api.confirm_proposal(proposal)  # single use
    finally:
        gc.is_configured = original  # type: ignore[assignment]
