import logging

from fastapi import APIRouter, Response

from app.config import settings
from app.db import session as db_session

router = APIRouter(tags=["health"])
logger = logging.getLogger("app")


@router.get("/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "version": settings.version,
        "environment": settings.environment,
    }


@router.get("/ready")
def readiness_check(response: Response) -> dict:
    try:
        latency_ms = db_session.check_database()
    except Exception as exc:
        logger.warning("database check failed: %s", type(exc).__name__)
        response.status_code = 503
        return {"status": "unavailable", "database": "down"}
    return {
        "status": "ok",
        "database": "up",
        "database_latency_ms": round(latency_ms, 2),
    }