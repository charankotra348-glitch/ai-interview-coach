import pytest
from fastapi.testclient import TestClient

from app.db import session as db_session
from app.main import create_app

client = TestClient(create_app())


def test_ready_when_database_is_up(monkeypatch):
    monkeypatch.setattr(db_session, "check_database", lambda: 1.5)
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "up",
        "database_latency_ms": 1.5,
    }


def test_ready_returns_503_when_database_is_down(monkeypatch):
    def fail():
        raise ConnectionError("connection refused to coach@localhost")

    monkeypatch.setattr(db_session, "check_database", fail)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["database"] == "down"
    assert "coach@localhost" not in response.text


def test_liveness_does_not_touch_database(monkeypatch):
    def fail():
        raise AssertionError("liveness must not call the database")

    monkeypatch.setattr(db_session, "check_database", fail)
    assert client.get("/health").status_code == 200


@pytest.mark.integration
def test_ready_with_real_database_p95_under_50ms():
    times = []
    for _ in range(20):
        response = client.get("/ready")
        assert response.status_code == 200
        times.append(response.json()["database_latency_ms"])
    times.sort()
    print(f"\ndb p50={times[9]:.2f}ms p95={times[18]:.2f}ms")
    assert times[18] < 50