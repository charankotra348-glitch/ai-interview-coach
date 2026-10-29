"""Amazon Bedrock through the Converse API: the hosted provider for the AWS deployment.

On AWS the task's IAM role signs the calls, so there is no API key to store. Like the
other providers it returns only raw facts (text, model, token counts as reported) and
maps every failure to one of our LLMError types; LLMClient owns retries, so boto3
makes a single attempt.
"""

import boto3
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)

from app.llm.errors import (
    LLMError,
    ProviderAuthError,
    ProviderRateLimited,
    ProviderRequestError,
    ProviderTimeout,
    ProviderUnavailable,
)
from app.llm.types import LLMRequest, ProviderResponse

# Converse has no JSON switch for every model, so JSON requests say so in the system prompt;
# structured.parse_json_object still validates (and tolerates a code fence).
JSON_INSTRUCTION = "Reply with a single JSON object and nothing else."

TIMEOUT_CODES = {"ModelTimeoutException"}
RATE_LIMIT_CODES = {"ThrottlingException", "TooManyRequestsException", "ServiceQuotaExceededException"}
AUTH_CODES = {"AccessDeniedException", "UnrecognizedClientException", "ExpiredTokenException"}
UNAVAILABLE_CODES = {"ServiceUnavailableException", "InternalServerException", "ModelNotReadyException"}


class BedrockProvider:
    name = "bedrock"

    def __init__(self, region: str, *, timeout_s: float = 60.0, client=None):
        self._client = client or boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(read_timeout=timeout_s, connect_timeout=10, retries={"max_attempts": 1}),
        )

    def complete(self, request: LLMRequest, *, model: str, timeout_s: float) -> ProviderResponse:
        system = request.system or ""
        if request.response_format == "json":
            system = f"{system}\n\n{JSON_INSTRUCTION}".strip()

        kwargs = {
            "modelId": model,
            "messages": [
                {"role": m.role, "content": [{"text": m.content}]} for m in request.messages
            ],
            "inferenceConfig": {"maxTokens": request.max_tokens, "temperature": request.temperature},
        }
        if system:
            kwargs["system"] = [{"text": system}]

        try:
            response = self._client.converse(**kwargs)
        except (ReadTimeoutError, ConnectTimeoutError) as exc:
            raise ProviderTimeout() from exc
        except EndpointConnectionError as exc:
            raise ProviderUnavailable() from exc
        except ClientError as exc:
            raise map_client_error(exc) from exc
        except BotoCoreError as exc:
            raise ProviderUnavailable() from exc

        blocks = response.get("output", {}).get("message", {}).get("content", [])
        usage = response.get("usage") or {}
        input_tokens, output_tokens = usage.get("inputTokens"), usage.get("outputTokens")
        if input_tokens is None or output_tokens is None:
            input_tokens = output_tokens = None
        return ProviderResponse(
            text="".join(block.get("text", "") for block in blocks),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


def map_client_error(exc: ClientError) -> LLMError:
    code = exc.response.get("Error", {}).get("Code", "")
    if code in TIMEOUT_CODES:
        return ProviderTimeout()
    if code in RATE_LIMIT_CODES:
        return ProviderRateLimited()
    if code in AUTH_CODES:
        return ProviderAuthError()
    if code in UNAVAILABLE_CODES:
        return ProviderUnavailable()
    return ProviderRequestError()
