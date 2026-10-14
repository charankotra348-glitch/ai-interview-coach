import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import create_app

# Nothing listens on port 1, so every connection attempt fails at once.
DEAD_DATABASE = "postgresql+psycopg://coach:coach@127.0.0.1:1/coach"


@pytest.fixture
def client():
    engine = create_engine(DEAD_DATABASE, connect_args={"connect_timeout": 1})

    def dead_db():
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = dead_db
    yield TestClient(app)
    engine.dispose()


def test_database_outage_is_a_clear_retryable_503(client):
    response = client.post("/auth/register",
                           json={"email": "a@example.com", "password": "a long enough password"})
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "database_unavailable"
    assert detail["retryable"] is True
    assert "coach" not in response.text            # no connection details leak out


def test_health_still_answers_while_the_database_is_down(client):
    assert client.get("/health").status_code == 200