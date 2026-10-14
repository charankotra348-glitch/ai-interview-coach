import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from pydantic import SecretStr, ValidationError

from app.auth import tokens
from app.auth.passwords import hash_password, verify_password
from app.auth.tokens import InvalidToken, create_access_token, decode_access_token
from app.config import Settings, settings
from tests.timing import measure_ms, percentile

PASSWORD = "correct horse battery staple"
USER_ID = uuid.uuid4()


# --- passwords ---------------------------------------------------------------------

def test_hash_is_argon2id_with_production_settings():
    hashed = hash_password(PASSWORD)
    assert hashed.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    assert PASSWORD not in hashed
    assert hash_password(PASSWORD) != hashed       # a fresh random salt every time


def test_verify_accepts_only_the_right_password():
    hashed = hash_password(PASSWORD)
    assert verify_password(PASSWORD, hashed)
    assert not verify_password(PASSWORD + "!", hashed)


@pytest.mark.parametrize("stored", [None, "", "!"])  # no account, or the old dev user
def test_missing_or_unusable_hash_never_matches(stored):
    assert not verify_password(PASSWORD, stored)


def test_unknown_account_costs_the_same_as_a_real_check():
    """Login time must not reveal whether an email is registered."""
    hashed = hash_password(PASSWORD)
    real = percentile(measure_ms(lambda: verify_password("wrong password!", hashed), runs=10, warmup=1), 0.5)
    fake = percentile(measure_ms(lambda: verify_password("wrong password!", None), runs=10, warmup=1), 0.5)
    print(f"\nverify p50: real account {real:.0f} ms, unknown account {fake:.0f} ms")
    assert 0.5 < fake / real < 2


# --- tokens ------------------------------------------------------------------------

def claims(**overrides):
    now = datetime.now(timezone.utc)
    base = {"sub": str(USER_ID), "iat": now, "exp": now + timedelta(minutes=5),
            "iss": tokens.ISSUER, "aud": tokens.AUDIENCE, "type": "access"}
    return {**base, **overrides}


def sign(payload, secret=None, algorithm="HS256"):
    return jwt.encode(payload, secret or settings.jwt_secret.get_secret_value(), algorithm=algorithm)


def test_token_round_trip():
    token, expires_in = create_access_token(USER_ID)
    assert decode_access_token(token) == USER_ID
    assert expires_in == settings.jwt_ttl_minutes * 60


def test_expired_token_is_rejected():
    token, _ = create_access_token(USER_ID, now=datetime.now(timezone.utc) - timedelta(days=1))
    with pytest.raises(InvalidToken):
        decode_access_token(token)


@pytest.mark.parametrize("token", [
    sign(claims(), secret="another-secret-that-is-long-enough-123"),   # forged signature
    sign(claims(aud="some-other-api")),                                 # meant for another service
    sign(claims(iss="someone-else")),                                   # issued by someone else
    sign(claims(type="refresh")),                                       # not an access token
    sign(claims(sub="not-a-uuid")),
    sign({k: v for k, v in claims().items() if k != "exp"}),            # never expires
    jwt.encode(claims(), key=None, algorithm="none"),                   # unsigned
    "not.a.token",
    "",
])
def test_bad_tokens_are_rejected(token):
    with pytest.raises(InvalidToken):
        decode_access_token(token)


def test_tampered_token_is_rejected():
    token, _ = create_access_token(USER_ID)
    header, payload, signature = token.split(".")
    other, _ = create_access_token(uuid.uuid4())
    with pytest.raises(InvalidToken):
        decode_access_token(".".join([header, other.split(".")[1], signature]))


# --- the signing secret ---------------------------------------------------------------

def test_production_refuses_to_start_without_a_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET must be set"):
        Settings(environment="production", jwt_secret=None, _env_file=None)


def test_short_secret_is_refused():
    with pytest.raises(ValidationError, match="at least 32"):
        Settings(environment="production", jwt_secret=SecretStr("too-short"), _env_file=None)


def test_development_gets_a_random_secret_when_none_is_set():
    a = Settings(environment="local", jwt_secret=None, _env_file=None)
    b = Settings(environment="local", jwt_secret=None, _env_file=None)
    assert len(a.jwt_secret.get_secret_value()) >= 32
    assert a.jwt_secret.get_secret_value() != b.jwt_secret.get_secret_value()