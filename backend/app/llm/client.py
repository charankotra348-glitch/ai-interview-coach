import json
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app.llm.base import LLMProvider
from app.llm.errors import LLMCallFailed, LLMError
from app.llm.pricing import PriceTable
from app.llm.types import (
    NO_COST,
    NO_USAGE,
    Cost,
    LLMRequest,
    LLMResult,
    ProviderResponse,
    Usage,
)

logger = logging.getLogger("app.llm")


@dataclass(frozen=True)
class CallRecord:
    purpose: str
    session_id: UUID | None
    provider: str
    model: str
    latency_ms: float
    success: bool
    error_type: str | None
    usage: Usage
    cost: Cost


Recorder = Callable[[CallRecord], None]


def usage_from(response: ProviderResponse) -> Usage:
    # Partial counts are treated as missing: we never fill in a guess.
    if response.input_tokens is None or response.output_tokens is None:
        return NO_USAGE
    return Usage(
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        source="provider",
    )


def _full_jitter_half(delay: float) -> float:
    return delay * random.uniform(0.5, 1.0)


class LLMClient:
    def __init__(
        self,
        provider: LLMProvider,
        *,
        model: str,
        prices: PriceTable,
        recorder: Recorder | None = None,
        timeout_s: float = 30.0,
        max_attempts: int = 3,
        backoff_s: float = 2.0,
        budget_s: float | None = None,
        min_attempt_s: float = 10.0,
        jitter: Callable[[float], float] = _full_jitter_half,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._check_budget(budget_s, min_attempt_s)
        self.provider = provider
        self.model = model
        self.prices = prices
        self.recorder = recorder
        self.timeout_s = timeout_s
        self.max_attempts = max_attempts
        self.backoff_s = backoff_s
        self.budget_s = budget_s
        self.min_attempt_s = min_attempt_s
        self.jitter = jitter
        self.sleep = sleep
        self.clock = clock

    @staticmethod
    def _check_budget(budget_s: float | None, min_attempt_s: float) -> None:
        if budget_s is not None and budget_s < min_attempt_s:
            raise ValueError(f"budget_s must be at least {min_attempt_s} seconds")

    def complete(self, request: LLMRequest, *, budget_s: float | None = None) -> LLMResult:
        budget = budget_s if budget_s is not None else self.budget_s
        self._check_budget(budget, self.min_attempt_s)
        deadline = self.clock() + budget if budget is not None else None

        for attempt in range(1, self.max_attempts + 1):
            timeout = self.timeout_s
            if deadline is not None:
                remaining = deadline - self.clock()
                timeout = min(self.timeout_s, max(remaining, self.min_attempt_s))

            start = time.perf_counter()
            try:
                response = self.provider.complete(request, model=self.model, timeout_s=timeout)
            except LLMError as exc:
                self._record(
                    request,
                    model=self.model,
                    latency_ms=_elapsed_ms(start),
                    success=False,
                    error_type=exc.error_type,
                    usage=NO_USAGE,
                    cost=NO_COST,
                    attempt=attempt,
                )
                if not exc.retryable or attempt == self.max_attempts:
                    raise LLMCallFailed(exc.error_type, attempt) from exc
                delay = self.jitter(self.backoff_s * 2 ** (attempt - 1))
                # Don't start a retry that can't get a useful amount of time.
                if deadline is not None and self.clock() + delay + self.min_attempt_s > deadline:
                    raise LLMCallFailed(exc.error_type, attempt, budget_exhausted=True) from exc
                self.sleep(delay)
                continue

            latency_ms = _elapsed_ms(start)
            usage = usage_from(response)
            cost = self.prices.estimate(response.model, usage)
            self._record(
                request,
                model=response.model,
                latency_ms=latency_ms,
                success=True,
                error_type=None,
                usage=usage,
                cost=cost,
                attempt=attempt,
            )
            return LLMResult(
                text=response.text,
                provider=self.provider.name,
                model=response.model,
                latency_ms=latency_ms,
                attempts=attempt,
                usage=usage,
                cost=cost,
            )
        raise AssertionError("unreachable")

    def _record(self, request: LLMRequest, *, attempt: int, **fields) -> None:
        record = CallRecord(
            purpose=request.purpose,
            session_id=request.session_id,
            provider=self.provider.name,
            **fields,
        )
        logger.info(json.dumps({
            "event": "llm_call",
            "purpose": record.purpose,
            "provider": record.provider,
            "model": record.model,
            "attempt": attempt,
            "success": record.success,
            "error_type": record.error_type,
            "latency_ms": record.latency_ms,
            "input_tokens": record.usage.input_tokens,
            "output_tokens": record.usage.output_tokens,
            "usage_source": record.usage.source,
            "cost_usd": str(record.cost.usd) if record.cost.usd is not None else None,
            "cost_basis": record.cost.basis,
        }))
        if self.recorder is None:
            return
        try:
            self.recorder(record)
        except Exception as exc:  # recording must never break the user's request
            logger.warning("llm call recording failed: %s", type(exc).__name__)


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)