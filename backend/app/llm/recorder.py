from collections.abc import Callable

from sqlalchemy.orm import Session

from app.db.models import LLMCall
from app.llm.client import CallRecord, Recorder


def database_recorder(session_factory: Callable[[], Session]) -> Recorder:
    def record(rec: CallRecord) -> None:
        with session_factory() as db:
            db.add(LLMCall(
                purpose=rec.purpose,
                session_id=rec.session_id,
                provider=rec.provider,
                model=rec.model,
                latency_ms=rec.latency_ms,
                success=rec.success,
                error_type=rec.error_type,
                input_tokens=rec.usage.input_tokens,
                output_tokens=rec.usage.output_tokens,
                usage_source=rec.usage.source,
                cost_usd=rec.cost.usd,
                cost_basis=rec.cost.basis,
                price_table_version=rec.cost.price_table_version,
            ))
            db.commit()

    return record