"""API-key protection, and the proxy contract that makes it usable.

Enabling `API_KEY` used to break the browser demo: the backend demanded a
bearer token on its mutating routes, and the frontend had no way to send one —
anything shipped in a JS bundle is public, so embedding the key would protect
nothing. The two were mutually exclusive.

The fix attaches the header at the nginx proxy instead, server-side. These
tests pin both halves of that contract: the backend's own enforcement, and the
template that supplies the header.
"""

import importlib
import re
from pathlib import Path
from typing import Any, Dict, Iterator

import pytest
from fastapi.testclient import TestClient

NGINX_TEMPLATE = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "templates"
    / "default.conf.template"
)


def _valid_config() -> Dict[str, Any]:
    return {
        "simulation": {"timeStep": 0.1, "duration": 30, "warmupTime": 0.0},
        "geometry": {"intersectionType": "fixed_time_signal"},
    }


@pytest.fixture
def secured_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A client against an app instance that requires an API key.

    API_KEY is read at import time, so the module is reloaded under the patched
    environment rather than poked afterwards.
    """
    monkeypatch.setenv("API_KEY", "test-secret-key")
    import src.main as main

    importlib.reload(main)
    try:
        yield TestClient(main.app)
    finally:
        monkeypatch.delenv("API_KEY", raising=False)
        importlib.reload(main)


# ── Backend enforcement ───────────────────────────────────────────────────


def test_mutating_route_rejects_a_missing_key(secured_client: TestClient) -> None:
    response = secured_client.post("/api/v1/simulations", json=_valid_config())
    assert response.status_code == 401


def test_mutating_route_rejects_a_wrong_key(secured_client: TestClient) -> None:
    response = secured_client.post(
        "/api/v1/simulations",
        json=_valid_config(),
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert response.status_code == 401


def test_mutating_route_rejects_a_malformed_header(
    secured_client: TestClient,
) -> None:
    response = secured_client.post(
        "/api/v1/simulations",
        json=_valid_config(),
        headers={"Authorization": "test-secret-key"},  # no "Bearer " prefix
    )
    assert response.status_code == 401


def test_mutating_route_accepts_the_correct_key(secured_client: TestClient) -> None:
    """This is the request nginx makes on the browser's behalf."""
    response = secured_client.post(
        "/api/v1/simulations",
        json=_valid_config(),
        headers={"Authorization": "Bearer test-secret-key"},
    )
    assert response.status_code == 201


def test_read_only_route_stays_open(secured_client: TestClient) -> None:
    """Health and status must not require a key, or probes break."""
    assert secured_client.get("/health").status_code == 200


def test_auth_is_disabled_when_no_key_is_configured() -> None:
    """The local-development default must stay frictionless."""
    import src.main as main

    client = TestClient(main.app)
    response = client.post("/api/v1/simulations", json=_valid_config())
    assert response.status_code == 201


# ── Proxy contract ────────────────────────────────────────────────────────


def test_nginx_template_injects_the_bearer_header_on_both_proxies() -> None:
    """The browser cannot send the key, so the proxy must."""
    template = NGINX_TEMPLATE.read_text(encoding="utf-8")
    header = 'proxy_set_header Authorization "Bearer ${BACKEND_API_KEY}";'

    assert template.count(header) == 2, (
        "both the /api/ and /ws/ proxy blocks must attach the API key"
    )


def test_nginx_template_keeps_runtime_variables_unsubstituted() -> None:
    """envsubst must not eat nginx's own variables.

    nginx runtime variables use the same ``$name`` syntax as the substitution
    placeholder, so the image pins NGINX_ENVSUBST_FILTER to BACKEND_API_KEY
    alone. If that filter were dropped, `$host` and friends would be replaced
    with empty strings and proxying would break in ways no unit test would
    otherwise catch.
    """
    template = NGINX_TEMPLATE.read_text(encoding="utf-8")
    for runtime_var in ("$host", "$remote_addr", "$http_upgrade", "$scheme"):
        assert runtime_var in template

    dockerfile = (
        Path(__file__).resolve().parents[3] / "frontend" / "Dockerfile"
    ).read_text(encoding="utf-8")
    assert "NGINX_ENVSUBST_FILTER" in dockerfile
    assert "BACKEND_API_KEY" in dockerfile


def test_nginx_template_only_templates_the_api_key() -> None:
    """Exactly one placeholder, so the filter above is sufficient."""
    template = NGINX_TEMPLATE.read_text(encoding="utf-8")
    placeholders = set(re.findall(r"\$\{(\w+)\}", template))
    assert placeholders == {"BACKEND_API_KEY"}


def test_nginx_template_includes_the_optional_access_gate() -> None:
    """The gate controls *who* may use the demo, which the key does not."""
    template = NGINX_TEMPLATE.read_text(encoding="utf-8")
    assert "include /etc/nginx/auth-gate/*.conf;" in template


def test_compose_wires_the_proxy_key_from_the_same_value_as_the_backend() -> None:
    """A mismatch here would fail closed at runtime with a 401 on every call."""
    compose = (Path(__file__).resolve().parents[3] / "docker-compose.yml").read_text(
        encoding="utf-8"
    )
    assert "API_KEY=${API_KEY:-}" in compose
    assert "BACKEND_API_KEY=${API_KEY:-}" in compose
