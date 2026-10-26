"""Unit tests of the UrbanFlow client with a fake transport (no network)."""

from __future__ import annotations

import http.server
import json
import pickle
import threading
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import pytest

from urbanflow_client import (
    ApiError,
    AuthenticationError,
    Client,
    ConfigurationError,
    Conflict,
    InvalidRequest,
    NotFound,
    PayloadTooLarge,
    PermissionDenied,
    QuotaExceeded,
    RequestTimeout,
    Response,
    ResponseTooLarge,
    ServerError,
    TransportError,
    WaitTimeout,
    cli,
)
from urbanflow_client.client import _urllib_transport

TOKEN = "uf_pat_SECRETSECRETSECRETSECRETSECRETSECRETSECRET"
KEY = "infrastructure-key-123"
URL = "https://urbanflow.test"

Call = Tuple[str, str, Mapping[str, str], Optional[bytes]]


class Fake:
    """A transport that replays queued responses (the last one repeats) and records the requests."""

    def __init__(self, *responses: Any) -> None:
        self.queue: List[Any] = list(responses)
        self.calls: List[Call] = []

    def __call__(self, method, url, headers, body, timeout, max_bytes):  # noqa: ANN001
        self.calls.append((method, url, dict(headers), body))
        item = self.queue.pop(0) if len(self.queue) > 1 else self.queue[0]
        if isinstance(item, Exception):
            raise item
        return item


def reply(
    status: int = 200, body: Any = None, headers: Optional[Dict[str, str]] = None
) -> Response:
    raw = (
        body
        if isinstance(body, bytes)
        else json.dumps(body if body is not None else {}).encode()
    )
    return Response(status, headers or {}, raw)


def make(*responses: Any, **kwargs: Any) -> Tuple[Client, Fake]:
    fake = Fake(*responses)
    kwargs.setdefault("sleep", lambda _s: None)
    return Client(URL, TOKEN, transport=fake, **kwargs), fake


# ---- configuration and secrets ----------------------------------------------------------------------


def test_requires_an_http_url_and_a_pat_shaped_token(monkeypatch):
    monkeypatch.delenv("URBANFLOW_URL", raising=False)
    with pytest.raises(ConfigurationError):
        Client(None, TOKEN)
    for bad in (
        "ftp://x",
        "https://",
        "https://u:p@host",
        "https://host?x=1",
        "nonsense",
    ):
        with pytest.raises(ConfigurationError):
            Client(bad, TOKEN)
    with pytest.raises(ConfigurationError) as err:
        Client(URL, "not-a-pat-SECRETVALUE")
    assert "SECRETVALUE" not in str(err.value)


def test_credentials_are_refused_over_plain_http_except_loopback():
    with pytest.raises(ConfigurationError, match="plain HTTP"):
        Client("http://example.com", TOKEN)
    Client("http://localhost:8000", TOKEN)
    Client("http://127.0.0.1:8000", TOKEN)
    Client("http://example.com", TOKEN, allow_insecure=True)
    Client("http://example.com")  # no credential, nothing to protect


def test_environment_variables_supply_url_and_token(monkeypatch):
    monkeypatch.setenv("URBANFLOW_URL", URL)
    monkeypatch.setenv("URBANFLOW_TOKEN", TOKEN)
    fake = Fake(reply(200, {"apiVersion": 3}))
    client = Client(transport=fake)
    assert client.capabilities()["apiVersion"] == 3
    assert fake.calls[0][2]["Authorization"] == f"Bearer {TOKEN}"


def test_a_credential_never_shows_in_repr_vars_or_pickles():
    client = Client(URL, TOKEN, api_key=KEY)
    for text in (repr(client), str(client), repr(vars(client))):
        assert TOKEN not in text and KEY not in text and "SECRETSECRET" not in text
    with pytest.raises(TypeError):
        pickle.dumps(client)


def test_headers_carry_the_bearer_token_and_optional_api_key():
    client, fake = make(reply(200, {}), api_key=KEY)
    client.capabilities()
    headers = fake.calls[0][2]
    assert headers["Authorization"] == f"Bearer {TOKEN}" and headers["X-API-Key"] == KEY
    client2, fake2 = make(reply(200, {}))
    client2.capabilities()
    assert "X-API-Key" not in fake2.calls[0][2]


def test_a_call_without_a_token_fails_before_any_request():
    fake = Fake(reply())
    client = Client(URL, "", transport=fake)
    with pytest.raises(ConfigurationError, match="no personal access token"):
        client.capabilities()
    assert fake.calls == []


# ---- requests ---------------------------------------------------------------------------------------


