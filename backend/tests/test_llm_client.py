import time
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.llm.client import LLMClient
from app.llm.errors import (
    LLMCallFailed,
    ProviderRateLimited,
    ProviderRequestError,
    ProviderTimeout,
    ProviderUnavailable,
)
from app.llm.fake import FakeProvider
from app.llm.pricing import ModelPrice, PriceTable, load_price_table
from app.llm.types import LLMRequest, Message, ProviderResponse

PRICES = PriceTable(
    version="test-2026-10-11",
    models={
        "fake-1": ModelPrice(
            input_per_million=Decimal("3"), output_per_million=Decimal("15")
        )
    },
)


def request(**overrides):
    fields = dict(purpose="evaluation", messages=[Message(role="user", content="Hi")])
    fields.update(overrides)
    return LLMRequest(**fields)


def make_client(script=None, **kwargs):
    provider = FakeProvider(script)
    records, sleeps = [], []
    options = dict(
        model="fake-1",
        prices=PRICES,
        recorder=records.append,
        sleep=sleeps.append,
        backoff_s=0.5,
        jitter=lambda d: d,
    )
    options.update(kwargs)
    client = LLMClient(provider, **options)
    return client, provider, records, sleeps


# --- usage and cost honesty (decision 002) --------------------------------

def test_reported_usage_gives_estimated_cost():
    client, _, records, _ = make_client([
        ProviderResponse(text="ok", model="fake-1", input_tokens=1000, output_tokens=200)
    ])
    result = client.complete(request())
    assert result.usage.source == "provider"
    # 1000 * 3/1M + 200 * 15/1M = 0.003 + 0.003
    assert result.cost.usd == Decimal("0.006000")
    assert result.cost.basis == "price_table_estimate"
    assert result.cost.price_table_version == "test-2026-10-11"
    assert records[0].success


def test_missing_usage_is_unavailable_never_zero():
    client, *_ = make_client([ProviderResponse(text="ok", model="fake-1")])
    result = client.complete(request())
    assert result.usage.input_tokens is None
    assert result.usage.source == "unavailable"
    assert result.cost.usd is None
    assert result.cost.basis == "unavailable"


def test_partial_usage_is_treated_as_unavailable():
    client, *_ = make_client([
        ProviderResponse(text="ok", model="fake-1", input_tokens=50)
    ])
    result = client.complete(request())
    assert result.usage.source == "unavailable"
    assert result.usage.input_tokens is None


def test_unpriced_model_keeps_usage_but_has_no_cost():
    client, *_ = make_client([
        ProviderResponse(text="ok", model="other-model", input_tokens=10, output_tokens=5)
    ])
    result = client.complete(request())
    assert result.usage.source == "provider"
    assert result.cost.basis == "unavailable"


def test_shipped_price_table_loads():
    table = load_price_table()
    assert table.version


def test_purpose_longer_than_column_is_rejected():
    with pytest.raises(ValidationError):
        request(purpose="x" * 41)


# --- retries and failures ----------------------------------------------------

def test_retryable_error_is_retried_then_succeeds():
    client, _, records, sleeps = make_client([ProviderTimeout(), ProviderResponse(
        text="ok", model="fake-1", input_tokens=1, output_tokens=1
    )])
    result = client.complete(request())
    assert result.attempts == 2
    assert [r.success for r in records] == [False, True]
    assert records[0].error_type == "timeout"
    assert sleeps == [0.5]


def test_non_retryable_error_fails_immediately():
    client, _, records, sleeps = make_client([ProviderRequestError()])
    with pytest.raises(LLMCallFailed) as exc_info:
        client.complete(request())
    assert exc_info.value.attempts == 1
    assert exc_info.value.error_type == "bad_request"
    assert len(records) == 1
    assert sleeps == []


def test_gives_up_after_max_attempts_with_exponential_backoff():
    client, _, records, sleeps = make_client(
        [ProviderRateLimited(), ProviderRateLimited(), ProviderRateLimited()]
    )
    with pytest.raises(LLMCallFailed) as exc_info:
        client.complete(request())
    assert exc_info.value.attempts == 3
    assert len(records) == 3
    assert sleeps == [0.5, 1.0]


def test_failed_attempts_record_no_usage_or_cost():
    client, _, records, _ = make_client([ProviderRequestError()])
    with pytest.raises(LLMCallFailed):
        client.complete(request())
    assert records[0].usage.source == "unavailable"
    assert records[0].cost.basis == "unavailable"


def test_recorder_failure_does_not_break_the_call():
    def broken_recorder(_):
        raise RuntimeError("database down")

    client = LLMClient(
        FakeProvider(), model="fake-1", prices=PRICES, recorder=broken_recorder
    )
    assert client.complete(request()).text == "fake response"


