import json
import logging

from fastapi.testclient import TestClient
from app.config import settings
from app.main import create_app

client = TestClient(create_app())


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == settings.version
    assert body["environment"] == settings.environment


def test_every_response_has_timing_header():
    response = client.get("/health")
    assert float(response.headers["x-response-time-ms"]) >= 0


def test_request_id_is_echoed_back():
    response = client.get("/health", headers={"X-Request-ID": "test-123"})
    assert response.headers["x-request-id"] == "test-123"


def test_request_id_is_generated_when_missing():
    response = client.get("/health")
    assert len(response.headers["x-request-id"]) == 36


def test_invalid_request_id_is_replaced():
    response = client.get(
        "/health",
        headers={"X-Request-ID": "invalid id with spaces"},
    )
    assert response.headers["x-request-id"] != "invalid id with spaces"
    assert len(response.headers["x-request-id"]) == 36


def test_request_is_logged_as_json(caplog):
    with caplog.at_level(logging.INFO, logger="app"):
        response = client.get("/health")

    records = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "app" and record.message.startswith("{")
    ]
    request_record = next(
        record for record in records if record.get("event") == "request"
    )

    assert request_record["status"] == 200
    assert request_record["path"] == "/health"
    assert request_record["request_id"] == response.headers["x-request-id"]
    assert request_record["duration_ms"] >= 0


def test_health_p95_latency_under_50ms():
    times = sorted(
        float(client.get("/health").headers["x-response-time-ms"])
        for _ in range(100)
    )
    p95 = times[94]
    print(f"\nhealth p50={times[49]:.2f}ms p95={p95:.2f}ms")
    assert p95 < 50