def test_each_method_uses_the_documented_route():
    client, fake = make(reply(200, {"id": "abc", "status": "queued"}))
    client.validate({"a": 1})
    client.submit({"a": 1})
    client.status("abc")
    client.list_experiments(5, 10)
    client.result("abc")
    client.delete("abc")
    client.cancel("abc")
    client.resume("abc")
    client.list_tokens()
    client.revoke_token("pat_1")
    routes = [(m, u.replace(URL, "")) for m, u, _h, _b in fake.calls]
    assert routes == [
        ("POST", "/api/v3/experiments/validate"),
        ("POST", "/api/v3/experiments"),
        ("GET", "/api/v3/experiments/abc"),
        ("GET", "/api/v3/experiments?limit=5&offset=10"),
        ("GET", "/api/v3/experiments/abc/result"),
        ("DELETE", "/api/v3/experiments/abc"),
        ("POST", "/api/v3/experiments/abc/cancel"),
        ("POST", "/api/v3/experiments/abc/resume"),
        ("GET", "/api/v3/tokens"),
        ("DELETE", "/api/v3/tokens/pat_1"),
    ]
    assert json.loads(fake.calls[1][3]) == {"a": 1}


def test_ids_are_validated_not_interpolated():
    client, fake = make(reply())
    for bad in ("../x", "a/b", "", "a b", "x" * 80, "id?x=1"):
        with pytest.raises(ConfigurationError):
            client.status(bad)
    assert fake.calls == []


def test_wait_polls_until_a_terminal_state_and_reports_progress():
    seen: List[str] = []
    client, _fake = make(
        reply(200, {"status": "queued"}),
        reply(200, {"status": "running", "progress": {"fraction": 0.5}}),
        reply(200, {"status": "completed"}),
    )
    final = client.wait(
        "abc", poll_interval=0.01, on_progress=lambda s: seen.append(s["status"])
    )
    assert final["status"] == "completed" and seen == ["queued", "running", "completed"]


def test_wait_times_out_without_cancelling():
    client, fake = make(reply(200, {"status": "running"}))
    with pytest.raises(WaitTimeout) as err:
        client.wait("abc", poll_interval=0.01, timeout=0.0)
    assert err.value.experiment_id == "abc"
    assert all(m == "GET" for m, *_ in fake.calls)  # nothing was cancelled


def test_run_submits_waits_and_fetches_the_result():
    client, _fake = make(
        reply(202, {"id": "abc", "status": "queued"}),
        reply(200, {"status": "completed"}),
        reply(200, {"format": "urbanflow-experiment-result"}),
    )
    result = client.run({"x": 1}, poll_interval=0.01)
    assert result["format"] == "urbanflow-experiment-result"


# ---- packages ---------------------------------------------------------------------------------------


def test_export_writes_exclusively(tmp_path: Path):
    client, _fake = make(
        reply(200, b"PKzip-bytes", {"content-type": "application/zip"})
    )
    target = tmp_path / "x.ufpkg"
    assert client.export_package("abc", target) == b"PKzip-bytes"
    assert target.read_bytes() == b"PKzip-bytes"
    with pytest.raises(ConfigurationError, match="already exists"):
        client.export_package("abc", target)
    client.export_package("abc", target, overwrite=True)


def test_verify_sends_the_raw_bytes_and_enforces_the_size_limit(tmp_path: Path):
    client, fake = make(reply(200, {"internallyConsistent": True}))
    path = tmp_path / "p.ufpkg"
    path.write_bytes(b"abc")
    assert client.verify_package(path)["internallyConsistent"] is True
    assert client.verify_package(b"xyz")["internallyConsistent"] is True
    assert fake.calls[0][3] == b"abc"
    assert fake.calls[0][2]["Content-Type"] == "application/octet-stream"
    with pytest.raises(ConfigurationError):
        client.verify_package(b"0" * (10 * 1024 * 1024 + 1))
    assert len(fake.calls) == 2  # the oversized one never went out


# ---- errors -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status,cls",
    [
        (401, AuthenticationError),
        (403, PermissionDenied),
        (404, NotFound),
        (409, Conflict),
        (413, PayloadTooLarge),
        (422, InvalidRequest),
        (429, QuotaExceeded),
        (500, ServerError),
        (503, ServerError),
        (418, ApiError),
    ],
)
def test_statuses_map_to_exceptions(status, cls):
    client, _ = make(
        reply(status, {"error": {"message": "nope", "code": "X"}}), retries=0
    )
    with pytest.raises(cls) as err:
        client.status("abc")
    assert err.value.status == status and err.value.code == "X"
    assert "nope" in str(err.value) and "GET /api/v3/experiments/abc" in str(err.value)


