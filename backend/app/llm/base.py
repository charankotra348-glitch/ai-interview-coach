from typing import Protocol

from app.llm.types import LLMRequest, ProviderResponse


class LLMProvider(Protocol):
    name: str

    def complete(
        self, request: LLMRequest, *, model: str, timeout_s: float
    ) -> ProviderResponse: ...