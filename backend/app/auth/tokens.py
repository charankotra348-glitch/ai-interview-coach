"""Short-lived JWT access tokens, signed with HS256. See docs/decisions/005."""
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings

ALGORITHM = "HS256"
ISSUER = "ai-interview-coach"
AUDIENCE = "ai-interview-coach-api"
REQUIRED_CLAIMS = ["sub", "exp", "iat", "iss", "aud"]


class InvalidToken(Exception):
    pass


def _secret() -> str:
    return settings.jwt_secret.get_secret_value()


def create_access_token(user_id: uuid.UUID, *, now: datetime | None = None) -> tuple[str, int]:
    now = now or datetime.now(timezone.utc)
    ttl = timedelta(minutes=settings.jwt_ttl_minutes)
    claims = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + ttl,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "type": "access",
    }
    return jwt.encode(claims, _secret(), algorithm=ALGORITHM), int(ttl.total_seconds())


def decode_access_token(token: str) -> uuid.UUID:
    """The user id inside a valid token. Anything wrong with the token raises InvalidToken."""
    try:
        claims = jwt.decode(
            token,
            _secret(),
            algorithms=[ALGORITHM],  # a fixed list: a token cannot choose "none" or another algorithm
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": REQUIRED_CLAIMS},
        )
        if claims.get("type") != "access":
            raise InvalidToken("not an access token")
        return uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise InvalidToken(str(exc)) from exc