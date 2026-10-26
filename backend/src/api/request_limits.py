"""Limits on what one request may ask of the server.

* a request-body size cap for the stateless ``/api/v2`` compute endpoints;
* shared pagination and study-duration bounds;
* a cap on concurrent synchronous simulations (``compute_slot``).

Body size:

FastAPI reads the whole body into memory before any route dependency runs,
so a dependency cannot stop an oversized upload; this is plain ASGI
middleware instead. It refuses a declared ``Content-Length`` over the cap
before reading anything, and counts a body sent without one (chunked) as it
arrives, refusing it as soon as it passes the cap.
"""

from __future__ import annotations

import ipaddress
import json
import os
import threading
from datetime import datetime, timezone
from typing import (
    Annotated,
    Any,
    Awaitable,
    Callable,
    Dict,
    Iterator,
    MutableMapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from fastapi import HTTPException, Query, Request

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

# 1 MiB. The largest real documents these endpoints take (a network with
# inline junction scenarios, a planning study with every alternative) are a
# few tens of kilobytes; tests/api/test_request_limits.py pins that margin.
MAX_V2_BODY_BYTES = 1024 * 1024

# Stateless compute that is cheap per request but takes arbitrary documents.
LIMITED_PREFIXES: Sequence[str] = (
    "/api/v2/networks",
    "/api/v2/planning/validate",
    "/api/v3/experiments",
)


class _TooLarge(HTTPException):
    """Raised from ``receive``: FastAPI re-raises an HTTPException met while
    reading the body, so the app's own handler answers 413 in the usual
    error envelope."""

    def __init__(self, limit: int) -> None:
        super().__init__(
            status_code=413, detail=f"Request body exceeds the {limit}-byte limit"
        )


def _error_body(limit: int) -> bytes:
    # Same envelope as main.http_exception_handler.
    return json.dumps(
        {
            "error": {
                "code": "PAYLOAD_TOO_LARGE",
                "message": f"Request body exceeds the {limit}-byte limit",
                "details": None,
                "timestamp": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
            }
        }
    ).encode("utf-8")


async def _send_413(send: Send, limit: int) -> None:
    body = _error_body(limit)
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class BodySizeLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        max_bytes: int = MAX_V2_BODY_BYTES,
        prefixes: Sequence[str] = LIMITED_PREFIXES,
    ) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.prefixes = tuple(prefixes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not str(scope.get("path", "")).startswith(
            self.prefixes
        ):
            await self.app(scope, receive, send)
            return

        headers: Dict[bytes, bytes] = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                too_large = int(declared) > self.max_bytes
            except ValueError:
                too_large = False  # malformed: let the server reject it
            if too_large:
                await _send_413(send, self.max_bytes)
                return

        received = 0
        started = False

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _TooLarge(self.max_bytes)
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _TooLarge:
            if not started:
                await _send_413(send, self.max_bytes)


# ── Query and workload bounds shared by routers ───────────────────────────
# Moved from main.py so the routers split out of it share one definition.

# Pagination for the history/sweep/replay listings. The values go straight
# into SQL "LIMIT ? OFFSET ?", where SQLite reads a negative LIMIT as "no
# limit": ?limit=-1 dumped the entire table, sweep result blobs included, in
# one response.
MAX_PAGE_SIZE = 500
PageLimit = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
PageOffset = Annotated[int, Query(ge=0)]


# ── Synchronous compute gate ──────────────────────────────────────────────
# Several endpoints run whole simulations inside the request (the synchronous
# study endpoints, run reproduction, calibration and planning /run). Each holds
# one of the server's worker threads until it finishes, which can be minutes,
# and the browser proxy makes them reachable without signing in. Unbounded, a
# few dozen concurrent requests starve every synchronous route, /health
# included. The background-job endpoints have their own caps
# (study/jobs.py, planning/service.py); this bounds the synchronous ones, and a
# request that finds every slot busy is refused at once with 429 rather than
# queued behind work it cannot see. Simulation is CPU-bound Python, so more
# concurrent runs than this only slow every run down.
MAX_SYNC_COMPUTE_REQUESTS = 2
# One client may hold only one of those slots, so a single client cannot take
# both and lock everyone else out. A "client" is the socket peer, except when
# the peer is a configured trusted proxy (TRUSTED_PROXY_IPS): then it is the
# address that proxy reports in X-Real-IP (see client_key). Clients behind one
# NAT share a key.
MAX_SYNC_COMPUTE_PER_CLIENT = 1

_IPNetwork = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]


def parse_trusted_proxies(raw: str) -> Tuple[_IPNetwork, ...]:
    """Parse a comma-separated list of IP addresses and CIDRs.

    Raises ValueError (naming the entry's position, not its text) on any invalid
    entry, so a typo stops startup instead of silently trusting a wider or
    different range than intended.
    """
    networks = []
    for position, entry in enumerate(raw.split(","), start=1):
        entry = entry.strip()
        if not entry:
            continue
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            raise ValueError(
                f"TRUSTED_PROXY_IPS entry {position} is not an IP address or CIDR"
            ) from None
    return tuple(networks)


# Empty by default: no forwarding header is trusted. Read once at import, like
# the other deployment settings; an invalid value raises and stops startup.
TRUSTED_PROXY_NETWORKS: Tuple[_IPNetwork, ...] = parse_trusted_proxies(
    os.getenv("TRUSTED_PROXY_IPS", "")
)

_compute_slots = threading.BoundedSemaphore(MAX_SYNC_COMPUTE_REQUESTS)
_clients_lock = threading.Lock()
_running_per_client: Dict[str, int] = {}


def _parse_ip(value: str) -> Optional[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """A single IP address (IPv4-mapped IPv6 folded to IPv4), else None."""
    try:
        ip = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def client_key(request: Request) -> str:
    """The client a request is counted against.

    The socket peer, unless the peer is inside TRUSTED_PROXY_IPS; only then is
    X-Real-IP honoured, and only when it is one valid IP address (not a chain,
    not text). A missing or malformed value from a trusted proxy falls back to
    the proxy's own address. X-Forwarded-For is never consulted. Used by both
    the failed-authentication limiter and ``compute_slot``.
    """
    peer_host = request.client.host if request.client else ""
    peer = _parse_ip(peer_host)
    if peer is None:
        return peer_host or "unknown"
    if any(peer in net for net in TRUSTED_PROXY_NETWORKS):
        forwarded = _parse_ip(request.headers.get("x-real-ip") or "")
        if forwarded is not None:
            return str(forwarded)
    return str(peer)


def compute_slot(request: Request) -> Iterator[None]:
    """FastAPI dependency: hold one synchronous-compute slot for the request."""
    key = client_key(request)
    with _clients_lock:
        if _running_per_client.get(key, 0) >= MAX_SYNC_COMPUTE_PER_CLIENT:
            raise HTTPException(
                status_code=429,
                detail=(
                    "A simulation you started is still running; wait for it to "
                    "finish, or use the background-job endpoint"
                ),
            )
        if not _compute_slots.acquire(blocking=False):
            raise HTTPException(
                status_code=429,
                detail=(
                    f"The server is already running {MAX_SYNC_COMPUTE_REQUESTS} "
                    "simulations for other requests; try again shortly, or use "
                    "the background-job endpoint"
                ),
            )
        _running_per_client[key] = _running_per_client.get(key, 0) + 1
    try:
        yield
    finally:
        with _clients_lock:
            remaining = _running_per_client[key] - 1
            if remaining:
                _running_per_client[key] = remaining
            else:
                del _running_per_client[key]
        _compute_slots.release()
