import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar
from uuid import UUID

from app.llm.client import LLMClient
from app.llm.types import LLMRequest, LLMResult, Message

logger = logging.getLogger("app.llm")
T = TypeVar("T")
FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


class StructuredOutputError(Exception):
    """The model did not produce valid output within the allowed attempts or time."""


@dataclass(frozen=True)
class StructuredResult(Generic[T]):
    value: T
    attempts: int
    calls: list[LLMResult]


def parse_json_object(text: str) -> dict:
    data = json.loads(FENCE.sub("", text.strip()))
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data


def wrap_document(kind: str, text: str) -> str:
    # Remove our own closing tag so untrusted text can't "escape" its wrapper.
    safe = text.replace(f"</{kind}>", "")
    return f"<{kind}>\n{safe}\n</{kind}>"


def complete_json(
    client: LLMClient,
    *,
    purpose: str,
    system: str,
    content: str,
    validate: Callable[[dict], T],
    max_tokens: int = 4096,
    budget_s: float | None = None,
    session_id: UUID | None = None,
) -> StructuredResult[T]:
    """Ask for JSON, validate it, and allow one repair attempt within one time budget."""
    budget = budget_s if budget_s is not None else client.budget_s
    deadline = client.clock() + budget if budget is not None else None
    messages = [Message(role="user", content=content)]
    calls: list[LLMResult] = []
    last_error: Exception | None = None

    for attempt in (1, 2):
        remaining = None
        if deadline is not None:
            remaining = deadline - client.clock()
            if remaining < client.min_attempt_s:
                break  # not enough time left for a useful repair attempt
        result = client.complete(
            LLMRequest(
                purpose=purpose,
                system=system,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.0,
                response_format="json",
                session_id=session_id,
            ),
            budget_s=remaining,
        )
        calls.append(result)
        try:
            value = validate(parse_json_object(result.text))
        except ValueError as exc:  # includes JSON decode errors and pydantic validation errors
            last_error = exc
            detail = f"{type(exc).__name__}: {str(exc)[:300]}"
            messages = messages + [
                Message(role="assistant", content=result.text or "(empty)"),
                Message(role="user", content=(
                    f"That reply was not a valid JSON object of the required shape "
                    f"({detail}). Reply again with only the JSON object."
                )),
            ]
            continue

        logger.info(json.dumps({
            "event": "structured_output", "purpose": purpose,
            "attempts": attempt, "valid_first_try": attempt == 1,
        }))
        return StructuredResult(value=value, attempts=attempt, calls=calls)

    logger.info(json.dumps({
        "event": "structured_output", "purpose": purpose,
        "attempts": len(calls), "valid_first_try": False, "failed": True,
    }))
    raise StructuredOutputError(
        f"{purpose}: no valid output after {len(calls)} attempt(s)"
    ) from last_error