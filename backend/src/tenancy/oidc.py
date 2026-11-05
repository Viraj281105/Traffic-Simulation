"""OIDC token verification against a JWKS (RS256 only).

Checks signature, ``iss``, audience, ``exp`` and ``nbf``. Signing keys are
found by ``kid`` in a cached JWKS; an unknown ``kid`` triggers one refetch
(rotation), rate-limited by a cooldown so made-up kids cannot turn requests
into fetches. The JWKS is fetched through an injectable ``fetcher`` so tests
never touch the network.

Works with a Cognito-style issuer (``cognito_config``): Cognito ID tokens carry
the app client in ``aud``, access tokens carry it in ``client_id``; both are
accepted as the audience.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

import jwt

ALLOWED_ALGORITHMS: Tuple[str, ...] = ("RS256",)

JwksFetcher = Callable[[str], Mapping[str, Any]]


class TokenError(Exception):
    """A token that must be refused. ``code`` is a stable machine reason;
    the message is safe to show a client."""

    def __init__(self, code: str, message: str = "Invalid or expired token") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class JwksUnavailableError(Exception):
    """The key set could not be fetched and no key is cached."""


@dataclass(frozen=True)
class OidcConfig:
    issuer: str
    audience: str
    jwks_url: str = ""
    leeway_seconds: int = 30
    require_nbf: bool = False
    jwks_ttl_seconds: float = 3600.0
    jwks_refresh_cooldown_seconds: float = 60.0

    @property
    def keys_url(self) -> str:
        return self.jwks_url or self.issuer.rstrip("/") + "/.well-known/jwks.json"


def cognito_config(region: str, user_pool_id: str, client_id: str) -> OidcConfig:
    """The OIDC settings of an Amazon Cognito user pool."""
    return OidcConfig(
        issuer=f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}",
        audience=client_id,
    )


def fetch_jwks_http(url: str) -> Mapping[str, Any]:
    """Default fetcher: HTTPS GET of the JWKS document (``requests`` is
    pinned in requirements.txt). Not used in tests."""
    if not url.startswith("https://"):
        raise JwksUnavailableError("JWKS URL must be https")
    import requests

    response = requests.get(url, timeout=10)
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise JwksUnavailableError("JWKS document is not an object")
    return body


class JwksCache:
    """Signing keys by ``kid``, refetched when stale or when a kid is unknown."""

    def __init__(
        self,
        url: str,
        fetcher: JwksFetcher = fetch_jwks_http,
        *,
        ttl_seconds: float = 3600.0,
        refresh_cooldown_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._url = url
        self._fetcher = fetcher
        self._ttl = ttl_seconds
        self._cooldown = refresh_cooldown_seconds
        self._clock = clock
        self._keys: Dict[str, Any] = {}
        self._fetched_at: Optional[float] = None
        self._attempted_at: Optional[float] = None
        self._lock = threading.Lock()
        self.fetch_count = 0

    def _refetch(self) -> None:
        self._attempted_at = self._clock()
        self.fetch_count += 1
        try:
            document = self._fetcher(self._url)
            raw_keys = document.get("keys", [])
            parsed: Dict[str, Any] = {}
            if isinstance(raw_keys, list):
                for jwk in raw_keys:
                    if not isinstance(jwk, dict):
                        continue
                    kid, kty = jwk.get("kid"), jwk.get("kty")
                    if not isinstance(kid, str) or kty != "RSA":
                        continue
                    if jwk.get("use", "sig") != "sig":
                        continue
                    try:
                        parsed[kid] = jwt.PyJWK(jwk).key
                    except Exception:  # a malformed key must not poison the set
                        continue
        except Exception as exc:
            if not self._keys:
                raise JwksUnavailableError("JWKS could not be fetched") from exc
            return  # keep the last good set rather than lock everyone out
        self._keys = parsed
        self._fetched_at = self._clock()

    def get_key(self, kid: str) -> Any:
        with self._lock:
            now = self._clock()
            stale = self._fetched_at is None or now - self._fetched_at >= self._ttl
            if stale or kid not in self._keys:
                cooled = (
                    self._attempted_at is None
                    or now - self._attempted_at >= self._cooldown
                )
                if cooled:
                    self._refetch()
            key = self._keys.get(kid)
        if key is None:
            raise TokenError("unknown_kid")
        return key


@dataclass
class OidcVerifier:
    config: OidcConfig
    fetcher: JwksFetcher = fetch_jwks_http
    clock: Callable[[], float] = time.monotonic
    jwks: JwksCache = field(init=False)

    def __post_init__(self) -> None:
        self.jwks = JwksCache(
            self.config.keys_url,
            self.fetcher,
            ttl_seconds=self.config.jwks_ttl_seconds,
            refresh_cooldown_seconds=self.config.jwks_refresh_cooldown_seconds,
            clock=self.clock,
        )

    def verify(self, token: str) -> Dict[str, Any]:
        """Return the verified claims or raise ``TokenError``."""
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise TokenError("malformed") from exc
        if header.get("alg") not in ALLOWED_ALGORITHMS:
            raise TokenError("bad_algorithm")
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise TokenError("missing_kid")
        key = self.jwks.get_key(kid)
        required: List[str] = ["exp", "iss", "sub"]
        if self.config.require_nbf:
            required.append("nbf")
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=list(ALLOWED_ALGORITHMS),
                issuer=self.config.issuer,
                leeway=self.config.leeway_seconds,
                options={"verify_aud": False, "require": required},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenError("expired", "Token expired") from exc
        except jwt.ImmatureSignatureError as exc:
            raise TokenError("not_yet_valid") from exc
        except jwt.InvalidIssuerError as exc:
            raise TokenError("bad_issuer") from exc
        except jwt.PyJWTError as exc:
            raise TokenError("invalid") from exc
        if not _audience_ok(claims, self.config.audience):
            raise TokenError("bad_audience")
        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub:
            raise TokenError("invalid")
        return dict(claims)


def _audience_ok(claims: Mapping[str, Any], audience: str) -> bool:
    aud = claims.get("aud")
    if isinstance(aud, str) and aud == audience:
        return True
    if isinstance(aud, list) and audience in aud:
        return True
    return claims.get("client_id") == audience  # Cognito access tokens
