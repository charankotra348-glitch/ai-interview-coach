from functools import lru_cache

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.tokens import InvalidToken, decode_access_token
from app.db.models import User
from app.db.session import get_db
from app.llm.client import LLMClient

# Reads "Authorization: Bearer <token>". tokenUrl also powers the Authorize button in /docs.
bearer_token = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


def unauthorized(message: str = "Not authenticated.") -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"code": "unauthenticated", "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: str | None = Depends(bearer_token),
    db: Session = Depends(get_db),
) -> User:
    """The user a valid access token belongs to. Every failure is the same 401."""
    if not token:
        raise unauthorized()
    try:
        user_id = decode_access_token(token)
    except InvalidToken:
        raise unauthorized("Invalid or expired token.")
    user = db.get(User, user_id)
    if user is None:  # the account was deleted after the token was issued
        raise unauthorized("Invalid or expired token.")
    return user


@lru_cache
def get_llm_client() -> LLMClient:
    from app.llm.factory import build_llm_client

    return build_llm_client()