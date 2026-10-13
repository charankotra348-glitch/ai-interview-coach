# 002: Provider-independent LLM interface

Status: Accepted (2026-10-11, revised 2026-10-12)

## Context
The app must not depend on any single model provider's SDK. Gemini is the
hosted provider; Ollama runs open models locally for free development.

## Decision
Every provider implements one interface and returns raw facts only (text,
model, token counts if reported). A shared LLMClient owns retries with
exponential backoff and jitter, timeouts, structured logging, cost
estimation and recording every attempt to the llm_calls table.

Usage and cost carry their source. Missing or partial token counts are
recorded as unavailable, never as zero. Cost is computed only from
provider-reported tokens and a dated price table, and is always labeled
an estimate. Thinking tokens count as output, because they are billed.

## Enforced by
- Database CHECK constraints reject token counts without provider usage,
  and estimated costs without a price table version
- A test fails if any code outside app/llm imports a provider SDK
- A test fails if the configured model has no price
- A test fails if an API key appears in any tracked file
- Unit tests use FakeProvider and never call a paid API

## Consequences
Switching providers is one line in .env, with no code changes. This was
exercised in practice when Gemini was overloaded.
