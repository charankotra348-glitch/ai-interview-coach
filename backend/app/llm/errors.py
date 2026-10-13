class LLMError(Exception):
    retryable = False
    error_type = "llm_error"


class ProviderTimeout(LLMError):
    retryable = True
    error_type = "timeout"


class ProviderRateLimited(LLMError):
    retryable = True
    error_type = "rate_limited"


class ProviderUnavailable(LLMError):
    retryable = True
    error_type = "unavailable"


class ProviderRequestError(LLMError):
    retryable = False
    error_type = "bad_request"


class ProviderAuthError(LLMError):
    retryable = False
    error_type = "auth"


class LLMCallFailed(Exception):
    def __init__(self, error_type: str, attempts: int):
        super().__init__(f"LLM call failed after {attempts} attempt(s): {error_type}")
        self.error_type = error_type
        self.attempts = attempts