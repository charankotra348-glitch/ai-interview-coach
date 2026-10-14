import json
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.api import auth, health, profiles, sessions
from app.api import health, profiles, sessions
from app.config import settings
from app.ingest.extract import DocumentError
from app.llm.errors import LLMCallFailed
from app.llm.structured import StructuredOutputError

logging.basicConfig(level=settings.log_level, format="%(message)s")
logger = logging.getLogger("app")


def _error(status: int, code: str, message: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=status, content={
        "detail": {"code": code, "message": message, **extra},
    })


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.version)

    @app.middleware("http")
    async def request_metrics(request: Request, call_next):
        supplied_id = request.headers.get("x-request-id", "")
        valid_id = (
            0 < len(supplied_id) <= 128
            and supplied_id.isascii()
            and all(c.isalnum() or c in "-_." for c in supplied_id)
        )
        request_id = supplied_id if valid_id else str(uuid.uuid4())
        start = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            duration_ms = (time.perf_counter() - start) * 1000
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time-ms"] = f"{duration_ms:.2f}"
            return response
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(json.dumps({
                "event": "request",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "duration_ms": round(duration_ms, 2),
            }))

    @app.exception_handler(DocumentError)
    async def document_error(request: Request, exc: DocumentError):
        return _error(422, exc.code, exc.message)

    @app.exception_handler(StructuredOutputError)
    async def structured_output_error(request: Request, exc: StructuredOutputError):
        return _error(502, "extraction_failed",
                      "The AI returned an unusable result. Please try again.")

    @app.exception_handler(LLMCallFailed)
    async def llm_unavailable(request: Request, exc: LLMCallFailed):
        logger.warning(json.dumps({
            "event": "llm_call_failed",
            "error_type": exc.error_type,
            "attempts": exc.attempts,
            "budget_exhausted": exc.budget_exhausted,
        }))
        return _error(503, "ai_unavailable",
                      "The AI service is busy. Please try again in a few minutes.",
                      retryable=True)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(profiles.router)
    app.include_router(sessions.router)
    return app
  


app = create_app()