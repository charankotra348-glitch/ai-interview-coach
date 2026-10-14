from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.auth.tokens import create_access_token
from app.db.models import User
from app.db.session import get_db
from app.main import create_app

pytestmark = pytest.mark.integration

EMAIL = "Charan.Test@Example.com"
PASSWORD = "a long enough password"


@pytest.fixture
def client(db, fast_hashing):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def register(client, email=EMAIL, password=PASSWORD):
    return client.post("/auth/register", json={"email": email, "password": password})


def login(client, email=EMAIL, password=PASSWORD):
    return client.post("/auth/token", data={"username": email, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


# --- registration ----------------------------------------------------------------------

def test_register_stores_a_hash_not_the_password(client, db):
    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "charan.test@example.com"      # normalized
    stored = db.get(User, body["id"]).password_hash
    assert stored.startswith("$argon2id$")
    assert PASSWORD not in stored


def test_same_email_in_other_case_is_taken(client):
    assert register(client).status_code == 201
    again = register(client, email=EMAIL.upper())
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "email_taken"


@pytest.mark.parametrize("email, password", [
    ("not-an-email", PASSWORD),
    (EMAIL, "short"),                       # under 12 characters
    (EMAIL, "x" * 129),                     # over 128 characters
])
def test_invalid_registration_is_422(client, email, password):
    assert register(client, email, password).status_code == 422


# --- login -----------------------------------------------------------------------------

def test_login_returns_a_working_token(client):
    register(client)
    response = login(client, email="  charan.test@EXAMPLE.com ")
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 30 * 60
    me = client.get("/auth/me", headers=bearer(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "charan.test@example.com"


def test_wrong_password_and_unknown_email_look_the_same(client):
    register(client)
    wrong_password = login(client, password="not the right password")
    unknown_email = login(client, email="nobody@example.com")
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()   # nothing reveals which one it was
    assert wrong_password.json()["detail"]["code"] == "invalid_credentials"


def test_the_old_dev_user_cannot_log_in(client, db):
    db.add(User(email="dev@local.test", password_hash="!"))
    db.flush()
    assert login(client, email="dev@local.test", password="!" * 12).status_code == 401


# --- protected route -----------------------------------------------------------------------

def test_missing_token_is_401_with_a_bearer_challenge(client):
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["detail"]["code"] == "unauthenticated"


@pytest.mark.parametrize("header", [
    {"Authorization": "Bearer not.a.token"},
    {"Authorization": "Basic Y2hhcmFuOnBhc3M="},           # the wrong scheme
])
def test_bad_credentials_are_401(client, header):
    assert client.get("/auth/me", headers=header).status_code == 401


def test_expired_token_is_401(client):
    user_id = register(client).json()["id"]
    token, _ = create_access_token(user_id, now=datetime.now(timezone.utc) - timedelta(hours=2))
    assert client.get("/auth/me", headers=bearer(token)).status_code == 401


def test_token_of_a_deleted_user_is_401(client, db):
    register(client)
    token = login(client).json()["access_token"]
    db.delete(db.query(User).filter_by(email="charan.test@example.com").one())
    db.flush()
    assert client.get("/auth/me", headers=bearer(token)).status_code == 401