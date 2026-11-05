"""OIDC verification against a mock issuer (no network)."""

import time

import jwt
import pytest
from tenancy_mock_issuer import AUDIENCE, ISSUER, MockIssuer, new_key

from src.tenancy.oidc import (
    JwksUnavailableError,
    OidcConfig,
    OidcVerifier,
    TokenError,
    cognito_config,
)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture(scope="module")
def issuer() -> MockIssuer:
    return MockIssuer()


def make(issuer: MockIssuer, clock: Clock, **cfg: object) -> OidcVerifier:
    issuer.fetches = 0
    issuer.fail = False
    config = OidcConfig(issuer=ISSUER, audience=AUDIENCE, **cfg)  # type: ignore[arg-type]
    return OidcVerifier(config, fetcher=issuer.fetcher, clock=clock)


def reason(verifier: OidcVerifier, token: str) -> str:
    with pytest.raises(TokenError) as info:
        verifier.verify(token)
    return info.value.code


def test_valid_token_returns_claims(issuer: MockIssuer) -> None:
    claims = make(issuer, Clock()).verify(issuer.token(sub="u9"))
    assert claims["sub"] == "u9"
    assert claims["custom:tenant_id"] == "acme"


def test_cognito_config_derives_issuer_and_jwks_url() -> None:
    cfg = cognito_config("eu-west-1", "eu-west-1_abc", "cid")
    assert cfg.issuer == "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_abc"
    assert cfg.keys_url == cfg.issuer + "/.well-known/jwks.json"
    assert cfg.audience == "cid"


@pytest.mark.parametrize(
    "kwargs, code",
    [
        ({"expires_in": -3600}, "expired"),
        ({"not_before_in": 3600}, "not_yet_valid"),
        ({"issuer": "https://evil.example.com/pool"}, "bad_issuer"),
        ({"audience": "someone-else"}, "bad_audience"),
    ],
)
def test_claim_checks_refuse(issuer: MockIssuer, kwargs: dict, code: str) -> None:  # type: ignore[type-arg]
    assert reason(make(issuer, Clock()), issuer.token(**kwargs)) == code


def test_cognito_access_token_client_id_counts_as_audience(issuer: MockIssuer) -> None:
    claims = make(issuer, Clock()).verify(_without_aud(issuer))
    assert claims["client_id"] == AUDIENCE


def _without_aud(issuer: MockIssuer) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": "svc",
            "iss": ISSUER,
            "client_id": AUDIENCE,
            "token_use": "access",
            "exp": now + 600,
        },
        issuer.keys["kid-1"],
        algorithm="RS256",
        headers={"kid": "kid-1"},
    )


def test_require_nbf_option(issuer: MockIssuer) -> None:
    verifier = make(issuer, Clock(), require_nbf=True)
    assert reason(verifier, issuer.token()) == "invalid"
    assert verifier.verify(issuer.token(not_before_in=-5))["sub"] == "user-1"


def test_signature_from_another_key_is_refused(issuer: MockIssuer) -> None:
    forged = issuer.token(signing_key=new_key(), kid="kid-1")
    assert reason(make(issuer, Clock()), forged) == "invalid"


def test_hs256_with_public_key_as_secret_is_refused(issuer: MockIssuer) -> None:
    """Algorithm confusion: only RS256 is ever accepted."""
    token = jwt.encode(
        {"sub": "x", "iss": ISSUER, "aud": AUDIENCE, "exp": 4102444800},
        "s" * 40,
        algorithm="HS256",
        headers={"kid": "kid-1"},
    )
    assert reason(make(issuer, Clock()), token) == "bad_algorithm"


def test_alg_none_is_refused(issuer: MockIssuer) -> None:
    token = jwt.encode({"sub": "x"}, None, algorithm="none", headers={"kid": "kid-1"})
    assert reason(make(issuer, Clock()), token) == "bad_algorithm"


def test_garbage_and_missing_kid(issuer: MockIssuer) -> None:
    verifier = make(issuer, Clock())
    assert reason(verifier, "not-a-jwt") == "malformed"
    no_kid = jwt.encode(
        {"sub": "x", "iss": ISSUER, "aud": AUDIENCE, "exp": 4102444800},
        issuer.keys["kid-1"],
        algorithm="RS256",
    )
    assert reason(verifier, no_kid) == "missing_kid"


def test_jwks_is_cached_between_verifications(issuer: MockIssuer) -> None:
    verifier = make(issuer, Clock())
    for _ in range(5):
        verifier.verify(issuer.token())
    assert issuer.fetches == 1


def test_key_rotation_new_kid_triggers_refetch_after_cooldown() -> None:
    issuer, clock = MockIssuer(), Clock()
    verifier = make(issuer, clock, jwks_refresh_cooldown_seconds=60.0)
    old = issuer.token()
    verifier.verify(old)
    issuer.rotate("kid-2", keep_old=False)
    new = issuer.token()
    clock.now += 61
    assert verifier.verify(new)["sub"] == "user-1"
    assert issuer.fetches == 2
    # the withdrawn key stops verifying once the set was refreshed
    assert reason(verifier, old) == "unknown_kid"


def test_unknown_kids_cannot_force_a_fetch_per_request() -> None:
    issuer, clock = MockIssuer(), Clock()
    verifier = make(issuer, clock, jwks_refresh_cooldown_seconds=60.0)
    verifier.verify(issuer.token())
    key = new_key()
    for i in range(10):
        token = jwt.encode(
            {"sub": "x"}, key, algorithm="RS256", headers={"kid": f"made-up-{i}"}
        )
        assert reason(verifier, token) == "unknown_kid"
    assert issuer.fetches <= 2  # first load, plus at most one refetch


def test_stale_set_is_refetched_after_ttl() -> None:
    issuer, clock = MockIssuer(), Clock()
    verifier = make(issuer, clock, jwks_ttl_seconds=100.0)
    verifier.verify(issuer.token())
    clock.now += 101
    verifier.verify(issuer.token())
    assert issuer.fetches == 2


def test_fetch_failure_keeps_last_good_keys() -> None:
    issuer, clock = MockIssuer(), Clock()
    verifier = make(issuer, clock, jwks_ttl_seconds=100.0)
    verifier.verify(issuer.token())
    issuer.fail = True
    clock.now += 101
    assert verifier.verify(issuer.token())["sub"] == "user-1"


def test_cold_start_with_unreachable_issuer_raises() -> None:
    issuer = MockIssuer()
    verifier = make(issuer, Clock())
    issuer.fail = True
    with pytest.raises(JwksUnavailableError):
        verifier.verify(issuer.token())
