"""A local OIDC issuer for tests: generates RSA keys, publishes them as a JWKS
(through an injectable fetcher, so there is no network) and signs tokens."""

import time
from typing import Any, Dict, List, Mapping, Optional

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

ISSUER = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TESTPOOL"
AUDIENCE = "test-client-id"


def new_key() -> RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class MockIssuer:
    def __init__(self, issuer: str = ISSUER, audience: str = AUDIENCE) -> None:
        self.issuer = issuer
        self.audience = audience
        self.keys: Dict[str, RSAPrivateKey] = {"kid-1": new_key()}
        self.fetches = 0
        self.fail = False

    # -- the JWKS endpoint ------------------------------------------------
    def jwks(self) -> Dict[str, List[Dict[str, Any]]]:
        keys = []
        for kid, key in self.keys.items():
            jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
            keys.append({**jwk, "kid": kid, "use": "sig", "alg": "RS256"})
        return {"keys": keys}

    def fetcher(self, url: str) -> Mapping[str, Any]:
        self.fetches += 1
        if self.fail:
            raise OSError("jwks endpoint down")
        return self.jwks()

    def rotate(self, new_kid: str, *, keep_old: bool = False) -> None:
        old = self.keys if keep_old else {}
        self.keys = {**old, new_kid: new_key()}

    # -- tokens -------------------------------------------------------------
    def token(
        self,
        *,
        sub: str = "user-1",
        tenant: Optional[str] = "acme",
        groups: Optional[List[str]] = None,
        kid: Optional[str] = None,
        expires_in: int = 3600,
        not_before_in: Optional[int] = None,
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
        signing_key: Optional[RSAPrivateKey] = None,
    ) -> str:
        now = int(time.time())
        claims: Dict[str, Any] = {
            "sub": sub,
            "iss": issuer or self.issuer,
            "aud": audience or self.audience,
            "iat": now,
            "exp": now + expires_in,
            "email": f"{sub}@example.com",
            "cognito:groups": ["analyst"] if groups is None else groups,
        }
        if tenant is not None:
            claims["custom:tenant_id"] = tenant
        if not_before_in is not None:
            claims["nbf"] = now + not_before_in
        claims.update(extra or {})
        use_kid = kid or next(reversed(self.keys))
        key = signing_key or self.keys[use_kid]
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": use_kid})
