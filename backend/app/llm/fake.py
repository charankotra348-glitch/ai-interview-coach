from app.llm.errors import LLMError
from app.llm.types import LLMRequest, ProviderResponse


class FakeProvider:
    """Scripted provider for tests. Each call pops the next scripted item."""

    name = "fake"

    def __init__(self, script: list[ProviderResponse | LLMError] | None = None):
        self.script = list(script or [])
        self.calls: list[dict] = []

    def complete(
        self, request: LLMRequest, *, model: str, timeout_s: float
    ) -> ProviderResponse:
        self.calls.append({"request": request, "model": model, "timeout_s": timeout_s})
        if not self.script:
            return ProviderResponse(
                text="fake response", model=model, input_tokens=10, output_tokens=5
            )
        item = self.script.pop(0)
        if isinstance(item, LLMError):
            raise item
        return item