def test_provider_receives_configured_model_and_timeout():
    client, provider, *_ = make_client(timeout_s=12.0)
    client.complete(request())
    assert provider.calls[0]["model"] == "fake-1"
    assert provider.calls[0]["timeout_s"] == 12.0


def test_invalid_max_attempts_rejected():
    with pytest.raises(ValueError):
        LLMClient(FakeProvider(), model="fake-1", prices=PRICES, max_attempts=0)


def test_default_jitter_keeps_delay_between_half_and_full():
    sleeps = []
    client = LLMClient(
        FakeProvider([ProviderUnavailable(), ProviderUnavailable(), ProviderUnavailable()]),
        model="fake-1", prices=PRICES, sleep=sleeps.append,
    )
    with pytest.raises(LLMCallFailed):
        client.complete(request())
    first, second = sleeps
    assert 1.0 <= first <= 2.0      # base 2s, jittered
    assert 2.0 <= second <= 4.0     # doubled, jittered


# --- time budget ---------------------------------------------------------------

class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class SlowProvider(FakeProvider):
    """Each call 'takes' a fixed number of simulated seconds."""

    def __init__(self, clock: FakeClock, seconds: float, script):
        super().__init__(script)
        self.clock = clock
        self.seconds = seconds

    def complete(self, request, *, model, timeout_s):
        self.clock.advance(self.seconds)
        return super().complete(request, model=model, timeout_s=timeout_s)


def budget_client(provider, clock, **kwargs):
    return LLMClient(
        provider, model="fake-1", prices=PRICES,
        timeout_s=60.0, backoff_s=2.0, jitter=lambda d: d,
        sleep=clock.advance, clock=clock, **kwargs,
    )


def test_budget_stops_retries_that_cannot_finish():
    clock = FakeClock()
    provider = SlowProvider(clock, 20, [ProviderUnavailable()] * 3)
    client = budget_client(provider, clock, budget_s=45)

    with pytest.raises(LLMCallFailed) as exc_info:
        client.complete(request())

    # t=0: attempt 1 (20s) -> t=22 after 2s wait: attempt 2 (20s) -> t=42.
    # A third attempt would need 4s wait + 10s minimum: past the 45s deadline.
    assert exc_info.value.attempts == 2
    assert exc_info.value.budget_exhausted is True
    assert clock.now <= 45


def test_each_attempt_timeout_shrinks_to_the_remaining_budget():
    clock = FakeClock()
    provider = SlowProvider(clock, 20, [ProviderUnavailable()] * 3)
    client = budget_client(provider, clock, budget_s=45)
    with pytest.raises(LLMCallFailed):
        client.complete(request())
    assert [c["timeout_s"] for c in provider.calls] == [45, 23]


def test_call_within_budget_succeeds_normally():
    clock = FakeClock()
    ok = ProviderResponse(text="ok", model="fake-1", input_tokens=1, output_tokens=1)
    provider = SlowProvider(clock, 5, [ProviderUnavailable(), ok])
    client = budget_client(provider, clock, budget_s=45)
    assert client.complete(request()).attempts == 2


def test_budget_can_be_overridden_per_call():
    clock = FakeClock()
    provider = SlowProvider(clock, 12, [ProviderUnavailable()] * 3)
    client = budget_client(provider, clock, budget_s=45)
    with pytest.raises(LLMCallFailed) as exc_info:
        client.complete(request(), budget_s=20)
    assert exc_info.value.attempts == 1        # 12s used; 2s wait + 10s min > 20s
    assert exc_info.value.budget_exhausted is True


def test_budget_below_minimum_attempt_is_rejected():
    with pytest.raises(ValueError):
        LLMClient(FakeProvider(), model="fake-1", prices=PRICES, budget_s=5)


def test_no_budget_keeps_previous_behavior():
    client, _, records, _ = make_client([ProviderUnavailable()] * 3)
    with pytest.raises(LLMCallFailed) as exc_info:
        client.complete(request())
    assert exc_info.value.attempts == 3
    assert exc_info.value.budget_exhausted is False


# --- architecture rule (decision 002) ----------------------------------------

def test_only_llm_package_imports_provider_sdks():
    sdk_modules = {"anthropic", "openai", "google"}
    app_dir = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in app_dir.rglob("*.py"):
        if path.relative_to(app_dir).parts[0] == "llm":
            continue
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                module = stripped.split()[1].split(".")[0]
                if module in sdk_modules:
                    offenders.append(f"{path.relative_to(app_dir)}: {stripped}")
    assert offenders == []


# --- metric -----------------------------------------------------------------

def test_client_overhead_p95_under_2ms():
    client, *_ = make_client()
    times = []
    for _ in range(200):
        start = time.perf_counter()
        client.complete(request())
        times.append((time.perf_counter() - start) * 1000)
    times.sort()
    print(f"\nllm client overhead p50={times[99]:.3f}ms p95={times[189]:.3f}ms")
    assert times[189] < 2