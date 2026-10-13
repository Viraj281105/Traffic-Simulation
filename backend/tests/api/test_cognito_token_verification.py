"""The production token path of src/auth.py ``verify_token``, end to end.

Every other test either overrides the identity dependencies or uses the dev
bypass, so the Cognito branch -- find the key by ``kid``, check the RS256
signature, expiry and audience -- was only ever exercised with an empty key
set. Here a locally generated RSA key stands in for the user pool's JWKS, and
the classic forgeries are tried against it.
"""

import base64
import time
from typing import Any, Dict

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

import src.auth as auth

CLIENT = "test-client-id"
KID = "test-kid"


def _b64(n: int) -> str:
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _key() -> Any:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _pem(key: Any) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def _jwk(key: Any, kid: str = KID) -> Dict[str, str]:
    numbers = key.public_key().public_numbers()
    return {
        "kty": "RSA",
        "alg": "RS256",
        "use": "sig",
        "kid": kid,
        "n": _b64(numbers.n),
        "e": _b64(numbers.e),
    }


POOL_KEY = _key()


@pytest.fixture(autouse=True)
def pool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "USER_POOL_ID", "eu-west-1_TESTPOOL")
    monkeypatch.setattr(auth, "CLIENT_ID", CLIENT)
    monkeypatch.setattr(auth, "get_jwks", lambda: [_jwk(POOL_KEY)])
    monkeypatch.delenv("DEV_AUTH_BYPASS", raising=False)


def _claims(**extra: Any) -> Dict[str, Any]:
    return {
        "sub": "user-123",
        "email": "user@example.com",
        "email_verified": True,
        "aud": CLIENT,
        "token_use": "id",
        "exp": int(time.time()) + 600,
        **extra,
    }


def _sign(claims: Dict[str, Any], key: Any = POOL_KEY, kid: str = KID) -> str:
    return jwt.encode(claims, _pem(key), algorithm="RS256", headers={"kid": kid})


def _verify(token: str) -> Dict[str, Any]:
    return auth.verify_token(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    )


def _refused(token: str) -> None:
    with pytest.raises(HTTPException) as err:
        _verify(token)
    assert err.value.status_code == 401


def test_a_valid_pool_token_is_accepted() -> None:
    claims = _verify(_sign(_claims()))
    assert claims["sub"] == "user-123"
    assert auth.get_current_user_id(claims) == "user-123"
    # Access tokens carry client_id instead of aud.
    access = _claims(client_id=CLIENT, token_use="access")
    del access["aud"]
    assert _verify(_sign(access))["sub"] == "user-123"


def test_expired_and_wrong_audience_tokens_are_refused() -> None:
    _refused(_sign(_claims(exp=int(time.time()) - 1)))
    _refused(_sign(_claims(aud="another-app")))
    no_exp = _claims()
    del no_exp["exp"]
    _refused(_sign(no_exp))


def test_a_token_signed_by_another_key_is_refused() -> None:
    _refused(_sign(_claims(), key=_key()))  # same kid, wrong key
    _refused(_sign(_claims(), kid="unknown-kid"))


def test_a_tampered_payload_is_refused() -> None:
    header, payload, signature = _sign(_claims()).split(".")
    forged_payload = (
        base64.urlsafe_b64encode(
            jwt.get_unverified_claims(_sign(_claims(sub="admin"))).__repr__().encode()
        )
        .rstrip(b"=")
        .decode()
    )
    _refused(".".join((header, forged_payload, signature)))
    other = _sign(_claims(sub="someone-else")).split(".")[1]
    _refused(".".join((header, other, signature)))


def test_algorithm_confusion_and_unsigned_tokens_are_refused() -> None:
    public_pem = POOL_KEY.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    # HS256 "signed" with the public key as the HMAC secret.
    header = base64.urlsafe_b64encode(
        b'{"alg":"HS256","typ":"JWT","kid":"' + KID.encode() + b'"}'
    ).rstrip(b"=")
    body = _sign(_claims()).split(".")[1].encode()
    import hashlib
    import hmac

    mac = hmac.new(public_pem, header + b"." + body, hashlib.sha256).digest()
    hs = b".".join((header, body, base64.urlsafe_b64encode(mac).rstrip(b"=")))
    _refused(hs.decode())
    # alg "none", empty signature.
    none_header = base64.urlsafe_b64encode(
        b'{"alg":"none","typ":"JWT","kid":"' + KID.encode() + b'"}'
    ).rstrip(b"=")
    _refused((none_header + b"." + body + b".").decode())


def test_malformed_tokens_are_refused() -> None:
    for token in ("garbage", "a.b", "a.b.c", "....", "e30.e30.e30"):
        _refused(token)


def test_hs256_signed_with_the_der_public_key_is_refused() -> None:
    """CVE-2026-85394: python-jose <= 3.5.0 accepts a DER public key as an
    HMAC secret. verify_token never lets the token choose the algorithm."""
    import hashlib
    import hmac

    der = POOL_KEY.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    header = base64.urlsafe_b64encode(
        b'{"alg":"HS256","typ":"JWT","kid":"' + KID.encode() + b'"}'
    ).rstrip(b"=")
    body = _sign(_claims()).split(".")[1].encode()
    mac = hmac.new(der, header + b"." + body, hashlib.sha256).digest()
    _refused(
        b".".join((header, body, base64.urlsafe_b64encode(mac).rstrip(b"="))).decode()
    )
