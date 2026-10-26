"""Client identity for the rate limiters: X-Real-IP only from a TRUSTED_PROXY_IPS peer."""

from typing import Optional

import pytest
from fastapi import HTTPException, Request

from src.api import request_limits


def _proxied(peer: str, real_ip: Optional[str] = None) -> Request:
    headers = [(b"x-real-ip", real_ip.encode())] if real_ip is not None else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


def _trust(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setattr(
        request_limits, "TRUSTED_PROXY_NETWORKS", request_limits.parse_trusted_proxies(raw)
    )


def test_empty_allowlist_ignores_x_real_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    _trust(monkeypatch, "")
    assert request_limits.client_key(_proxied("172.18.0.5", "198.51.100.9")) == (
        "172.18.0.5"
    )


def test_untrusted_peer_cannot_forge_x_real_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    _trust(monkeypatch, "172.18.0.0/16")
    assert request_limits.client_key(_proxied("203.0.113.7", "198.51.100.9")) == (
        "203.0.113.7"
    )


def test_trusted_peer_x_real_ip_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    _trust(monkeypatch, "172.18.0.0/16")
    assert request_limits.client_key(_proxied("172.18.0.5", "198.51.100.9")) == (
        "198.51.100.9"
    )


@pytest.mark.parametrize(
    "real_ip", [None, "", "not-an-ip", "198.51.100.9, 10.0.0.1", "198.51.100.9:80"]
)
def test_trusted_peer_with_bad_x_real_ip_falls_back_to_the_peer(
    monkeypatch: pytest.MonkeyPatch, real_ip: Optional[str]
) -> None:
    _trust(monkeypatch, "172.18.0.5")
    assert request_limits.client_key(_proxied("172.18.0.5", real_ip)) == "172.18.0.5"


def test_x_forwarded_for_is_never_trusted(monkeypatch: pytest.MonkeyPatch) -> None:
    _trust(monkeypatch, "172.18.0.5")
    request = Request(
        {
            "type": "http",
            "headers": [(b"x-forwarded-for", b"198.51.100.9")],
            "client": ("172.18.0.5", 1),
        }
    )
    assert request_limits.client_key(request) == "172.18.0.5"


def test_ipv4_ipv6_and_cidr_matching(monkeypatch: pytest.MonkeyPatch) -> None:
    _trust(monkeypatch, "10.1.2.3, 192.168.0.0/24, fd00::/8, 2001:db8::1")
    key = request_limits.client_key
    assert key(_proxied("10.1.2.3", "198.51.100.1")) == "198.51.100.1"
    assert key(_proxied("192.168.0.200", "198.51.100.2")) == "198.51.100.2"
    assert key(_proxied("fd12::1", "2001:db8:ffff::5")) == "2001:db8:ffff::5"
    assert key(_proxied("2001:db8::1", "198.51.100.3")) == "198.51.100.3"
    assert key(_proxied("::ffff:10.1.2.3", "198.51.100.4")) == "198.51.100.4"
    # Outside every configured range: header ignored.
    assert key(_proxied("10.1.2.4", "198.51.100.5")) == "10.1.2.4"
    assert key(_proxied("192.168.1.1", "198.51.100.6")) == "192.168.1.1"
    assert key(_proxied("2001:db8::2", "198.51.100.7")) == "2001:db8::2"


def test_non_ip_peer_is_never_trusted(monkeypatch: pytest.MonkeyPatch) -> None:
    _trust(monkeypatch, "0.0.0.0/0")
    assert request_limits.client_key(_proxied("not-an-ip", "198.51.100.9")) == (
        "not-an-ip"
    )


@pytest.mark.parametrize("raw", ["300.1.1.1", "10.0.0.0/33", "abc", "10.0.0.1;10.0.0.2"])
def test_invalid_trusted_proxy_config_is_rejected(raw: str) -> None:
    with pytest.raises(ValueError, match="TRUSTED_PROXY_IPS entry 1"):
        request_limits.parse_trusted_proxies(raw)


def test_trusted_proxy_default_is_empty() -> None:
    assert request_limits.parse_trusted_proxies("") == ()
    assert request_limits.parse_trusted_proxies(" , ") == ()


def test_both_limiters_share_one_resolution_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.api.auth as auth

    # The auth limiter uses the very same function as compute_slot.
    assert auth.client_key is request_limits.client_key

    _trust(monkeypatch, "")
    # Compute slots: rotating a forged X-Real-IP from one peer is still one client.
    first = request_limits.compute_slot(_proxied("203.0.113.7", "198.51.100.1"))
    next(first)
    try:
        with pytest.raises(HTTPException) as err:
            next(request_limits.compute_slot(_proxied("203.0.113.7", "198.51.100.2")))
        assert err.value.status_code == 429
    finally:
        first.close()

    # Auth failures: rotating X-Real-IP does not escape the failure counter.
    auth.reset_auth_failures()
    try:
        for i in range(auth.MAX_AUTH_FAILURES):
            auth.record_auth_failure(
                request_limits.client_key(_proxied("203.0.113.7", f"198.51.100.{i}"))
            )
        assert auth.is_auth_rate_limited(
            request_limits.client_key(_proxied("203.0.113.7", "198.51.100.200"))
        )
    finally:
        auth.reset_auth_failures()
