import json

import httpx
import pytest

from app.llm.errors import ProviderRequestError, ProviderTimeout, ProviderUnavailable
from app.llm.ollama_provider import OllamaProvider
from app.llm.types import LLMRequest, Message


def provider_with(handler):
    client = httpx.Client(
        base_url="http://ollama.test", transport=httpx.MockTransport(handler)
    )
    return OllamaProvider(client=client)


def chat_reply(**overrides):
    body = {
        "model": "llama3.2",
        "message": {"role": "assistant", "content": "Tell me about a time..."},
        "prompt_eval_count": 25,
        "eval_count": 9,
    }
    body.update(overrides)
    return httpx.Response(200, json=body)


def request(**overrides):
    fields = dict(purpose="question", messages=[Message(role="user", content="Hi")])
    fields.update(overrides)
    return LLMRequest(**fields)


def call(provider, req=None):
    return provider.complete(req or request(), model="llama3.2", timeout_s=5.0)


def test_text_and_usage_are_extracted():
    response = call(provider_with(lambda r: chat_reply()))
    assert response.text == "Tell me about a time..."
    assert (response.input_tokens, response.output_tokens) == (25, 9)


def test_missing_counts_are_reported_as_none():
    def handler(_):
        body = chat_reply().json()
        del body["prompt_eval_count"]
        return httpx.Response(200, json=body)

    response = call(provider_with(handler))
    assert response.input_tokens is None


def test_request_payload():
    seen = {}

    def handler(req):
        seen.update(json.loads(req.content))
        return chat_reply()

    call(provider_with(handler), request(system="Be brief.", max_tokens=50))
    assert seen["stream"] is False
    assert seen["messages"][0] == {"role": "system", "content": "Be brief."}
    assert seen["options"]["num_predict"] == 50


def test_ollama_not_running_is_unavailable():
    def handler(req):
        raise httpx.ConnectError("connection refused", request=req)

    with pytest.raises(ProviderUnavailable):
        call(provider_with(handler))


def test_timeout_maps_to_provider_timeout():
    def handler(req):
        raise httpx.ReadTimeout("too slow", request=req)

    with pytest.raises(ProviderTimeout):
        call(provider_with(handler))


def test_missing_model_is_a_request_error():
    with pytest.raises(ProviderRequestError):
        call(provider_with(lambda r: httpx.Response(404, json={"error": "model not found"})))


def test_server_error_is_unavailable():
    with pytest.raises(ProviderUnavailable):
        call(provider_with(lambda r: httpx.Response(500)))

def test_json_mode_is_requested():
    seen = {}

    def handler(req):
        seen.update(json.loads(req.content))
        return chat_reply()

    call(provider_with(handler), request(response_format="json"))
    assert seen["format"] == "json"