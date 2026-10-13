from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors

from app.config import settings
from app.llm.errors import (
    ProviderAuthError,
    ProviderRateLimited,
    ProviderRequestError,
    ProviderTimeout,
    ProviderUnavailable,
)
from app.llm.gemini_provider import GeminiProvider
from app.llm.pricing import load_price_table
from app.llm.types import LLMRequest, Message

REQ = httpx.Request("POST", "https://generativelanguage.googleapis.com")


class FakeModels:
    def __init__(self, result):
        self.result = result
        self.kwargs = None

    def generate_content(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def provider_returning(result):
    fake = SimpleNamespace(models=FakeModels(result))
    return GeminiProvider(client=fake), fake.models


def reply(text="Tell me about a time...", prompt=20, candidates=5, thoughts=None):
    usage = SimpleNamespace(
        prompt_token_count=prompt,
        candidates_token_count=candidates,
        thoughts_token_count=thoughts,
    )
    return SimpleNamespace(text=text, model_version="gemini-3.8-flash", usage_metadata=usage)


def api_error(code, message="error", status="ERROR"):
    cls = errors.ServerError if code >= 500 else errors.ClientError
    return cls(code, {"error": {"code": code, "message": message, "status": status}})


def request(**overrides):
    fields = dict(purpose="question", messages=[Message(role="user", content="Hi")])
    fields.update(overrides)
    return LLMRequest(**fields)


def call(provider, req=None):
    return provider.complete(req or request(), model="gemini-3.8-flash", timeout_s=7.0)


def test_text_and_usage_are_extracted():
    response = call(provider_returning(reply())[0])
    assert response.text == "Tell me about a time..."
    assert (response.input_tokens, response.output_tokens) == (20, 5)
    assert response.model == "gemini-3.8-flash"


def test_thinking_tokens_count_as_output():
    response = call(provider_returning(reply(candidates=5, thoughts=40))[0])
    assert response.output_tokens == 45


def test_missing_usage_is_reported_as_none():
    response = call(provider_returning(reply(prompt=None))[0])
    assert response.input_tokens is None
    assert response.output_tokens is None


def test_empty_text_becomes_empty_string():
    response = call(provider_returning(reply(text=None))[0])
    assert response.text == ""


def test_request_is_translated_for_the_sdk():
    provider, sdk = provider_returning(reply())
    req = request(
        system="You are an interviewer.",
        max_tokens=300,
        messages=[
            Message(role="user", content="Hi"),
            Message(role="assistant", content="Hello"),
            Message(role="user", content="Ask me a question"),
        ],
    )
    call(provider, req)
    contents = sdk.kwargs["contents"]
    assert [c.role for c in contents] == ["user", "model", "user"]
    config = sdk.kwargs["config"]
    assert config.system_instruction == "You are an interviewer."
    assert config.max_output_tokens == 300
    assert config.http_options.timeout == 7000


@pytest.mark.parametrize(
    "sdk_error, expected",
    [
        (httpx.ReadTimeout("slow", request=REQ), ProviderTimeout),
        (httpx.ConnectError("refused", request=REQ), ProviderUnavailable),
        (api_error(504, "Deadline expired", "DEADLINE_EXCEEDED"), ProviderTimeout),
        (api_error(400, "Manually set deadline 1s is too short.", "INVALID_ARGUMENT"), ProviderRequestError),
        (api_error(429), ProviderRateLimited),
        (api_error(403), ProviderAuthError),
        (api_error(400, "API key not valid. Please pass a valid API key."), ProviderAuthError),
        (api_error(400, "Invalid argument"), ProviderRequestError),
        (api_error(404, "model not found"), ProviderRequestError),
        (api_error(500), ProviderUnavailable),
        (api_error(503), ProviderUnavailable),
    ],
)
def test_sdk_errors_map_to_our_errors(sdk_error, expected):
    provider, _ = provider_returning(sdk_error)
    with pytest.raises(expected):
        call(provider)


def test_missing_api_key_fails_fast():
    with pytest.raises(ValueError):
        GeminiProvider(api_key=None)


def test_configured_model_has_a_price():
    # Fails if GEMINI_MODEL changes without updating prices.json.
    assert settings.gemini_model in load_price_table().models

def test_timeout_below_gemini_minimum_is_rejected_at_startup():
    from pydantic import ValidationError

    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(llm_timeout_s=1)    

def test_json_mode_is_requested():
    provider, sdk = provider_returning(reply())
    call(provider, request(response_format="json"))
    assert sdk.kwargs["config"].response_mime_type == "application/json"
