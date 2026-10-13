from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class LLMRequest(BaseModel):
    purpose: str = Field(min_length=1, max_length=40)
    messages: list[Message] = Field(min_length=1)
    system: str | None = None
    max_tokens: int = Field(default=1024, gt=0, le=8192)
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    response_format: Literal["text", "json"] = "text"
    session_id: UUID | None = None


class ProviderResponse(BaseModel):
    """Raw facts from a provider. Never contains cost."""
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class Usage(BaseModel):
    input_tokens: int | None
    output_tokens: int | None
    source: Literal["provider", "unavailable"]


class Cost(BaseModel):
    usd: Decimal | None
    basis: Literal["provider_billing", "price_table_estimate", "unavailable"]
    price_table_version: str | None = None


class LLMResult(BaseModel):
    text: str
    provider: str
    model: str
    latency_ms: float
    attempts: int
    usage: Usage
    cost: Cost


NO_USAGE = Usage(input_tokens=None, output_tokens=None, source="unavailable")
NO_COST = Cost(usd=None, basis="unavailable")