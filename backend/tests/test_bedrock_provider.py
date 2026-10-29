import boto3
import pytest
from botocore.exceptions import EndpointConnectionError, ReadTimeoutError
from botocore.stub import Stubber

from app.llm.bedrock_provider import JSON_INSTRUCTION, BedrockProvider
from app.llm.errors import (
    ProviderAuthError,
    ProviderRateLimited,
    ProviderRequestError,
    ProviderTimeout,
    ProviderUnavailable,
)
from app.llm.types import LLMRequest, Message

MODEL = "us.amazon.nova-lite-v1:0"


def stubbed():
    client = boto3.client(
        "bedrock-runtime", region_name="us-east-1",
        aws_access_key_id="test", aws_secret_access_key="test",
    )
    return BedrockProvider("us-east-1", client=client), Stubber(client)


def reply(text="Tell me about a time...", usage=None):
    return {
        "output": {"message": {"role": "assistant", "content": [{"text": text}]}},
        "stopReason": "end_turn",
        "usage": usage or {"inputTokens": 31, "outputTokens": 12, "totalTokens": 43},
        "metrics": {"latencyMs": 120},
    }


def request(**overrides):
    fields = dict(purpose="question", messages=[Message(role="user", content="Hi")])
    fields.update(overrides)
    return LLMRequest(**fields)


def test_text_usage_and_the_converse_request():
    provider, stub = stubbed()
    stub.add_response("converse", reply(), {
        "modelId": MODEL,
        "messages": [{"role": "user", "content": [{"text": "Hi"}]}],
        "system": [{"text": "Be brief."}],
        "inferenceConfig": {"maxTokens": 1024, "temperature": 0.0},
    })
    with stub:
        out = provider.complete(request(system="Be brief."), model=MODEL, timeout_s=5)
    assert (out.text, out.model, out.input_tokens, out.output_tokens) == (
        "Tell me about a time...", MODEL, 31, 12)


def test_json_requests_ask_for_json_in_the_system_prompt():
    provider, stub = stubbed()
    stub.add_response("converse", reply('{"ok": true}'), {
        "modelId": MODEL,
        "messages": [{"role": "user", "content": [{"text": "Hi"}]}],
        "system": [{"text": JSON_INSTRUCTION}],
        "inferenceConfig": {"maxTokens": 1024, "temperature": 0.0},
    })
    with stub:
        out = provider.complete(request(response_format="json"), model=MODEL, timeout_s=5)
    assert out.text == '{"ok": true}'


def test_missing_counts_stay_missing():
    class NoUsage:
        def converse(self, **_):
            body = reply()
            del body["usage"]["outputTokens"]
            return body

    out = BedrockProvider("us-east-1", client=NoUsage()).complete(request(), model=MODEL, timeout_s=5)
    assert (out.input_tokens, out.output_tokens) == (None, None)   # never half a count


@pytest.mark.parametrize(("code", "error"), [
    ("ThrottlingException", ProviderRateLimited),
    ("ServiceQuotaExceededException", ProviderRateLimited),
    ("AccessDeniedException", ProviderAuthError),
    ("ModelTimeoutException", ProviderTimeout),
    ("ServiceUnavailableException", ProviderUnavailable),
    ("ModelNotReadyException", ProviderUnavailable),
    ("ValidationException", ProviderRequestError),
])
def test_service_errors_map_to_our_error_types(code, error):
    provider, stub = stubbed()
    stub.add_client_error("converse", service_error_code=code, http_status_code=400)
    with stub, pytest.raises(error):
        provider.complete(request(), model=MODEL, timeout_s=5)


def test_network_errors_map_to_timeout_and_unavailable():
    class Raises:
        def __init__(self, exc):
            self.exc = exc

        def converse(self, **_):
            raise self.exc

    with pytest.raises(ProviderTimeout):
        BedrockProvider("us-east-1", client=Raises(ReadTimeoutError(endpoint_url="x"))).complete(
            request(), model=MODEL, timeout_s=5)
    with pytest.raises(ProviderUnavailable):
        BedrockProvider("us-east-1", client=Raises(EndpointConnectionError(endpoint_url="x"))).complete(
            request(), model=MODEL, timeout_s=5)
