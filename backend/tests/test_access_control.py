import uuid

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import create_app
from tests.auth_helpers import sign_in

# The only routes anyone may call without a token. Adding a route here is a security decision.
PUBLIC = {
    ("GET", "/health"),
    ("GET", "/ready"),
    ("POST", "/auth/register"),
    ("POST", "/auth/token"),
}


def api_routes(app):
    """Every documented (method, path), read from the OpenAPI schema the app publishes."""
    for path, operations in app.openapi()["paths"].items():
        for method in operations:
            yield method.upper(), path


def test_every_other_route_needs_a_token():
    """A new route that forgets authentication fails this test."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: None   # never reached without a token
    client = TestClient(app)
    checked = 0
    for method, path in api_routes(app):
        if (method, path) in PUBLIC:
            continue
        url = path
        for part in [p for p in path.split("/") if p.startswith("{")]:
            url = url.replace(part, str(uuid.uuid4()))
        response = client.request(method, url)
        assert response.status_code == 401, f"{method} {path} answered {response.status_code}"
        checked += 1
    assert checked >= 9                                  # the profile, session and /auth/me routes


def test_public_routes_are_still_public():
    paths = {(m, p) for m, p in api_routes(create_app())}
    assert PUBLIC <= paths


@pytest.mark.integration
def test_two_real_users_cannot_see_each_others_interviews(db, fast_hashing):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    alice, bob = TestClient(app), TestClient(app)
    sign_in(alice, email="alice@example.com")
    sign_in(bob, email="bob@example.com")

    session_id = alice.post("/sessions", json={"mode": "behavioral"}).json()["id"]
    assert alice.get(f"/sessions/{session_id}").status_code == 200
    assert bob.get(f"/sessions/{session_id}").status_code == 404     # not 403: no hint it exists
    assert bob.get(f"/sessions/{session_id}/summary").status_code == 404