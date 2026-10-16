"""WebSocket handshakes from other sites' pages are refused (src/api/ws_origin.py).

CORS does not cover WebSockets and the browser sends the visitor's cookies,
so without this a page on another site could open /ws/simulation/live and
watch the visitor's own live run.
"""

from typing import Any, Optional

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.api.ws_origin import origin_allowed
from src.main import app

DEV = ["http://localhost:5173", "http://127.0.0.1:5173"]


@pytest.mark.parametrize(
    "origin,host,allowed",
    [
        (None, "anything", True),  # not a browser
        ("https://urbanflow.example", "urbanflow.example", True),  # via nginx
        ("http://urbanflow.example:8080", "urbanflow.example", True),  # custom port
        ("https://URBANFLOW.example", "urbanflow.example:443", True),
        ("http://localhost:5173", "backend:8000", True),  # Vite proxy
        ("http://localhost:5173/", "backend:8000", True),
        ("https://evil.example", "urbanflow.example", False),
        ("https://urbanflow.example.evil.example", "urbanflow.example", False),
        ("null", "urbanflow.example", False),  # sandboxed iframe / file://
        ("", "urbanflow.example", False),
        ("https://evil.example", None, False),
        ("http://[::1]:5173", "[::1]:8000", True),
    ],
)
def test_origin_rule(origin: Optional[str], host: Optional[str], allowed: bool) -> None:
    assert origin_allowed(origin, host, DEV) is allowed


def test_wildcard_cors_allows_any_origin() -> None:
    assert origin_allowed("https://evil.example", "a.example", ["*"])


ROUTES = ["/ws/simulation/live", "/ws/simulation/dual", "/ws/v1/stream?simulationId=x"]


@pytest.mark.parametrize("path", ROUTES)
def test_a_foreign_page_cannot_open_a_stream(path: str) -> None:
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as closed:
        with client.websocket_connect(path, headers={"Origin": "https://evil.example"}):
            pass
    assert closed.value.code == 1008


def _first_frame_or_close(path: str, headers: dict[str, str]) -> Any:
    client = TestClient(app)
    try:
        with client.websocket_connect(path, headers=headers) as ws:
            return ws.receive_json()
    except WebSocketDisconnect as exc:
        return exc


def test_same_site_and_dev_pages_still_connect() -> None:
    # The live stream sends a frame right away; it is accepted, not refused.
    for headers in (
        {"Origin": "http://testserver"},
        {"Origin": "http://localhost:5173"},
        {},
    ):
        frame = _first_frame_or_close("/ws/simulation/live", headers)
        assert not isinstance(frame, WebSocketDisconnect), headers
