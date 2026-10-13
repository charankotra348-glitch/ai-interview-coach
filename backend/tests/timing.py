import time
from collections.abc import Callable


def measure_ms(fn: Callable[[], object], *, runs: int = 100, warmup: int = 5) -> list[float]:
    """Run fn repeatedly and return sorted durations in milliseconds, after warm-up."""
    for _ in range(warmup):
        fn()
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        times.append((time.perf_counter() - start) * 1000)
    return sorted(times)


def percentile(sorted_times: list[float], p: float) -> float:
    index = min(len(sorted_times) - 1, int(len(sorted_times) * p))
    return sorted_times[index]