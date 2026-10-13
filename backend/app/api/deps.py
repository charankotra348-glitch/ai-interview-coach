from functools import lru_cache

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import User
from app.db.session import get_db
from app.llm.client import LLMClient

DEV_ENVIRONMENTS = {"local", "ci", "test"}
DEV_EMAIL = "dev@local.test"


def get_current_user(db: Session = Depends(get_db)) -> User:
    """Temporary until Step 7 adds real authentication. Refuses to run outside development."""
    if settings.environment not in DEV_ENVIRONMENTS:
        raise HTTPException(status_code=401, detail={
            "code": "unauthenticated", "message": "Authentication required.",
        })
    user = db.scalar(select(User).where(User.email == DEV_EMAIL))
    if user is None:
        user = User(email=DEV_EMAIL, password_hash="!")  # "!" can never match a real password
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@lru_cache
def get_llm_client() -> LLMClient:
    from app.llm.factory import build_llm_client

    return build_llm_client()