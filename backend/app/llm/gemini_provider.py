import httpx
from google import genai
from google.genai import errors, types

from app.llm.errors import (
    LLMError,
    ProviderAuthError,
    ProviderRateLimited,
    ProviderRequestError,
    ProviderTimeout,
    ProviderUnavailable,
)
from app.llm.types import LLMRequest, ProviderResponse


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str | None = None, *, client=None):
        if client is None:
            if not api_key:
                raise ValueError("GEMINI_API_KEY is not set")
            # Our LLMClient owns retries, so the SDK makes exactly one attempt.
            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(
                    retry_options=types.HttpRetryOptions(attempts=1)
                ),
            )
        self._client = client

    def complete(
        self, request: LLMRequest, *, model: str, timeout_s: float
    ) -> ProviderResponse:
        contents = [
            types.Content(
                role="model" if m.role == "assistant" else "user",
                parts=[types.Part.from_text(text=m.content)],
            )
            for m in request.messages
        ]
        config = types.GenerateContentConfig(
            system_instruction=request.system,
            temperature=request.temperature,
            max_output_tokens=request.max_tokens,
            http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),  # ms
        )

        try:
            response = self._client.models.generate_content(
                model=model, contents=contents, config=config
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeout() from exc
        except httpx.TransportError as exc:
            raise ProviderUnavailable() from exc
        except errors.APIError as exc:
            raise map_api_error(exc) from exc

        return ProviderResponse(
            text=response.text or "",
            model=getattr(response, "model_version", None) or model,
            **token_counts(getattr(response, "usage_metadata", None)),
        )


def token_counts(usage) -> dict:
    prompt = getattr(usage, "prompt_token_count", None)
    candidates = getattr(usage, "candidates_token_count", None)
    if prompt is None or candidates is None:
        return {"input_tokens": None, "output_tokens": None}
    # Gemini bills "thinking" tokens as output, so they count toward output.
    thoughts = getattr(usage, "thoughts_token_count", None) or 0
    return {"input_tokens": prompt, "output_tokens": candidates + thoughts}


def map_api_error(exc: errors.APIError) -> LLMError:
    code = getattr(exc, "code", None) or 0
    status = str(getattr(exc, "status", "") or "").upper()
    message = str(getattr(exc, "message", "") or "").lower()
    if code == 504 or status == "DEADLINE_EXCEEDED":
        return ProviderTimeout()
    if code == 429:
        return ProviderRateLimited()
    if code in (401, 403) or "api key" in message:
        return ProviderAuthError()
    if code >= 500:
        return ProviderUnavailable()
    return ProviderRequestError()