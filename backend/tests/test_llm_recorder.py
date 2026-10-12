import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.models import LLMCall
from app.llm.client import LLMClient
from app.llm.errors import LLMCallFailed, ProviderRequestError
from app.llm.fake import FakeProvider
from app.llm.pricing import ModelPrice, PriceTable
from app.llm.recorder import database_recorder
from app.llm.types import LLMRequest, Message, ProviderResponse

pytestmark = pytest.mark.integration

PRICES = PriceTable(
    version="test-2026-10-11",
    models={"fake-1": ModelPrice(
        input_per_million=Decimal("3"), output_per_million=Decimal("15")
    )},
)


def test_recorded_calls_satisfy_database_rules(migrated_engine):
    factory = sessionmaker(bind=migrated_engine)
    marker = f"t-{uuid.uuid4().hex[:12]}"
    provider = FakeProvider([
        ProviderResponse(text="a", model="fake-1", input_tokens=100, output_tokens=20),
        ProviderResponse(text="b", model="fake-1"),
        ProviderRequestError(),
    ])
    client = LLMClient(
        provider, model="fake-1", prices=PRICES, recorder=database_recorder(factory)
    )
    req = LLMRequest(purpose=marker, messages=[Message(role="user", content="Hi")])

    client.complete(req)
    client.complete(req)
    with pytest.raises(LLMCallFailed):
        client.complete(req)

    with factory() as db:
        rows = db.scalars(
            select(LLMCall).where(LLMCall.purpose == marker).order_by(LLMCall.created_at)
        ).all()

    assert len(rows) == 3
    estimated, unavailable, failed = rows
    assert estimated.cost_basis == "price_table_estimate"
    assert estimated.cost_usd == Decimal("0.000600")
    assert unavailable.usage_source == "unavailable"
    assert unavailable.cost_usd is None
    assert failed.success is False
    assert failed.error_type == "bad_request"