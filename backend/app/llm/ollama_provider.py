import json
import logging

import httpx

from app.llm.errors import ProviderRequestError, ProviderTimeout, ProviderUnavailable
from app.llm.types import LLMRequest, ProviderResponse

logger = logging.getLogger("app.llm")


class OllamaProvider:
    name = "ollama"

    def __init__(
        self, base_url: str = "http://localhost:11434", *, client: httpx.Client | None = None
    ):
        self._client = client or httpx.Client(base_url=base_url)

    def complete(
        self, request: LLMRequest, *, model: str, timeout_s: float
    ) -> ProviderResponse:
        messages = [m.model_dump() for m in request.messages]
        if request.system:
            messages.insert(0, {"role": "system", "content": request.system})
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        if request.response_format == "json":
            payload["format"] = "json"

        try:
            response = self._client.post("/api/chat", json=payload, timeout=timeout_s)
        except httpx.TimeoutException as exc:
            raise ProviderTimeout() from exc
        except httpx.TransportError as exc:  # Ollama not running
            raise ProviderUnavailable() from exc

        if response.status_code >= 400:
            logger.warning(json.dumps({
                "event": "provider_error",
                "provider": "ollama",
                "status": response.status_code,
                "detail": response.text[:300],
            }))
        if response.status_code >= 500:
            raise ProviderUnavailable()
        if response.status_code >= 400:  # e.g. 404: model not pulled
            raise ProviderRequestError()

        data = response.json()
        return ProviderResponse(
            text=data.get("message", {}).get("content", ""),
            model=data.get("model", model),
            input_tokens=data.get("prompt_eval_count"),
            output_tokens=data.get("eval_count"),
        )