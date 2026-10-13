import sys
from decimal import Decimal

from app.llm.factory import build_llm_client
from app.llm.types import LLMRequest, Message

n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
client = build_llm_client()
results = []

for i in range(n):
    result = client.complete(LLMRequest(
        purpose="smoke_test",
        max_tokens=1024,
        messages=[Message(
            role="user",
            content="Ask me one short behavioral interview question. Reply with the question only.",
        )],
    ))
    results.append(result)
    print(
        f"{i + 1}: {result.latency_ms:.0f}ms  in={result.usage.input_tokens} "
        f"out={result.usage.output_tokens}  cost=${result.cost.usd} "
        f"({result.cost.basis})  model={result.model}"
    )

latencies = sorted(r.latency_ms for r in results)
total = sum((r.cost.usd or Decimal(0)) for r in results)
print(f"\nlatency p50={latencies[len(latencies) // 2]:.0f}ms  max={latencies[-1]:.0f}ms")
print(f"total estimated cost=${total}  ({n} calls)")
print(f"sample question: {results[-1].text}")