def test_errors_never_contain_the_token_or_api_key():
    leak = {"error": {"message": f"bad header Bearer {TOKEN} and {KEY}\x1b[31m"}}
    client, _ = make(reply(401, leak), api_key=KEY, retries=0)
    with pytest.raises(AuthenticationError) as err:
        client.capabilities()
    text = str(err.value) + repr(err.value.__dict__)
    assert TOKEN not in text and KEY not in text and "\x1b" not in text


def test_validation_errors_are_listed():
    body = {
        "error": {
            "message": "invalid",
            "details": {"errors": ["a is wrong", "b is wrong"]},
        }
    }
    client, _ = make(reply(422, body))
    with pytest.raises(InvalidRequest) as err:
        client.submit({})
    assert err.value.errors == ["a is wrong", "b is wrong"]


def test_non_json_error_bodies_and_redirects():
    client, _ = make(reply(502, b"<html>bad gateway</html>"), retries=0)
    with pytest.raises(ServerError) as err:
        client.capabilities()
    assert "html" not in str(err.value)
    client, _ = make(reply(302, b"", {"Location": "https://evil.example"}))
    with pytest.raises(ApiError):
        client.capabilities()


def test_reads_are_retried_but_writes_are_not():
    client, fake = make(
        reply(503, {}, {"Retry-After": "1"}),
        reply(503, {}),
        reply(200, {"ok": True}),
        retries=2,
    )
    assert client.capabilities() == {"ok": True} and len(fake.calls) == 3
    client, fake = make(reply(503, {}), reply(200, {}), retries=2)
    with pytest.raises(ServerError):
        client.submit({})
    assert len(fake.calls) == 1


def test_429_carries_retry_after():
    client, _ = make(
        reply(429, {"detail": "slow down"}, {"Retry-After": "7"}), retries=0
    )
    with pytest.raises(QuotaExceeded) as err:
        client.capabilities()
    assert err.value.retry_after == 7.0


def test_transport_failures_propagate_as_typed_errors():
    client, _ = make(RequestTimeout("slow"), retries=0)
    with pytest.raises(RequestTimeout):
        client.capabilities()
    client, _ = make(TransportError("down"), retries=0)
    with pytest.raises(TransportError):
        client.capabilities()


def _serve(handler: type) -> http.server.HTTPServer:
    server = http.server.HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_the_default_transport_does_not_follow_redirects():
    seen: List[str] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            seen.append(self.headers.get("Authorization", ""))
            if self.path == "/start":
                self.send_response(302)
                self.send_header("Location", "/elsewhere")
                self.end_headers()
            else:
                self.send_response(200)
                self.end_headers()

        def log_message(self, *args):  # noqa: ANN002
            pass

    server = _serve(Handler)
    try:
        response = _urllib_transport(
            "GET",
            f"http://127.0.0.1:{server.server_port}/start",
            {"Authorization": f"Bearer {TOKEN}"},
            None,
            5.0,
            1000,
        )
    finally:
        server.shutdown()
    assert response.status == 302
    assert len(seen) == 1  # the redirect target was never contacted


def test_the_default_transport_caps_the_reply_size():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"x" * 5000)

        def log_message(self, *args):  # noqa: ANN002
            pass

    server = _serve(Handler)
    try:
        with pytest.raises(ResponseTooLarge):
            _urllib_transport(
                "GET", f"http://127.0.0.1:{server.server_port}/", {}, None, 5.0, 1000
            )
    finally:
        server.shutdown()


def test_the_default_transport_reports_a_refused_connection():
    with pytest.raises(TransportError):
        _urllib_transport("GET", "http://127.0.0.1:9/", {}, None, 2.0, 1000)


# ---- command line -----------------------------------------------------------------------------------


def test_cli_prints_json_and_returns_exit_codes(tmp_path, capsys):
    client, _ = make(reply(200, {"apiVersion": 3}))
    assert cli.main(["capabilities"], client=client) == 0
    assert json.loads(capsys.readouterr().out) == {"apiVersion": 3}

    client, _ = make(reply(404, {"detail": "Experiment not found"}), retries=0)
    assert cli.main(["status", "abc"], client=client) == 1
    assert "404" in capsys.readouterr().err

    experiment = tmp_path / "e.json"
    experiment.write_text("not json")
    client, _ = make(reply(200, {}))
    assert cli.main(["submit", str(experiment)], client=client) == 2

    package = tmp_path / "p.ufpkg"
    package.write_bytes(b"x")
    client, _ = make(reply(200, {"internallyConsistent": False, "errors": ["bad"]}))
    assert cli.main(["verify", str(package)], client=client) == 1


def test_cli_without_configuration_is_a_usage_error(monkeypatch, capsys):
    monkeypatch.delenv("URBANFLOW_URL", raising=False)
    assert cli.main(["capabilities"]) == 2
    assert "configuration error" in capsys.readouterr().err
