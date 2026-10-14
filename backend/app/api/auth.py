import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.auth.passwords import MAX_LENGTH, MIN_LENGTH, hash_password, verify_password
from app.auth.tokens import create_access_token
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=MIN_LENGTH, max_length=MAX_LENGTH)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


def normalize_email(email: str) -> str:
    return email.strip().lower()


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    user = User(email=normalize_email(body.email), password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # the unique email constraint, also under concurrent sign-ups
        db.rollback()
        raise HTTPException(status_code=409, detail={
            "code": "email_taken", "message": "An account with this email already exists.",
        })
    return UserOut(id=user.id, email=user.email)


@router.post("/token", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 password flow: form fields "username" (the email) and "password"."""
    user = None
    if len(form.password) <= MAX_LENGTH:
        user = db.scalar(select(User).where(User.email == normalize_email(form.username)))
    # Always verify, even for an unknown email, so both failures take the same time.
    valid = verify_password(form.password[:MAX_LENGTH], user.password_hash if user else None)
    if user is None or not valid:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_credentials", "message": "Incorrect email or password."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_in = create_access_token(user.id)
    return TokenOut(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut(id=user.id, email=user.email)